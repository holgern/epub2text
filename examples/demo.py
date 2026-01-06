#!/usr/bin/env python3
"""
Comprehensive examples for epub2text library.

This module demonstrates all features of epub2text:
- Creating sample EPUBs with pypub
- Parsing EPUBs and extracting metadata
- Text extraction with various options
- Text cleaning and formatting
- Bookmark management
- CLI-equivalent operations

Run with: python -m examples.demo
"""

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import pypub  # type: ignore[import-untyped]

from epub2text import (
    Bookmark,
    BookmarkManager,
    Chapter,
    EPUBParser,
    Metadata,
    TextCleaner,
    epub2txt,
)
from epub2text.formatters import (
    PHRASPLIT_AVAILABLE,
    collapse_paragraph,
    format_clauses,
    format_paragraphs,
    format_sentences,
    split_long_lines,
    split_paragraphs,
)

# =============================================================================
# EPUB Creation Examples
# =============================================================================


def create_sample_epub(output_path: Optional[Path] = None) -> Path:
    """
    Create a sample EPUB file for demonstration purposes.

    This creates a realistic EPUB with multiple chapters, various HTML
    elements, and complete metadata - perfect for testing all epub2text
    features.

    Args:
        output_path: Optional path for the EPUB. If None, creates in temp dir.

    Returns:
        Path to the created EPUB file.

    Example:
        >>> epub_path = create_sample_epub()
        >>> print(f"Created: {epub_path}")
        Created: /tmp/.../sample_book.epub
    """
    if output_path is None:
        output_path = Path(tempfile.mkdtemp()) / "sample_book.epub"

    # Create book with full metadata
    book = pypub.Epub(
        title="The Art of Text Extraction",
        creator="Jane Developer",
        language="en-US",
        rights="Copyright 2024 Jane Developer. Creative Commons BY-NC-SA 4.0",
        publisher="Open Source Press",
        date=datetime(2024, 6, 15),
    )

    # Chapter 1: Introduction with various paragraph styles
    chapter1_html = b"""
    <html>
    <head><title>Introduction</title></head>
    <body>
        <h1>Chapter 1: Introduction</h1>

        <p>Welcome to "The Art of Text Extraction," a comprehensive guide
        to working with digital books. This book will teach you everything
        you need to know about extracting, cleaning, and formatting text
        from EPUB files.</p>

        <p>Text extraction is more than just reading content. It involves
        understanding document structure, handling various encodings, and
        preserving the author's intended formatting while adapting it for
        different output needs.</p>

        <h2>Why Text Extraction Matters</h2>

        <p>In today's digital world, we often need to:</p>

        <ul>
            <li>Convert books for text-to-speech applications</li>
            <li>Create searchable indexes of book content</li>
            <li>Analyze writing patterns and styles</li>
            <li>Generate summaries and excerpts</li>
        </ul>

        <p>Each of these use cases requires different approaches to text
        processing, which we'll explore throughout this book.</p>

        <blockquote>
            <p>"The ability to read between the lines is what separates
            good text processing from great text processing."</p>
            <p>- Anonymous Developer</p>
        </blockquote>

        <p>Let's begin our journey into the fascinating world of text
        extraction!</p>
    </body>
    </html>
    """

    # Chapter 2: Technical content with code and lists
    chapter2_html = b"""
    <html>
    <head><title>Getting Started</title></head>
    <body>
        <h1>Chapter 2: Getting Started</h1>

        <p>Before we dive into advanced techniques, let's cover the basics
        of setting up your text extraction environment. You'll need Python
        3.8 or higher, along with a few essential libraries.</p>

        <h2>Installation Steps</h2>

        <p>Follow these steps to get started:</p>

        <ol>
            <li>Install Python from python.org or your package manager</li>
            <li>Create a virtual environment for your project</li>
            <li>Install epub2text using pip</li>
            <li>Verify the installation by running a simple test</li>
        </ol>

        <h2>Basic Usage</h2>

        <p>Once installed, you can extract text from any EPUB file with
        just a few lines of code. The library handles all the complexity
        of parsing EPUB structure, decoding content, and cleaning text.</p>

        <p>Here's what happens behind the scenes when you extract text:</p>

        <ol>
            <li>The EPUB archive is opened and validated</li>
            <li>Navigation documents (NCX or NAV) are parsed</li>
            <li>Content is extracted in reading order</li>
            <li>HTML is converted to plain text</li>
            <li>Optional cleaning and formatting is applied</li>
        </ol>

        <p>Understanding this process helps you customize extraction for
        your specific needs.</p>
    </body>
    </html>
    """

    # Chapter 3: Content with special characters and formatting
    chapter3_html = b"""
    <html>
    <head><title>Advanced Techniques</title></head>
    <body>
        <h1>Chapter 3: Advanced Techniques</h1>

        <p>Now that you understand the basics, let's explore some advanced
        text processing techniques. These methods will help you handle
        edge cases and produce professional-quality output.</p>

        <h2>Handling Special Characters</h2>

        <p>Text often contains special characters that need careful handling:</p>

        <ul>
            <li>Quotes: "double" and 'single' quotation marks</li>
            <li>Dashes: em-dash, en-dash, and hyphens</li>
            <li>Ellipsis: Wait for it... the suspense builds</li>
            <li>Ampersands: Fish &amp; Chips, Rock &amp; Roll</li>
            <li>Mathematical: 5 &lt; 10 &gt; 3, x = y + z</li>
        </ul>

        <h2>Sentence Boundaries</h2>

        <p>Detecting sentence boundaries is trickier than it seems. Consider
        these examples:</p>

        <p>Dr. Smith went to Washington D.C. for a meeting. She arrived at
        3 p.m. and left by 6 p.m. The meeting was productive.</p>

        <p>Sometimes sentences end with questions? Or exclamations! And
        sometimes they trail off...</p>

        <h2>Clause Detection</h2>

        <p>When processing text for speech synthesis, splitting at clause
        boundaries creates natural pauses. For example, this sentence has
        multiple clauses, separated by commas, which can be split for
        better readability.</p>

        <p>Complex sentences, like this one, often contain parenthetical
        remarks (which add context), embedded clauses, and multiple ideas
        that benefit from careful parsing.</p>
    </body>
    </html>
    """

    # Chapter 4: Conclusion
    chapter4_html = b"""
    <html>
    <head><title>Conclusion</title></head>
    <body>
        <h1>Chapter 4: Conclusion</h1>

        <p>We've covered a lot of ground in this book, from basic text
        extraction to advanced formatting techniques. Here's a summary
        of the key points:</p>

        <ol>
            <li>EPUB files are structured archives with navigation metadata</li>
            <li>Text cleaning removes artifacts while preserving content</li>
            <li>Different output formats serve different purposes</li>
            <li>Sentence and clause detection enable speech synthesis</li>
            <li>Bookmarks help track reading progress</li>
        </ol>

        <h2>Next Steps</h2>

        <p>Armed with this knowledge, you're ready to build your own text
        processing applications. Whether you're creating an audiobook
        converter, a content analyzer, or a reading application, the
        techniques in this book will serve you well.</p>

        <p>Happy coding, and may your text always be clean!</p>

        <p><em>The End</em></p>
    </body>
    </html>
    """

    # Add chapters to book
    book.add_chapter(
        pypub.create_chapter_from_html(chapter1_html, title="Chapter 1: Introduction")
    )
    book.add_chapter(
        pypub.create_chapter_from_html(
            chapter2_html, title="Chapter 2: Getting Started"
        )
    )
    book.add_chapter(
        pypub.create_chapter_from_html(
            chapter3_html, title="Chapter 3: Advanced Techniques"
        )
    )
    book.add_chapter(
        pypub.create_chapter_from_html(chapter4_html, title="Chapter 4: Conclusion")
    )

    # Create the EPUB
    book.create(str(output_path))

    return output_path


