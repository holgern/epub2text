import json

import pytest
from click.testing import CliRunner
from ebooklib import epub

from epub2text import EPUBParser, extract_epub_structure
from epub2text.blocks import extract_blocks
from epub2text.cli import cli
from epub2text.structured import NavigationEntry
from epub2text.toc_map import annotate_blocks_with_navigation


def make_epub(path):
    book = epub.EpubBook()
    book.set_identifier("id")
    book.set_title("Structured Test")
    book.set_language("en")
    chapter = epub.EpubHtml(title="Chapter", file_name="chap.xhtml", lang="en")
    chapter.content = """<html><body><h1 id="c1">Chapter</h1><p>Hello <em>world</em> &amp; A&nbsp;B<sup>1</sup></p><ol start="4"><li>Alpha</li><li>Beta</li></ol></body></html>"""  # noqa: E501
    book.add_item(chapter)
    book.add_item(epub.EpubNav())
    book.add_item(epub.EpubNcx())
    book.toc = (epub.Link("chap.xhtml#c1", "Chapter", "c1"),)
    book.spine = ["nav", chapter]
    epub.write_epub(str(path), book)


def make_epub_with_body(path, body):
    book = epub.EpubBook()
    book.set_identifier("id")
    book.set_title("Structured Test")
    book.set_language("en")
    chapter = epub.EpubHtml(title="Chapter", file_name="chap.xhtml", lang="en")
    chapter.content = f"<html><body>{body}</body></html>"
    book.add_item(chapter)
    book.add_item(epub.EpubNav())
    book.add_item(epub.EpubNcx())
    book.spine = ["nav", chapter]
    epub.write_epub(str(path), book)


