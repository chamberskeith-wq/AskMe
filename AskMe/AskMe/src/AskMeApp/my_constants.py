'''
Created on Sep 10, 2025

@author: keith.chambers
'''

'''
Read configuration file and create global constants
'''


# setup logging for this module
import logging
logger = logging.getLogger(__name__)

# imports
from enum import Enum
import os

# --------------------------------------------------------------------------------------
# constants
CONFIG_FILE_NAME = 'AskMe.yml'
CONFIG_FILE_PATH = os.path.abspath(f".\\") 

class LLM_types(Enum):
    OPEN_AI = 'open_ai' #place holder for Open AI models
    ANTROPIC = 'anthropic' #place holder for Antrhopic models
    GEMINI_2_5_Pro = 'gemini-2.5-pro' #
    GEMINI_2_5_FLASH = 'gemini-2.5-flash' # Used
    GEMINI_2_5_FLASH_LITE = 'gemini-2.5-flash-lite' #
    GEMINI_2_0_FLASH = 'gemini-2.0-flash' #
    GEMINI_2_0_FLASH_LITE = 'gemini-2.0-flash-lite' #
    GEMINI_3_5_FLASH_LITE = 'gemini-3.5-flash-lite'