# =============================================================================
# EPUBParser Examples
# =============================================================================


def example_parser_basic(epub_path: Path) -> None:
    """
    Basic EPUBParser usage: loading and extracting text.

    Example:
        >>> epub_path = create_sample_epub()
        >>> example_parser_basic(epub_path)
    """
    print("\n" + "=" * 60)
    print("EXAMPLE: Basic EPUBParser Usage")
    print("=" * 60)

    # Create parser instance
    parser = EPUBParser(str(epub_path))

    # Extract all text
    full_text = parser.extract_chapters()

    print(f"\nLoaded EPUB: {epub_path.name}")
    print(f"Total text length: {len(full_text):,} characters")
    print(f"\nFirst 200 characters:\n{full_text[:200]}...")


def example_parser_metadata(epub_path: Path) -> None:
    """
    Extract and display EPUB metadata.

    Example:
        >>> epub_path = create_sample_epub()
        >>> example_parser_metadata(epub_path)
    """
    print("\n" + "=" * 60)
    print("EXAMPLE: Metadata Extraction")
    print("=" * 60)

    parser = EPUBParser(str(epub_path))
    metadata: Metadata = parser.get_metadata()

    print(f"\nTitle: {metadata.title}")
    print(f"Authors: {', '.join(metadata.authors)}")
    print(f"Publisher: {metadata.publisher}")
    print(f"Language: {metadata.language}")
    print(f"Year: {metadata.publication_year}")
    print(f"Rights: {metadata.rights}")
    print(f"Identifier: {metadata.identifier}")

    # Using __str__ method
    print("\nFormatted metadata:")
    print(str(metadata))


