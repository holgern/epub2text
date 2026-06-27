"""Map structured text blocks to EPUB navigation / TOC entries."""

from __future__ import annotations

from dataclasses import replace

from .structured import NavigationEntry, TextBlock

# Sentinel used in sort keys when a position is unavailable. Any real spine index
# or source offset is far smaller than this, so unresolved entries sort last.
_UNSET = 10**12


def _effective_start(entry: NavigationEntry) -> int | None:
    """Return the effective source-char start position for a navigation entry.

    A whole-document href (no fragment) with a known document and spine points at
    the start of that document, so it maps from position 0. An unresolved fragment
    (e.g. ``chap.xhtml#missing``) has no resolvable offset and must stay unmappable.
    """
    if entry.source_char_start is not None:
        return entry.source_char_start
    if (
        entry.fragment is None
        and entry.document_href is not None
        and entry.spine_index is not None
    ):
        return 0
    return None


def _entry_sort_key(entry: NavigationEntry) -> tuple[int, int, int, int]:
    """Sort navigation entries into stable reading order.

    Ties at the same start prefer the deeper level, then the higher order, so a
    child chapter sorts after a parent part that shares the same anchor and wins.
    """
    start = _effective_start(entry)
    return (
        entry.spine_index if entry.spine_index is not None else _UNSET,
        start if start is not None else _UNSET,
        entry.level,
        entry.order,
    )


def annotate_blocks_with_navigation(
    blocks: list[TextBlock],
    navigation: list[NavigationEntry],
) -> list[TextBlock]:
    """Return ``blocks`` with chapter fields populated from navigation.

    ``chapter_id`` is set to the matching :class:`NavigationEntry.id`, so consumers can
    join blocks directly to ``StructuredEpubExtraction.navigation``. A navigation entry
    marks a start point; its end is the next entry in reading order. Each block is
    assigned to the latest entry whose start is at or before the block's outer start,
    or whose anchor falls inside the block's outer range. Later entries win, and for a
    shared start the deeper entry wins because of the sort key.

    Blocks that match no resolvable navigation range keep ``chapter_id=None``.
    """
    nav_entries = [
        entry
        for entry in navigation
        if entry.source != "fallback"
        and entry.document_href is not None
        and entry.spine_index is not None
        and _effective_start(entry) is not None
    ]
    nav_entries.sort(key=_entry_sort_key)

    annotated: list[TextBlock] = []
    for block in blocks:
        block_spine = block.spine_index
        block_start = block.outer_char_start
        block_end = block.outer_char_end
        if block_spine is None:
            annotated.append(block)
            continue

        active: NavigationEntry | None = None
        for entry in nav_entries:
            entry_spine = entry.spine_index
            entry_start = _effective_start(entry)
            if entry_spine is None or entry_start is None:
                continue

            if entry_spine < block_spine:
                active = entry
                continue

            if entry_spine > block_spine:
                break

            # Same spine document. The block is covered when the entry starts at or
            # before the block, or the TOC anchor lands inside the block's outer range
            # (e.g. the anchor is the ``id`` attribute of a heading block).
            if entry_start <= block_start or block_start <= entry_start < block_end:
                active = entry
                continue

            # Entry starts at or beyond the end of this block; nothing later can match.
            break

        if active is None:
            annotated.append(block)
        else:
            annotated.append(
                replace(
                    block,
                    chapter_id=active.id,
                    chapter_title=active.title,
                )
            )

    return annotated
