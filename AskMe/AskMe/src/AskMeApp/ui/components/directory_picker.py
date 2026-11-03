'''
Created on Feb 12, 2026

@author: keith.chambers
'''

# setup logging for this module
import logging
logger = logging.getLogger(__name__)

import os
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.textinput import TextInput


class DirectoryPickerPopup(Popup):
    """
    Reusable directory picker popup.

    Args:
        initial_path (str): Current configured path
        on_select (callable): Callback receiving selected path
    """

    def __init__(self, initial_path: str, on_select, **kwargs):
        super().__init__(**kwargs)

        self.title = "Select Database Folder"
        self.size_hint = (0.9, 0.9)

        self._callback = on_select
        self._initial_path = os.path.abspath(initial_path or os.getcwd())

        self._build_ui()

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self):

        configured_path = self._initial_path
        parent_path = os.path.dirname(configured_path)

        if not os.path.exists(configured_path):
            parent_path = os.getcwd()
            configured_path = parent_path

        content = BoxLayout(orientation="vertical")

        self.chooser = FileChooserListView(
            dirselect=True,
            multiselect=False,
            path=parent_path,
            selection=[configured_path]
        )

        # prevent ghost selection highlight
        def enforce_single_selection(instance, value):
            if value:
                last = value[-1]
                instance.selection = [last]
                instance._update_files()

        self.chooser.bind(selection=enforce_single_selection)

        content.add_widget(self.chooser)

        # --- Buttons ---
        button_row = BoxLayout(size_hint_y=None, height=40, spacing=5)

        select_btn = Button(text="Select")
        new_folder_btn = Button(text="New Context")
        cancel_btn = Button(text="Cancel")

        select_btn.bind(on_release=self._select_directory)
        new_folder_btn.bind(on_release=self._open_new_folder_popup)
        cancel_btn.bind(on_release=lambda *_: self.dismiss())
        
        select_btn.disabled = True

        def update_select_button(instance, value):
            select_btn.disabled = not bool(value)
        
        self.chooser.bind(selection=update_select_button)


        button_row.add_widget(select_btn)
        button_row.add_widget(new_folder_btn)
        button_row.add_widget(cancel_btn)

        content.add_widget(button_row)
        
        self.content = content

    # ------------------------------------------------------------------
    # Selection Handler
    # ------------------------------------------------------------------

    def _select_directory(self, instance):

        if self.chooser.selection:
            selected = os.path.abspath(self.chooser.selection[0])
            
            if not os.path.isdir(selected):
                return
            
            logger.debug("Directory selected: %s", selected)

            if self._callback:
                self._callback(selected)

        self.dismiss()
        
    # ------------------------------------------------------------------
    # New Folder Popup
    # ------------------------------------------------------------------

    def _open_new_folder_popup(self, *_):

        layout = BoxLayout(
            orientation="vertical",
            spacing=5,
            padding=5
        )

        name_input = TextInput(
            hint_text="Enter folder name",
            multiline=False,
            size_hint_y=None,
            height=40
        )

        layout.add_widget(name_input)

        button_row = BoxLayout(size_hint_y=None, height=40, spacing=5)

        create_btn = Button(text="Create")
        cancel_btn = Button(text="Cancel")

        button_row.add_widget(create_btn)
        button_row.add_widget(cancel_btn)

        layout.add_widget(button_row)

        popup = Popup(
            title="Create New Folder",
            content=layout,
            size_hint=(0.6, 0.3)
        )
        

        create_btn.bind(
            on_release=lambda *_: self._create_folder(name_input.text, popup)
        )

        cancel_btn.bind(on_release=lambda *_: popup.dismiss())

        popup.open()

    # ------------------------------------------------------------------
    # Create Folder Logic
    # ------------------------------------------------------------------

    def _create_folder(self, folder_name: str, popup: Popup):

        folder_name = folder_name.strip()

        if not folder_name:
            return

        new_path = os.path.join(self.chooser.path, folder_name)

        try:
            os.makedirs(new_path, exist_ok=False)

            logger.info("Created folder: %s", new_path)

            # Refresh chooser safely
            self.chooser.path = self.chooser.path

            # Auto-select new folder
            self.chooser.selection = [new_path]

            popup.dismiss()

        except FileExistsError:
            logger.warning("Folder already exists: %s", new_path)

        except OSError as e:
            logger.error("Error creating folder: %s", e)