def example_parser_chapters(epub_path: Path) -> None:
    """
    List and selectively extract chapters.

    Example:
        >>> epub_path = create_sample_epub()
        >>> example_parser_chapters(epub_path)
    """
    print("\n" + "=" * 60)
    print("EXAMPLE: Chapter Navigation")
    print("=" * 60)

    parser = EPUBParser(str(epub_path))
    chapters: list[Chapter] = parser.get_chapters()

    print(f"\nFound {len(chapters)} chapters:\n")

    for i, chapter in enumerate(chapters, 1):
        indent = "  " * (chapter.level - 1)
        print(f"{i}. {indent}{chapter.title} ({chapter.char_count:,} chars)")

    # Extract specific chapters
    if len(chapters) >= 2:
        selected_ids = [chapters[0].id, chapters[1].id]
        selected_text = parser.extract_chapters(selected_ids)

        print(f"\nExtracted chapters 1-2: {len(selected_text):,} characters")


def example_parser_paragraph_separator(epub_path: Path) -> None:
    """
    Demonstrate different paragraph separator options.

    Example:
        >>> epub_path = create_sample_epub()
        >>> example_parser_paragraph_separator(epub_path)
    """
    print("\n" + "=" * 60)
    print("EXAMPLE: Paragraph Separator Options")
    print("=" * 60)

    # Compact format (single newlines)
    parser_compact = EPUBParser(str(epub_path), paragraph_separator="\n")
    chapters_compact = parser_compact.get_chapters()
    text_compact = chapters_compact[0].text if chapters_compact else ""

    # Readable format (double newlines)
    parser_readable = EPUBParser(str(epub_path), paragraph_separator="\n\n")
    chapters_readable = parser_readable.get_chapters()
    text_readable = chapters_readable[0].text if chapters_readable else ""

    print("\nCompact format (single newlines):")
    print(f"  Lines: {len(text_compact.splitlines())}")
    print(f"  Preview: {text_compact[:150]}...")

    print("\nReadable format (double newlines):")
    print(f"  Lines: {len(text_readable.splitlines())}")
    print(f"  Preview: {text_readable[:150]}...")


# =============================================================================
# TextCleaner Examples
# =============================================================================


def example_cleaner_basic() -> None:
    """
    Basic TextCleaner usage with default options.

    Example:
        >>> example_cleaner_basic()
    """
    print("\n" + "=" * 60)
    print("EXAMPLE: Basic Text Cleaning")
    print("=" * 60)

    # Sample text with various issues
    dirty_text = """
    This is   some    text [1] with  multiple   issues.

    It has footnotes [23] and page    numbers.

    42

    Also trailing page numbers 123

    And multiple


    blank lines.
    """

    cleaner = TextCleaner()
    clean = cleaner.clean(dirty_text)

    print("\nOriginal text:")
    print(repr(dirty_text[:200]))

    print("\nCleaned text:")
    print(repr(clean[:200]))


def example_cleaner_options() -> None:
    """
    Demonstrate various TextCleaner configuration options.

    Example:
        >>> example_cleaner_options()
    """
    print("\n" + "=" * 60)
    print("EXAMPLE: TextCleaner Options")
    print("=" * 60)

    sample = (
        "Text [1] with footnotes [23] and   extra   spaces.\n\n"
        "New paragraph here.\n- Page 42 -"
    )

    # Default cleaning
    default = TextCleaner().clean(sample)

    # Keep footnotes
    keep_footnotes = TextCleaner(remove_footnotes=False).clean(sample)

    # Keep page numbers
    keep_pages = TextCleaner(remove_page_numbers=False).clean(sample)

    # Preserve single newlines (compact mode)
    compact = TextCleaner(preserve_single_newlines=True).clean(sample)

    # Minimal cleaning
    minimal = TextCleaner(
        remove_page_numbers=False,
        remove_footnotes=False,
        normalize_whitespace=False,
    ).clean(sample)

    print(f"\nOriginal: {repr(sample)}")
    print(f"\nDefault:        {repr(default)}")
    print(f"Keep footnotes: {repr(keep_footnotes)}")
    print(f"Keep pages:     {repr(keep_pages)}")
    print(f"Compact:        {repr(compact)}")
    print(f"Minimal:        {repr(minimal)}")


