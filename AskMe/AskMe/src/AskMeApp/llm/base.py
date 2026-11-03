'''
Created on Feb 12, 2026

@author: keith.chambers
'''

# -----------------------------
# imports
# -----------------------------
from abc import ABC, abstractmethod
from AskMeApp.my_prompt import MyPrompt


#===============================================================================
# BaseLLMProvider
#===============================================================================
class BaseLLMProvider(ABC):
    """
    Abstract LLM provider interface.
    """

    @abstractmethod
    def initialize(self) -> None:
        """Initialize client resources."""
        pass

    @abstractmethod
    def call(self, prompt: MyPrompt) -> str:
        """Call the LLM and return response text."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Clean up resources (optional)."""
        pass
