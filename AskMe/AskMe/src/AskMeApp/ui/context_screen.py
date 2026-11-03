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

    def ingest_files(self, files):
        app = App.get_running_app()

        if not app.chroma.collection:
            try:
                app.chroma.load_collection()
            except Exception:
                logger.error("No collection loaded")
                return

        for file_path in files:
            try:
                with open(file_path, "rb") as f:
                    content = f.read()

                app.chroma.add_documents(
                    documents=[content.decode(errors="ignore")],
                    ids=[str(uuid.uuid4())],
                    metadatas=[{"source": file_path}]
                )

                logger.info("Ingested %s", file_path)

            except Exception:
                logger.exception("Failed ingesting file: %s", file_path)

    
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
