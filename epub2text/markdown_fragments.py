"""Deterministic Markdown fragment rendering from structured runs."""

from __future__ import annotations

import html
import re
import urllib.parse
from dataclasses import dataclass, field

from .diagnostics import Diagnostic
from .inline_spans import InlineSpan, InlineSpanIssue, build_inline_spans
from .structured import (
    ExtractionPolicy,
    InlineTagRun,
    MarkdownFragment,
    TextBlock,
    TextSegment,
)

INLINE_MARKDOWN_MAP = {
    "em": ("*", "*"),
    "i": ("*", "*"),
    "dfn": ("*", "*"),
    "cite": ("*", "*"),
    "strong": ("**", "**"),
    "b": ("**", "**"),
}
RAW_HTML_FALLBACK_TAGS = frozenset({"sub", "sup", "ruby", "rt", "rp"})
STRIKETHROUGH_TAGS = frozenset({"s", "del"})
SEMANTIC_UNWRAP_TAGS = frozenset(
    {
        "abbr",
        "bdi",
        "bdo",
        "ins",
        "mark",
        "q",
        "rt",
        "rp",
        "ruby",
        "sub",
        "sup",
        "u",
        "wbr",
    }
)
SILENT_UNWRAP_TAGS = frozenset({"data", "small", "span", "time"})
_MARKDOWN_SPECIALS = re.compile(r"([\\`*_{}\[\]<>|~])")


@dataclass
class _RangeSpan:
    span: InlineSpan
    start: int
    end: int
    children: list[_RangeSpan] = field(default_factory=list)
    empties: list[InlineSpan] = field(default_factory=list)


def escape_markdown_text(text: str) -> str:
    return _MARKDOWN_SPECIALS.sub(r"\\\1", text)


def code_span(text: str) -> str:
    max_ticks = max(
        (len(match.group(0)) for match in re.finditer(r"`+", text)),
        default=0,
    )
    ticks = "`" * (max_ticks + 1)
    needs_pad = (
        text.startswith("`")
        or text.endswith("`")
        or text.startswith(" ")
        or text.endswith(" ")
    )
    pad = " " if needs_pad else ""
    return f"{ticks}{pad}{text}{pad}{ticks}"


def safe_link_destination(href: str, policy: ExtractionPolicy) -> str:
    if not href or any(ch in href for ch in "\r\n\x00"):
        return ""
    parsed = urllib.parse.urlsplit(href)
    if parsed.scheme.lower() not in policy.allowed_markdown_link_schemes:
        return ""
    if " " in href or "(" in href or ")" in href:
        safe = href.replace("<", "%3C").replace(">", "%3E")
        return f"<{safe}>"
    return href.replace("\\", "\\\\")


def _diagnostic(
    severity: str,
    code: str,
    message: str,
    block: TextBlock,
    span: InlineSpan | None = None,
) -> Diagnostic:
    run = span.run if span is not None else None
    return Diagnostic(
        severity,
        code,
        message,
        block.document_href,
        run.source_char_start if run else block.inner_char_start,
        run.source_char_end if run else block.inner_char_end,
    )


def _normalize_markdown_run(
    run: InlineTagRun,
) -> tuple[str, tuple[tuple[str, str], ...]]:
    return run.tag_name.lower(), run.attrs


def _append_unbalanced_diagnostics(
    issues: list[InlineSpanIssue], block: TextBlock, diagnostics: list[Diagnostic]
) -> None:
    for issue in issues:
        message = (
            f"Unmatched closing inline tag: {issue.tag}"
            if issue.kind == "unmatched_closing"
            else f"Unclosed inline tag: {issue.tag}"
        )
        diagnostics.append(
            Diagnostic(
                "warning",
                "markdown_fragment_unbalanced_inline",
                message,
                block.document_href,
                issue.run.source_char_start,
                issue.run.source_char_end,
            )
        )


def _clip_spans(
    spans: list[InlineSpan], start: int, end: int, text_length: int
) -> tuple[list[_RangeSpan], list[InlineSpan]]:
    root_nodes: list[_RangeSpan] = []
    root_empties: list[InlineSpan] = []
    ranged_nodes: list[_RangeSpan] = []
    empties: list[InlineSpan] = []
    for span in spans:
        span_end = text_length if span.end is None else span.end
        if span.empty:
            if start <= span.start <= end:
                empties.append(span)
            continue
        if span.start < end and span_end > start:
            ranged_nodes.append(
                _RangeSpan(
                    span=span,
                    start=max(span.start, start),
                    end=min(span_end, end),
                )
            )
    ranged_nodes.sort(
        key=lambda node: (node.start, -(node.end - node.start), node.span.source)
    )
    stack: list[_RangeSpan] = []
    for node in ranged_nodes:
        while stack and node.start >= stack[-1].end:
            stack.pop()
        while stack and node.end > stack[-1].end:
            stack.pop()
        if stack:
            stack[-1].children.append(node)
        else:
            root_nodes.append(node)
        stack.append(node)
    for empty in sorted(empties, key=lambda span: (span.start, span.source)):
        container = _find_deepest_container(root_nodes, empty.start)
        if container is None:
            root_empties.append(empty)
        else:
            container.empties.append(empty)
    return root_nodes, root_empties


