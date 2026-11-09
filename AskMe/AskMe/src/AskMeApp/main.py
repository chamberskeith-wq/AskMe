'''
Created on Aug 25, 2025

@author: keith.chambers
'''

# -----------------------------
# Configure logging
# -----------------------------
from AskMeApp.my_logging import configure_base_logging, enforce_library_levels, APP_NAMESPACE
configure_base_logging()

import logging
logger = logging.getLogger(APP_NAMESPACE)

# -----------------------------
# imports
# -----------------------------
# Kivy imports
from kivy.app import App
from kivy.utils import colormap 

# import modules in this package
from AskMeApp.my_LLM import LLMClient
from AskMeApp.my_prompt import MyPrompt
from AskMeApp.my_configuration import ConfigError, load_config 
from AskMeApp.my_chroma import ChromaClient
from AskMeApp.chromaDb.document_retreival import DocumentRetrieval
from AskMeApp.llm.context_assembly import ContextAssembler

# these need to be imported even though they are not referenced
from AskMeApp.ui.query_screen import QueryScreen
from AskMeApp.ui.settings_screen import SettingsScreen
from AskMeApp.ui.context_screen import ContextScreen

#===============================================================================
# AskMeApp - kivy app
#===============================================================================
class AskMeApp(App):
    """ kivy application
    
    """

    # Define a palette of common colors.
    colors = colormap
    
    #===========================================================================
    # build
    #===========================================================================
    def build(self):
        #overload the app build 
           
        #3 Let Kivy load KV + root widget
        return super().build()
    
    #===========================================================================
    # on_start
    #===========================================================================
    def on_start(self):

        #App is now live — UI exists
        
        #reset logger level for noisy libs
        enforce_library_levels()

        # Load and validate configuration
        try:
            self.app_config = load_config() 
        except ConfigError as e:
            logger.error("Configuration error: %s", e)
            # do something here
            raise
        
        # Initialize services
        #---------------------
        
        # Create an LLM client instance
        try:
            self.llm = LLMClient(self.app_config)
        except Exception as e:
            logger.exception("LLM initialization failed")
            raise

        #create a global prompt instance
        try:
            self.my_prompt = MyPrompt('','')
        except Exception as e:
            logger.exception("prompt initialization failed")
            raise
        
        #create the chromaDB client
        try:
            self.chroma = ChromaClient(self.app_config)
        except Exception as e:
            logger.exception("chromaDB initialization failed")
            raise
        if not self.chroma.database_exists():
            logger.warning("Configured context database doesn't exist'")
        
        logger.info("App started")

        # Create the retrieval service
        try:
            self.retrieval = DocumentRetrieval(self.chroma)
        except Exception:
            logger.exception("Document retrieval initialization failed")
            raise

        # Create the context assembler
        try:
            self.context_assembler = ContextAssembler()
        except Exception:
            logger.exception("Context assembler initialization failed")
            raise
        
    #===============================================================================
    # reinitialize_llm
    #===============================================================================
    def reinitialize_llm(self):
        """ re-initialize the configured LLM client
        
        Args:
            None
    
        Returns:
            None
    
        Raises:
            None
        
        """
            
        logger.info("Reinitializing LLM client due to configuration change")
    
        # Reset prompt chat session
        self.my_prompt.chat = False
        self.my_prompt.make_dirty()
    
        # Recreate LLM client
        self.llm = LLMClient(self.app_config)

    #===========================================================================
    # reinitialize_chroma
    #===========================================================================
    def reinitialize_chroma(self):
        """
        Reinitialize Chroma service due to configuration change.
        """
    
        logger.info("Reinitializing Chroma service")
    
        if hasattr(self, "chroma") and self.chroma:
            self.chroma.shutdown()
    
        self.chroma = ChromaClient(self.app_config)
    
        # Recreate retrieval service using the new Chroma client
        self.retrieval = DocumentRetrieval(self.chroma)
        
    #===========================================================================
    # def _initialize_chroma(self):
    #     """
    #     Create and initialize Chroma service.
    #     Does NOT auto-create DB.
    #     """
    # 
    #     logger.info("Initializing Chroma service")
    # 
    #     self.chroma = ChromaService(
    #         db_path=self.app_config.chroma_db_path,
    #         db_name=self.app_config.chroma_db
    #     )
    # 
    #     self.chroma.initialize()
    # 
    #     if self.chroma.database_exists():
    #         self.chroma.load_collection()
    #         logger.info("Chroma collection loaded")
    #     else:
    #         logger.warning("Configured Chroma collection does not exist")
    #===========================================================================
        
# run the app
# this loads the screen manager and the first defined screen via Kivy magic

if __name__ == '__main__':
    AskMeApp().run()