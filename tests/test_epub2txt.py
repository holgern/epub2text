"""Test version."""

from epub2text import __version__


def test_version():
    """Test that version is defined and starts with expected format."""
    assert __version__
    # Version should be in format like "0.1.0" or "0.1.0+unknown" or "0.0.0+unknown"
    assert len(__version__) >= 5