def _find_deepest_container(nodes: list[_RangeSpan], pos: int) -> _RangeSpan | None:
    for node in nodes:
        if node.start <= pos < node.end:
            child = _find_deepest_container(node.children, pos)
            return child or node
    return None


def _allowed_raw_attrs(tag: str, policy: ExtractionPolicy) -> frozenset[str]:
    allowed: set[str] = set()
    for owner, names in policy.allowed_markdown_raw_html_attrs:
        if owner == "*" or owner == tag:
            allowed.update(names)
    return frozenset(allowed)


def _raw_html_attrs(
    tag: str, attrs: tuple[tuple[str, str], ...], policy: ExtractionPolicy
) -> tuple[tuple[str, str], ...]:
    allowed = _allowed_raw_attrs(tag, policy)
    return tuple(
        (name, value)
        for name, value in attrs
        if not name.lower().startswith("on") and name.lower() in allowed
    )


def _raw_start_tag(tag: str, attrs: tuple[tuple[str, str], ...]) -> str:
    suffix = "".join(
        f' {name}="{html.escape(value, quote=True)}"' for name, value in attrs
    )
    return f"<{tag}{suffix}>"


def _raw_end_tag(tag: str) -> str:
    return f"</{tag}>"


def _render_items(
    block: TextBlock,
    start: int,
    end: int,
    children: list[_RangeSpan],
    empties: list[InlineSpan],
    policy: ExtractionPolicy,
    diagnostics: list[Diagnostic],
    *,
    link_depth: int = 0,
) -> str:
    items = [("span", child.start, child.span.source, child) for child in children] + [
        ("empty", empty.start, empty.source, empty) for empty in empties
    ]
    items.sort(key=lambda item: (item[1], item[2], 0 if item[0] == "empty" else 1))
    parts: list[str] = []
    pos = start
    for kind, item_start, _, item in items:
        if pos < item_start:
            parts.append(escape_markdown_text(block.text[pos:item_start]))
            pos = item_start
        if kind == "empty":
            parts.append(_render_empty(item, block, policy, diagnostics))
            continue
        parts.append(
            _render_span(
                item,
                block,
                policy,
                diagnostics,
                link_depth=link_depth,
            )
        )
        pos = item.end
    if pos < end:
        parts.append(escape_markdown_text(block.text[pos:end]))
    return "".join(parts)


def _render_empty(
    span: InlineSpan,
    block: TextBlock,
    policy: ExtractionPolicy,
    diagnostics: list[Diagnostic],
) -> str:
    tag = span.tag
    if tag == "br":
        return "  \n"
    if tag == "wbr":
        diagnostics.append(
            _diagnostic(
                "warning",
                "markdown_fragment_no_markdown_equivalent",
                "Dropped word-break opportunity inline tag from Markdown fragment.",
                block,
                span,
            )
        )
        return ""
    if tag not in policy.allowed_markdown_inline_tags:
        diagnostics.append(
            _diagnostic(
                "warning",
                "markdown_fragment_disallowed_tag",
                f"Dropped disallowed inline tag from Markdown fragment: {tag}",
                block,
                span,
            )
        )
        return ""
    diagnostics.append(
        _diagnostic(
            "warning",
            "markdown_fragment_no_markdown_equivalent",
            f"Dropped inline tag without a Markdown equivalent: {tag}",
            block,
            span,
        )
    )
    return ""


