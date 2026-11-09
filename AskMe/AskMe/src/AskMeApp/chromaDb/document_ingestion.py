'''
Created on Nov 3, 2026

@author: keith.chambers
'''
"""
Document ingestion service for AskMe.

Supports text-based PDF and TXT files. This module has no Kivy dependency:
the UI calls DocumentIngestion.ingest_files() and displays the returned
summary. Scanned PDFs require OCR and are reported as having no extractable
text; OCR is intentionally not included in this minimal implementation.
"""

import hashlib
import html
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from pypdf import PdfReader

logger = logging.getLogger(__name__)


class DocumentIngestion:
    """Extract, chunk and store PDF/TXT documents in an active Chroma collection."""

    def __init__(
        self,
        chroma_client,
        chunk_size: int = 2400,
        overlap: int = 300,
        batch_size: int = 100,
    ):
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be >= 0 and smaller than chunk_size")
        if batch_size < 1:
            raise ValueError("batch_size must be positive")

        self.chroma = chroma_client
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.batch_size = batch_size

    # Extraction ------------------------------------------------------------

    @staticmethod
    def clean_pdf_text(raw_text: str) -> str:
        """
        Conservatively remove repeated PDF page furniture.

        The original pypdf output is retained separately as `raw_text`.
        Clinical content, test names, results, units, ranges, comments and
        section headings are retained. Only recognizable report headers,
        page labels and publication/legal boilerplate are removed.
        """
        text = html.unescape(raw_text or "")
        text = text.replace("\xa0", " ").replace("\u00a0", " ")
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        lines = [line.rstrip() for line in text.splitlines()]

        # Remove the repeated main-report header. The block begins with
        # PATIENT INFORMATION and ends at the report's column-heading line.
        # Keep that column-heading line as a useful cue for downstream retrieval.
        main_start = next(
            (i for i, line in enumerate(lines)
             if line.strip().upper() == "PATIENT INFORMATION:"),
            None,
        )
        if main_start is not None:
            main_end = next(
                (i for i in range(main_start + 1, len(lines))
                 if re.search(
                     r"Test\s+In\s+Range\s+Out\s+Of\s+Range\s+Reference\s+Range",
                     lines[i],
                     re.I,
                 )),
                None,
            )
            if main_end is not None:
                lines = lines[:main_start] + [lines[main_end]] + lines[main_end + 1:]

        # Remove the repeated appendix identity/client header. Keep the
        # first actual clinical section/table heading after it.
        appendix_start = next(
            (i for i, line in enumerate(lines)
             if re.match(r"^\s*Report Status:\s*Final\s*$", line, re.I)),
            None,
        )
        if appendix_start is not None:
            appendix_end = next(
                (i for i in range(appendix_start + 1, len(lines))
                 if re.search(r"Test\s+Name\s+In\s+Range", lines[i], re.I)
                 or re.match(r"^\s*Immunology\s*$", lines[i], re.I)),
                None,
            )
            if appendix_end is not None:
                lines = (
                    lines[:appendix_start]
                    + [lines[appendix_end]]
                    + lines[appendix_end + 1:]
                )

        # Remove page labels and repeated publisher/trademark boilerplate.
        filtered = []
        for line in lines:
            stripped = line.strip()
            if re.match(r"^Keith Chambers Quest Result\s+\d{2}/\d{2}/\d{4}$", stripped, re.I):
                continue
            if re.match(r"^Page\s+\d+\s+of\s+\d+$", stripped, re.I):
                continue
            if re.match(r"^Appendix\s+1\s+\[Enhanced PDF Report.*\]\s*-\s*Page\s+\d+\s+of\s+\d+$", stripped, re.I):
                continue
            if re.match(r"^Quest, Quest Diagnostics, the associated logo.*trademarks of Quest Diagnostics\.$", stripped, re.I):
                continue
            if re.match(r"^Printed from Health Gorilla Secure Clinical Network\.", stripped, re.I):
                continue
            if re.match(r"^https?://www\.healthgorilla\.com$", stripped, re.I):
                continue
            if re.match(r"^Health Gorilla Inc\.$", stripped, re.I):
                continue
            filtered.append(line)

        # Remove the legal confidentiality notice if present, but leave all
        # preceding clinical content untouched.
        text = "\n".join(filtered)
        footer_start = re.search(
            r"(?im)^\s*The contents of this document and/or fax transmission are intended",
            text,
        )
        if footer_start:
            text = text[:footer_start.start()]

        # Collapse runs of blank lines, not single line breaks: single line
        # breaks may separate rows or wrapped labels in extracted tables.
        text = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", text)
        return text.strip()

    def extract_pdf_text(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Return pages with direct pypdf output and a cleaned chunking version.

        `raw_text` is retained unchanged for traceability; `text` is the
        conservative cleaned version consumed by the existing ingestion flow.
        """
        reader = PdfReader(file_path)
        pages = []

        for page_number, page in enumerate(reader.pages, start=1):
            raw_text = page.extract_text() or ""
            
            logger.info(
                "PDF PAGE %d: lowercase t count=%d",
                page_number,
                raw_text.count("t")
            )
            
            if raw_text.strip():
                pages.append({
                    "page": page_number,
                    "raw_text": raw_text,
                    "text": self.clean_pdf_text(raw_text),
                })

        return pages

    @staticmethod
    def extract_text_file(file_path: str) -> List[Dict[str, Any]]:
        """Read a TXT file, trying common encodings if UTF-8 fails."""
        try:
            text = Path(file_path).read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            text = Path(file_path).read_text(encoding="cp1252")

        return [{"page": 1, "text": text}]

    # Chunking --------------------------------------------------------------

    def chunk_text(self, text: str) -> List[str]:
        """
        Chunk plain text using paragraph boundaries.

        Used for TXT files. PDF files use chunk_pdf_text() so their
        single-line breaks (often meaningful table rows) are preserved.
        """
        paragraphs = [
            re.sub(r"\s+", " ", part).strip()
            for part in re.split(r"\n\\s*\n", text)
        ]
        paragraphs = [p for p in paragraphs if p]

        chunks: List[str] = []
        current = ""

        def split_long_text(value: str) -> List[str]:
            pieces = []
            start = 0
            while start < len(value):
                end = min(start + self.chunk_size, len(value))
                if end < len(value):
                    boundary = value.rfind(" ", start, end)
                    if boundary > start:
                        end = boundary
                piece = value[start:end].strip()
                if piece:
                    pieces.append(piece)
                if end >= len(value):
                    break
                start = max(end - self.overlap, start + 1)
            return pieces

        for paragraph in paragraphs:
            if len(paragraph) > self.chunk_size:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.extend(split_long_text(paragraph))
                continue

            candidate = f"{current}\n\n{paragraph}" if current else paragraph
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = paragraph

        if current:
            chunks.append(current)

        return [chunk for chunk in chunks if chunk.strip()]

    def chunk_pdf_text(self, text: str) -> List[str]:
        """
        Chunk PDF text while preserving single line breaks.

        PDF line breaks often represent table rows or wrapped test names.
        This method packs adjacent lines together and prefers splitting at
        line boundaries. It does not attempt to infer missing table columns.
        """
        normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
        lines = [re.sub(r"[ \t]+", " ", line).strip()
                 for line in normalized.split("\n")]

        # Remove excess blank lines, but retain one blank line as a section break.
        compact_lines: List[str] = []
        previous_blank = False
        for line in lines:
            if not line:
                if compact_lines and not previous_blank:
                    compact_lines.append("")
                previous_blank = True
            else:
                compact_lines.append(line)
                previous_blank = False

        chunks: List[str] = []
        current_lines: List[str] = []

        def current_text() -> str:
            return "\n".join(current_lines).strip()

        def split_oversized_line(line: str) -> List[str]:
            """Fallback for an individual extracted line longer than chunk_size."""
            pieces = []
            start = 0
            while start < len(line):
                end = min(start + self.chunk_size, len(line))
                if end < len(line):
                    boundary = line.rfind(" ", start, end)
                    if boundary > start:
                        end = boundary
                piece = line[start:end].strip()
                if piece:
                    pieces.append(piece)
                if end >= len(line):
                    break
                start = max(end - self.overlap, start + 1)
            return pieces

        def overlap_lines(previous: List[str], next_line: str) -> List[str]:
            """Carry whole trailing lines forward without exceeding the budget."""
            if not self.overlap:
                return [next_line]
            selected: List[str] = []
            used = len(next_line)
            for old_line in reversed(previous):
                addition = len(old_line) + (1 if selected or next_line else 0)
                if used + addition > self.overlap:
                    break
                selected.insert(0, old_line)
                used += addition
            return selected + [next_line]

        for line in compact_lines:
            if len(line) > self.chunk_size:
                if current_lines:
                    chunks.append(current_text())
                    current_lines = []
                chunks.extend(split_oversized_line(line))
                continue

            candidate_lines = current_lines + [line]
            candidate = "\n".join(candidate_lines).strip()

            if not current_lines or len(candidate) <= self.chunk_size:
                current_lines = candidate_lines
                continue

            previous = current_lines[:]
            chunks.append(current_text())
            current_lines = overlap_lines(previous, line)

            # Defensive fallback if overlap plus the new line exceeds the limit.
            while len(current_text()) > self.chunk_size and len(current_lines) > 1:
                current_lines.pop(0)

        if current_lines:
            final_chunk = current_text()
            if final_chunk:
                chunks.append(final_chunk)

        return [chunk for chunk in chunks if chunk.strip()]

    # Laboratory result normalization -------------------------------------

    @staticmethod
    def extract_lab_result_records(text: str) -> List[Dict[str, str]]:
        """
        Extract conservative, one-line laboratory result records.

        This first-pass parser handles rows where a test label and numeric
        result occur on the same line, plus labels wrapped onto the preceding
        line(s). It deliberately retains the complete result/range text rather
        than guessing which trailing numbers are previous results or ranges.
        """
        lines = [re.sub(r"[ \t]+", " ", line).strip()
                 for line in (text or "").splitlines()]
        records: List[Dict[str, str]] = []
        seen = set()

        # Numeric result at the start of a line, followed by optional flag
        # and the remaining extracted range/unit/previous-result text.
        result_pattern = re.compile(
            r"^(?P<result>[+-]?(?:\d+(?:\.\d+)?|\.\d+))"
            r"\s*(?P<flag>[HA])?\s*(?P<details>.*)$",
            re.I,
        )

        # Also accept a result embedded immediately after a test name,
        # including flattened appendix rows such as "CHOLESTEROL, TOTAL133 ...".
        embedded_pattern = re.compile(
            r"^(?P<label>[A-Za-z(][A-Za-z0-9 ,()/+._-]*?)"
            r"\s*(?P<result>[+-]?(?:\d+(?:\.\d+)?|\.\d+))"
            r"\s*(?P<flag>[HA])?\s*(?P<details>.*)$"
        )

        def valid_label(label: str) -> bool:
            label = label.strip(" :-")
            letters = [char for char in label if char.isalpha()]
            if len(label) < 3 or len(letters) < 3:
                return False
            # Lab analyte labels in this report are predominantly uppercase.
            # This rejects explanatory prose and most citation fragments.
            uppercase_ratio = sum(char.isupper() for char in letters) / len(letters)
            if uppercase_ratio < 0.75:
                return False
            if label.lower().startswith(("reference range", "desirable range", "risk:")):
                return False
            if re.search(r"\b(?:FOR|WITH|FROM|MAY|ONLY|PATIENTS|DIABETES)\b", label, re.I):
                return False
            return True

        for index, line in enumerate(lines):
            if not line:
                continue

            label = ""
            result_text = ""

            embedded = embedded_pattern.match(line)
            if embedded and valid_label(embedded.group("label")):
                label = embedded.group("label").strip()

                # Quest may wrap this analyte as:
                # "UREA NITROGEN" on one line, then "(BUN) 13 ..." on the next.
                if (
                    label.upper() == "(BUN)"
                    and index > 0
                    and lines[index - 1].strip().upper() == "UREA NITROGEN"
                ):
                    label = "UREA NITROGEN (BUN)"

                # Rejoin other wrapped analyte names, e.g.
                # "CHOLESTEROL," + "TOTAL133".
                elif (
                    index > 0
                    and lines[index - 1].endswith(",")
                    and valid_label(lines[index - 1].rstrip(","))
                ):
                    label = lines[index - 1].rstrip(",") + ", " + label
                result_text = (
                    embedded.group("result")
                    + (f" {embedded.group('flag')}" if embedded.group("flag") else "")
                    + (f" {embedded.group('details')}" if embedded.group("details") else "")
                ).strip()
            else:
                # Try one or two preceding lines as a wrapped test label.
                result_match = result_pattern.match(line)
                if not result_match:
                    continue

                for back in (2, 1):
                    if index - back < 0:
                        continue
                    preceding = lines[index - back:index]
                    if any(not item for item in preceding):
                        continue
                    candidate = " ".join(preceding).strip()
                    if valid_label(candidate) and len(candidate) <= 90:
                        label = candidate
                        result_text = (
                            result_match.group("result")
                            + (f" {result_match.group('flag')}" if result_match.group("flag") else "")
                            + (f" {result_match.group('details')}" if result_match.group("details") else "")
                        ).strip()
                        break

            if not label or not result_text:
                continue
            # pypdf splits "HEMOGLOBIN A1c" into "HEMOGLOBIN A" + "1 c";
            # skip this ambiguous first-pass parse rather than mislabel it.
            if label.strip().upper() == "HEMOGLOBIN A":
                continue
            if re.search(r"\b(?:Collected|Received|Reported):", result_text, re.I):
                continue
            # Avoid known extraction artifacts: split A1c token and lab
            # director/facility blocks are not analyte result rows.
            if re.match(r"^1\s+c\b", result_text, re.I):
                continue
            if re.search(r"QUEST DIAGNOSTICS|LABORATORY DIRECTOR|CLIA:", label + " " + result_text, re.I):
                continue

            # Avoid turning obvious dates, phone numbers, IDs or table headings
            # into test results.
            if re.search(r"\b(?:DOB|PHONE|PATIENT ID|SPECIMEN|ACCESSION|PAGE)\b", label, re.I):
                continue

            key = (re.sub(r"\s+", " ", label).casefold(), result_text.casefold())
            if key in seen:
                continue
            seen.add(key)

            records.append({
                "test_name": re.sub(r"\s+", " ", label).strip(),
                "result_details": result_text,
            })

        return records

    @staticmethod
    def format_lab_result_record(record: Dict[str, str]) -> str:
        """Format a parsed row as a self-contained retrieval document."""
        return (
            "Laboratory result record\n"
            f"Test: {record['test_name']}\n"
            f"Reported result and accompanying extracted details: "
            f"{record['result_details']}"
        )

    # IDs and metadata ------------------------------------------------------

    @staticmethod
    def _sha256_file(file_path: str) -> str:
        digest = hashlib.sha256()
        with open(file_path, "rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _document_id(file_path: str) -> str:
        # Stable for the same path, including across file-content revisions.
        normalized_path = os.path.normcase(os.path.abspath(file_path))
        return hashlib.sha256(normalized_path.encode("utf-8")).hexdigest()

    @staticmethod
    def _chunk_id(document_id: str, file_hash: str,
                  chunk_index: int, chunk: str) -> str:
        value = f"{document_id}:{file_hash}:{chunk_index}:{chunk}"
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    # Ingestion -------------------------------------------------------------

    def ingest_file(self, file_path: str) -> Dict[str, Any]:
        """Ingest one supported file and return a structured result."""
        file_path = os.path.abspath(file_path)
        extension = Path(file_path).suffix.lower()

        if extension == ".pdf":
            pages = self.extract_pdf_text(file_path)
        elif extension == ".txt":
            pages = self.extract_text_file(file_path)
        else:
            raise ValueError(f"Unsupported file type: {extension or '(none)'}")

        if not pages or not any(page["text"].strip() for page in pages):
            raise ValueError(
                "No extractable text found. If this is a scanned PDF, OCR is required."
            )

        file_hash = self._sha256_file(file_path)
        document_id = self._document_id(file_path)
        filename = os.path.basename(file_path)

        documents: List[str] = []
        ids: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        chunk_index = 0

        for page_data in pages:
            page_number = int(page_data["page"])
            chunker = self.chunk_pdf_text if extension == ".pdf" else self.chunk_text

            # Original extracted-text chunks remain available for traceability.
            for chunk in chunker(page_data["text"]):
                documents.append(chunk)
                ids.append(
                    self._chunk_id(document_id, file_hash, chunk_index, chunk)
                )
                metadatas.append({
                    "document_id": document_id,
                    "source": filename,
                    "source_path": file_path,
                    "file_type": extension.lstrip("."),
                    "file_hash": file_hash,
                    "page": page_number,
                    "chunk_index": chunk_index,
                    "chunk_size": len(chunk),
                    "content_type": "source_text",
                })
                chunk_index += 1

            # Add normalized records only for PDFs; original chunks are not
            # discarded, and each normalized record retains its source page.
            if extension == ".pdf":
                for record in self.extract_lab_result_records(page_data["text"]):
                    normalized = self.format_lab_result_record(record)
                    documents.append(normalized)
                    ids.append(
                        self._chunk_id(document_id, file_hash, chunk_index, normalized)
                    )
                    metadatas.append({
                        "document_id": document_id,
                        "source": filename,
                        "source_path": file_path,
                        "file_type": "pdf",
                        "file_hash": file_hash,
                        "page": page_number,
                        "chunk_index": chunk_index,
                        "chunk_size": len(normalized),
                        "content_type": "lab_result",
                        "test_name": record["test_name"],
                    })
                    chunk_index += 1

        if not documents:
            raise ValueError("No text chunks were generated")

        # Upsert new content first. If this fails, the previous version remains.
        self.chroma.upsert_documents(
            documents=documents,
            ids=ids,
            metadatas=metadatas,
            batch_size=self.batch_size,
        )

        # Remove stale chunks from an earlier version of this same file.
        # This is done only after the new chunks have been stored successfully.
        existing = self.chroma.get(
            where={"document_id": document_id},
            include=["metadatas"],
        )
        existing_ids = set(existing.get("ids", []))
        stale_ids = sorted(existing_ids.difference(ids))
        if stale_ids:
            self.chroma.delete(ids=stale_ids)

        return {
            "file": file_path,
            "status": "success",
            "document_id": document_id,
            "file_hash": file_hash,
            "pages_extracted": len(pages),
            "chunks_ingested": len(documents),
            "stale_chunks_removed": len(stale_ids),
        }

    def ingest_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """Ingest multiple files; one file failure does not stop the others."""
        if not self.chroma.collection:
            self.chroma.load_collection()

        results = []
        for file_path in file_paths:
            try:
                result = self.ingest_file(file_path)
                results.append(result)
                logger.info(
                    "Ingested %s: %d chunks",
                    file_path,
                    result["chunks_ingested"],
                )
            except Exception as exc:
                logger.exception("Failed ingesting file: %s", file_path)
                results.append({
                    "file": os.path.abspath(file_path),
                    "status": "failed",
                    "error": str(exc),
                })

        successful = [r for r in results if r["status"] == "success"]
        failed = [r for r in results if r["status"] == "failed"]

        return {
            "files_processed": len(results),
            "files_succeeded": len(successful),
            "files_failed": len(failed),
            "total_chunks": sum(r["chunks_ingested"] for r in successful),
            "results": results,
        }
