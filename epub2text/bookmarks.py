"""Bookmark management for epub2text reader."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass
class Bookmark:
    """Represents a reading position bookmark."""

    chapter_index: int
    line_offset: int
    percentage: float
    last_read: str
    title: str

    @classmethod
    def create(
        cls,
        chapter_index: int,
        line_offset: int,
        percentage: float,
        title: str,
    ) -> "Bookmark":
        """Create a new bookmark with current timestamp."""
        return cls(
            chapter_index=chapter_index,
            line_offset=line_offset,
            percentage=percentage,
            last_read=datetime.now(timezone.utc).isoformat(),
            title=title,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Bookmark":
        """Create a Bookmark from a dictionary."""
        return cls(
            chapter_index=int(data.get("chapter_index", 0)),
            line_offset=int(data.get("line_offset", 0)),
            percentage=float(data.get("percentage", 0.0)),
            last_read=str(data.get("last_read", "")),
            title=str(data.get("title", "")),
        )


class BookmarkManager:
    """Manages bookmarks for EPUB files."""

    def __init__(self, bookmark_file: Optional[Path] = None) -> None:
        """
        Initialize bookmark manager.

        Args:
            bookmark_file: Path to bookmark JSON file.
                          Defaults to ~/.epub2text/bookmarks.json
        """
        if bookmark_file is None:
            self.bookmark_file = Path.home() / ".epub2text" / "bookmarks.json"
        else:
            self.bookmark_file = bookmark_file
        self._bookmarks: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Load bookmarks from file."""
        if self.bookmark_file.exists():
            try:
                with open(self.bookmark_file, encoding="utf-8") as f:
                    data = json.load(f)
                    self._bookmarks = data.get("bookmarks", {})
            except (json.JSONDecodeError, OSError):
                self._bookmarks = {}
        else:
            self._bookmarks = {}

    def _save(self) -> None:
        """Save bookmarks to file."""
        # Ensure directory exists
        self.bookmark_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.bookmark_file, "w", encoding="utf-8") as f:
            json.dump({"bookmarks": self._bookmarks}, f, indent=2, ensure_ascii=False)

    def _normalize_path(self, epub_path: str) -> str:
        """Normalize path for consistent storage."""
        return str(Path(epub_path).resolve())

    def save(self, epub_path: str, bookmark: Bookmark) -> None:
        """
        Save bookmark for a specific EPUB file.

        Args:
            epub_path: Path to the EPUB file
            bookmark: Bookmark data to save
        """
        key = self._normalize_path(epub_path)
        self._bookmarks[key] = asdict(bookmark)
        self._save()

    def load(self, epub_path: str) -> Optional[Bookmark]:
        """
        Load bookmark for a specific EPUB file.

        Args:
            epub_path: Path to the EPUB file

        Returns:
            Bookmark if found, None otherwise
        """
        key = self._normalize_path(epub_path)
        data = self._bookmarks.get(key)
        if data is None:
            return None
        return Bookmark.from_dict(data)

    def delete(self, epub_path: str) -> bool:
        """
        Delete bookmark for a specific EPUB file.

        Args:
            epub_path: Path to the EPUB file

        Returns:
            True if bookmark was deleted, False if not found
        """
        key = self._normalize_path(epub_path)
        if key in self._bookmarks:
            del self._bookmarks[key]
            self._save()
            return True
        return False

    def list_all(self) -> dict[str, Bookmark]:
        """
        List all bookmarks.

        Returns:
            Dictionary mapping file paths to bookmarks
        """
        return {
            path: Bookmark.from_dict(data) for path, data in self._bookmarks.items()
        }
