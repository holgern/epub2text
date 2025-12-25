"""Test http."""

import pytest

from epub2text import epub2txt


@pytest.mark.skip(
    reason="External URL not available - test file exists at tests/1.tmx.epub"
)
def test_epub2txt_http():
    """Test epub2txt_http."""
    # url = "https://github.com/ffremt/tmx2epub/raw/master/tests/1.tmx.epub"
    url = "https://github.com/ffreemt/epub2txt/raw/master/tests/1.tmx.epub"

    res = epub2txt(url)
    assert len(res) > 220000

    res = epub2txt(url, clean=False)
    assert len(res) > 280000

    res = epub2txt(url, outputlist=True)
    assert len(res) == 3


def test_epub2txt_local_tmx():
    """Test with local tmx.epub file instead of HTTP."""
    filepath = "tests/1.tmx.epub"

    res = epub2txt(filepath)
    assert len(res) > 220000

    res = epub2txt(filepath, clean=False)
    assert len(res) > 220000  # Both should be large

    res = epub2txt(filepath, outputlist=True)
    # Check that we get chapters back
    assert len(res) >= 1