def test_structured_extraction_blocks_runs_entities_and_json(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub(epub_path)

    parser = EPUBParser(str(epub_path))
    extraction = parser.extract_structured(include_segments=True)

    assert parser.inspect_package().nav_href == "nav.xhtml"
    assert [doc.href for doc in extraction.documents] == ["chap.xhtml"]
    texts = [block.text for block in extraction.blocks]
    assert "Hello world & A\xa0B1" in texts
    assert "Alpha" in texts
    assert "Beta" in texts
    assert all("__TAG_" not in text and "__SPANTX_" not in text for text in texts)

    paragraph = next(block for block in extraction.blocks if block.tag_name == "p")
    assert (
        "<p"
        in extraction.documents[0].text[
            paragraph.outer_char_start : paragraph.outer_char_end
        ]
    )
    assert "<em>" in [getattr(run, "raw", None) for run in paragraph.runs]
    assert any(
        getattr(run, "raw", None) == "&amp;" and run.text == "&"
        for run in paragraph.runs
    )
    assert "\xa0" in paragraph.text
    assert "".join(getattr(run, "text", "") for run in paragraph.runs) == paragraph.text

    for segment in extraction.segments:
        block = next(
            block for block in extraction.blocks if block.id == segment.block_id
        )
        assert (
            block.text[segment.block_text_start : segment.block_text_end]
            == segment.text
        )

    payload = extraction.to_json(include_raw=False, indent=2)
    assert payload == parser.extract_structured(include_segments=True).to_json(
        include_raw=False, indent=2
    )
    decoded = json.loads(payload)
    assert decoded["schema"] == "epub2text.structured.v1"
    assert "text" not in decoded["documents"][0]


def test_extract_epub_structure_convenience(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub(epub_path)
    extraction = extract_epub_structure(str(epub_path), include_segments=True)
    assert extraction.blocks
    assert extraction.segments


def test_extract_epub_structure_supports_markdown_fragments(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(epub_path, "<p><s>old</s> new</p>")
    extraction = extract_epub_structure(
        str(epub_path),
        include_markdown_fragments=True,
        markdown_flavor="gfm",
    )
    block = next(block for block in extraction.blocks if block.tag_name == "p")
    assert block.markdown_fragment.markdown == "~~old~~ new"
    assert block.xhtml_fragment is None


def visible_text(xhtml):
    from html.parser import HTMLParser

    class Parser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts = []

        def handle_data(self, data):
            self.parts.append(data)

    parser = Parser()
    parser.feed(xhtml)
    return "".join(parser.parts)


def test_xhtml_block_fragment_preserves_inline_emphasis(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(epub_path, "<p>A <em>small</em> test.</p>")
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_xhtml_fragments=True
    )
    block = next(block for block in extraction.blocks if block.tag_name == "p")
    assert block.text == "A small test."
    assert block.xhtml_fragment.xhtml == "A <em>small</em> test."
    assert block.xhtml_fragment.text == block.text


def test_xhtml_segment_fragment_includes_wrapping_emphasis(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(
        epub_path,
        "<p>Plain. <em>Running down again – always at the worst "
        "possible moment!</em></p>",
    )
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_segments=True, include_xhtml_fragments=True
    )
    segment = next(
        segment
        for segment in extraction.segments
        if segment.text.strip().startswith("Running")
    )
    assert segment.text == "Running down again – always at the worst possible moment!"
    assert (
        segment.xhtml_fragment.xhtml
        == "<em>Running down again – always at the worst possible moment!</em>"
    )


def test_xhtml_nested_inline_tags_remain_balanced(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(
        epub_path, '<p>A <span class="ship"><em>Esca Volenti</em></span> shuddered.</p>'
    )
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_xhtml_fragments=True
    )
    block = next(block for block in extraction.blocks if block.tag_name == "p")
    assert (
        block.xhtml_fragment.xhtml
        == 'A <span class="ship"><em>Esca Volenti</em></span> shuddered.'
    )


def test_xhtml_entities_preserve_visible_text_equivalence(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(epub_path, "<p>A&nbsp;B &amp; C</p>")
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_xhtml_fragments=True
    )
    fragment = next(
        block.xhtml_fragment for block in extraction.blocks if block.tag_name == "p"
    )
    assert fragment.text == "A\xa0B & C"
    assert visible_text(fragment.xhtml) == fragment.text


def test_xhtml_disallowed_attributes_produce_diagnostics(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(
        epub_path, '<p><span onclick="evil()" class="ok">text</span></p>'
    )
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_xhtml_fragments=True
    )
    block = next(block for block in extraction.blocks if block.tag_name == "p")
    assert "onclick" not in block.xhtml_fragment.xhtml
    assert 'class="ok"' in block.xhtml_fragment.xhtml
    assert any(
        d.code == "xhtml_fragment_disallowed_attr" for d in extraction.diagnostics
    )


def test_xhtml_default_json_omits_fragments(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(epub_path, "<p>A <em>small</em> test.</p>")
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_segments=True, include_xhtml_fragments=True
    )
    assert "xhtml_fragment" not in extraction.to_json(
        include_runs=True, include_segments=True
    )


def test_xhtml_fragments_serialize_without_runs(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(epub_path, "<p>A <em>small</em> test.</p>")
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_xhtml_fragments=True
    )
    decoded = json.loads(
        extraction.to_json(include_runs=False, include_xhtml_fragments=True)
    )
    assert "runs" not in decoded["blocks"][0]
    assert decoded["blocks"][0]["xhtml_fragment"]["xhtml"] == "A <em>small</em> test."


def test_xhtml_segment_starts_before_inline_and_ends_inside(tmp_path):
    epub_path = tmp_path / "book.epub"
    # phrasplit needs a second terminated sentence; the original unpunctuated
    # "end" is grouped with the first sentence and no longer splits.
    make_epub_with_body(epub_path, "<p>Start <em>middle. The end.</em></p>")
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_segments=True, include_xhtml_fragments=True
    )
    segment = extraction.segments[0]
    assert segment.text == "Start middle."
    assert segment.xhtml_fragment.xhtml == "Start <em>middle.</em>"


def test_xhtml_segment_starts_inside_inline_and_ends_after(tmp_path):
    epub_path = tmp_path / "book.epub"
    # phrasplit needs both clauses to be terminated sentences; the original
    # unpunctuated "middle" is grouped with "end." into one segment.
    make_epub_with_body(epub_path, "<p>One. <em>Two. three</em> The end.</p>")
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_segments=True, include_xhtml_fragments=True
    )
    segment = next(
        segment
        for segment in extraction.segments
        if segment.text == "Two. three The end."
    )
    assert segment.xhtml_fragment.xhtml == "<em>Two. three</em> The end."


def test_xhtml_void_inline_tags_are_deterministic(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(epub_path, "<p>A<br/>B<wbr/>C</p>")
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_xhtml_fragments=True
    )
    fragment = next(
        block.xhtml_fragment for block in extraction.blocks if block.tag_name == "p"
    )
    assert fragment.xhtml == "A<br/>B<wbr/>C"
    assert visible_text(fragment.xhtml) == fragment.text


def test_xhtml_disallowed_tags_produce_diagnostics(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(epub_path, "<p>A <script>alert(1)</script> B</p>")
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_xhtml_fragments=True
    )
    fragment = next(
        block.xhtml_fragment for block in extraction.blocks if block.tag_name == "p"
    )
    assert "script" not in fragment.xhtml
    assert not any("<script" in fragment.xhtml for _ in [0])
    assert any(
        d.code == "xhtml_fragment_disallowed_tag" for d in extraction.diagnostics
    )


def test_xhtml_segments_split_emphasis_sentence_boundaries(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(
        epub_path,
        (
            "<p>He nodded slowly. "
            "<em>I can’t force her, for all that I need her.</em> "
            "Perhaps Tisamon would have more luck in persuading her.</p>"
        ),
    )

    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_segments=True,
        include_xhtml_fragments=True,
    )

    block = next(block for block in extraction.blocks if block.tag_name == "p")
    segments = [
        segment for segment in extraction.segments if segment.block_id == block.id
    ]

    assert [segment.text for segment in segments] == [
        "He nodded slowly.",
        "I can’t force her, for all that I need her.",
        "Perhaps Tisamon would have more luck in persuading her.",
    ]
    assert [segment.xhtml_fragment.xhtml for segment in segments] == [
        "He nodded slowly.",
        "<em>I can’t force her, for all that I need her.</em>",
        "Perhaps Tisamon would have more luck in persuading her.",
    ]


def test_markdown_block_fragment_preserves_emphasis(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(epub_path, "<p>A <em>small</em> test.</p>")
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_markdown_fragments=True
    )
    block = next(block for block in extraction.blocks if block.tag_name == "p")
    assert block.markdown_fragment.markdown == "A *small* test."
    assert block.xhtml_fragment is None


def test_markdown_block_fragment_preserves_strong(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(epub_path, "<p>A <strong>large</strong> test.</p>")
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_markdown_fragments=True
    )
    block = next(block for block in extraction.blocks if block.tag_name == "p")
    assert block.markdown_fragment.markdown == "A **large** test."


def test_markdown_link_fragment(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(epub_path, '<p>See <a href="chap.xhtml#x">chapter</a>.</p>')
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_markdown_fragments=True
    )
    block = next(block for block in extraction.blocks if block.tag_name == "p")
    assert block.markdown_fragment.markdown == "See [chapter](chap.xhtml#x)."


def test_markdown_code_span_uses_dynamic_backticks(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(epub_path, "<p>Use <code>a ` b</code>.</p>")
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_markdown_fragments=True
    )
    block = next(block for block in extraction.blocks if block.tag_name == "p")
    assert block.markdown_fragment.markdown == "Use ``a ` b``."


def test_markdown_line_break_uses_hard_break(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(epub_path, "<p>A<br/>B</p>")
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_markdown_fragments=True
    )
    block = next(block for block in extraction.blocks if block.tag_name == "p")
    assert block.markdown_fragment.markdown == "A  \nB"


def test_markdown_gfm_strikethrough(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(epub_path, "<p><s>old</s> new</p>")
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_markdown_fragments=True,
        markdown_flavor="gfm",
    )
    block = next(block for block in extraction.blocks if block.tag_name == "p")
    assert block.markdown_fragment.markdown == "~~old~~ new"


def test_markdown_commonmark_strikethrough_unwraps(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(epub_path, "<p><s>old</s> new</p>")
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_markdown_fragments=True
    )
    block = next(block for block in extraction.blocks if block.tag_name == "p")
    assert block.markdown_fragment.markdown == "old new"
    assert any(
        d.code == "markdown_fragment_no_markdown_equivalent"
        for d in extraction.diagnostics
    )


def test_markdown_segment_starts_inside_emphasis(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(epub_path, "<p>Alpha. <em>Bravo. Charlie.</em></p>")
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_segments=True,
        include_markdown_fragments=True,
    )
    markdowns = [segment.markdown_fragment.markdown for segment in extraction.segments]
    assert "*Bravo.*" in markdowns
    assert "*Charlie.*" in markdowns


def test_markdown_default_json_omits_fragments(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(epub_path, "<p>A <em>small</em> test.</p>")
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_markdown_fragments=True
    )
    payload = extraction.to_dict()
    assert "markdown_fragment" not in payload["blocks"][0]


def test_markdown_fragments_serialize_when_requested(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(epub_path, "<p>A <em>small</em> test.</p>")
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_markdown_fragments=True
    )
    payload = extraction.to_dict(include_markdown_fragments=True)
    assert payload["blocks"][0]["markdown_fragment"]["markdown"] == "A *small* test."


def test_markdown_escapes_inline_markers_but_not_periods(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(epub_path, "<p>A *literal* marker.</p>")
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_markdown_fragments=True
    )
    block = next(block for block in extraction.blocks if block.tag_name == "p")
    assert block.markdown_fragment.markdown == r"A \*literal\* marker."


@pytest.mark.parametrize(
    "href",
    ["javascript:alert(1)", "data:text/plain,hello"],
)
def test_markdown_unsafe_link_unwraps(tmp_path, href):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(epub_path, f'<p><a href="{href}">bad</a></p>')
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_markdown_fragments=True
    )
    block = next(block for block in extraction.blocks if block.tag_name == "p")
    assert block.markdown_fragment.markdown == block.text
    assert block.markdown_fragment.markdown.strip() == "bad"
    assert any(
        d.code == "markdown_fragment_invalid_href" for d in extraction.diagnostics
    )


