'''
Created on Nov 3, 2026

@author: keith.chambers
'''

"""
Document ingestion service for AskMe.

Responsibilities:
- Extract text from PDF files
- Read TXT files
- Split text into overlapping chunks
- Generate deterministic document and chunk IDs
- Generate metadata
- Store documents in ChromaDB
- Replace obsolete chunks when a document changes
"""

import os
import re
import hashlib
import logging

from pathlib import Path
from typing import List, Dict, Any

from pypdf import PdfReader

logger = logging.getLogger(__name__)


class DocumentIngestion:
    """Extract, chunk and store documents in ChromaDB."""

    def __init__(
        self,
        chroma_client,
        chunk_size=900,
        overlap=120,
        batch_size=100
    ):

        if chunk_size < 1:
            raise ValueError("Chunk size must be positive")

        if overlap < 0 or overlap >= chunk_size:
            raise ValueError(
                "Overlap must be smaller than chunk size"
            )

        if batch_size < 1:
            raise ValueError("Batch size must be positive")

        self.chroma = chroma_client
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.batch_size = batch_size

    # ---------------------------------------------------------
    # PDF Extraction
    # ---------------------------------------------------------

    def extract_pdf_text(self, file_path):
        """Extract PDF text while retaining page numbers."""

        reader = PdfReader(file_path)
        pages = []

        for page_number, page in enumerate(
            reader.pages, start=1
        ):

            text = page.extract_text() or ""

            if text.strip():
                pages.append({
                    "page": page_number,
                    "text": text
                })

        return pages

    # ---------------------------------------------------------
    # TXT Extraction
    # ---------------------------------------------------------

    @staticmethod
    def extract_text_file(file_path):
        """Read a text file with basic encoding fallback."""

        try:
            text = Path(file_path).read_text(
                encoding="utf-8-sig"
            )

        except UnicodeDecodeError:
            text = Path(file_path).read_text(
                encoding="cp1252"
            )

        return [{
            "page": 1,
            "text": text
        }]

    # ---------------------------------------------------------
    # Text Chunking
    # ---------------------------------------------------------


    @staticmethod
    def _get_overlap_tail(text: str, max_chars: int) -> str:
        """Return the last complete words within the requested character limit."""

        if max_chars <= 0:
            return ""

        words = text.split()
        tail = []

        for word in reversed(words):
            candidate = " ".join([word] + tail)

            if len(candidate) > max_chars:
                break

            tail.insert(0, word)

        return " ".join(tail)

    def _split_long_paragraph(self, paragraph: str) -> List[str]:
        """
        Split an oversized paragraph into sentence-sized units.

        If a sentence is still too long, split it at word boundaries.
        """

        sentences = re.split(
            r"(?<=[.!?])\s+",
            paragraph
        )

        units = []

        for sentence in sentences:

            sentence = sentence.strip()

            if not sentence:
                continue

            if len(sentence) <= self.chunk_size:
                units.append(sentence)
                continue

            # Sentence is too long: split at word boundaries.
            words = sentence.split()
            current = ""

            for word in words:

                # Handle an unusually long word.
                if len(word) > self.chunk_size:

                    if current:
                        units.append(current)
                        current = ""

                    for start in range(
                        0, len(word), self.chunk_size
                    ):
                        units.append(
                            word[start:start + self.chunk_size]
                        )

                    continue

                candidate = (
                    f"{current} {word}"
                    if current else word
                )

                if len(candidate) <= self.chunk_size:
                    current = candidate

                else:
                    if current:
                        units.append(current)

                    current = word

            if current:
                units.append(current)

        return units

    def chunk_text(self, text: str) -> List[str]:
        """
        Create overlapping chunks using paragraph and sentence boundaries.

        Chunk size and overlap are measured in characters.
        """

        if not text or not text.strip():
            return []

        # Normalize line endings.
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Treat single line breaks as normal spacing.
        # Preserve blank lines as paragraph boundaries.
        text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)

        paragraphs = [
            re.sub(r"[ \t]+", " ", part).strip()
            for part in re.split(r"\n\s*\n", text)
        ]

        paragraphs = [
            paragraph for paragraph in paragraphs
            if paragraph
        ]

        # Build units that do not exceed the chunk size.
        units = []

        for paragraph in paragraphs:

            if len(paragraph) <= self.chunk_size:
                units.append(paragraph)

            else:
                units.extend(
                    self._split_long_paragraph(paragraph)
                )

        chunks = []
        current = ""

        # Combine units into chunks.
        for unit in units:

            candidate = (
                f"{current}\n\n{unit}"
                if current else unit
            )

            if len(candidate) <= self.chunk_size:
                current = candidate
                continue

            # Save the completed chunk.
            if current:
                chunks.append(current)

            # Carry forward a controlled amount of overlap.
            available = (
                self.chunk_size - len(unit) - 2
            )

            tail = self._get_overlap_tail(
                current,
                min(self.overlap, max(0, available))
            )

            current = (
                f"{tail}\n\n{unit}"
                if tail else unit
            )

        if current:
            chunks.append(current)

        return [
            chunk for chunk in chunks
            if chunk.strip()
        ]

    # def chunk_text(self, text):
    #     """
    #     Split text into overlapping chunks.
    #
    #     Preserve paragraph boundaries where possible.
    #     Split oversized paragraphs at word boundaries.
    #     """
    #
    #     paragraphs = [
    #         re.sub(r"\s+", " ", part).strip()
    #         for part in re.split(r"\n\s*\n", text)
    #     ]
    #
    #     paragraphs = [
    #         p for p in paragraphs if p
    #     ]
    #
    #     chunks = []
    #     current = ""
    #
    #     def split_long_paragraph(paragraph):
    #
    #         pieces = []
    #         start = 0
    #
    #         while start < len(paragraph):
    #
    #             end = min(
    #                 start + self.chunk_size,
    #                 len(paragraph)
    #             )
    #
    #             if end < len(paragraph):
    #
    #                 boundary = paragraph.rfind(
    #                     " ", start, end
    #                 )
    #
    #                 if boundary > start:
    #                     end = boundary
    #
    #             piece = paragraph[start:end].strip()
    #
    #             if piece:
    #                 pieces.append(piece)
    #
    #             if end >= len(paragraph):
    #                 break
    #
    #             start = max(
    #                 end - self.overlap,
    #                 start + 1
    #             )
    #
    #         return pieces
    #
    #     for paragraph in paragraphs:
    #
    #         # Handle oversized paragraphs separately
    #         if len(paragraph) > self.chunk_size:
    #
    #             if current:
    #                 chunks.append(current)
    #                 current = ""
    #
    #             chunks.extend(
    #                 split_long_paragraph(paragraph)
    #             )
    #
    #             continue
    #
    #         candidate = (
    #             f"{current}\n\n{paragraph}"
    #             if current else paragraph
    #         )
    #
    #         if len(candidate) <= self.chunk_size:
    #
    #             current = candidate
    #
    #         else:
    #
    #             if current:
    #                 chunks.append(current)
    #
    #             # Carry the end of the previous chunk forward
    #             if self.overlap and current:
    #
    #                 tail = current[-self.overlap:].lstrip()
    #
    #                 current = (
    #                     f"{tail}\n\n{paragraph}"
    #                     if tail else paragraph
    #                 )
    #
    #                 if len(current) > self.chunk_size:
    #                     current = paragraph
    #
    #             else:
    #                 current = paragraph
    #
    #     if current:
    #         chunks.append(current)
    #
    #     return [
    #         chunk for chunk in chunks
    #         if chunk.strip()
    #     ]

    # ---------------------------------------------------------
    # File Identification
    # ---------------------------------------------------------

    @staticmethod
    def _sha256_file(file_path):
        """Generate a hash of the complete source file."""

        digest = hashlib.sha256()

        with open(file_path, "rb") as source:

            for block in iter(
                lambda: source.read(1024 * 1024),
                b""
            ):
                digest.update(block)

        return digest.hexdigest()

    @staticmethod
    def _document_id(file_path):
        """Generate a stable ID based on the source path."""

        normalized_path = os.path.normcase(
            os.path.abspath(file_path)
        )

        return hashlib.sha256(
            normalized_path.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _chunk_id(
        document_id,
        file_hash,
        chunk_index,
        chunk
    ):
        """Generate a deterministic chunk ID."""

        value = (
            f"{document_id}:"
            f"{file_hash}:"
            f"{chunk_index}:"
            f"{chunk}"
        )

        return hashlib.sha256(
            value.encode("utf-8")
        ).hexdigest()

    # ---------------------------------------------------------
    # Single File Ingestion
    # ---------------------------------------------------------

    def ingest_file(self, file_path):

        file_path = os.path.abspath(file_path)

        extension = Path(file_path).suffix.lower()

        # Extract source text
        if extension == ".pdf":

            pages = self.extract_pdf_text(file_path)

        elif extension == ".txt":

            pages = self.extract_text_file(file_path)

        else:

            raise ValueError(
                f"Unsupported file type: {extension}"
            )

        if not pages or not any(
            page["text"].strip() for page in pages
        ):

            raise ValueError(
                "No extractable text found. "
                "Scanned PDFs require OCR."
            )

        # Identify source document
        file_hash = self._sha256_file(file_path)

        document_id = self._document_id(file_path)

        filename = os.path.basename(file_path)

        documents = []
        ids = []
        metadatas = []

        chunk_index = 0

        # Generate chunks and metadata
        for page_data in pages:

            chunks = self.chunk_text(
                page_data["text"]
            )

            for chunk in chunks:

                documents.append(chunk)

                ids.append(
                    self._chunk_id(
                        document_id,
                        file_hash,
                        chunk_index,
                        chunk
                    )
                )

                metadatas.append({
                    "document_id": document_id,
                    "source": filename,
                    "source_path": file_path,
                    "file_type": extension.lstrip("."),
                    "file_hash": file_hash,
                    "page": int(page_data["page"]),
                    "chunk_index": chunk_index,
                    "chunk_size": len(chunk)
                })

                chunk_index += 1

        if not documents:

            raise ValueError(
                "No text chunks were generated"
            )

        # Store new chunks before removing old ones
        self.chroma.upsert_documents(
            documents=documents,
            ids=ids,
            metadatas=metadatas,
            batch_size=self.batch_size
        )

        # Find previously stored chunks for this file
        existing = self.chroma.get(
            where={"document_id": document_id},
            include=["metadatas"]
        )

        existing_ids = set(
            existing.get("ids", [])
        )

        # Remove obsolete chunks
        stale_ids = sorted(
            existing_ids.difference(ids)
        )

        if stale_ids:

            self.chroma.delete(
                ids=stale_ids
            )

        return {
            "file": file_path,
            "status": "success",
            "document_id": document_id,
            "file_hash": file_hash,
            "pages_extracted": len(pages),
            "chunks_ingested": len(documents),
            "stale_chunks_removed": len(stale_ids)
        }

    # ---------------------------------------------------------
    # Multiple File Ingestion
    # ---------------------------------------------------------

    def ingest_files(self, file_paths):
        """Ingest multiple files and report individual results."""

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
                    result["chunks_ingested"]
                )

            except Exception as exc:

                logger.exception(
                    "Failed ingesting file: %s",
                    file_path
                )

                results.append({
                    "file": os.path.abspath(file_path),
                    "status": "failed",
                    "error": str(exc)
                })

        successful = [
            r for r in results
            if r["status"] == "success"
        ]

        failed = [
            r for r in results
            if r["status"] == "failed"
        ]

        return {
            "files_processed": len(results),
            "files_succeeded": len(successful),
            "files_failed": len(failed),
            "total_chunks": sum(
                r["chunks_ingested"]
                for r in successful
            ),
            "results": results
        }