def example_cleaner_length() -> None:
    """
    Calculate text length excluding markers and metadata.

    Example:
        >>> example_cleaner_length()
    """
    print("\n" + "=" * 60)
    print("EXAMPLE: Text Length Calculation")
    print("=" * 60)

    text_with_markers = """Introduction

    This is the actual content of the chapter.

    <<METADATA_TITLE: Some Title>>

    More content here."""

    cleaner = TextCleaner()
    length = cleaner.calculate_length(text_with_markers)

    print(f"\nText with markers:\n{text_with_markers}")
    print(f"\nCalculated length (excluding markers): {length} characters")
    print(f"Raw length: {len(text_with_markers)} characters")


# =============================================================================
# Formatter Examples
# =============================================================================


def example_formatters_paragraphs() -> None:
    """
    Demonstrate paragraph formatting options.

    Example:
        >>> example_formatters_paragraphs()
    """
    print("\n" + "=" * 60)
    print("EXAMPLE: Paragraph Formatting")
    print("=" * 60)

    text = """First paragraph has
multiple lines that will
be handled differently.

Second paragraph also spans
multiple lines here.

Third paragraph is short."""

    # Split into paragraphs
    paragraphs = split_paragraphs(text)
    print(f"\nFound {len(paragraphs)} paragraphs")

    # Format with separator
    formatted = format_paragraphs(text, separator="  ")
    print(f"\nWith '  ' separator:\n{formatted}")

    # One line per paragraph
    one_line = format_paragraphs(text, separator=">> ", one_line_per_paragraph=True)
    print(f"\nOne line per paragraph:\n{one_line}")

    # Collapse single paragraph
    collapsed = collapse_paragraph(paragraphs[0])
    print(f"\nCollapsed first paragraph: {collapsed}")


def example_formatters_sentences() -> None:
    """
    Demonstrate sentence-level formatting (requires spaCy).

    Example:
        >>> example_formatters_sentences()
    """
    print("\n" + "=" * 60)
    print("EXAMPLE: Sentence Formatting")
    print("=" * 60)

    if not PHRASPLIT_AVAILABLE:
        print("\nNote: Install phrasplit for sentence formatting:")
        print("  pip install epub2text[sentences]")
        return

    text = """Dr. Smith went to Washington D.C. for a meeting. She arrived
at 3 p.m. and stayed until evening. The conference was very productive.

This is a new paragraph. It has multiple sentences too! And even questions?"""

    formatted = format_sentences(text, separator="  ")

    print("\nOriginal text:")
    print(text)

    print("\nOne sentence per line:")
    print(formatted)


def example_formatters_clauses() -> None:
    """
    Demonstrate clause-level formatting (requires spaCy).

    Example:
        >>> example_formatters_clauses()
    """
    print("\n" + "=" * 60)
    print("EXAMPLE: Clause Formatting")
    print("=" * 60)

    if not PHRASPLIT_AVAILABLE:
        print("\nNote: Install phrasplit for clause formatting:")
        print("  pip install epub2text[sentences]")
        return

    text = """When the sun rises, the birds begin to sing, and the world slowly awakens.

Complex sentences, like this one, benefit from clause splitting,
which creates natural pauses."""

    formatted = format_clauses(text, separator="  ")

    print("\nOriginal text:")
    print(text)

    print("\nOne clause per line:")
    print(formatted)


def example_formatters_long_lines() -> None:
    """
    Demonstrate splitting long lines at natural boundaries.

    Example:
        >>> example_formatters_long_lines()
    """
    print("\n" + "=" * 60)
    print("EXAMPLE: Long Line Splitting")
    print("=" * 60)

    if not PHRASPLIT_AVAILABLE:
        print("\nNote: Install phrasplit for long line splitting:")
        print("  pip install epub2text[sentences]")
        return

    long_text = (
        "This is an extremely long line that contains multiple sentences "
        "and clauses, which would be difficult to read on a narrow display, "
        "but can be intelligently split at natural boundaries like sentence "
        "endings, comma positions, and other punctuation marks to improve "
        "readability."
    )

    split = split_long_lines(long_text, max_length=60, separator="")

    print(f"\nOriginal ({len(long_text)} chars):")
    print(long_text)

    print("\nSplit at max 60 chars:")
    for line in split.split("\n"):
        print(f"  [{len(line):2d}] {line}")


