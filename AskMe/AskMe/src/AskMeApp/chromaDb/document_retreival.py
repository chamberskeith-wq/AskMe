'''
Created on Nov 5, 2026

@author: keith.chambers
'''

"""
Document retrieval service for AskMe.

Responsibilities:
- Search the active ChromaDB collection
- Apply optional metadata filters
- Return matching chunks and their metadata
- Keep ChromaDB query details out of Kivy screens
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DocumentRetrieval:
    """Search an active ChromaDB collection for relevant document chunks."""

    def __init__(self, chroma_client):
        self.chroma = chroma_client

    def search(
        self,
        query_text: str,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return the top matching chunks.

        Each result contains:
            id
            document
            metadata
            distance
        """

        if not query_text or not query_text.strip():
            raise ValueError("Search query cannot be empty")

        if not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be a positive integer")

        # Ensure a collection is active.
        if not self.chroma.collection:
            self.chroma.load_collection()

        # Avoid querying an empty collection.
        collection_count = self.chroma.count()

        if collection_count == 0:
            return []

        number_of_results = min(top_k, collection_count)

        query_args = {
            "query_texts": [query_text.strip()],
            "n_results": number_of_results,
            "include": ["documents", "metadatas", "distances"],
        }

        if where is not None:
            query_args["where"] = where

        if where_document is not None:
            query_args["where_document"] = where_document

        results = self.chroma.query(**query_args)

        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        search_results = []

        for doc_id, document, metadata, distance in zip(
            ids, documents, metadatas, distances
        ):
            search_results.append({
                "id": doc_id,
                "document": document,
                "metadata": metadata or {},
                "distance": distance,
            })

        logger.info(
            "Document search returned %d results",
            len(search_results),
        )

        return search_results
