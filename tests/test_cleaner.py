"""Tests for TextCleaner option interactions."""

import pytest

from epub2text.cleaner import TextCleaner


@pytest.mark.parametrize(
    ("remove_page_numbers", "remove_footnotes", "expect_footnote", "expect_page"),
    [
        (True, False, True, False),
        (False, True, False, True),
        (True, True, False, False),
        (False, False, True, True),
    ],
)
def test_cleaner_footnote_page_number_matrix(
    remove_page_numbers: bool,
    remove_footnotes: bool,
    expect_footnote: bool,
    expect_page: bool,
) -> None:
    """Ensure footnotes and page numbers are controlled independently."""
    cleaner = TextCleaner(
        remove_page_numbers=remove_page_numbers,
        remove_footnotes=remove_footnotes,
    )
    text = "Hello[1] world\n\n42\n"
    result = cleaner.clean(text)

    assert ("[1]" in result) is expect_footnote
    assert ("42" in result) is expect_page


@pytest.mark.parametrize("normalize_whitespace", [True, False])
def test_cleaner_normalize_whitespace_toggle(normalize_whitespace: bool) -> None:
    """Check whitespace normalization can be toggled."""
    cleaner = TextCleaner(
        normalize_whitespace=normalize_whitespace,
        preserve_single_newlines=True,
    )
    text = "Text   with    extra   spaces."
    result = cleaner.clean(text)

    if normalize_whitespace:
        assert "  " not in result
    else:
        assert "  " in result


@pytest.mark.parametrize("preserve_single_newlines", [True, False])
def test_cleaner_preserve_single_newlines_toggle(
    preserve_single_newlines: bool,
) -> None:
    """Check preserve_single_newlines overrides single newline replacement."""
    cleaner = TextCleaner(
        preserve_single_newlines=preserve_single_newlines,
        replace_single_newlines=True,
    )
    text = "Line one.\nLine two.\n\nLine three."
    result = cleaner.clean(text)

    if preserve_single_newlines:
        assert "Line one.\nLine two." in result
        assert "\n\n" in result
    else:
        assert "Line one. Line two." in result
        assert "\n\n" in result
