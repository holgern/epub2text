"""Deterministic XHTML fragment rendering from structured runs."""

from __future__ import annotations

import html
from html.parser import HTMLParser

from .diagnostics import Diagnostic
from .inline_spans import (
    InlineSpan,
    InlineSpanIssue,
    build_inline_spans,
    iter_text_events,
)
from .structured import (
    ExtractionPolicy,
    InlineTagRun,
    TextBlock,
    TextSegment,
    XhtmlFragment,
)


def _diagnostic(
    code: str, message: str, block: TextBlock, run: InlineTagRun | None = None
) -> Diagnostic:
    return Diagnostic(
        "warning",
        code,
        message,
        block.document_href,
        run.source_char_start if run else block.inner_char_start,
        run.source_char_end if run else block.inner_char_end,
    )


def _allowed_attrs(tag: str, policy: ExtractionPolicy) -> frozenset[str]:
    allowed: set[str] = set()
    for owner, names in policy.allowed_inline_fragment_attrs:
        if owner == "*" or owner == tag:
            allowed.update(names)
    return frozenset(allowed)


def _sanitize_tag(
    run: InlineTagRun,
    policy: ExtractionPolicy,
    block: TextBlock,
    diagnostics: list[Diagnostic],
) -> tuple[str, tuple[tuple[str, str], ...]] | None:
    tag = run.tag_name.lower()
    if tag not in policy.allowed_inline_fragment_tags:
        diagnostics.append(
            _diagnostic(
                "xhtml_fragment_disallowed_tag",
                f"Dropped disallowed inline tag: {tag}",
                block,
                run,
            )
        )
        return None
    allowed = _allowed_attrs(tag, policy)
    attrs = []
    for name, value in run.attrs:
        lname = name.lower()
        if lname.startswith("on") or lname not in allowed:
            diagnostics.append(
                _diagnostic(
                    "xhtml_fragment_disallowed_attr",
                    f"Dropped disallowed attribute: {name}",
                    block,
                    run,
                )
            )
            continue
        attrs.append((name, value))
    if run.kind == "opaque_inline":
        diagnostics.append(
            _diagnostic(
                "xhtml_fragment_opaque_inline",
                f"Opaque inline tag preserved: {tag}",
                block,
                run,
            )
        )
    return tag, tuple(attrs)


def _start_tag(tag: str, attrs: tuple[tuple[str, str], ...]) -> str:
    suffix = "".join(
        f' {name}="{html.escape(value, quote=True)}"' for name, value in attrs
    )
    return f"<{tag}{suffix}>"


def _end_tag(tag: str) -> str:
    return f"</{tag}>"


def _empty_tag(tag: str, attrs: tuple[tuple[str, str], ...]) -> str:
    suffix = "".join(
        f' {name}="{html.escape(value, quote=True)}"' for name, value in attrs
    )
    return f"<{tag}{suffix}/>"


def _span_diagnostics(
    issues: list[InlineSpanIssue], block: TextBlock, diagnostics: list[Diagnostic]
) -> None:
    for issue in issues:
        message = (
            f"Unmatched closing inline tag: {issue.tag}"
            if issue.kind == "unmatched_closing"
            else f"Unclosed inline tag: {issue.tag}"
        )
        diagnostics.append(
            _diagnostic(
                "xhtml_fragment_unbalanced_inline",
                message,
                block,
                issue.run,
            )
        )


def _render(
    block: TextBlock, start: int, end: int, policy: ExtractionPolicy
) -> XhtmlFragment:
    diagnostics: list[Diagnostic] = []
    spans, issues = build_inline_spans(
        block, lambda run: _sanitize_tag(run, policy, block, diagnostics)
    )
    _span_diagnostics(issues, block, diagnostics)
    opens: dict[int, list[InlineSpan]] = {}
    closes: dict[int, list[InlineSpan]] = {}
    empties: dict[int, list[InlineSpan]] = {}
    active = []
    for span in spans:
        s = span.start
        e = span.end if span.end is not None else len(block.text)
        if span.empty:
            if start <= s <= end:
                empties.setdefault(s, []).append(span)
            continue
        if s < end and e > start:
            os = max(s, start)
            oe = min(e, end)
            opens.setdefault(os, []).append(span)
            closes.setdefault(oe, []).append(span)
            active.append(span.tag)
    text_events = iter_text_events(
        block, start, end, lambda text: html.escape(text, quote=False)
    )
    points = sorted({start, end, *opens, *closes, *empties, *text_events})
    parts: list[str] = []
    for point in points:
        for span in sorted(
            closes.get(point, []),
            key=lambda item: (item.start, item.source),
            reverse=True,
        ):
            parts.append(_end_tag(span.tag))
        for span in sorted(
            opens.get(point, []),
            key=lambda item: (item.start, item.source),
        ):
            parts.append(_start_tag(span.tag, span.attrs))
        for span in empties.get(point, []):
            parts.append(_empty_tag(span.tag, span.attrs))
        parts.extend(text_events.get(point, []))
    xhtml = "".join(parts)
    expected = block.text[start:end]
    if _visible_text(xhtml) != expected:
        diagnostics.append(
            _diagnostic(
                "xhtml_fragment_text_mismatch",
                "Fragment visible text does not match block text slice",
                block,
            )
        )
    return XhtmlFragment(
        expected,
        xhtml,
        tuple(active),
        block.inner_char_start,
        block.inner_char_end,
        diagnostics,
    )


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _visible_text(xhtml: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(xhtml)
    return "".join(parser.parts)


def render_block_xhtml_fragment(
    block: TextBlock, policy: ExtractionPolicy
) -> XhtmlFragment:
    return _render(block, 0, len(block.text), policy)


def render_segment_xhtml_fragment(
    block: TextBlock, segment: TextSegment, policy: ExtractionPolicy
) -> XhtmlFragment:
    return _render(block, segment.block_text_start, segment.block_text_end, policy)
