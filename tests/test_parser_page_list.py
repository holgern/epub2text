"""Tests for page-list NAV detection."""

import ebooklib  # type: ignore[import-untyped]

from epub2text.parser import EPUBParser


class StubItem:
    """Minimal stub for ebooklib items."""

    def __init__(self, name: str, content: bytes) -> None:
        self._name = name
        self._content = content

    def get_name(self) -> str:
        return self._name

    def get_content(self) -> bytes:
        return self._content


class StubBook:
    """Minimal stub for ebooklib book."""

    def __init__(self, nav_items: list[StubItem], doc_items: list[StubItem]) -> None:
        self._nav_items = nav_items
        self._doc_items = doc_items

    def get_items_of_type(self, item_type: int) -> list[StubItem]:
        if item_type == ebooklib.ITEM_NAVIGATION:
            return self._nav_items
        if item_type == ebooklib.ITEM_DOCUMENT:
            return self._doc_items
        return []


def _make_parser_with_nav(nav_content: str) -> EPUBParser:
    parser = EPUBParser.__new__(EPUBParser)
    parser.book = StubBook(
        nav_items=[StubItem("nav.xhtml", nav_content.encode("utf-8"))],
        doc_items=[],
    )
    parser._page_list_nav = None
    parser._page_list_nav_checked = False
    return parser


def _make_parser_with_ncx(ncx_content: str) -> EPUBParser:
    parser = EPUBParser.__new__(EPUBParser)
    parser.book = StubBook(
        nav_items=[StubItem("toc.ncx", ncx_content.encode("utf-8"))],
        doc_items=[],
    )
    parser._page_list_nav = None
    parser._page_list_nav_checked = False
    return parser


def test_page_list_nav_single_quotes() -> None:
    """Detect page-list with single quotes."""
    nav_content = """
    <html><body>
      <nav epub:type='page-list'>
        <ol><li><a href='chap.xhtml#p1'>1</a></li></ol>
      </nav>
    </body></html>
    """
    parser = _make_parser_with_nav(nav_content)
    result = parser._find_page_list_nav()

    assert result is not None
    _, nav_type = result
    assert nav_type == "html"


def test_page_list_nav_whitespace_variation() -> None:
    """Detect page-list with whitespace around attributes."""
    nav_content = """
    <html><body>
      <nav epub:type = "page-list">
        <ol><li><a href="chap.xhtml#p1">1</a></li></ol>
      </nav>
    </body></html>
    """
    parser = _make_parser_with_nav(nav_content)
    result = parser._find_page_list_nav()

    assert result is not None
    _, nav_type = result
    assert nav_type == "html"


def test_page_list_ncx_parsing() -> None:
    """Detect page-list in NCX format."""
    ncx_content = """
    <ncx xmlns="http://www.daisy.org/z3986/2005/ncx/">
      <pageList>
        <pageTarget id="p1">
          <navLabel><text>i</text></navLabel>
          <content src="chap.xhtml#p1" />
        </pageTarget>
      </pageList>
    </ncx>
    """
    parser = _make_parser_with_ncx(ncx_content)
    result = parser._find_page_list_nav()

    assert result is not None
    page_list, nav_type = result
    assert nav_type == "ncx"
    assert page_list.tag.endswith("pageList")
