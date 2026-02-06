
from __future__ import annotations
import logging
import sys
from pythonjsonlogger.json import JsonFormatter
from typing import Optional

def setup_logging(level=logging.INFO, log_file: str | None = None):
    """
    Configures the root logger to output JSON logs to stderr and optionally to a file.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates/conflicts
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)
            
    # Console Handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(console_handler)
    
    # File Handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JsonFormatter())
        root_logger.addHandler(file_handler)

