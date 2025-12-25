"""
epub2text - Extract text from EPUB files with smart cleaning.

A niche CLI tool for extracting and processing text from EPUB files.
Supports selective chapter extraction, smart text cleaning, and
both CLI and library usage.
"""

from .parser import EPUBParser
from .models import Chapter, Metadata
from .cleaner import clean_text, TextCleaner

__all__ = [
    "EPUBParser",
    "Chapter",
    "Metadata",
    "clean_text",
    "TextCleaner",
]

try:
    from ._version import version as __version__
except ImportError:
    __version__ = "0.0.0+unknown"
