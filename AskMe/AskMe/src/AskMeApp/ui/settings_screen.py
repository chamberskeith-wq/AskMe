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
from kivy.app import App
from kivy.uix.screenmanager import Screen#, ScreenManager
from kivy.properties import StringProperty, BooleanProperty
#from kivy.uix.widget import Widget
#from kivy.properties import NumericProperty, ReferenceListProperty, ObjectProperty, ListProperty, DictProperty
import os
import copy

# import modules in this package
from AskMeApp.my_constants import LLM_types
from AskMeApp.ui.components.directory_picker import DirectoryPickerPopup
from AskMeApp.ui.components.message_popup import MessagePopup
from AskMeApp.my_chroma import ChromaClient
from AskMeApp.my_configuration import save_config, set_google_api_key, ConfigError 

#===============================================================================
# SettingsScreen - linked to entry in kivy file
#===============================================================================
class SettingsScreen(Screen):
    """ Settings screen, linked by kivy magic to UI elements
        Args:
            None
        Returns:
            None
        Raises:
            None
    """
    
    # set up kivy properties
    current_path = StringProperty("") #path to the ChromaDB database
    is_dirty = BooleanProperty(False) # dirty flag to enable the apply button
    
    #===========================================================================
    # on_kv_post
    #===========================================================================
    def on_kv_post(self, base_widget): 
        """ Lifecycle method, after Kivy has created the widget tree for the display
        Args:
            base_widget:
        """
        
        # Bind change listeners for Apply button handling
        self._bind_dirty_tracking()
        
    #===========================================================================
    # on_pre_enter
    #===========================================================================
    def on_pre_enter(self):
        """ Lifecycle method, on entry to the UI
            Args:
                None
            Returns:
                None
            Rasies:
                None
        """

        #Populate fields when entering Settings screen.
        app = App.get_running_app()
        
        # create working copy and initialize current_path
        self._working_config = copy.deepcopy(app.app_config)
        

        self.ids.chroma_db.text = self._working_config.chroma_db or ""
        self.current_path = self._working_config.chroma_db_path or "" #kivy is binding this property to the label

        # Populate spinner with enum names
        llm_names = [e.name for e in LLM_types]
        self.ids.default_llm.values = llm_names
        self.ids.default_llm.text = self._working_config.default_llm.name

        # Load the editable system instructions from the working config.
        self.ids.prompt_instructions.text = (
            self._working_config.prompt_instructions or ""
        )

        # Never preload secrets
        self.ids.google_api_key.text = ""
        
        # Reset dirty state
        self.is_dirty = False

    #===========================================================================
    # browse_path for context database
    #===========================================================================
    def browse_path(self):
        """Open reusable directory picker popup."""
    
        popup = DirectoryPickerPopup(
            initial_path=self.current_path,
            on_select=self._on_directory_selected
        )
    
        popup.open()
        
    #===========================================================================
    # apply_settings
    #===========================================================================
    def apply_settings(self):
        """ save setting button on the settings screen
        Args:
            None
        Returns:
            None
        Raises:
            ConfigError
        """
        
        app = App.get_running_app()
        
        try:
            self._working_config.update(
                chroma_db=self.ids.chroma_db.text.strip(),
                chroma_db_path=self.current_path,
                default_llm=LLM_types[self.ids.default_llm.text],
                prompt_instructions=self.ids.prompt_instructions.text.strip(),
            )

            # Save config
            save_config(self._working_config)

            # Replace active config
            old_llm = app.app_config.default_llm
            old_db_name = app.app_config.chroma_db
            old_db_path = app.app_config.chroma_db_path
            
            app.app_config = self._working_config

            # Apply the updated instructions to the active prompt.
            app.my_prompt.instructions = app.app_config.prompt_instructions

            # Store API key if provided
            api_key = self.ids.google_api_key.text.strip()
            if api_key:
                set_google_api_key(api_key)

            # Reinitialize LLM if changed
            if old_llm != app.app_config.default_llm:
                app.reinitialize_llm()
            
            if (
                old_db_name != app.app_config.chroma_db or
                old_db_path != app.app_config.chroma_db_path
            ):
                app.reinitialize_chroma()
                
                # Check if DB exists
                if not app.chroma.database_exists():
                    self._prompt_create_database(app)
                    return  # Stop until user responds                


            self.is_dirty = False
            self.manager.current = "query"

        except ConfigError as e:
            #ErrorPopup(str(e), title="Configuration Error").open()
            MessagePopup(str(e), level="error", title="Configuration Error").open()
            
    #===========================================================================
    # cancel_settings
    #===========================================================================
    def cancel_settings(self):
        """ save setting button on the settings screen
        Args:
            None
        Returns:
            None
        Raises:
            ConfigError
        """

        self.manager.current = "query"
     
    #===========================================================================
    # _on_directory_selected
    #===========================================================================
    def _on_directory_selected(self, selected_path: str):
        """Callback from DirectoryPickerPopup."""
        self.current_path = selected_path
          
    #===========================================================================
    # _bind_dirty_tracking
    #===========================================================================
    def _bind_dirty_tracking(self):
        """ binds the config fields to the dirty check. path and google key are handled directly 
        args:
            None
        Returns:
            None
        Raises:
            None
        """
        
        self.bind(current_path=lambda *a: self._check_dirty())
        self.ids.chroma_db.bind(text=lambda *a: self._check_dirty())
        self.ids.default_llm.bind(text=lambda *a: self._check_dirty())
        self.ids.prompt_instructions.bind(text=lambda *a: self._check_dirty())
        self.ids.google_api_key.bind(text=lambda *a: self._check_dirty())
    
    #===========================================================================
    # _check_dirty
    #===========================================================================
    def _check_dirty(self):
        """ function to compare current and previous version of config fields
        args:
            None
        returns:
            None
        raises:
            None
        """

        # Compare UI state to original working config
        db_changed = (
            self.ids.chroma_db.text.strip()
            != self._working_config.chroma_db
        )
    
        path_changed = (
            os.path.abspath(self.current_path)
            != os.path.abspath(self._working_config.chroma_db_path)
        )
    
        llm_changed = (
            self.ids.default_llm.text
            != self._working_config.default_llm.name
        )

        instructions_changed = (
            self.ids.prompt_instructions.text.strip()
            != self._working_config.prompt_instructions
        )

        api_key_entered = bool(self.ids.google_api_key.text.strip())
    
        self.is_dirty = (
            db_changed or
            path_changed or
            llm_changed or
            instructions_changed or
            api_key_entered
        )

    #===========================================================================
    # _prompt_create_database
    #===========================================================================
    def _prompt_create_database(self, app):
        
        MessagePopup(
            message=(
                f"Chroma database '{app.app_config.chroma_db} does not exist\n"
                "Create it?"
            ),
            level="question",
            title="Create Chroma Database",
            on_confirm=lambda: self._create_chroma_db(app),
            on_cancel=lambda: None,
            confirm_text="Create",
            cancel_text="Cancel"
        ).open()
    
    #===========================================================================
    # _create_chroma_db
    #===========================================================================
    def _create_chroma_db(self, *_):
        app = App.get_running_app()
    
        try:
            app.chroma.create_database()
    
            self.is_dirty = False
            self.manager.current = "query"
    
        except Exception as e:
            MessagePopup(
                str(e),
                level="error",
                title="Chroma Error"
            ).open()
 