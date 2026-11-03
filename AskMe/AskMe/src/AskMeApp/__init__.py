from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout

import chromadb
from chromadb.config import Settings

class ChromaScreen(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=10, spacing=10, **kwargs)

        # Database and collection handles
        self.client = None
        self.collection = None

        # UI setup
        self.status = Label(text="No database loaded", size_hint_y=None, height=30)
        self.add_widget(self.status)

        # DB name entry
        self.db_name_input = TextInput(hint_text="Enter or create database name", multiline=False)
        self.add_widget(self.db_name_input)

        # Buttons for DB control
        btns = BoxLayout(size_hint_y=None, height=40, spacing=5)
        btn_load = Button(text="Load/Create DB", on_release=self.load_db)
        btns.add_widget(btn_load)
        self.add_widget(btns)

        # Input for text entries
        self.text_input = TextInput(hint_text="Enter text to add to database", size_hint_y=0.3)
        self.add_widget(self.text_input)

        # Buttons for adding/searching
        btns2 = BoxLayout(size_hint_y=None, height=40, spacing=5)
        btn_add = Button(text="Add Text", on_release=self.add_text)
        btn_search = Button(text="Search Similar", on_release=self.search_text)
        btns2.add_widget(btn_add)
        btns2.add_widget(btn_search)
        self.add_widget(btns2)

        # Query input
        self.query_input = TextInput(hint_text="Enter query text", size_hint_y=None, height=40)
        self.add_widget(self.query_input)

        # Output area
        self.results_label = Label(text="", halign='left', valign='top', size_hint_y=None)
        self.results_label.bind(texture_size=self._update_height)

        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(self.results_label)
        self.add_widget(scroll)

    def _update_height(self, instance, value):
        instance.height = instance.texture_size[1]
        instance.text_size = (self.width - 20, None)

    # --------------------------------------------------
    # ChromaDB Operations
    # --------------------------------------------------
    def load_db(self, *args):
        name = self.db_name_input.text.strip() or "default_db"
        self.client = chromadb.Client(Settings(
            persist_directory=f"./{name}_chroma"  # saves to a folder
        ))
        self.collection = self.client.get_or_create_collection(name="my_collection")
        self.status.text = f"Database '{name}' loaded."

    def add_text(self, *args):
        if not self.collection:
            self.status.text = "Please load a database first."
            return
        text = self.text_input.text.strip()
        if not text:
            self.status.text = "No text to add."
            return

        self.collection.add(documents=[text], ids=[f"id_{len(self.collection.get()['ids']) + 1}"])
        self.status.text = "Text added."
        self.text_input.text = ""

    def search_text(self, *args):
        if not self.collection:
            self.status.text = "Please load a database first."
            return
        query = self.query_input.text.strip()
        if not query:
            self.status.text = "No query entered."
            return
        results = self.collection.query(query_texts=[query], n_results=5)
        docs = results.get("documents", [[]])[0]
        self.results_label.text = "\n".join([f"• {d}" for d in docs]) or "No matches found."

# --------------------------------------------------
# Kivy App
# --------------------------------------------------
class ChromaDBApp(App):
    def build(self):
        return ChromaScreen()

if __name__ == "__main__":
    ChromaDBApp().run()