"""Text formatting utilities for different output styles."""

import re
from typing import Any

try:
    import spacy  # type: ignore[import-not-found]

    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None

# Cache for loaded spaCy model
_nlp_cache: dict[str, Any] = {}

# Placeholder for ellipsis during spaCy processing
_ELLIPSIS_PLACEHOLDER = "\u2026"  # Unicode ellipsis character


def _protect_ellipsis(text: str) -> str:
    """
    Replace ellipsis patterns with a placeholder to prevent sentence splitting.

    Handles:
    - Spaced ellipsis: . . .
    - Regular ellipsis: ...
    - Unicode ellipsis: …
    """
    # Replace spaced ellipsis first (. . .)
    text = re.sub(r"\.\s+\.\s+\.", _ELLIPSIS_PLACEHOLDER, text)
    # Replace regular ellipsis (...)
    text = re.sub(r"\.{3,}", _ELLIPSIS_PLACEHOLDER, text)
    return text


def _restore_ellipsis(text: str) -> str:
    """Restore ellipsis placeholder back to spaced ellipsis."""
    return text.replace(_ELLIPSIS_PLACEHOLDER, ". . .")


def _get_nlp(language_model: str = "en_core_web_sm") -> Any:
    """Get or load a spaCy model (cached)."""
    if not SPACY_AVAILABLE:
        raise ImportError(
            "spaCy is required for this feature. "
            "Install with: pip install epub2text[sentences]"
        )

    if language_model not in _nlp_cache:
        try:
            # spacy is guaranteed to be not None here due to SPACY_AVAILABLE check above
            assert spacy is not None
            _nlp_cache[language_model] = spacy.load(language_model)
        except OSError:
            raise OSError(
                f"spaCy language model '{language_model}' not found. "
                f"Download with: python -m spacy download {language_model}"
            ) from None

    return _nlp_cache[language_model]


