"""
Created on Feb 6, 2026
@author: keith.chambers

Centralized logging configuration for AskMeApp.
"""

from __future__ import annotations

import logging
from typing import Iterable

APP_NAMESPACE = "AskMeApp"

NOISY_LIBRARIES: tuple[str, ...] = (
    "kivy",
    "kivy.uix",
    "kivy.core",
    "google",
    "google_genai",
    "google.ai",
    "google.generativeai",
    "httpx",
    "httpcore",
    "grpc",
    "keyring",
)

LOG_FORMAT = "[%(levelname)-7s] [%(name)-22s] %(message)s"

LIB_LOG_LEVEL = logging.WARNING
APP_LOG_LEVEL = logging.INFO


# -----------------------------------------------------------------------------
# Phase 1: Base logging setup (call BEFORE importing frameworks)
# -----------------------------------------------------------------------------
#===============================================================================
# base logging setup
#===============================================================================
def configure_base_logging(
    *,
    level: int = LIB_LOG_LEVEL,
    fmt: str = LOG_FORMAT,
) -> None:
    """ 
    Args:
        level:
        fmt:
    """

    root = logging.getLogger()
    formatter = logging.Formatter(fmt)

    stream_handler_found = False

    for h in root.handlers:
        if isinstance(h, logging.StreamHandler):
            h.setFormatter(formatter)
            stream_handler_found = True

    if not stream_handler_found:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root.addHandler(handler)

    root.setLevel(level)    
    
# -----------------------------------------------------------------------------
# Post-import enforcement (call AFTER Kivy is running)
# -----------------------------------------------------------------------------

def enforce_library_levels(
    *,
    app_level: int = APP_LOG_LEVEL,
    library_level: int = LIB_LOG_LEVEL,
    libraries: Iterable[str] = NOISY_LIBRARIES,
) -> None:
    
    for name in libraries:
        logging.getLogger(name).setLevel(library_level)

    logging.getLogger(APP_NAMESPACE).setLevel(app_level)
    
