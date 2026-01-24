"""Tests for reader bookmark loading behavior."""

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
