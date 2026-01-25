"""Bookmark management for epub2text reader."""

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


logger = logging.getLogger(__name__)


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
        self._bookmarks = {}
        if not self.bookmark_file.exists():
            return

        data = self._read_bookmarks_file(self.bookmark_file)
        if data is not None:
            self._bookmarks = data.get("bookmarks", {})
            return

        backup_path = self._backup_path()
        if backup_path.exists():
            backup_data = self._read_bookmarks_file(backup_path)
            if backup_data is not None:
                self._bookmarks = backup_data.get("bookmarks", {})
                logger.warning("Recovered bookmarks from backup: %s", backup_path)

    def _save(self) -> None:
        """Save bookmarks to file."""
        # Ensure directory exists
        self.bookmark_file.parent.mkdir(parents=True, exist_ok=True)

        data = {"bookmarks": self._bookmarks}
        backup_path = self._backup_path()
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.bookmark_file.parent,
                suffix=".tmp",
                delete=False,
            ) as tmp:
                tmp_path = Path(tmp.name)
                json.dump(data, tmp, indent=2, ensure_ascii=False)
                tmp.flush()
                os.fsync(tmp.fileno())

            if self.bookmark_file.exists():
                self.bookmark_file.replace(backup_path)
            tmp_path.replace(self.bookmark_file)
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    def _backup_path(self) -> Path:
        """Return the path for the bookmark backup file."""
        return self.bookmark_file.with_suffix(self.bookmark_file.suffix + ".bak")

    def _read_bookmarks_file(self, path: Path) -> Optional[dict[str, Any]]:
        """Read bookmarks JSON from disk."""
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load bookmarks from %s: %s", path, exc)
            return None

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
