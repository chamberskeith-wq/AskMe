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
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle

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
        """Build collection statistics and show a readable record sample."""
        app = App.get_running_app()

        if not app.chroma.collection:
            try:
                app.chroma.load_collection()
            except Exception:
                logger.exception("No collection loaded for inspection")
                return

        try:
            total_records = app.chroma.count()
            metadata_rows = self._read_all_metadata(app.chroma, batch_size=1000)
            stats = self._build_inspection_stats(metadata_rows, total_records)

            # Fetch full document text only for the small visible preview.
            preview = app.chroma.get(
                limit=min(15, total_records),
                include=["documents", "metadatas"],
            ) if total_records else {"ids": [], "documents": [], "metadatas": []}

            self._show_database_popup(stats, preview)

        except Exception:
            logger.exception("Database inspection failed")

    @staticmethod
    def _read_all_metadata(chroma_client, batch_size=1000):
        """Read metadata in pages; avoid loading all document text for stats."""
        rows = []
        offset = 0

        while True:
            batch = chroma_client.get(
                limit=batch_size,
                offset=offset,
                include=["metadatas"],
            )
            ids = batch.get("ids", []) or []
            metadatas = batch.get("metadatas", []) or []

            if not ids:
                break

            for index, record_id in enumerate(ids):
                metadata = metadatas[index] if index < len(metadatas) else None
                rows.append({"id": record_id, "metadata": metadata or {}})

            offset += len(ids)
            if len(ids) < batch_size:
                break

        return rows

    @staticmethod
    def _build_inspection_stats(metadata_rows, total_records):
        """Calculate collection-level statistics from Chroma metadata."""
        from collections import Counter, defaultdict

        type_counts = Counter()
        source_counts = Counter()
        source_pages = defaultdict(set)
        chunk_sizes = []
        document_ids = set()
        page_keys = set()

        for row in metadata_rows:
            meta = row.get("metadata") or {}
            source = meta.get("source") or meta.get("source_path") or "Unknown source"
            content_type = meta.get("content_type") or "unspecified"

            type_counts[str(content_type)] += 1
            source_counts[str(source)] += 1

            document_id = meta.get("document_id")
            if document_id:
                document_ids.add(document_id)

            page = meta.get("page")
            if page is not None:
                source_pages[str(source)].add(page)
                page_keys.add((str(source), page))

            size = meta.get("chunk_size")
            if isinstance(size, (int, float)):
                chunk_sizes.append(int(size))

        return {
            "total_records": total_records,
            "metadata_records_read": len(metadata_rows),
            "source_count": len(source_counts),
            "document_count": len(document_ids) or len(source_counts),
            "page_count": len(page_keys),
            "type_counts": dict(type_counts),
            "source_counts": dict(source_counts),
            "source_pages": {key: len(value) for key, value in source_pages.items()},
            "chunk_sizes": chunk_sizes,
        }

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
    
    
    @staticmethod
    def _fit_inspection_label(label, *args):
        """Wrap a Kivy label to its available width and size it to its text."""
        label.text_size = (max(label.width - dp(20), dp(100)), None)
        label.height = label.texture_size[1] + dp(16)

    def _show_database_popup(self, stats, preview):
        """Display collection statistics and a scrollable record preview."""
        root = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
            padding=dp(10),
        )

        sizes = stats["chunk_sizes"]
        if sizes:
            size_summary = (
                f"Chunk size (characters): min {min(sizes):,} | "
                f"avg {sum(sizes) / len(sizes):,.0f} | max {max(sizes):,}"
            )
        else:
            size_summary = "Chunk size statistics unavailable (metadata missing)."

        summary_lines = [
            f"COLLECTION OVERVIEW",
            f"Records: {stats['total_records']:,}    "
            f"Source files: {stats['document_count']:,}    "
            f"Pages represented: {stats['page_count']:,}",
            f"Metadata inspected: {stats['metadata_records_read']:,}",
            size_summary,
            "",
            "RECORD TYPES",
        ]
        if stats["type_counts"]:
            summary_lines.extend(
                f"  {name}: {amount:,}"
                for name, amount in sorted(stats["type_counts"].items())
            )
        else:
            summary_lines.append("  No content_type metadata found.")

        summary_lines.extend(["", "RECORDS BY SOURCE"])
        if stats["source_counts"]:
            ranked_sources = sorted(
                stats["source_counts"].items(),
                key=lambda item: item[1],
                reverse=True,
            )
            for source, amount in ranked_sources[:8]:
                pages = stats["source_pages"].get(source, 0)
                summary_lines.append(
                    f"  {source} — {amount:,} records, {pages:,} pages"
                )
            remaining_sources = len(ranked_sources) - 8
            if remaining_sources > 0:
                summary_lines.append(
                    f"  ... and {remaining_sources:,} more source files"
                )
        else:
            summary_lines.append("  No source metadata found.")

        summary = Label(
            text="\n".join(summary_lines),
            markup=False,
            size_hint_y=None,
            halign="left",
            valign="top",
        )
        summary.bind(width=self._fit_inspection_label)
        summary.bind(texture_size=lambda widget, size: setattr(
            widget, "height", size[1] + dp(16)
        ))
        root.add_widget(summary)

        separator = Label(
            text=f"SAMPLE RECORDS (showing {len(preview.get('ids', [])):,} "
                 f"of {stats['total_records']:,})",
            size_hint_y=None,
            height=dp(30),
            halign="left",
            valign="middle",
        )
        root.add_widget(separator)

        scroll = ScrollView(
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=dp(8),
        )
        records_layout = GridLayout(
            cols=1,
            spacing=dp(10),
            padding=(dp(4), dp(4)),
            size_hint_y=None,
        )
        records_layout.bind(minimum_height=records_layout.setter("height"))

        ids = preview.get("ids", []) or []
        documents = preview.get("documents", []) or []
        metadatas = preview.get("metadatas", []) or []

        if not ids:
            empty = Label(
                text="This collection contains no records.",
                size_hint_y=None,
                height=dp(40),
            )
            records_layout.add_widget(empty)
        else:
            for index, record_id in enumerate(ids):
                document = documents[index] if index < len(documents) else ""
                metadata = metadatas[index] if index < len(metadatas) else {}
                metadata = metadata or {}

                source = metadata.get("source", "Unknown source")
                page = metadata.get("page", "?")
                content_type = metadata.get("content_type", "unspecified")
                chunk_size = metadata.get("chunk_size", len(document or ""))
                test_name = metadata.get("test_name")
                snippet = (document or "").strip()
                
                if len(snippet) > 650:
                    snippet = snippet[:650].rsplit(" ", 1)[0] + " …"

                heading = [
                    f"Record {index + 1} | {content_type}",
                    f"Source: {source} | Page: {page} | Characters: {chunk_size}",
                ]
                if test_name:
                    heading.append(f"Test: {test_name}")
                heading.append(f"ID: {record_id}")
                heading.append("")
                heading.append(snippet or "[No document text returned]")

                card = Label(
                    text="\n".join(heading),
                    markup=False,
                    size_hint_y=None,
                    halign="left",
                    valign="top",
                )
                card.bind(width=self._fit_inspection_label)
                card.bind(texture_size=lambda widget, size: setattr(
                    widget, "height", size[1] + dp(18)
                ))
                records_layout.add_widget(card)

        scroll.add_widget(records_layout)
        root.add_widget(scroll)

        popup = Popup(
            title="ChromaDB Collection Inspection",
            content=root,
            size_hint=(0.94, 0.94),
            auto_dismiss=True,
        )
        popup.open()