def split_into_paragraphs(text: str) -> list[str]:
    """
    Split text into paragraphs (separated by double newlines).

    Args:
        text: Input text

    Returns:
        List of paragraphs (non-empty, stripped)
    """
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

    Args:
        text: Input text with paragraph breaks (double newlines)
        separator: String to prepend to new paragraphs (default: "  " two spaces)
        one_line_per_paragraph: If True, collapse each paragraph to single line

    Returns:
        Formatted text with separator at start of each new paragraph
    """
    paragraphs = split_into_paragraphs(text)

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
            if separator and not para.startswith("<<CHAPTER:"):
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

    Args:
        text: Input text with paragraph breaks
        separator: String to prepend at paragraph boundaries (default: "  ")
        language_model: spaCy language model to use

    Returns:
        Text with one sentence per line, separator at paragraph boundaries
    """
    nlp = _get_nlp(language_model)
    paragraphs = split_into_paragraphs(text)

    if not paragraphs:
        return ""

    result_lines = []
    for i, para in enumerate(paragraphs):
        # Check if this is a chapter marker
        if para.startswith("<<CHAPTER:"):
            result_lines.append(para)
            continue

        # Protect ellipsis from being treated as sentence boundaries
        para = _protect_ellipsis(para)

        # Process paragraph into sentences
        doc = nlp(para)
        sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]

        if not sentences:
            continue

        # Add separator to first sentence if not first paragraph
        for j, sent in enumerate(sentences):
            # Restore ellipsis in the sentence
            sent = _restore_ellipsis(sent)
            if i > 0 and j == 0 and separator:
                result_lines.append(separator + sent)
            else:
                result_lines.append(sent)

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

    Args:
        text: Input text (may already be formatted)
        max_length: Maximum line length in characters
        separator: Paragraph separator (preserved)
        language_model: spaCy language model to use

    Returns:
        Text with long lines split
    """
    nlp = _get_nlp(language_model)

    lines = text.split("\n")
    result_lines = []

    for line in lines:
        # Preserve chapter markers as-is
        if line.startswith("<<CHAPTER:") or line.startswith(separator + "<<CHAPTER:"):
            result_lines.append(line)
            continue

        # Check if line is within limit
        if len(line) <= max_length:
            result_lines.append(line)
            continue

        # Determine if line starts with separator
        has_separator = line.startswith(separator) if separator else False
        content = line[len(separator) :] if has_separator else line

        # Split the long line
        split_lines = _split_at_boundaries(content, max_length, nlp)

        # Add separator to first line if original had it
        for k, split_line in enumerate(split_lines):
            if k == 0 and has_separator:
                result_lines.append(separator + split_line)
            else:
                result_lines.append(split_line)

    return "\n".join(result_lines)


def _split_at_boundaries(text: str, max_length: int, nlp: Any) -> list[str]:
    """
    Split text at sentence/clause boundaries to fit within max_length.

    Args:
        text: Text to split
        max_length: Maximum line length
        nlp: spaCy language model

    Returns:
        List of lines
    """
    # Protect ellipsis before spaCy processing
    protected_text = _protect_ellipsis(text)

    # First, try splitting by sentences
    doc = nlp(protected_text)
    sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]

    result = []
    current_line = ""

    for sent in sentences:
        # Restore ellipsis in the sentence
        sent = _restore_ellipsis(sent)
        # If sentence itself exceeds max_length, split at clauses
        if len(sent) > max_length:
            # Flush current line first
            if current_line:
                result.append(current_line)
                current_line = ""
            # Split sentence at clause boundaries
            clause_lines = _split_at_clauses(sent, max_length)
            result.extend(clause_lines)
        elif not current_line:
            current_line = sent
        elif len(current_line) + 1 + len(sent) <= max_length:
            current_line += " " + sent
        else:
            result.append(current_line)
            current_line = sent

    if current_line:
        result.append(current_line)

    return result if result else [text]


def _split_at_clauses(text: str, max_length: int) -> list[str]:
    """
    Split text at clause boundaries (commas, semicolons, colons, dashes).

    Args:
        text: Text to split
        max_length: Maximum line length

    Returns:
        List of lines
    """
    # Split at clause boundaries, keeping the delimiter with the preceding text
    # Pattern: split after comma/semicolon/colon/dash followed by space
    # We use a lookbehind to keep the delimiter with the first part
    parts = re.split(r"(?<=[,;:\u2014\u2013])\s+", text)

    result = []
    current_line = ""

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if not current_line:
            current_line = part
        elif len(current_line) + 1 + len(part) <= max_length:
            current_line += " " + part
        else:
            if current_line:
                result.append(current_line)
            current_line = part

    if current_line:
        result.append(current_line)

    # If still too long, do hard split at word boundaries
    final_result = []
    for line in result:
        if len(line) > max_length:
            final_result.extend(_hard_split(line, max_length))
        else:
            final_result.append(line)

    return final_result if final_result else [text]


def _hard_split(text: str, max_length: int) -> list[str]:
    """
    Hard split text at word boundaries when clause splitting isn't enough.

    Args:
        text: Text to split
        max_length: Maximum line length

    Returns:
        List of lines
    """
    words = text.split()
    result = []
    current_line = ""

    for word in words:
        if not current_line:
            current_line = word
        elif len(current_line) + 1 + len(word) <= max_length:
            current_line += " " + word
        else:
            result.append(current_line)
            current_line = word

    if current_line:
        result.append(current_line)

    return result if result else [text]


# Keep backward compatibility alias
def format_as_sentences(text: str, language_model: str = "en_core_web_sm") -> str:
    """
    Format text with one sentence per line using spaCy.

    Deprecated: Use format_sentences() instead.

    Args:
        text: Input text with paragraph breaks
        language_model: spaCy language model to use (default: "en_core_web_sm")

    Returns:
        Text with sentences separated by newlines
    """
    return format_sentences(text, separator="", language_model=language_model)
