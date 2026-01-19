"""
chiaki-python: Python scripting interface for PlayStation Remote Play

This package provides a Python API for controlling PS4/PS5 via Chiaki.
"""

from .session import PS4Session, PS5Session
from .controller import Controller
from .discovery import discover_consoles, get_console_status

__version__ = "0.1.0"
__all__ = ["PS4Session", "PS5Session", "Controller", "discover_consoles", "get_console_status"]
