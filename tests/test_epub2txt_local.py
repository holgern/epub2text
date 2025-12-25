"""Test local file."""

from epub2text import epub2txt


def test_epub2txt_local():
    """Test epub2txt with local file."""
    filepath = "tests/test.epub"

    res = epub2txt(filepath)
    assert len(res) > 200

    res = epub2txt(filepath, clean=False)
    assert len(res) > 500

    res = epub2txt(filepath, outputlist=True)
    # Our parser finds 5 chapters (more thorough than old epub2txt which found 4)
    assert len(res) == 5

    res = epub2txt(filepath, outputlist=True, clean=False)
    assert len(res) == 5
