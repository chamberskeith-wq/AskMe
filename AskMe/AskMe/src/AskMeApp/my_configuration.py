'''
Created on Jan 15, 2026

@author: keith.chambers
'''

#===============================================================================
# Module logger
#===============================================================================
import logging
logger = logging.getLogger(__name__)

# common imports
import yaml 
import os
import keyring
from pathlib import Path
from dataclasses import dataclass

from AskMeApp.my_constants import CONFIG_FILE_NAME, CONFIG_FILE_PATH, LLM_types

#===============================================================================
# ConfigError object
#===============================================================================
class ConfigError(Exception):
    """Raised when application configuration is invalid.
    
    Args:
        Exception (Exception): The configuration exception
    
    Returns:
        None
    
    Raises:
         None
    """    

    pass

#===============================================================================
# # Application configuration object
#===============================================================================
@dataclass
class AppConfig:
    ''' This is a doc string '''
    chroma_db: str
    chroma_db_path: str
    default_llm: LLM_types

    def validate(self) -> None:
        ''' Doc string '''
        
        # ---- CHROMA DB NAME ----
        if not isinstance(self.chroma_db, str) or not self.chroma_db.strip():
            raise ConfigError("CHROMA_DB must be a non-empty string")

        invalid_chars = r'<>:"/\\|?*'
        if any(c in self.chroma_db for c in invalid_chars):
            raise ConfigError(
                f"CHROMA_DB contains invalid filesystem characters: {invalid_chars}"
            )

        # ---- CHROMA DB PATH ----
        if not isinstance(self.chroma_db_path, str) or not self.chroma_db_path.strip():
            raise ConfigError("CHROMA_DB_PATH must be a non-empty string")

        path = Path(self.chroma_db_path).expanduser()

        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ConfigError(f"Cannot create/access CHROMA_DB_PATH: {path}") from e

        if not path.is_dir():
            raise ConfigError(f"CHROMA_DB_PATH is not a directory: {path}")

        self.chroma_db_path = str(path)

        # ---- DEFAULT LLM ----
        if not isinstance(self.default_llm, LLM_types):
            raise ConfigError("DEFAULT_LLM must be a valid LLM_types enum value")

    def update(
        self,
        *,
        chroma_db: str,
        chroma_db_path: str,
        default_llm: LLM_types,
    ) -> None:
        
        self.chroma_db = chroma_db
        self.chroma_db_path = chroma_db_path
        self.default_llm = default_llm
        self.validate()
        
        
# --------------------
# Persistence
# --------------------

#===============================================================================
# load_config
#===============================================================================
def load_config() -> AppConfig:
    ''' Doc string '''
    config_path = Path(CONFIG_FILE_PATH) / CONFIG_FILE_NAME

    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ConfigError("Configuration file is not valid YAML") from e
    except OSError as e:
        raise ConfigError(f"Unable to read config file: {config_path}") from e

    try:
        config = AppConfig(
            chroma_db=raw["CHROMA_DB"],
            chroma_db_path=raw["CHROMA_DB_PATH"],
            default_llm=LLM_types(raw["DEFAULT_LLM"]),
        )
    except KeyError as e:
        raise ConfigError(f"Missing required config key: {e.args[0]}") from e

    config.validate()
    return config


#===============================================================================
# save_config
#===============================================================================
def save_config(config: AppConfig) -> None:
    config_path = Path(CONFIG_FILE_PATH) / CONFIG_FILE_NAME
    config_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                {
                    "CHROMA_DB": config.chroma_db,
                    "CHROMA_DB_PATH": config.chroma_db_path,
                    "DEFAULT_LLM": config.default_llm.value,
                },
                f,
            )
    except OSError as e:
        raise ConfigError("Failed to save configuration file") from e


# --------------------
# Secrets
# --------------------

SERVICE_NAME = "AskMeApp"
KEY_NAME = "google_api_key"


#===============================================================================
# get_google_api_key
#===============================================================================
def get_google_api_key() -> str | None:
    try:
        key = keyring.get_password(SERVICE_NAME, KEY_NAME)
    except Exception:
        key = None

    return key or os.environ.get("GOOGLE_API_KEY")


#===============================================================================
# set_google_api_key
#===============================================================================
def set_google_api_key(value: str) -> None:
    try:
        keyring.set_password(SERVICE_NAME, KEY_NAME, value)
    except Exception as e:
        raise ConfigError("Failed to store Google API key in keyring") from e

