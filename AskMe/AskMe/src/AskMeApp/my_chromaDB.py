'''
Created on Jan 14, 2026

@author: keith.chambers
'''

# create module logger
import logging
logger = logging.getLogger(__name__)

#imports
import chromadb
from chromadb.config import Settings
import os
import uuid
from pypdf import PdfReader

#modules in this package
#import AskMeApp.my_constants
from AskMeApp.my_constants import CONTEXT_DB_NAME, CONTEXT_DB_PATH

def load_db(self):
    """Load or create a persistent ChromaDB database with full error handling."""

    name = CONTEXT_DB_NAME
    folder = CONTEXT_DB_PATH

    try:
        # ---- Validate path ----
        if not folder:
            raise ValueError("CONTEXT_DB_PATH is empty")

        # Expand user (~) and normalize path
        folder = os.path.abspath(os.path.expanduser(folder))

        # Ensure directory exists
        os.makedirs(folder, exist_ok=True)

        # ---- Create persistent client ----
        try:
            self.client = chromadb.PersistentClient(path=folder)
        except Exception as e:
            raise RuntimeError(f"Failed to create ChromaDB client at {folder}: {e}")

        # ---- Load or create collection ----
        try:
            self.collection = self.client.get_or_create_collection(name="my_collection")
        except Exception as e:
            raise RuntimeError(f"Failed to load collection 'my_collection': {e}")

        # ---- Verify database integrity ----
        try:
            count = self.collection.count()
        except Exception:
            count = "unknown"

        # ---- Update UI ----
        self.ids.status.text = f"Database '{name}' loaded ({count} documents)."
        self.refresh_explorer()

    except Exception as e:
        # ---- Hard failure handling ----
        error_msg = f"Failed to load database '{name}': {str(e)}"
        self.ids.status.text = error_msg

        # Log full traceback for debugging
        print("\n=== ChromaDB Load Error ===")
        print(error_msg)
        traceback.print_exc()
        print("==========================")

        # Reset partially-created objects
        self.client = None
        self.collection = None
