'''
Created on Aug 28, 2025

@author: keith.chambers
'''

# setup logging for this module
import logging
logger = logging.getLogger(__name__)

# -----------------------------
# imports
# -----------------------------
from AskMeApp.llm.providers.gemini import GeminiProvider
from AskMeApp.my_constants import LLM_types

#===============================================================================
class LLMClient:

    def __init__(self, app_config):
        self.config = app_config
        self.provider = self._create_provider()
        self.provider.initialize()
        # self.initialized = False

    def _create_provider(self):

        if self.config.default_llm == LLM_types.GEMINI_2_5_FLASH:
            return GeminiProvider(self.config)

        raise RuntimeError("Unsupported LLM type")

    def call(self, prompt):

        if not prompt.dirty:
            return prompt.answer

        response = self.provider.call(prompt)
        prompt.answer = response
        return response

    def shutdown(self):
        self.provider.shutdown()




    
    
    