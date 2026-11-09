"""
Document retrieval service for AskMe.

Supports:
- Unfiltered semantic search
- Searches restricted by metadata/content type
- Side-by-side comparison of lab_result and source_text
- Combined retrieval that preserves both result groups
- Exact text lookup for auditing normalized lab records

The service deliberately does not discard near-duplicate laboratory records.
Repeated measurements can represent different dates or report sections; they
must be inspected before any automatic deduplication rule is introduced.
"""

import logging
import re
from collections import OrderedDict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DocumentRetrieval:
    """Search an active ChromaDB collection for relevant document chunks."""

    CONTENT_TYPES = ("lab_result", "source_text")

    def __init__(self, chroma_client):
        self.chroma = chroma_client

    def _ensure_collection(self):
        """Ensure a Chroma collection is active."""
        if not self.chroma.collection:
            self.chroma.load_collection()

    @staticmethod
    def _validate_search(query_text: str, top_k: int):
        if not query_text or not query_text.strip():
            raise ValueError("Search query cannot be empty")

        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
            raise ValueError("top_k must be a positive integer")

    @staticmethod
    def _combine_where(
        where: Optional[Dict[str, Any]],
        content_type: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Combine a caller's metadata filter with content_type."""
        if content_type is None:
            return where

        if content_type not in DocumentRetrieval.CONTENT_TYPES:
            raise ValueError(
                f"Unsupported content_type {content_type!r}; "
                f"expected one of {DocumentRetrieval.CONTENT_TYPES}"
            )

        type_filter = {"content_type": content_type}
        if where is None:
            return type_filter

        return {"$and": [where, type_filter]}

    @staticmethod
    def _flatten_query_result(results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert Chroma's one-query nested result into ordinary dictionaries."""
        ids = (results.get("ids") or [[]])[0] or []
        documents = (results.get("documents") or [[]])[0] or []
        metadatas = (results.get("metadatas") or [[]])[0] or []
        distances = (results.get("distances") or [[]])[0] or []

        flattened = []
        for doc_id, document, metadata, distance in zip(
            ids, documents, metadatas, distances
        ):
            flattened.append({
                "id": doc_id,
                "document": document or "",
                "metadata": metadata or {},
                "distance": distance,
            })
        return flattened

    def search(
        self,
        query_text: str,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        content_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return the closest matching chunks.

        content_type may be "lab_result" or "source_text". If omitted,
        all record types are searched, preserving the original API.
        """
        self._validate_search(query_text, top_k)
        self._ensure_collection()

        if self.chroma.count() == 0:
            return []

        query_args = {
            "query_texts": [query_text.strip()],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }

        query_filter = self._combine_where(where, content_type)
        if query_filter is not None:
            query_args["where"] = query_filter

        if where_document is not None:
            query_args["where_document"] = where_document

        results = self.chroma.query(**query_args)
        matches = self._flatten_query_result(results)

        logger.info(
            "Document search returned %d results (content_type=%s)",
            len(matches),
            content_type or "all",
        )
        return matches

    def compare_content_types(
        self,
        query_text: str,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Return separate ranked lists for lab results and source text."""
        self._validate_search(query_text, top_k)

        return {
            record_type: self.search(
                query_text=query_text,
                top_k=top_k,
                where=where,
                where_document=where_document,
                content_type=record_type,
            )
            for record_type in self.CONTENT_TYPES
        }

    @staticmethod
    def _lab_identity(result: Dict[str, Any]):
        """
        Build a conservative identity for repeated normalized lab records.

        Records are considered duplicates only when they belong to the same
        ingested file, have the same analyte name, and have the same leading
        reported result/reference-range text. Historical-result suffixes are
        excluded from the comparison but retained in the original records.
        """
        metadata = result.get("metadata") or {}
        document = result.get("document") or ""

        document_key = (
            metadata.get("file_hash")
            or metadata.get("document_id")
            or metadata.get("source_path")
            or metadata.get("source")
        )
        if not document_key:
            # Without a reliable source identity, do not merge records.
            return None

        test_name = metadata.get("test_name")
        if not test_name:
            match = re.search(
                r"(?im)^Test:\s*(.+?)\s*$",
                document,
            )
            test_name = match.group(1) if match else None
        if not test_name:
            return None

        details_match = re.search(
            r"(?is)Reported result and accompanying extracted details:\s*(.+)",
            document,
        )
        if not details_match:
            return None

        details = re.sub(r"\s+", " ", details_match.group(1)).strip()

        # In this ingestion format, a prior value/date follows the current
        # result and reference range, e.g. "13 7-25 mg/dL 15.0 10/22/2025 UL".
        # Strip that suffix only for identity comparison; preserve full text.
        details = re.split(
            r"\s+\d+(?:\.\d+)?\s+\d{1,2}/\d{1,2}/\d{4}\b",
            details,
            maxsplit=1,
        )[0]

        normalized_test = re.sub(r"\s+", " ", str(test_name)).strip().casefold()
        normalized_details = re.sub(r"\s+", " ", details).strip().casefold()

        if not normalized_details:
            return None

        return (
            str(document_key),
            normalized_test,
            normalized_details,
        )

    @classmethod
    def deduplicate_lab_results(
        cls,
        lab_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Consolidate exact repeated measurements while preserving provenance.

        The representative result is the occurrence with the lowest cosine
        distance. Its document text is retained, and every occurrence is
        preserved under `source_occurrences` with its original ID, page,
        metadata, distance and document text.

        Ambiguous records (missing source identity, test name or result details)
        are left untouched.
        """
        groups = OrderedDict()
        ungrouped = []

        for result in lab_results:
            identity = cls._lab_identity(result)
            if identity is None:
                ungrouped.append(result)
                continue
            groups.setdefault(identity, []).append(result)

        consolidated = []
        for occurrences in groups.values():
            if len(occurrences) == 1:
                consolidated.append(occurrences[0])
                continue

            def distance_key(item):
                distance = item.get("distance")
                return float("inf") if distance is None else float(distance)

            ordered = sorted(occurrences, key=distance_key)
            representative = dict(ordered[0])
            representative_metadata = dict(
                representative.get("metadata") or {}
            )

            source_occurrences = []
            pages = []
            for occurrence in occurrences:
                metadata = occurrence.get("metadata") or {}
                page = metadata.get("page")
                if page is not None and page not in pages:
                    pages.append(page)

                source_occurrences.append({
                    "id": occurrence.get("id"),
                    "page": page,
                    "distance": occurrence.get("distance"),
                    "metadata": dict(metadata),
                    "document": occurrence.get("document") or "",
                })

            representative_metadata["duplicate_count"] = len(occurrences)
            representative_metadata["source_pages"] = pages
            representative["metadata"] = representative_metadata
            representative["source_occurrences"] = source_occurrences

            consolidated.append(representative)

        consolidated.extend(ungrouped)

        # Retain relevance ordering across consolidated and ungrouped records.
        consolidated.sort(
            key=lambda item: (
                float("inf") if item.get("distance") is None
                else float(item["distance"])
            )
        )
        return consolidated

    def search_combined(
        self,
        query_text: str,
        top_k_per_type: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        deduplicate_labs: bool = True,
    ) -> Dict[str, Any]:
        """
        Search both record types and return raw and consolidated result views.

        Each type gets its own top_k_per_type allowance. Source-text chunks
        remain unchanged. Lab records are conservatively consolidated when
        they have the same source file, analyte and current result/reference
        range. Set deduplicate_labs=False to inspect the raw lab matches.
        """
        comparison = self.compare_content_types(
            query_text=query_text,
            top_k=top_k_per_type,
            where=where,
            where_document=where_document,
        )

        raw_lab_results = comparison["lab_result"]
        lab_results = (
            self.deduplicate_lab_results(raw_lab_results)
            if deduplicate_labs else raw_lab_results
        )
        source_text = comparison["source_text"]

        combined = lab_results + source_text
        combined.sort(
            key=lambda item: (
                float("inf") if item.get("distance") is None
                else float(item["distance"])
            )
        )

        for rank, item in enumerate(combined, start=1):
            item["combined_rank"] = rank

        result = {
            "query": query_text.strip(),
            "lab_results": lab_results,
            "raw_lab_results": raw_lab_results,
            "source_text": source_text,
            "combined": combined,
            "counts": {
                "raw_lab_results": len(raw_lab_results),
                "lab_results": len(lab_results),
                "source_text": len(source_text),
                "combined": len(combined),
            },
        }

        logger.info(
            "Combined retrieval returned %d raw lab records, %d consolidated "
            "lab records and %d source chunks",
            result["counts"]["raw_lab_results"],
            result["counts"]["lab_results"],
            result["counts"]["source_text"],
        )
        return result

    def find_lab_records(
        self,
        text_fragment: str,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find stored normalized lab records containing a literal text fragment.

        This is a diagnostic lookup, not semantic search. It is useful for
        checking whether an analyte (for example, UREA NITROGEN) was actually
        normalized during ingestion before changing the parser.
        """
        if not text_fragment or not text_fragment.strip():
            raise ValueError("text_fragment cannot be empty")

        self._ensure_collection()

        filters = {"content_type": "lab_result"}
        if where:
            filters = {"$and": [filters, where]}

        stored = self.chroma.get(
            where=filters,
            where_document={"$contains": text_fragment.strip()},
            include=["documents", "metadatas"],
        )

        ids = stored.get("ids") or []
        documents = stored.get("documents") or []
        metadatas = stored.get("metadatas") or []

        return [
            {
                "id": doc_id,
                "document": document or "",
                "metadata": metadata or {},
            }
            for doc_id, document, metadata in zip(ids, documents, metadatas)
        ]
