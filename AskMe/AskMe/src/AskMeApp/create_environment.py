'''
Created on Sep 9, 2025

@author: keith.chambers
'''
'''
Create a YAML configuration file for the AskMe app

'''

import yaml
from enum import Enum
import os

# Check these definitions match the current YAML file, which may of been edited directly
# The enumeration is built with an python friendly name, with the api name used as the value
'''
class LLM_types(Enum) :
    DEFAULT = 'default' #a default model to use
    OPEN_AI = 'open_ai' #place holder for Open AI models
    ANTROPIC = 'anthropic' #place holder for Antrhopic models
    GEMINI_2_5_Pro = 'gemini-2.5-pro' #
    GEMINI_2_5_FLASH = 'gemini-2.5-flash' # Used
    GEMINI_2_5_FLASH_LITE = 'gemini-2.5-flash-lite' #
    GEMINI_2_0_FLASH = 'gemini-2.0-flash' #
    GEMINI_2_0_FLASH_LITE = 'gemini-2.0-flash-lite' #

LLM_dictionary = {lll_type.name: lll_type.value for lll_type in LLM_types}
'''
# Define environment variable
#
# GOOGLE_API_KEY Access to the google AI apis
# DEFAULT_LLM  constrained to a member of LLM_Types

env_config = {
        'GOOGLE_API_KEY' : 'AIzaSyAs2Nvqn_8Xb3T3K33ReCD9Z_c783zJpVc',
        'DEFAULT_LLM' : 'gemini-2.5-flash',
        'CHROMA_DB' : 'MyHealth',
        #'CHROMA_DB_PATH' : os.path.abspath(f"./HC_chroma")
        'CHROMA_DB_PATH' : os.path.abspath(f"./AskMe_ChromaDB")
        }

with open('AskMe.yml','w') as file:
    yaml.dump(env_config,file)
    