# =============================================================================
# BookmarkManager Examples
# =============================================================================


def example_bookmarks(epub_path: Path) -> None:
    """
    Demonstrate bookmark management functionality.

    Example:
        >>> epub_path = create_sample_epub()
        >>> example_bookmarks(epub_path)
    """
    print("\n" + "=" * 60)
    print("EXAMPLE: Bookmark Management")
    print("=" * 60)

    # Use temporary bookmark file for demo
    temp_dir = Path(tempfile.mkdtemp())
    bookmark_file = temp_dir / "bookmarks.json"

    manager = BookmarkManager(bookmark_file)

    # Create and save a bookmark
    bookmark = Bookmark.create(
        chapter_index=2,
        line_offset=150,
        percentage=45.5,
        title="The Art of Text Extraction",
    )

    manager.save(str(epub_path), bookmark)
    print(f"\nSaved bookmark for: {epub_path.name}")
    print(f"  Chapter: {bookmark.chapter_index}")
    print(f"  Line: {bookmark.line_offset}")
    print(f"  Progress: {bookmark.percentage:.1f}%")
    print(f"  Saved at: {bookmark.last_read}")

    # Load bookmark
    loaded = manager.load(str(epub_path))
    if loaded:
        print("\nLoaded bookmark:")
        print(f"  Chapter: {loaded.chapter_index}")
        print(f"  Progress: {loaded.percentage:.1f}%")

    # List all bookmarks
    all_bookmarks = manager.list_all()
    print(f"\nTotal bookmarks: {len(all_bookmarks)}")

    # Delete bookmark
    deleted = manager.delete(str(epub_path))
    print(f"Deleted bookmark: {deleted}")

    # Cleanup
    bookmark_file.unlink(missing_ok=True)


# =============================================================================
# epub2txt Convenience Function Examples
# =============================================================================


def example_epub2txt_basic(epub_path: Path) -> None:
    """
    Demonstrate the epub2txt convenience function.

    Example:
        >>> epub_path = create_sample_epub()
        >>> example_epub2txt_basic(epub_path)
    """
    print("\n" + "=" * 60)
    print("EXAMPLE: epub2txt Convenience Function")
    print("=" * 60)

    # Basic extraction - returns single string
    text = epub2txt(str(epub_path))
    print(f"\nBasic extraction: {len(text):,} characters")
    print(f"Preview: {text[:150]}...")

    # Get list of chapters
    chapters = epub2txt(str(epub_path), outputlist=True)
    print(f"\nAs list: {len(chapters)} chapters")
    for i, ch in enumerate(chapters[:3], 1):
        print(f"  Chapter {i}: {len(ch):,} chars")

    # Raw extraction (no cleaning)
    raw = epub2txt(str(epub_path), clean=False)
    print(f"\nRaw (no cleaning): {len(raw):,} characters")

    # Cleaned extraction
    clean = epub2txt(str(epub_path), clean=True)
    print(f"Cleaned: {len(clean):,} characters")


# =============================================================================
# Complete Workflow Example
# =============================================================================


