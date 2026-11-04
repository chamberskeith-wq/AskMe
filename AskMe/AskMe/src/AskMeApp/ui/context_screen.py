'''
Created on Feb 12, 2026

@author: keith.chambers


'''

# setup logging for this module
import logging
logger = logging.getLogger(__name__)

# -----------------------------
# imports
# -----------------------------
# Kivy imports
import os
import uuid
from pypdf import PdfReader
import re
from AskMeApp.services.document_ingestion import DocumentIngestion

from kivy.clock import Clock
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty, ListProperty
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.button import Button
from kivy.uix.label import Label

#===============================================================================
# ContextScreen
#===============================================================================
class ContextScreen(Screen):
    """Enhanced ContextScreen
        - Create database
        - Select database
        - Ingest files/images
    
    """

    selected_db = StringProperty("")
    available_dbs = ListProperty([])

    # ---------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------

    def on_enter(self):
        self.refresh_database_list()

    # ---------------------------------------------------------
    # Database Management
    # ---------------------------------------------------------

    def refresh_database_list(self):
        app = App.get_running_app()
        client = app.chroma.client

        try:
            collections = client.list_collections()
            self.available_dbs = [c.name for c in collections]
        except Exception as e:
            logger.exception("Failed listing collections")
            self.available_dbs = []

    def create_database(self, db_name):
        app = App.get_running_app()

        if not db_name:
            return

        try:
            app.chroma.client.create_collection(name=db_name)
            self.selected_db = db_name
            app.app_config.chroma_db = db_name
            app.reinitialize_chroma()
            self.refresh_database_list()
        except Exception:
            logger.exception("Failed creating database")

    def select_database(self, db_name):
        app = App.get_running_app()

        try:
            app.app_config.chroma_db = db_name
            app.reinitialize_chroma()
            app.chroma.load_collection()
            self.selected_db = db_name
        except Exception:
            logger.exception("Failed selecting database")

    # ---------------------------------------------------------
    # Ingestion
    # ---------------------------------------------------------

    def open_file_picker(self):

        layout = BoxLayout(orientation="vertical")
        chooser = FileChooserListView(path=os.getcwd())
        layout.add_widget(chooser)

        btn = Button(text="Ingest Selected", size_hint_y=0.15)
        layout.add_widget(btn)

        popup = Popup(title="Select Files", content=layout,
                      size_hint=(0.9, 0.9))

        def ingest_files(instance):
            files = chooser.selection
            popup.dismiss()
            if files:
                self.ingest_files(files)

        btn.bind(on_release=ingest_files)
        popup.open()

    # ---------------------------------------------------------
    # PDF Text Extraction
    # ---------------------------------------------------------

    def extract_pdf_text(self, file_path):
        """Extract text from a PDF, retaining page numbers."""

        reader = PdfReader(file_path)
        pages = []

        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""

            if text.strip():
                pages.append({
                    "page": page_number,
                    "text": text
                })

        return pages

    # ---------------------------------------------------------
    # Text Chunking
    # ---------------------------------------------------------

    def chunk_text(self, text, chunk_size=1000, overlap=150):
        """Split text into overlapping chunks."""

        text = re.sub(r'\s+', ' ', text).strip()

        if not text:
            return []

        chunks = []
        start = 0

        while start < len(text):

            end = min(start + chunk_size, len(text))

            if end < len(text):
                # Prefer breaking at a word boundary
                boundary = text.rfind(" ", start, end)

                if boundary > start:
                    end = boundary

            chunk = text[start:end].strip()

            if chunk:
                chunks.append(chunk)

            if end >= len(text):
                break

            start = max(end - overlap, start + 1)

        return chunks

    # ---------------------------------------------------------
    # File Ingestion
    # ---------------------------------------------------------
    def ingest_files(self, files):
    
        app = App.get_running_app()
    
        try:
            ingestion = DocumentIngestion(
                chroma_client=app.chroma,
                chunk_size=2400,
                overlap=300,
                batch_size=100
            )
    
            result = ingestion.ingest_files(files)
    
            logger.info(
                "Ingestion complete: %d files, %d chunks, %d failures",
                result["files_succeeded"],
                result["total_chunks"],
                result["files_failed"]
            )
    
            return result
    
        except Exception:
            logger.exception("Document ingestion failed")
            return None

    # def ingest_files(self, files):
    #
    #     app = App.get_running_app()
    #
    #     if not app.chroma.collection:
    #         try:
    #             app.chroma.load_collection()
    #         except Exception:
    #             logger.exception("No collection loaded")
    #             return
    #
    #     total_chunks = 0
    #
    #     for file_path in files:
    #
    #         try:
    #             extension = os.path.splitext(file_path)[1].lower()
    #
    #             if extension == ".pdf":
    #
    #                 pages = self.extract_pdf_text(file_path)
    #
    #                 if not pages:
    #                     logger.warning(
    #                         "No extractable text found in PDF: %s",
    #                         file_path
    #                     )
    #                     continue
    #
    #             elif extension == ".txt":
    #
    #                 with open(file_path, "r", encoding="utf-8") as f:
    #                     pages = [{
    #                         "page": 1,
    #                         "text": f.read()
    #                     }]
    #
    #             else:
    #                 logger.warning(
    #                     "Unsupported file type: %s", file_path
    #                 )
    #                 continue
    #
    #             documents = []
    #             ids = []
    #             metadatas = []
    #
    #             chunk_index = 0
    #
    #             for page_data in pages:
    #
    #                 chunks = self.chunk_text(page_data["text"])
    #
    #                 for chunk in chunks:
    #
    #                     documents.append(chunk)
    #
    #                     ids.append(str(uuid.uuid4()))
    #
    #                     metadatas.append({
    #                         "source": os.path.basename(file_path),
    #                         "source_path": file_path,
    #                         "page": page_data["page"],
    #                         "chunk_index": chunk_index
    #                     })
    #
    #                     chunk_index += 1
    #
    #             if not documents:
    #                 logger.warning(
    #                     "No text chunks generated: %s", file_path
    #                 )
    #                 continue
    #
    #             app.chroma.add_documents(
    #                 documents=documents,
    #                 ids=ids,
    #                 metadatas=metadatas
    #             )
    #
    #             total_chunks += len(documents)
    #
    #             logger.info(
    #                 "Ingested %s: %d chunks",
    #                 file_path,
    #                 len(documents)
    #             )
    #
    #         except Exception:
    #             logger.exception(
    #                 "Failed ingesting file: %s", file_path
    #             )
    #
    #     logger.info(
    #         "Ingestion complete. Total chunks added: %d",
    #         total_chunks
    #     )
    
    def on_available_dbs(self, instance, value):
        Clock.schedule_once(self._refresh_db_buttons)
    
    def _refresh_db_buttons(self, *args):
        container = self.ids.db_list
        container.clear_widgets()
    
        for db in self.available_dbs:
            btn = Button(
                text=db,
                size_hint_y=None,
                height=40
            )
            btn.bind(on_release=lambda instance, name=db: self.select_database(name))
            container.add_widget(btn)

    # ---------------------------------------------------------
    # Semantic Search
    # ---------------------------------------------------------

    def semantic_search(self, query_text, top_k=5):
        app = App.get_running_app()

        if not query_text:
            return

        if not app.chroma.collection:
            try:
                app.chroma.load_collection()
            except Exception:
                logger.error("No collection loaded for search")
                return

        try:
            results = app.chroma.query(
                query_texts=[query_text],
                n_results=top_k
            )

            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            self.display_search_results(documents, metadatas, distances)

        except Exception:
            logger.exception("Semantic search failed")
            
    #===========================================================================
    # display_search_results
    #===========================================================================
    def display_search_results(self, documents, metadatas, distances):
        layout = BoxLayout(orientation="vertical", spacing=10, padding=10)

        if not documents:
            layout.add_widget(Label(text="No results found"))
        else:
            for doc, meta, dist in zip(documents, metadatas, distances):
                snippet = doc[:300] + ("..." if len(doc) > 300 else "")
                source = meta.get("source", "Unknown")

                result_label = Label(
                    text=f"[b]Source:[/b] {source}\n"
                         f"[b]Distance:[/b] {round(dist,4)}\n\n"
                         f"{snippet}",
                    markup=True,
                    size_hint_y=None
                )
                result_label.bind(
                    texture_size=lambda instance, value:
                    setattr(instance, "height", value[1])
                )
                layout.add_widget(result_label)

        popup = Popup(
            title="Semantic Search Results",
            content=layout,
            size_hint=(0.9, 0.9)
        )
        popup.open()

    #===========================================================================
    # inspect_database
    #===========================================================================
    def inspect_database(self):

        app = App.get_running_app()

        if not app.chroma.collection:
            try:
                app.chroma.load_collection()
            except Exception:
                logger.error("No collection loaded")
                return

        try:
            count = app.chroma.count()
            results = app.chroma.peek(limit=10)

            documents = results.get("documents", [])
            metadatas = results.get("metadatas", [])
            ids = results.get("ids", [])

            self._show_database_popup(count, ids, documents, metadatas)

        except Exception:
            logger.exception("Database inspection failed")

    #===========================================================================
    # _show_database_popup
    #===========================================================================
    def _show_database_popup(self, count, ids, documents, metadatas):

        layout = BoxLayout(orientation="vertical", spacing=10, padding=10)

        header = Label(
            text=f"[b]Total Records:[/b] {count}",
            markup=True,
            size_hint_y=None
        )
        header.bind(texture_size=lambda i, v: setattr(i, "height", v[1]))
        layout.add_widget(header)

        for doc_id, doc, meta in zip(ids, documents, metadatas):

            snippet = doc[:250] + ("..." if len(doc) > 250 else "")
            source = meta.get("source", "Unknown")

            label = Label(
                text=f"[b]ID:[/b] {doc_id}\n"
                     f"[b]Source:[/b] {source}\n\n"
                     f"{snippet}",
                markup=True,
                size_hint_y=None
            )

            label.bind(texture_size=lambda i, v: setattr(i, "height", v[1]))
            layout.add_widget(label)

        popup = Popup(
            title="Database Contents (Preview)",
            content=layout,
            size_hint=(0.9, 0.9)
        )
        popup.open()
