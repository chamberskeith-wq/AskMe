from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.filechooser import FileChooserListView

import chromadb
from chromadb.config import Settings
import os
import uuid
from pypdf import PdfReader

class ChromaScreen(BoxLayout):
    client = None
    collection = None

    #-------------------------Helper Functions-----------------------
    
    def _db_folder(self, name):
        folder = os.path.abspath(f"./{name}_chroma")
        print("Using Chroma folder:", folder)
        return folder

    def _read_text_file(self, filepath):
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    def _read_pdf_file(self, filepath):
        reader = PdfReader(filepath)
        pages = [p.extract_text() or "" for p in reader.pages]
        return "\n".join(pages)

    def _chunk_text(self, text, chunk_size=500, overlap=50):
        chunks = []
        start = 0
    
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end - overlap
    
        return chunks

    def _ingest_selected_file(self, chooser, popup):
        if not chooser.selection:
            return
    
        filepath = chooser.selection[0]
        popup.dismiss()
    
        self.ingest_file(filepath)
        
    def ingest_file(self, filepath):
        ext = os.path.splitext(filepath)[1].lower()
    
        if ext in [".txt", ".md"]:
            text = self._read_text_file(filepath)
        elif ext == ".pdf":
            text = self._read_pdf_file(filepath)
        else:
            self.ids.status.text = "Unsupported file type"
            return
    
        chunks = self._chunk_text(text)
    
        ids = []
        docs = []
        metas = []
    
        for i, chunk in enumerate(chunks):
            ids.append(str(uuid.uuid4()))
            docs.append(chunk)
            metas.append({
                "source": os.path.basename(filepath),
                "chunk": i
            })
    
        self.collection.add(
            documents=docs,
            ids=ids,
            metadatas=metas
        )
    
        self.ids.status.text = f"Ingested {len(chunks)} chunks from {os.path.basename(filepath)}"
        self.refresh_explorer()

    #-------------------------DB Control-----------------------

    def create_new_db(self):
        """Create a fresh ChromaDB in a new folder."""
        name = self.ids.db_name_input.text.strip() or "new_db"
        folder = self._db_folder(name)

        # Remove old folder if it exists
        if os.path.exists(folder):
            import shutil
            shutil.rmtree(folder)

        ''' create a persistent client connection '''
        self.client = chromadb.PersistentClient(path=folder)

        ''' create an empty collection '''
        self.collection = self.client.get_or_create_collection(name="my_collection")
        
        '''notify the UI '''
        self.ids.status.text = f"New database '{name}' created."
        self.refresh_explorer()

    def load_db(self):
        """Load or create a persistent ChromaDB database."""
        name = self.ids.db_name_input.text.strip() or "default_db"
        folder = self._db_folder(name)
        
        ''' create a persistent client connection '''
        self.client = chromadb.PersistentClient(path=folder)
        
        ''' load the collection '''
        self.collection = self.client.get_or_create_collection(name="my_collection")
        
        ''' notify the UI '''
        self.ids.status.text = f"Database '{name}' loaded."
        self.refresh_explorer()

    #-------------------------Explorer-----------------------

    def refresh_explorer(self):

        if not self.collection:
            self.ids.db_info.text = "Documents: 0"
            self.ids.explorer_list.text = ""
            return

        data = self.collection.get()
        ids = data.get("ids", [])
        docs = data.get("documents", [])

        self.ids.db_info.text = f"Documents: {len(ids)}"

        lines = []
        for i, (doc_id, doc) in enumerate(zip(ids, docs)):
            preview = doc[:120].replace("\n", " ")
            lines.append(f"{i+1}. {doc_id}\n   {preview}\n")

        self.ids.explorer_list.text = "\n".join(lines)


    #-------------------------Data Ops-----------------------

    def open_file_picker(self):
        
        if not self.collection:
            self.ids.status.text = "Load a database first"
            return
    
        chooser = FileChooserListView(filters=["*.txt", "*.md", "*.pdf"])
        btn = Button(text="Ingest Selected File", size_hint_y=None, height=40)
    
        layout = BoxLayout(orientation="vertical")
        layout.add_widget(chooser)
        layout.add_widget(btn)
    
        popup = Popup(
            title="Select File to Ingest",
            content=layout,
            size_hint=(0.9, 0.9)
        )
    
        btn.bind(on_release=lambda *a: self._ingest_selected_file(chooser, popup))
        popup.open()        

    def add_text(self):
        
        '''check the collection exists '''
        if not self.collection:
            self.ids.status.text = "Please load a database first."
            return
        
        text = self.ids.text_input.text.strip()
        if not text:
            self.ids.status.text = "No text to add."
            return
        
        self.collection.add(documents=[text], ids=[str(uuid.uuid4())])
        print("Count after add:", self.collection.count())

        ''' notify the UI '''
        self.ids.status.text = f"Text Added, Count '{self.collectionname}' loaded."
        self.ids.text_input.text = ""
        self.refresh_explorer()


    def search_text(self):
        if not self.collection:
            self.ids.status.text = "Please load a database first."
            return
        query = self.ids.query_input.text.strip()
        if not query:
            self.ids.status.text = "No query entered."
            return
        results = self.collection.query(query_texts=[query], n_results=2)
        docs = results.get("documents", [[]])[0]
        self.ids.results_label.text = "\n".join([f"• {d}" for d in docs]) or "No matches found."


class ChromaDBApp(App):
    def build(self):
        
#        self.screen = ChromaScreen()
        return ChromaScreen()

#    def on_stop(self):
#        # Make sure Chroma saves everything to disk
#        if hasattr(self.screen, 'client') and self.screen.client:
#            try:
#                self.screen.client.persist()   # flush to disk
#                print("Chroma database persisted successfully.")
#            except Exception as e:
#                print(f"Error persisting ChromaDB: {e}")

if __name__ == "__main__":
    ChromaDBApp().run()
