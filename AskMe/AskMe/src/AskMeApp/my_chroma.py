'''
Created on Feb 17, 2026

@author: keith.chambers


ChromaDB service layer.

Responsibilities:
- Manage PersistentClient lifecycle
- Validate database existence
- Create collections explicitly
- Abstract Chroma from UI
- Provide safe collection operations
'''

import os
import uuid
import logging
from typing import List, Dict, Any, Optional

from chromadb import PersistentClient

logger = logging.getLogger(__name__)


#===============================================================================
# ChromaClient
#===============================================================================
class ChromaClient:
    """ Encapsulates Chroma persistent database management.
    Acts as a vector database abstraction layer.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, config):
        self.config = config
        self.client: Optional[PersistentClient] = None
        self.collection = None
        self._initialize()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _initialize(self) -> None:
        db_path = self.config.chroma_db_path

        if not os.path.isdir(db_path):
            raise ValueError(f"Invalid Chroma path: {db_path}")

        logger.info("Initializing Chroma client", extra={
            "path": db_path,
            "db_name": self.config.chroma_db,
        })

        self.client = PersistentClient(path=db_path)
        self.collection = None

    def shutdown(self) -> None:
        logger.debug("Shutting down ChromaClient")
        self.client = None
        self.collection = None

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _require_client(self):
        if not self.client:
            raise RuntimeError("ChromaClient not initialized")

    def _require_collection(self):
        if not self.collection:
            raise RuntimeError("No collection loaded")

    # ------------------------------------------------------------------
    # Collection Management
    # ------------------------------------------------------------------

    #===========================================================================
    # list_databases
    #===========================================================================
    def list_databases(self) -> List[str]:
        self._require_client()
        return [c.name for c in self.client.list_collections()]

    #===========================================================================
    # database_exists
    #===========================================================================
    def database_exists(self) -> bool:
        self._require_client()

        try:
            self.client.get_collection(name=self.config.chroma_db)
            return True
        except Exception:
            return False

    #===========================================================================
    # create_database
    #===========================================================================
    def create_database(self) -> None:
        self._require_client()

        logger.info("Creating collection", extra={
            "db_name": self.config.chroma_db
        })

        self.collection = self.client.create_collection(
            name=self.config.chroma_db
        )

    #===========================================================================
    # load_collection
    #===========================================================================
    def load_collection(self) -> None:
        self._require_client()

        logger.info("Loading collection", extra={
            "db_name": self.config.chroma_db
        })

        self.collection = self.client.get_collection(
            name=self.config.chroma_db
        )

    #===========================================================================
    # delete_database
    #===========================================================================
    def delete_database(self) -> None:
        self._require_client()

        logger.warning("Deleting collection", extra={
            "db_name": self.config.chroma_db
        })

        self.client.delete_collection(name=self.config.chroma_db)
        self.collection = None

    # ------------------------------------------------------------------
    # Collection Operations (Vector API Abstraction)
    # ------------------------------------------------------------------

    #===========================================================================
    # count
    #===========================================================================
    def count(self) -> int:
        self._require_collection()
        return self.collection.count()

    #===========================================================================
    # add_documents
    #===========================================================================
    def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
    ) -> None:
        """ Add documents to collection. Generates UUIDs if not supplied.
        
        Args:
            documents: a list of file names
            metadatas:
            ids:
        """

        self._require_collection()

        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]

        logger.debug("Adding documents", extra={
            "count": len(documents)
        })

        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

    def get(self, **kwargs) -> Dict[str, Any]:
        self._require_collection()
        return self.collection.get(**kwargs)

    def query(self, **kwargs) -> Dict[str, Any]:
        self._require_collection()
        return self.collection.query(**kwargs)

    def delete(self, ids: Optional[List[str]] = None, where: Optional[Dict] = None):
        """
        Delete by ids or metadata filter.
        """
        self._require_collection()
        self.collection.delete(ids=ids, where=where)

    # ------------------------------------------------------------------
    # Debug / Inspection
    # ------------------------------------------------------------------

    def peek(self, limit: int = 10) -> Dict[str, Any]:
        self._require_collection()

        return self.collection.get(
            limit=limit,
            include=["documents", "metadatas"]
        )
