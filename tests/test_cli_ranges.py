"""Tests for CLI range parsing helpers."""

from epub2text.cli import parse_chapter_range, parse_page_range
from epub2text.models import Page, PageSource


def test_parse_page_range_is_deterministic() -> None:
    """Ensure page range parsing preserves order and de-duplicates."""
    pages = [
        Page(page_number=str(i), text="", char_count=0, source=PageSource.SYNTHETIC)
        for i in range(1, 6)
    ]

    expected = ["3", "1", "2"]
    assert parse_page_range("3,1-2,2", pages) == expected
    assert parse_page_range("3,1-2,2", pages) == expected


def test_parse_chapter_range_preserves_order() -> None:
    """Ensure chapter range parsing preserves input order."""
    assert parse_chapter_range("3,1-2,2") == [2, 0, 1]


def test_parse_page_range_accepts_literal_page_numbers() -> None:
    """Ensure literal page numbers are preserved in order."""
    pages = [
        Page(page_number="i", text="", char_count=0, source=PageSource.SYNTHETIC),
        Page(page_number="ii", text="", char_count=0, source=PageSource.SYNTHETIC),
        Page(page_number="1", text="", char_count=0, source=PageSource.SYNTHETIC),
    ]

    assert parse_page_range("ii,1", pages) == ["ii", "i"]
    assert parse_page_range("i-ii", pages) == ["i", "ii"]
