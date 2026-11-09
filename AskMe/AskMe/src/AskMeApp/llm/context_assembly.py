'''
Created on Nov 9, 2026

@author: keith.chambers
'''
"""
Context assembly for AskMe RAG.

This module converts DocumentRetrieval.search_combined() output into a
source-grounded context string suitable for MyPrompt / an LLM.

It does not call an LLM, interpret results, or change ChromaDB records.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ContextAssembler:
    """Build a bounded, traceable context from combined retrieval results."""

    def __init__(
        self,
        max_context_chars: int = 12000,
        max_lab_results: int = 8,
        max_source_chunks: int = 5,
        max_lab_record_chars: int = 1400,
        max_source_chunk_chars: int = 2600,
    ):
        if max_context_chars < 1:
            raise ValueError("max_context_chars must be positive")
        if max_lab_results < 0 or max_source_chunks < 0:
            raise ValueError("Result limits cannot be negative")
        if max_lab_record_chars < 1 or max_source_chunk_chars < 1:
            raise ValueError("Per-record character limits must be positive")

        self.max_context_chars = max_context_chars
        self.max_lab_results = max_lab_results
        self.max_source_chunks = max_source_chunks
        self.max_lab_record_chars = max_lab_record_chars
        self.max_source_chunk_chars = max_source_chunk_chars

    @staticmethod
    def _metadata_value(metadata: Dict[str, Any], key: str, default: str = "Unknown"):
        value = metadata.get(key)
        return default if value is None or value == "" else str(value)

    @staticmethod
    def _truncate(text: str, limit: int) -> Tuple[str, bool]:
        text = (text or "").strip()
        if len(text) <= limit:
            return text, False

        shortened = text[:limit].rsplit(" ", 1)[0].rstrip()
        return shortened + "\n[Record text truncated for context budget.]", True

    @staticmethod
    def _source_identity(result: Dict[str, Any]) -> str:
        """Prefer the Chroma ID; fall back to source/page/text identity."""
        if result.get("id"):
            return str(result["id"])

        metadata = result.get("metadata") or {}
        document = result.get("document") or ""
        return "|".join((
            str(metadata.get("source_path") or metadata.get("source") or ""),
            str(metadata.get("page") or ""),
            re.sub(r"\s+", " ", document).strip(),
        ))

    def _format_lab_result(self, result: Dict[str, Any], number: int):
        metadata = result.get("metadata") or {}
        document = result.get("document") or ""
        document, truncated = self._truncate(
            document, self.max_lab_record_chars
        )

        test_name = self._metadata_value(
            metadata, "test_name", "Unspecified test"
        )
        source = self._metadata_value(
            metadata, "source", self._metadata_value(metadata, "source_path")
        )
        page = self._metadata_value(metadata, "page")
        pages = metadata.get("source_pages") or []
        duplicate_count = metadata.get("duplicate_count", 1)

        lines = [
            f"[LAB RESULT {number}]",
            f"Test: {test_name}",
            f"Source: {source}",
            f"Representative page: {page}",
        ]

        if duplicate_count > 1:
            lines.append(
                f"Repeated occurrences: {duplicate_count}; "
                f"source pages: {', '.join(map(str, pages)) or 'not recorded'}"
            )

        lines.extend(["Record:", document])
        return "\n".join(lines), truncated

    def _format_source_chunk(self, result: Dict[str, Any], number: int):
        metadata = result.get("metadata") or {}
        document = result.get("document") or ""
        document, truncated = self._truncate(
            document, self.max_source_chunk_chars
        )

        source = self._metadata_value(
            metadata, "source", self._metadata_value(metadata, "source_path")
        )
        page = self._metadata_value(metadata, "page")

        block = "\n".join([
            f"[SOURCE TEXT {number}]",
            f"Source: {source}",
            f"Page: {page}",
            "Extracted text:",
            document,
        ])
        return block, truncated

    def assemble(self, retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assemble separate lab-result and source-text sections.

        Expected input is the dictionary returned by
        DocumentRetrieval.search_combined(). The returned `context` is a
        plain string; `sources` provides structured provenance for the UI.
        """
        if not isinstance(retrieval_result, dict):
            raise TypeError("retrieval_result must be a dictionary")

        lab_results = retrieval_result.get("lab_results") or []
        source_chunks = retrieval_result.get("source_text") or []

        selected_labs = lab_results[:self.max_lab_results]

        # Avoid passing the same source chunk twice if the retrieval layer
        # returns repeated IDs. Distinct overlapping chunks remain available.
        selected_sources = []
        seen_source_ids = set()
        for item in source_chunks:
            identity = self._source_identity(item)
            if identity in seen_source_ids:
                continue
            seen_source_ids.add(identity)
            selected_sources.append(item)
            if len(selected_sources) >= self.max_source_chunks:
                break

        sections = []
        source_manifest = []
        truncated_records = 0

        if selected_labs:
            lab_blocks = []
            for index, item in enumerate(selected_labs, start=1):
                block, truncated = self._format_lab_result(item, index)
                lab_blocks.append(block)
                truncated_records += int(truncated)

                metadata = item.get("metadata") or {}
                source_manifest.append({
                    "kind": "lab_result",
                    "id": item.get("id"),
                    "test_name": metadata.get("test_name"),
                    "source": metadata.get("source"),
                    "page": metadata.get("page"),
                    "source_pages": metadata.get("source_pages", []),
                    "distance": item.get("distance"),
                })
            sections.append(
                "LABORATORY RESULT RECORDS\n\n" + "\n\n".join(lab_blocks)
            )

        if selected_sources:
            source_blocks = []
            for index, item in enumerate(selected_sources, start=1):
                block, truncated = self._format_source_chunk(item, index)
                source_blocks.append(block)
                truncated_records += int(truncated)

                metadata = item.get("metadata") or {}
                source_manifest.append({
                    "kind": "source_text",
                    "id": item.get("id"),
                    "source": metadata.get("source"),
                    "page": metadata.get("page"),
                    "distance": item.get("distance"),
                })
            sections.append(
                "ORIGINAL SOURCE TEXT\n\n" + "\n\n".join(source_blocks)
            )

        context = "\n\n" + ("\n\n" + "=" * 72 + "\n\n").join(sections)
        context = context.strip()

        budget_truncated = False
        if len(context) > self.max_context_chars:
            context, _ = self._truncate(context, self.max_context_chars)
            budget_truncated = True

        result = {
            "context": context,
            "sources": source_manifest,
            "stats": {
                "lab_results_available": len(lab_results),
                "lab_results_included": len(selected_labs),
                "source_chunks_available": len(source_chunks),
                "source_chunks_included": len(selected_sources),
                "records_truncated": truncated_records,
                "context_chars": len(context),
                "context_budget": self.max_context_chars,
                "context_budget_truncated": budget_truncated,
            },
        }

        logger.info(
            "Assembled LLM context: %d lab records, %d source chunks, "
            "%d characters (budget=%d)",
            result["stats"]["lab_results_included"],
            result["stats"]["source_chunks_included"],
            result["stats"]["context_chars"],
            self.max_context_chars,
        )
        return result
