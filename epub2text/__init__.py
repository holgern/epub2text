"""
epub2text - Extract text from EPUB files with smart cleaning.

A niche CLI tool for extracting and processing text from EPUB files.
Supports selective chapter extraction, smart text cleaning, and
both CLI and library usage.
"""

import tempfile
import urllib.request
from pathlib import Path
from typing import Union
from .parser import EPUBParser
from .models import Chapter, Metadata, Page, PageSource
from .cleaner import clean_text, TextCleaner
from .bookmarks import Bookmark, BookmarkManager
from .reader import EpubReader, ReaderState

__all__ = [
    "EPUBParser",
    "Chapter",
    "Metadata",
    "Page",
    "PageSource",
    "clean_text",
    "TextCleaner",
    "epub2txt",
    "Bookmark",
    "BookmarkManager",
    "EpubReader",
    "ReaderState",
]

try:
    from ._version import version as __version__
except ImportError:
    __version__ = "0.0.0+unknown"


def epub2txt(
    filepath: str,
    outputlist: bool = False,
    clean: bool = True,
) -> Union[str, list[str]]:
    """
    Extract text from EPUB file (compatibility function for old epub2txt API).

    Args:
        filepath: Path to EPUB file or URL
        outputlist: If True, return list of chapter texts; if False,
            return single string
        clean: If True, apply text cleaning; if False, minimal processing

    Returns:
        Either a single string of all text (outputlist=False) or list of
        chapter texts (outputlist=True)

    Examples:
        >>> text = epub2txt("book.epub")
        >>> chapters = epub2txt("book.epub", outputlist=True)
        >>> raw_text = epub2txt("book.epub", clean=False)
        >>> text = epub2txt("https://example.com/book.epub")
    """
    # Check if filepath is a URL
    is_url = filepath.startswith("http://") or filepath.startswith("https://")

    tmp_path: str | None = None
    if is_url:
        # Download to temporary file
        try:
            with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
                tmp_path = tmp.name
            urllib.request.urlretrieve(filepath, tmp_path)
            actual_path = tmp_path
        except Exception:
            # Clean up temporary file on download failure
            if tmp_path and Path(tmp_path).exists():
                Path(tmp_path).unlink(missing_ok=True)
            raise
    else:
        actual_path = filepath

    try:
        # Use compact format (single newlines) to match old epub2txt behavior
        parser = EPUBParser(actual_path, paragraph_separator="\n")

        # Get all chapters
        chapters = parser.get_chapters()

        if outputlist:
            # Return list of chapter texts
            result = []
            for chapter in chapters:
                text = parser.extract_chapters([chapter.id])
                if clean:
                    cleaner = TextCleaner(preserve_single_newlines=True)
                    text = cleaner.clean(text)
                result.append(text)
            return result
        else:
            # Return single concatenated string
            text = parser.extract_chapters()
            if clean:
                cleaner = TextCleaner(preserve_single_newlines=True)
                text = cleaner.clean(text)
            return text
    finally:
        # Clean up temporary file if we downloaded one
        if is_url and tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