def _render_span(
    node: _RangeSpan,
    block: TextBlock,
    policy: ExtractionPolicy,
    diagnostics: list[Diagnostic],
    *,
    link_depth: int,
) -> str:
    tag = node.span.tag
    inner = _render_items(
        block,
        node.start,
        node.end,
        node.children,
        node.empties,
        policy,
        diagnostics,
        link_depth=link_depth + (1 if tag == "a" else 0),
    )
    if tag in policy.opaque_inline_tags or node.span.run.kind == "opaque_inline":
        diagnostics.append(
            _diagnostic(
                "info",
                "markdown_fragment_opaque_inline",
                f"Rendered opaque inline tag as a Markdown code span: {tag}",
                block,
                node.span,
            )
        )
        return code_span(block.text[node.start : node.end])
    if tag in INLINE_MARKDOWN_MAP:
        opener, closer = INLINE_MARKDOWN_MAP[tag]
        return f"{opener}{inner}{closer}" if inner else ""
    if tag == "a":
        if link_depth > 0:
            diagnostics.append(
                _diagnostic(
                    "warning",
                    "markdown_fragment_nested_link",
                    (
                        "Nested XHTML links cannot be represented as nested "
                        "Markdown links."
                    ),
                    block,
                    node.span,
                )
            )
            return inner
        href = next(
            (value for name, value in node.span.attrs if name.lower() == "href"),
            "",
        )
        destination = safe_link_destination(href, policy)
        if not destination:
            diagnostics.append(
                _diagnostic(
                    "warning",
                    "markdown_fragment_invalid_href",
                    (
                        "Unwrapped unsafe or invalid Markdown link destination: "
                        f"{href or '<empty>'}"
                    ),
                    block,
                    node.span,
                )
            )
            return inner
        return f"[{inner}]({destination})" if inner else f"[]({destination})"
    if tag in STRIKETHROUGH_TAGS:
        if policy.markdown_flavor == "gfm":
            return f"~~{inner}~~" if inner else ""
        diagnostics.append(
            _diagnostic(
                "warning",
                "markdown_fragment_no_markdown_equivalent",
                f"Unwrapped inline tag without a CommonMark equivalent: {tag}",
                block,
                node.span,
            )
        )
        return inner
    if (
        tag in policy.markdown_preserve_raw_html_for
        and tag in policy.allowed_markdown_raw_html_tags
        and tag in RAW_HTML_FALLBACK_TAGS
    ):
        diagnostics.append(
            _diagnostic(
                "warning",
                "markdown_fragment_raw_html_fallback",
                f"Rendered inline tag via raw HTML fallback: {tag}",
                block,
                node.span,
            )
        )
        attrs = _raw_html_attrs(tag, node.span.attrs, policy)
        return f"{_raw_start_tag(tag, attrs)}{inner}{_raw_end_tag(tag)}"
    if tag in SEMANTIC_UNWRAP_TAGS:
        diagnostics.append(
            _diagnostic(
                "warning",
                "markdown_fragment_no_markdown_equivalent",
                f"Unwrapped inline tag without a portable Markdown equivalent: {tag}",
                block,
                node.span,
            )
        )
        return inner
    if tag in SILENT_UNWRAP_TAGS:
        return inner
    if tag not in policy.allowed_markdown_inline_tags:
        action = "Dropped" if policy.markdown_unknown_inline == "drop" else "Unwrapped"
        diagnostics.append(
            _diagnostic(
                "warning",
                "markdown_fragment_disallowed_tag",
                f"{action} disallowed inline tag from Markdown fragment: {tag}",
                block,
                node.span,
            )
        )
        return "" if policy.markdown_unknown_inline == "drop" else inner
    diagnostics.append(
        _diagnostic(
            "warning",
            "markdown_fragment_no_markdown_equivalent",
            f"Unwrapped inline tag without a Markdown rendering rule: {tag}",
            block,
            node.span,
        )
    )
    return inner


def _render_markdown_fragment(
    block: TextBlock, start: int, end: int, policy: ExtractionPolicy
) -> MarkdownFragment:
    diagnostics: list[Diagnostic] = []
    spans, issues = build_inline_spans(block, _normalize_markdown_run)
    _append_unbalanced_diagnostics(issues, block, diagnostics)
    roots, root_empties = _clip_spans(spans, start, end, len(block.text))
    markdown = _render_items(
        block,
        start,
        end,
        roots,
        root_empties,
        policy,
        diagnostics,
    )
    active = [
        span.tag
        for span in spans
        if not span.empty
        and span.start < end
        and (span.end if span.end is not None else len(block.text)) > start
    ]
    return MarkdownFragment(
        text=block.text[start:end],
        markdown=markdown,
        flavor=policy.markdown_flavor,
        tag_skeleton=tuple(active),
        source_char_start=block.inner_char_start,
        source_char_end=block.inner_char_end,
        diagnostics=diagnostics,
    )


def render_block_markdown_fragment(
    block: TextBlock, policy: ExtractionPolicy
) -> MarkdownFragment:
    return _render_markdown_fragment(block, 0, len(block.text), policy)


def render_segment_markdown_fragment(
    block: TextBlock, segment: TextSegment, policy: ExtractionPolicy
) -> MarkdownFragment:
    return _render_markdown_fragment(
        block, segment.block_text_start, segment.block_text_end, policy
    )
