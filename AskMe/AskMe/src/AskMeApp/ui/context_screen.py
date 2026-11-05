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
from AskMeApp.chromaDb.document_ingestion import DocumentIngestion
from AskMeApp.chromaDb.document_retreival import DocumentRetrieval

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
    # UI bound methods
    # ---------------------------------------------------------

    #===========================================================================
    # Refresh button
    #===========================================================================
    def refresh_database_list(self):
        
        app = App.get_running_app()

        try:
            self.available_dbs = app.chroma.list_databases()

        except Exception:
            logger.exception("Failed listing collections")
            self.available_dbs = []
    
    #===========================================================================
    # Create button    
    #===========================================================================
    def create_database(self, db_name):
        
        app = App.get_running_app()

        if not db_name:
            return

        try:
       
            # Initialize Chroma using the new configuration
            app.reinitialize_chroma()
    
            # Create through the Chroma service
            app.chroma.create_database()
    
            self.selected_db = db_name
    
            self.refresh_database_list()

            app.app_config.chroma_db = db_name
    
            logger.info("Created collection: %s", db_name)
            
        except Exception:
            logger.exception("Failed creating database")
        
    #===========================================================================
    # Select database button    
    #===========================================================================
    def select_database(self, db_name):
        
        app = App.get_running_app()
        if not db_name:
            return

        try:
            
            app.reinitialize_chroma()
            app.chroma.load_collection()
            
            self.selected_db = db_name

            app.app_config.chroma_db = db_name
            
            logger.info("Selected collection: %s", db_name)
        except Exception:
            logger.exception("Failed selecting database")
            
    #===========================================================================
    # ingest files button
    #===========================================================================
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

    def ingest_files(self, files):
    
        app = App.get_running_app()
        
        if not app.chroma.collection:
            logger.warning("No Chroma collection selected")
            return None
    
        try:
            ingestion = DocumentIngestion(
                chroma_client=app.chroma,
                chunk_size=900,
                overlap=120,
                batch_size=100
            )
    
            result = ingestion.ingest_files(files)
    
            logger.info(
                "Ingestion complete: %d files, %d chunks, %d failures",
                result["files_succeeded"],
                result["total_chunks"],
                result["files_failed"]
            )
    
            self.show_ingestion_results(result)
             
            return result
    
        except Exception:
            logger.exception("Document ingestion failed")
            return None
        
    # ---------------------------------------------------------
    # Search button
    # ---------------------------------------------------------
    def semantic_search(self, query_text, top_k=5):
        
        app = App.get_running_app()

        if not query_text or not query_text.strip():
            return
    
        try:
            retrieval = DocumentRetrieval(app.chroma)
    
            results = retrieval.search(
                query_text=query_text,
                top_k=top_k
            )
    
            self.display_search_results(results)
    
        except Exception:
            logger.exception("Semantic search failed")

    #===========================================================================
    # View Database button
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


    # ---------------------------------------------------------
    # UI Support methods
    # ---------------------------------------------------------

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

    def show_ingestion_results(self, result):
    
        message = (
            f"Files processed: {result['files_processed']}\n"
            f"Successful: {result['files_succeeded']}\n"
            f"Failed: {result['files_failed']}\n"
            f"Total chunks: {result['total_chunks']}"
        )
    
        popup = Popup(
            title="Ingestion Results",
            content=Label(text=message),
            size_hint=(0.7, 0.4)
        )
    
        popup.open()

    def display_search_results(self, results):
    
        layout = BoxLayout(
            orientation="vertical",
            spacing=10,
            padding=10
        )
    
        if not results:
            layout.add_widget(
                Label(text="No results found")
            )
    
        else:
            for result in results:
    
                metadata = result["metadata"]
    
                source = metadata.get("source", "Unknown")
                page = metadata.get("page", "Unknown")
                distance = result["distance"]
                document = result["document"]
    
                text = (
                    f"Source: {source}\n"
                    f"Page: {page}\n"
                    f"Distance: {distance:.4f}\n\n"
                    f"{document[:500]}"
                )
    
                label = Label(
                    text=text,
                    markup=False,
                    size_hint_y=None
                )
    
                label.bind(
                    texture_size=lambda instance, value:
                    setattr(instance, "height", value[1])
                )
    
                layout.add_widget(label)
    
        popup = Popup(
            title="Document Retrieval Results",
            content=layout,
            size_hint=(0.9, 0.9)
        )
    
        popup.open()
    
    
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