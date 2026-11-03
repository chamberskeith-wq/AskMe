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
from google import genai
from AskMeApp.llm.base import BaseLLMProvider
from AskMeApp.my_configuration import ConfigError, get_google_api_key

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):

    def __init__(self, config):
        self.config = config
        self.client = None

    def initialize(self):
        api_key =get_google_api_key()
        if not api_key:
            raise ConfigError("Gemini selected but GOOGLE_API_KEY not configured")

        logger.info("Initializing Gemini provider")
        self.client = genai.Client(api_key=api_key)

    def call(self, prompt):
        if not prompt.chat:
            prompt.chat_session = self.client.chats.create(
                model=self.config.default_llm.value
            )
            prompt.chat = True

        response = prompt.chat_session.send_message(prompt.prompt)
        return response.text

    def shutdown(self):
        logger.debug("GeminiProvider shutdown")
