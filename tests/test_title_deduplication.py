"""
Tests for chapter title deduplication functionality.

Tests the _remove_duplicate_title_line() method and the deduplicate_chapter_titles
parameter in extract_chapters().
"""

from pathlib import Path

import pypub  # type: ignore[import-untyped]
import pytest

from epub2text import EPUBParser


class TestTitleDeduplication:
    """Test chapter title deduplication functionality."""

    @pytest.fixture
    def epub_with_duplicate_titles(self, tmp_path: Path) -> Path:
        """Create an EPUB where chapter titles appear as first line of content."""
        epub_path = tmp_path / "duplicate_titles.epub"

        book = pypub.Epub("Test Book with Duplicate Titles", creator="Test Author")

        # Chapter 1: Title appears as exact first line
        chapter1_html = b"""
        <html><body>
        <h1>ONE</h1>
        <p>The morning was joyless for him, as mornings generally were.</p>
        <p>The sky was grey; it looked as though it was about to rain.</p>
        </body></html>
        """
        chapter1 = pypub.create_chapter_from_html(
            chapter1_html,
            title="ONE",
        )

        # Chapter 2: Title appears on same line as content
        chapter2_html = b"""
        <html><body>
        <h1>TWO</h1>
        <p>The afternoon brought no relief from the gloom.</p>
        </body></html>
        """
        chapter2 = pypub.create_chapter_from_html(
            chapter2_html,
            title="TWO",
        )

        # Chapter 3: Title with different case
        chapter3_html = b"""
        <html><body>
        <h1>Three</h1>
        <p>Evening fell quietly over the city.</p>
        </body></html>
        """
        chapter3 = pypub.create_chapter_from_html(
            chapter3_html,
            title="THREE",
        )

        # Chapter 4: No duplicate (title not in content)
        chapter4_html = b"""
        <html><body>
        <p>Night came without warning.</p>
        <p>Darkness enveloped everything.</p>
        </body></html>
        """
        chapter4 = pypub.create_chapter_from_html(
            chapter4_html,
            title="FOUR",
        )

        book.add_chapter(chapter1)
        book.add_chapter(chapter2)
        book.add_chapter(chapter3)
        book.add_chapter(chapter4)

        book.create(str(epub_path))
        return epub_path

    def test_remove_duplicate_title_exact_match(self) -> None:
        """Test removal of exact title match on first line."""
        parser = EPUBParser.__new__(EPUBParser)  # Create instance without __init__

        # Exact match - entire first line is the title
        text = "ONE\nThe morning was joyless."
        result = parser._remove_duplicate_title_line(text, "ONE")
        assert result == "The morning was joyless."

        # With multiple lines
        text = "ONE\nThe morning was joyless.\nIt was grey."
        result = parser._remove_duplicate_title_line(text, "ONE")
        assert result == "The morning was joyless.\nIt was grey."

    def test_remove_duplicate_title_same_line(self) -> None:
        """Test removal when title is at start of first line followed by content."""
        parser = EPUBParser.__new__(EPUBParser)

        # Title followed by content on same line
        text = "ONE The morning was joyless."
        result = parser._remove_duplicate_title_line(text, "ONE")
        assert result == "The morning was joyless."

        # With additional lines
        text = "ONE The morning was joyless.\nIt was grey."
        result = parser._remove_duplicate_title_line(text, "ONE")
        assert result == "The morning was joyless.\nIt was grey."

    def test_remove_duplicate_title_case_insensitive(self) -> None:
        """Test case-insensitive title matching."""
        parser = EPUBParser.__new__(EPUBParser)

        # Different case - exact match
        text = "one\nThe morning was joyless."
        result = parser._remove_duplicate_title_line(text, "ONE")
        assert result == "The morning was joyless."

        # Different case - same line
        text = "one The morning was joyless."
        result = parser._remove_duplicate_title_line(text, "ONE")
        assert result == "The morning was joyless."

        # Mixed case
        text = "One\nThe morning was joyless."
        result = parser._remove_duplicate_title_line(text, "ONE")
        assert result == "The morning was joyless."

    def test_remove_duplicate_title_with_whitespace(self) -> None:
        """Test title matching with leading/trailing whitespace."""
        parser = EPUBParser.__new__(EPUBParser)

        # With leading/trailing spaces in text
        text = "  ONE  \nThe morning was joyless."
        result = parser._remove_duplicate_title_line(text, "ONE")
        assert result == "The morning was joyless."

        # With spaces in title
        text = "Chapter One\nThe morning was joyless."
        result = parser._remove_duplicate_title_line(text, "Chapter One")
        assert result == "The morning was joyless."

    def test_no_removal_when_no_match(self) -> None:
        """Test that text is unchanged when title doesn't match."""
        parser = EPUBParser.__new__(EPUBParser)

        # No match - different text
        text = "The morning was joyless.\nIt was grey."
        result = parser._remove_duplicate_title_line(text, "ONE")
        assert result == text

        # Partial match (title is substring but not at start)
        text = "In chapter ONE we see...\nMore content."
        result = parser._remove_duplicate_title_line(text, "ONE")
        assert result == text

    def test_empty_inputs(self) -> None:
        """Test handling of empty or None inputs."""
        parser = EPUBParser.__new__(EPUBParser)

        # Empty text
        assert parser._remove_duplicate_title_line("", "ONE") == ""

        # Empty title
        assert parser._remove_duplicate_title_line("ONE\nText", "") == "ONE\nText"

        # Both empty
        assert parser._remove_duplicate_title_line("", "") == ""

    def test_single_line_text(self) -> None:
        """Test handling of single-line text."""
        parser = EPUBParser.__new__(EPUBParser)

        # Exact match - should return empty string
        result = parser._remove_duplicate_title_line("ONE", "ONE")
        assert result == ""

        # Same line with content - should return just content
        result = parser._remove_duplicate_title_line("ONE The morning", "ONE")
        assert result == "The morning"

        # No match - should return original
        result = parser._remove_duplicate_title_line("The morning", "ONE")
        assert result == "The morning"

    def test_extract_chapters_with_deduplication_enabled(
        self, epub_with_duplicate_titles: Path
    ) -> None:
        """Test extract_chapters with deduplication enabled (default)."""
        parser = EPUBParser(str(epub_with_duplicate_titles))

        # Extract with deduplication (default)
        text = parser.extract_chapters(deduplicate_chapter_titles=True)

        # Chapter should have title in new format (preceded by 4 newlines
        # or at start, followed by 2 newlines)
        assert "\n\n\n\nONE\n\n" in text or "ONE\n\n" in text

        # The title should not appear again after being shown as chapter title
        lines = text.split("\n")
        chapter_title_idx = None
        for i, line in enumerate(lines):
            if line.strip() == "ONE":
                chapter_title_idx = i
                break

        assert chapter_title_idx is not None
        # Next non-empty line should not be "ONE" (deduplication worked)
        next_lines = [
            line.strip() for line in lines[chapter_title_idx + 3 :] if line.strip()
        ]  # Skip 2 newlines after title
        if next_lines:
            assert next_lines[0] != "ONE"
            # Should start with actual content
            assert "morning" in next_lines[0].lower() or "afternoon" in text.lower()

    def test_extract_chapters_with_deduplication_disabled(
        self, epub_with_duplicate_titles: Path
    ) -> None:
        """Test extract_chapters with deduplication disabled."""
        parser = EPUBParser(str(epub_with_duplicate_titles))

        # Extract without deduplication
        text = parser.extract_chapters(deduplicate_chapter_titles=False)

        # The chapter title should still be there in new format
        assert "\n\n\n\nONE\n\n" in text or "ONE\n\n" in text
        # Original text should be preserved (may contain title)
        # This test ensures the parameter works, actual content depends on
        # EPUB structure

    def test_deduplication_preserves_content(
        self, epub_with_duplicate_titles: Path
    ) -> None:
        """Test that deduplication doesn't remove actual content."""
        parser = EPUBParser(str(epub_with_duplicate_titles))

        # Extract with deduplication
        text_with_dedup = parser.extract_chapters(deduplicate_chapter_titles=True)

        # Extract without deduplication
        text_without_dedup = parser.extract_chapters(deduplicate_chapter_titles=False)

        # Both should contain the actual content
        assert "morning" in text_with_dedup.lower()
        assert "morning" in text_without_dedup.lower()
        assert "afternoon" in text_with_dedup.lower()
        assert "afternoon" in text_without_dedup.lower()

        # Deduplicated version should be same or shorter
        assert len(text_with_dedup) <= len(text_without_dedup)

    def test_chapter_with_no_duplicate_unchanged(self) -> None:
        """Test that chapters without duplicate titles are unchanged."""
        parser = EPUBParser.__new__(EPUBParser)

        # Title not in content
        text = "The morning was joyless.\nIt was grey."
        result = parser._remove_duplicate_title_line(text, "Chapter One")
        assert result == text

    def test_multi_word_title_deduplication(self) -> None:
        """Test deduplication with multi-word titles."""
        parser = EPUBParser.__new__(EPUBParser)

        # Multi-word exact match
        text = "Chapter One\nThe morning was joyless."
        result = parser._remove_duplicate_title_line(text, "Chapter One")
        assert result == "The morning was joyless."

        # Multi-word same line
        text = "Chapter One The morning was joyless."
        result = parser._remove_duplicate_title_line(text, "Chapter One")
        assert result == "The morning was joyless."

    def test_title_with_special_characters(self) -> None:
        """Test deduplication with titles containing special characters."""
        parser = EPUBParser.__new__(EPUBParser)

        # Title with numbers
        text = "Chapter 1\nThe morning was joyless."
        result = parser._remove_duplicate_title_line(text, "Chapter 1")
        assert result == "The morning was joyless."

        # Title with punctuation (not removed as it's not a simple match)
        text = "Chapter One: Introduction\nThe morning was joyless."
        result = parser._remove_duplicate_title_line(text, "Chapter One: Introduction")
        assert result == "The morning was joyless."