def example_complete_workflow() -> None:
    """
    Demonstrate a complete text extraction and processing workflow.

    This example shows how to:
    1. Create a sample EPUB
    2. Extract metadata and chapters
    3. Clean and format text
    4. Save reading progress

    Example:
        >>> example_complete_workflow()
    """
    print("\n" + "=" * 60)
    print("EXAMPLE: Complete Workflow")
    print("=" * 60)

    # Step 1: Create sample EPUB
    print("\n1. Creating sample EPUB...")
    epub_path = create_sample_epub()
    print(f"   Created: {epub_path}")

    # Step 2: Parse and extract metadata
    print("\n2. Extracting metadata...")
    parser = EPUBParser(str(epub_path))
    metadata = parser.get_metadata()
    print(f"   Title: {metadata.title}")
    print(f"   Author: {', '.join(metadata.authors)}")

    # Step 3: Get chapter structure
    print("\n3. Analyzing chapters...")
    chapters = parser.get_chapters()
    total_chars = sum(ch.char_count for ch in chapters)
    print(f"   Found {len(chapters)} chapters, {total_chars:,} total characters")

    # Step 4: Extract and clean text
    print("\n4. Extracting and cleaning text...")
    raw_text = parser.extract_chapters()

    cleaner = TextCleaner(
        remove_footnotes=True,
        remove_page_numbers=True,
        normalize_whitespace=True,
    )
    clean_text = cleaner.clean(raw_text)
    print(f"   Raw: {len(raw_text):,} chars -> Clean: {len(clean_text):,} chars")

    # Step 5: Format for output
    print("\n5. Formatting text...")
    formatted = format_paragraphs(
        clean_text, separator="  ", one_line_per_paragraph=True
    )
    line_count = len(formatted.splitlines())
    print(f"   Formatted into {line_count} lines")

    # Step 6: Save bookmark
    print("\n6. Saving reading progress...")
    temp_dir = Path(tempfile.mkdtemp())
    manager = BookmarkManager(temp_dir / "bookmarks.json")

    bookmark = Bookmark.create(
        chapter_index=1,
        line_offset=50,
        percentage=25.0,
        title=metadata.title or "Unknown",
    )
    manager.save(str(epub_path), bookmark)
    print(f"   Bookmark saved at {bookmark.percentage:.1f}%")

    # Cleanup
    print("\n7. Cleanup...")
    epub_path.unlink(missing_ok=True)
    print("   Done!")


# =============================================================================
# CLI Usage Examples (Documentation)
# =============================================================================


def print_cli_examples() -> None:
    """
    Print CLI usage examples for reference.

    Example:
        >>> print_cli_examples()
    """
    print("\n" + "=" * 60)
    print("CLI USAGE EXAMPLES")
    print("=" * 60)

    examples = """
# List chapters in an EPUB
epub2text list book.epub
epub2text list book.epub --format tree

# Extract text with various options
epub2text extract book.epub                    # All chapters to stdout
epub2text extract book.epub -o output.txt      # Save to file
epub2text extract book.epub --chapters 1-5     # Specific chapters
epub2text extract book.epub --interactive      # Interactive selection

# Text formatting options
epub2text extract book.epub --paragraphs       # One line per paragraph
epub2text extract book.epub --sentences        # One line per sentence
epub2text extract book.epub --comma            # One line per clause
epub2text extract book.epub --max-length 80    # Split long lines

# Output customization
epub2text extract book.epub --empty-lines      # Blank line separators
epub2text extract book.epub --separator ">> "  # Custom separator
epub2text extract book.epub --no-markers       # Hide chapter markers
epub2text extract book.epub --line-numbers     # Add line numbers

# Content filtering
epub2text extract book.epub --raw              # No cleaning
epub2text extract book.epub --keep-footnotes   # Preserve [1] markers
epub2text extract book.epub --keep-page-numbers

# Pagination
epub2text extract book.epub --offset 100       # Skip first 100 lines
epub2text extract book.epub --limit 50         # Only 50 lines

# Display metadata
epub2text info book.epub
epub2text info book.epub --format json
epub2text info book.epub --format table

# Interactive reader
epub2text read book.epub                       # Start reading
epub2text read book.epub --resume              # Resume from bookmark
epub2text read book.epub --chapter 5           # Start at chapter 5
epub2text read book.epub --sentences           # Sentence-per-line mode
epub2text read book.epub --width 80            # Limit content width
"""
    print(examples)


# =============================================================================
# Main Entry Point
# =============================================================================


def run_all_examples() -> None:
    """
    Run all examples in sequence.

    Example:
        >>> run_all_examples()
    """
    print("\n" + "#" * 60)
    print("#" + " " * 18 + "epub2text Examples" + " " * 18 + "#")
    print("#" * 60)

    # Create sample EPUB for examples
    epub_path = create_sample_epub()

    try:
        # Parser examples
        example_parser_basic(epub_path)
        example_parser_metadata(epub_path)
        example_parser_chapters(epub_path)
        example_parser_paragraph_separator(epub_path)

        # Cleaner examples
        example_cleaner_basic()
        example_cleaner_options()
        example_cleaner_length()

        # Formatter examples
        example_formatters_paragraphs()
        example_formatters_sentences()
        example_formatters_clauses()
        example_formatters_long_lines()

        # Bookmark examples
        example_bookmarks(epub_path)

        # epub2txt examples
        example_epub2txt_basic(epub_path)

        # Complete workflow
        example_complete_workflow()

        # CLI examples
        print_cli_examples()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)

    finally:
        # Cleanup
        epub_path.unlink(missing_ok=True)


if __name__ == "__main__":
    run_all_examples()
