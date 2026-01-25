"""Tests for reader bookmark loading behavior."""

import json
from pathlib import Path

from epub2text.bookmarks import Bookmark, BookmarkManager
from epub2text.models import Chapter
from epub2text.reader import EpubReader


def test_load_bookmark_with_empty_content(tmp_path: Path) -> None:
    """Ensure loading a bookmark with empty content does not crash."""
    bookmark_file = tmp_path / "bookmarks.json"
    bookmark_manager = BookmarkManager(bookmark_file)
    epub_path = tmp_path / "empty.epub"

    bookmark = Bookmark.create(
        chapter_index=0,
        line_offset=10,
        percentage=50.0,
        title="Empty Book",
    )
    bookmark_manager.save(str(epub_path), bookmark)

    reader = EpubReader(
        content="",
        chapters=[Chapter(id="1", title="Empty", text="", char_count=0)],
        title="Empty Book",
        epub_path=str(epub_path),
        bookmark_manager=bookmark_manager,
    )

    reader._load_bookmark()

    assert reader.current_line == 0
    assert reader._message is not None
    assert "content is empty" in reader._message.lower()


def test_bookmark_path_normalization(tmp_path: Path) -> None:
    """Ensure bookmarks are stored with normalized paths."""
    bookmark_file = tmp_path / "bookmarks.json"
    bookmark_manager = BookmarkManager(bookmark_file)
    book_path = tmp_path / "book.epub"
    alt_path = tmp_path / "subdir" / ".." / "book.epub"
    alt_path.parent.mkdir(parents=True, exist_ok=True)

    bookmark = Bookmark.create(
        chapter_index=1,
        line_offset=5,
        percentage=10.0,
        title="Test Book",
    )
    bookmark_manager.save(str(alt_path), bookmark)

    loaded = bookmark_manager.load(str(book_path))
    assert loaded is not None
    assert loaded.chapter_index == 1


def test_bookmark_multiple_books_and_delete(tmp_path: Path) -> None:
    """Ensure bookmarks handle multiple books and deletions."""
    bookmark_file = tmp_path / "bookmarks.json"
    bookmark_manager = BookmarkManager(bookmark_file)
    book_path_one = tmp_path / "first.epub"
    book_path_two = tmp_path / "second.epub"

    bookmark_one = Bookmark.create(0, 0, 1.0, "First")
    bookmark_two = Bookmark.create(2, 20, 33.3, "Second")

    bookmark_manager.save(str(book_path_one), bookmark_one)
    bookmark_manager.save(str(book_path_two), bookmark_two)

    all_bookmarks = bookmark_manager.list_all()
    assert len(all_bookmarks) == 2

    assert bookmark_manager.delete(str(book_path_one)) is True
    assert bookmark_manager.load(str(book_path_one)) is None
    assert bookmark_manager.load(str(book_path_two)) is not None


def test_bookmark_recovery_from_corrupt_file(tmp_path: Path) -> None:
    """Recover bookmarks from backup when JSON is corrupted."""
    bookmark_file = tmp_path / "bookmarks.json"
    backup_file = tmp_path / "bookmarks.json.bak"
    bookmark_manager = BookmarkManager(bookmark_file)
    book_path = tmp_path / "corrupt.epub"

    bookmark = Bookmark.create(1, 15, 25.0, "Corrupt Test")
    bookmark_manager.save(str(book_path), bookmark)

    backup_file.write_text(bookmark_file.read_text(encoding="utf-8"), encoding="utf-8")
    bookmark_file.write_text("{not json", encoding="utf-8")

    recovered_manager = BookmarkManager(bookmark_file)
    recovered = recovered_manager.load(str(book_path))
    assert recovered is not None
    assert recovered.title == "Corrupt Test"


def test_bookmark_save_creates_backup(tmp_path: Path) -> None:
    """Ensure save writes valid JSON and keeps backups."""
    bookmark_file = tmp_path / "bookmarks.json"
    bookmark_manager = BookmarkManager(bookmark_file)
    book_path = tmp_path / "book.epub"

    first = Bookmark.create(0, 0, 1.0, "First")
    second = Bookmark.create(1, 10, 5.0, "Second")

    bookmark_manager.save(str(book_path), first)
    bookmark_manager.save(str(book_path), second)

    backup_path = tmp_path / "bookmarks.json.bak"
    assert backup_path.exists()

    backup_payload = json.loads(backup_path.read_text(encoding="utf-8"))
    assert "bookmarks" in backup_payload
    assert backup_payload["bookmarks"]
    first_entry = next(iter(backup_payload["bookmarks"].values()))
    assert first_entry.get("title") == "First"
