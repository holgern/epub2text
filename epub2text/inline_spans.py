"""Shared inline span helpers for fragment rendering."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from .structured import EntityRun, InlineTagRun, TextBlock, TextRun

VOID_INLINE_TAGS = frozenset({"br", "wbr"})
NormalizedInlineTag = tuple[str, tuple[tuple[str, str], ...]]


@dataclass
class InlineSpan:
    tag: str
    attrs: tuple[tuple[str, str], ...]
    start: int
    source: int
    run: InlineTagRun
    end: int | None = None
    empty: bool = False


@dataclass(frozen=True)
class InlineSpanIssue:
    kind: Literal["unmatched_closing", "unclosed_inline"]
    tag: str
    run: InlineTagRun


def build_inline_spans(
    block: TextBlock,
    normalize_run: Callable[[InlineTagRun], NormalizedInlineTag | None] | None = None,
) -> tuple[list[InlineSpan], list[InlineSpanIssue]]:
    normalize = normalize_run or _normalize_run
    stack: list[InlineSpan] = []
    spans: list[InlineSpan] = []
    issues: list[InlineSpanIssue] = []
    for run in block.runs:
        if not isinstance(run, InlineTagRun):
            continue
        normalized = normalize(run)
        if normalized is None:
            continue
        tag, attrs = normalized
        pos = run.block_text_start or 0
        if (
            run.kind in {"inline_start", "opaque_inline"}
            and tag not in VOID_INLINE_TAGS
        ):
            stack.append(InlineSpan(tag, attrs, pos, run.source_char_start, run))
            continue
        if run.kind == "inline_end":
            for index in range(len(stack) - 1, -1, -1):
                if stack[index].tag == tag:
                    item = stack.pop(index)
                    item.end = pos
                    spans.append(item)
                    break
            else:
                issues.append(InlineSpanIssue("unmatched_closing", tag, run))
            continue
        spans.append(
            InlineSpan(
                tag,
                attrs,
                pos,
                run.source_char_start,
                run,
                end=pos,
                empty=True,
            )
        )
    for item in stack:
        item.end = len(block.text)
        issues.append(InlineSpanIssue("unclosed_inline", item.tag, item.run))
        spans.append(item)
    return spans, issues


def iter_text_events(
    block: TextBlock,
    start: int,
    end: int,
    escape: Callable[[str], str],
) -> dict[int, list[str]]:
    events: dict[int, list[str]] = {}
    for run in block.runs:
        if not isinstance(run, TextRun | EntityRun):
            continue
        overlap_start = max(start, run.block_text_start)
        overlap_end = min(end, run.block_text_end)
        if overlap_start >= overlap_end:
            continue
        text = run.text[
            overlap_start - run.block_text_start : overlap_end - run.block_text_start
        ]
        events.setdefault(overlap_start, []).append(escape(text))
    return events


def _normalize_run(run: InlineTagRun) -> NormalizedInlineTag:
    return run.tag_name.lower(), run.attrs
