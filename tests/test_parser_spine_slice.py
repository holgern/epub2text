"""Tests for spine HTML slicing helper."""

from epub2text.parser import EPUBParser


def _make_parser_with_docs() -> EPUBParser:
    parser = EPUBParser.__new__(EPUBParser)
    parser.doc_content = {
        "doc1.xhtml": "AAA111BBB",
        "doc2.xhtml": "CCC222DDD",
        "doc3.xhtml": "EEE333FFF",
    }
    return parser


def test_slice_spine_same_document() -> None:
    """Slice within a single document."""
    parser = _make_parser_with_docs()
    spine_docs = ["doc1.xhtml", "doc2.xhtml", "doc3.xhtml"]

    result = parser._slice_spine_html(
        "doc1.xhtml",
        3,
        "doc1.xhtml",
        6,
        spine_docs,
        allow_wraparound=False,
    )

    assert result == "111"


def test_slice_spine_across_documents() -> None:
    """Slice across multiple spine documents."""
    parser = _make_parser_with_docs()
    spine_docs = ["doc1.xhtml", "doc2.xhtml", "doc3.xhtml"]

    result = parser._slice_spine_html(
        "doc1.xhtml",
        6,
        "doc3.xhtml",
        3,
        spine_docs,
        allow_wraparound=False,
    )

    assert result == "BBBCCC222DDDEEE"


def test_slice_spine_last_page_includes_remaining_docs() -> None:
    """Last slice should include remaining spine documents."""
    parser = _make_parser_with_docs()
    spine_docs = ["doc1.xhtml", "doc2.xhtml", "doc3.xhtml"]

    result = parser._slice_spine_html(
        "doc2.xhtml",
        3,
        None,
        None,
        spine_docs,
        allow_wraparound=False,
    )

    assert result == "222DDDEEE333FFF"
