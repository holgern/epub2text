"""Text formatting utilities for different output styles."""

import re
from typing import Callable, Optional

# Type aliases for phrasplit functions
_SplitFunc = Callable[[str, str], list[str]]
_SplitLongLinesFunc = Callable[[str, int, str], list[str]]

# Try to import phrasplit, fall back to None when not available
PHRASPLIT_AVAILABLE: bool
phrasplit_clauses: Optional[_SplitFunc]
phrasplit_long_lines: Optional[_SplitLongLinesFunc]
phrasplit_paragraphs: Optional[Callable[[str], list[str]]]
phrasplit_sentences: Optional[_SplitFunc]

try:
    from phrasplit import (  # type: ignore[import-not-found]
        split_clauses as _phrasplit_clauses,
    )
    from phrasplit import (
        split_long_lines as _phrasplit_long_lines,
    )
    from phrasplit import (
        split_paragraphs as _phrasplit_paragraphs,
    )
    from phrasplit import (
        split_sentences as _phrasplit_sentences,
    )

    PHRASPLIT_AVAILABLE = True
    phrasplit_clauses = _phrasplit_clauses
    phrasplit_long_lines = _phrasplit_long_lines
    phrasplit_paragraphs = _phrasplit_paragraphs
    phrasplit_sentences = _phrasplit_sentences
except ImportError:
    PHRASPLIT_AVAILABLE = False
    phrasplit_clauses = None
    phrasplit_long_lines = None
    phrasplit_paragraphs = None
    phrasplit_sentences = None


def _check_phrasplit() -> None:
    """Check if phrasplit is available, raise ImportError if not."""
    if not PHRASPLIT_AVAILABLE:
        raise ImportError(
            "phrasplit is required for this feature. "
            "Install with: pip install epub2text[sentences]"
        )


def split_paragraphs(text: str) -> list[str]:
    """
    Split text into paragraphs (separated by double newlines).

    This function works without phrasplit by using a simple regex split.

    Args:
        text: Input text

    Returns:
        List of paragraphs (non-empty, stripped)
    """
    # Simple implementation that doesn't require phrasplit
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


def collapse_paragraph(paragraph: str) -> str:
    """
    Collapse a paragraph to a single line.

    Replaces internal newlines with spaces.

    Args:
        paragraph: Single paragraph text

    Returns:
        Paragraph as single line
    """
    # Replace newlines with spaces, collapse multiple spaces
    result = re.sub(r"\s*\n\s*", " ", paragraph)
    result = re.sub(r"  +", " ", result)
    return result.strip()


def format_paragraphs(
    text: str,
    separator: str = "  ",
    one_line_per_paragraph: bool = False,
) -> str:
    """
    Format text with paragraph separators.

    This function works without phrasplit.

    Args:
        text: Input text with paragraph breaks (double newlines)
        separator: String to prepend to new paragraphs (default: "  " two spaces)
        one_line_per_paragraph: If True, collapse each paragraph to single line

    Returns:
        Formatted text with separator at start of each new paragraph.
        Chapter titles (lines preceded by 4+ newlines) are preserved.
    """
    paragraphs = split_paragraphs(text)

    if not paragraphs:
        return ""

    result_parts = []
    for i, para in enumerate(paragraphs):
        if one_line_per_paragraph:
            para = collapse_paragraph(para)

        if i == 0:
            # First paragraph: no separator
            result_parts.append(para)
        else:
            # Subsequent paragraphs: add separator at start
            # Don't add separator to chapter titles (they are standalone)
            # Chapter titles are identified by checking if they're very short
            # and don't end with sentence-ending punctuation
            is_likely_chapter_title = (
                len(para) < 100
                and not para.rstrip().endswith((".", "!", "?", '"', "'"))
                and "\n" not in para
            )

            if separator and not is_likely_chapter_title:
                # Add separator to each line of the paragraph
                lines = para.split("\n")
                lines[0] = separator + lines[0]
                para = "\n".join(lines)
            result_parts.append(para)

    return "\n".join(result_parts)


def format_sentences(
    text: str,
    separator: str = "  ",
    language_model: str = "en_core_web_sm",
) -> str:
    """
    Format text with one sentence per line.

    Requires phrasplit to be installed.

    Args:
        text: Input text with paragraph breaks
        separator: String to prepend at paragraph boundaries (default: "  ")
        language_model: spaCy language model to use

    Returns:
        Text with one sentence per line, separator at paragraph boundaries.
        Chapter titles are preserved.
    """
    _check_phrasplit()
    assert phrasplit_sentences is not None

    paragraphs = split_paragraphs(text)

    if not paragraphs:
        return ""

    result_lines: list[str] = []
    for i, para in enumerate(paragraphs):
        # Check if this is likely a chapter title
        # (short, no sentence-ending punctuation)
        is_likely_chapter_title = (
            len(para) < 100
            and not para.rstrip().endswith((".", "!", "?", '"', "'"))
            and "\n" not in para
        )

        if is_likely_chapter_title:
            result_lines.append(para)
            continue

        # Process paragraph into sentences using phrasplit
        sentences = phrasplit_sentences(para, language_model)

        if not sentences:
            continue

        # Add separator to first sentence if not first paragraph
        for j, sent in enumerate(sentences):
            if i > 0 and j == 0 and separator:
                result_lines.append(separator + sent)
            else:
                result_lines.append(sent)

    return "\n".join(result_lines)