def test_markdown_sub_unwraps_by_default(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_with_body(epub_path, "<p>H<sub>2</sub>O</p>")
    extraction = EPUBParser(str(epub_path)).extract_structured(
        include_markdown_fragments=True
    )
    block = next(block for block in extraction.blocks if block.tag_name == "p")
    assert block.markdown_fragment.markdown == "H2O"


def test_extract_structure_cli_includes_markdown_fragments(tmp_path):
    epub_path = tmp_path / "book.epub"
    output_path = tmp_path / "structure.json"
    make_epub_with_body(epub_path, "<p>A <em>small</em> test.</p>")
    result = CliRunner().invoke(
        cli,
        [
            "extract-structure",
            str(epub_path),
            "--segments",
            "sentence",
            "--xhtml-fragments",
            "--markdown-fragments",
            "--markdown-flavor",
            "gfm",
            "--output",
            str(output_path),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["blocks"][0]["xhtml_fragment"]["xhtml"] == "A <em>small</em> test."
    assert payload["blocks"][0]["markdown_fragment"]["markdown"] == "A *small* test."
    assert payload["blocks"][0]["markdown_fragment"]["flavor"] == "gfm"


def make_epub_no_fragment(path):
    book = epub.EpubBook()
    book.set_identifier("id")
    book.set_title("Structured Test")
    book.set_language("en")
    chapter = epub.EpubHtml(title="Chapter", file_name="chap.xhtml", lang="en")
    chapter.content = (
        '<html><body><h1 id="c1">Chapter</h1><p>Hello world.</p></body></html>'
    )
    book.add_item(chapter)
    book.add_item(epub.EpubNav())
    book.add_item(epub.EpubNcx())
    book.toc = (epub.Link("chap.xhtml", "Chapter", "chap"),)
    book.spine = ["nav", chapter]
    epub.write_epub(str(path), book)


def make_epub_unresolved_fragment(path):
    book = epub.EpubBook()
    book.set_identifier("id")
    book.set_title("Structured Test")
    book.set_language("en")
    chapter = epub.EpubHtml(title="Chapter", file_name="chap.xhtml", lang="en")
    chapter.content = (
        '<html><body><h1 id="c1">Chapter</h1><p>Hello world.</p></body></html>'
    )
    book.add_item(chapter)
    book.add_item(epub.EpubNav())
    book.add_item(epub.EpubNcx())
    book.toc = (epub.Link("chap.xhtml#missing", "Chapter", "chap"),)
    book.spine = ["nav", chapter]
    epub.write_epub(str(path), book)


def make_epub_nested(path):
    book = epub.EpubBook()
    book.set_identifier("id")
    book.set_title("Structured Test")
    book.set_language("en")
    chapter = epub.EpubHtml(title="Chapter", file_name="chap.xhtml", lang="en")
    chapter.content = (
        "<html><body>"
        '<h1 id="c1">Parent</h1><p>One.</p>'
        '<h2 id="c2">Child</h2><p>Two.</p>'
        "</body></html>"
    )
    book.add_item(chapter)
    book.add_item(epub.EpubNav())
    book.add_item(epub.EpubNcx())
    book.toc = (
        (
            epub.Section("Parent", href="chap.xhtml#c1"),
            (epub.Link("chap.xhtml#c2", "Child", "c2"),),
        ),
    )
    book.spine = ["nav", chapter]
    epub.write_epub(str(path), book)


def make_epub_multi_document(path):
    book = epub.EpubBook()
    book.set_identifier("id")
    book.set_title("Structured Test")
    book.set_language("en")
    alpha = epub.EpubHtml(title="Alpha", file_name="a.xhtml", lang="en")
    alpha.content = '<html><body><h1 id="a1">Alpha</h1><p>First.</p></body></html>'
    beta = epub.EpubHtml(title="Beta", file_name="b.xhtml", lang="en")
    beta.content = '<html><body><h1 id="b1">Beta</h1><p>Second.</p></body></html>'
    book.add_item(alpha)
    book.add_item(beta)
    book.add_item(epub.EpubNav())
    book.add_item(epub.EpubNcx())
    book.toc = (
        epub.Link("a.xhtml#a1", "Alpha", "a1"),
        epub.Link("b.xhtml#b1", "Beta", "b1"),
    )
    book.spine = ["nav", alpha, beta]
    epub.write_epub(str(path), book)


def _content_navigation_entry(extraction, title):
    # Skip ebooklib's synthetic "Introduction" entry that has no resolvable spine.
    entries = [
        entry
        for entry in extraction.navigation
        if entry.title == title and entry.source == "nav"
    ]
    return entries[0]


def test_structured_blocks_are_annotated_with_navigation(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub(epub_path)

    extraction = EPUBParser(str(epub_path)).extract_structured(include_segments=True)
    heading = next(block for block in extraction.blocks if block.tag_name == "h1")
    paragraph = next(block for block in extraction.blocks if block.tag_name == "p")

    assert heading.chapter_id is not None
    assert heading.chapter_title == "Chapter"
    assert paragraph.chapter_id == heading.chapter_id
    assert paragraph.chapter_title == "Chapter"
    assert any(entry.id == paragraph.chapter_id for entry in extraction.navigation)


def test_structured_segments_inherit_navigation_assignment(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub(epub_path)

    extraction = EPUBParser(str(epub_path)).extract_structured(include_segments=True)

    assert extraction.segments
    assert all(segment.chapter_id is not None for segment in extraction.segments)
    block_ids = {block.id: block for block in extraction.blocks}
    for segment in extraction.segments:
        assert segment.chapter_id == block_ids[segment.block_id].chapter_id


def test_whole_document_href_without_fragment_maps_from_zero(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_no_fragment(epub_path)

    extraction = EPUBParser(str(epub_path)).extract_structured()

    entry = _content_navigation_entry(extraction, "Chapter")
    assert entry.fragment is None
    assert entry.source_char_start is None  # only resolvable at map time
    heading = next(block for block in extraction.blocks if block.tag_name == "h1")
    paragraph = next(block for block in extraction.blocks if block.tag_name == "p")
    assert heading.chapter_id == entry.id
    assert heading.chapter_title == "Chapter"
    assert paragraph.chapter_id == entry.id


def test_unresolved_fragment_href_does_not_map_blocks(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_unresolved_fragment(epub_path)

    extraction = EPUBParser(str(epub_path)).extract_structured()

    entry = _content_navigation_entry(extraction, "Chapter")
    assert entry.fragment == "missing"
    assert entry.source_char_start is None
    assert all(block.chapter_id is None for block in extraction.blocks)


def test_nested_toc_chooses_deepest_active_entry(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_nested(epub_path)

    extraction = EPUBParser(str(epub_path)).extract_structured()
    parent = _content_navigation_entry(extraction, "Parent")
    child = _content_navigation_entry(extraction, "Child")
    assert child.level > parent.level
    assert child.parent_id == parent.id

    before_child = [
        block for block in extraction.blocks if block.text in {"Parent", "One."}
    ]
    after_child = [
        block for block in extraction.blocks if block.text in {"Child", "Two."}
    ]
    assert before_child
    assert after_child
    assert all(block.chapter_id == parent.id for block in before_child)
    assert all(block.chapter_id == child.id for block in after_child)


def test_multi_document_toc_ranges(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub_multi_document(epub_path)

    extraction = EPUBParser(str(epub_path)).extract_structured()
    alpha = _content_navigation_entry(extraction, "Alpha")
    beta = _content_navigation_entry(extraction, "Beta")

    alpha_blocks = [
        block for block in extraction.blocks if block.document_href == "a.xhtml"
    ]
    beta_blocks = [
        block for block in extraction.blocks if block.document_href == "b.xhtml"
    ]
    assert alpha_blocks and beta_blocks
    assert all(block.chapter_id == alpha.id for block in alpha_blocks)
    assert all(block.chapter_title == "Alpha" for block in alpha_blocks)
    assert all(block.chapter_id == beta.id for block in beta_blocks)
    assert all(block.chapter_title == "Beta" for block in beta_blocks)


def test_missing_nav_fallback_does_not_assign_blocks(tmp_path):
    epub_path = tmp_path / "book.epub"
    make_epub(epub_path)

    parser = EPUBParser(str(epub_path))
    raw_blocks = []
    for document in parser.get_spine_documents():
        raw_blocks.extend(extract_blocks(document))
    assert raw_blocks
    assert all(block.chapter_id is None for block in raw_blocks)

    fallback = NavigationEntry(
        "nav:0:fallback",
        "Document",
        None,
        None,
        None,
        None,
        None,
        None,
        1,
        None,
        0,
        (),
        "fallback",
        [],
    )
    result = annotate_blocks_with_navigation(raw_blocks, [fallback])
    assert result
    assert all(block.chapter_id is None for block in result)