def format_clauses(
    text: str,
    separator: str = "  ",
    language_model: str = "en_core_web_sm",
) -> str:
    """
    Format text with one clause per line (split at commas).

    Uses spaCy for sentence detection, then splits each sentence at commas.
    The comma stays at the end of each clause, creating natural pause points
    for text-to-speech processing.

    Requires phrasplit to be installed.

    Args:
        text: Input text with paragraph breaks
        separator: String to prepend at paragraph boundaries (default: "  ")
        language_model: spaCy language model to use

    Returns:
        Text with one clause per line, separator at paragraph boundaries.
        Chapter titles are preserved.

    Example:
        Input: "I do like coffee, and I like wine."
        Output:
            "I do like coffee,
            and I like wine."
    """
    _check_phrasplit()
    assert phrasplit_clauses is not None

    paragraphs = split_paragraphs(text)

    if not paragraphs:
        return ""

    result_lines: list[str] = []
    for i, para in enumerate(paragraphs):
        # Check if this is likely a chapter title
        is_likely_chapter_title = (
            len(para) < 100
            and not para.rstrip().endswith((".", "!", "?", '"', "'"))
            and "\n" not in para
        )

        if is_likely_chapter_title:
            result_lines.append(para)
            continue

        # Process paragraph into clauses using phrasplit
        clauses = phrasplit_clauses(para, language_model)

        if not clauses:
            continue

        # Add separator to first clause if not first paragraph
        is_first_clause_in_para = True
        for clause in clauses:
            if i > 0 and is_first_clause_in_para and separator:
                result_lines.append(separator + clause)
            else:
                result_lines.append(clause)
            is_first_clause_in_para = False

    return "\n".join(result_lines)


def split_long_lines(
    text: str,
    max_length: int,
    separator: str = "  ",
    language_model: str = "en_core_web_sm",
) -> str:
    """
    Split lines exceeding max_length at clause/sentence boundaries.

    Strategy:
    1. First try to split at sentence boundaries
    2. If still too long, split at clause boundaries (commas, semicolons, etc.)
    3. If still too long, split at word boundaries

    Requires phrasplit to be installed.

    Args:
        text: Input text (may already be formatted)
        max_length: Maximum line length in characters
        separator: Paragraph separator (preserved)
        language_model: spaCy language model to use

    Returns:
        Text with long lines split. Chapter titles are preserved.
    """
    _check_phrasplit()
    assert phrasplit_long_lines is not None

    lines = text.split("\n")
    result_lines: list[str] = []

    for line in lines:
        # Preserve chapter titles (short lines without typical sentence endings)
        is_likely_chapter_title = (
            len(line.strip()) < 100
            and line.strip()
            and not line.strip().endswith((".", "!", "?", '"', "'"))
        )

        if is_likely_chapter_title:
            result_lines.append(line)
            continue

        # Check if line is within limit
        if len(line) <= max_length:
            result_lines.append(line)
            continue

        # Determine if line starts with separator
        has_separator = line.startswith(separator) if separator else False
        content = line[len(separator) :] if has_separator else line

        # Split the long line using phrasplit
        split_lines_list = phrasplit_long_lines(content, max_length, language_model)

        # Add separator to first line if original had it
        for k, split_line in enumerate(split_lines_list):
            if k == 0 and has_separator:
                result_lines.append(separator + split_line)
            else:
                result_lines.append(split_line)

    return "\n".join(result_lines)


# Keep backward compatibility alias
def format_as_sentences(text: str, language_model: str = "en_core_web_sm") -> str:
    """
    Format text with one sentence per line using spaCy.

    Deprecated: Use format_sentences() instead.

    Requires phrasplit to be installed.

    Args:
        text: Input text with paragraph breaks
        language_model: spaCy language model to use (default: "en_core_web_sm")

    Returns:
        Text with sentences separated by newlines
    """
    return format_sentences(text, separator="", language_model=language_model)


__all__ = [
    "PHRASPLIT_AVAILABLE",
    "collapse_paragraph",
    "format_paragraphs",
    "format_sentences",
    "format_clauses",
    "split_long_lines",
    "format_as_sentences",
    "split_paragraphs",
]
