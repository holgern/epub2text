Usage Guide
===========

epub2text provides three main commands: ``list``, ``extract``, and ``info``.

List Chapters
-------------

Display all chapters in an EPUB file::

    # Table format (default)
    epub2text list book.epub

    # Tree format (shows hierarchy)
    epub2text list book.epub --format tree

The table format shows chapter numbers, titles, character counts, and nesting levels.
The tree format displays the hierarchical structure of nested chapters.

Extract Text
------------

Basic Extraction
~~~~~~~~~~~~~~~~

Extract all chapters to stdout::

    epub2text extract book.epub

Extract to a file::

    epub2text extract book.epub -o output.txt

Chapter Selection
~~~~~~~~~~~~~~~~~

Extract specific chapters by number::

    # Single chapter
    epub2text extract book.epub -c 1

    # Multiple chapters
    epub2text extract book.epub -c 1,3,5

    # Chapter range
    epub2text extract book.epub -c 1-5

    # Complex range
    epub2text extract book.epub -c 1-5,7,9-12 -o selected.txt

Interactive chapter selection::

    epub2text extract book.epub --interactive

Output Formatting
~~~~~~~~~~~~~~~~~

**Paragraph Mode** (``-p, --paragraphs``): One line per paragraph::

    epub2text extract book.epub --paragraphs

**Sentence Mode** (``-s, --sentences``): One line per sentence (requires spaCy)::

    epub2text extract book.epub --sentences

**Max Line Length** (``-m, --max-length``): Split long lines at clause boundaries::

    epub2text extract book.epub --max-length 80

**Paragraph Separators**:

By default, paragraphs are separated by two spaces at the start of each new
paragraph. You can customize this behavior::

    # Use empty lines between paragraphs
    epub2text extract book.epub --empty-lines

    # Custom separator (e.g., tab)
    epub2text extract book.epub --separator "\\t"

    # No separator
    epub2text extract book.epub --separator ""

Text Cleaning Options
~~~~~~~~~~~~~~~~~~~~~

By default, epub2text applies smart text cleaning. You can disable or customize it::

    # Disable all cleaning (raw output)
    epub2text extract book.epub --raw

    # Keep bracketed footnotes like [1]
    epub2text extract book.epub --keep-footnotes

    # Keep page numbers
    epub2text extract book.epub --keep-page-numbers

    # Hide chapter markers
    epub2text extract book.epub --no-markers

Output Control
~~~~~~~~~~~~~~

Control which lines are output::

    # Skip first 10 lines
    epub2text extract book.epub --offset 10

    # Limit to 100 lines
    epub2text extract book.epub --limit 100

    # Add line numbers
    epub2text extract book.epub --line-numbers

Language Model
~~~~~~~~~~~~~~

For sentence-level formatting, you can specify a different spaCy language model::

    # Use German language model
    epub2text extract book.epub --sentences --language-model de_core_news_sm

Show Metadata
-------------

Display EPUB metadata and statistics::

    # Panel format (default)
    epub2text info book.epub

    # Table format
    epub2text info book.epub --format table

    # JSON format (for scripting)
    epub2text info book.epub --format json

The ``info`` command displays:

- Title
- Authors
- Contributors
- Publisher
- Publication Year
- Identifier (ISBN, UUID, etc.)
- Language
- Rights (copyright)
- Coverage
- Description
- Chapter count
- Total character count

Chapter Markers
---------------

Extracted text includes chapter markers in the format::

    <<CHAPTER: Chapter Title>>

    Chapter text content here...

    <<CHAPTER: Next Chapter>>

    More content...

Use ``--no-markers`` to hide these markers.

Examples
--------

Extract a book for text-to-speech processing::

    # One sentence per line, suitable for TTS
    epub2text extract book.epub --sentences -o book.txt

Create a clean plain text version::

    # Paragraphs with empty lines, no markers
    epub2text extract book.epub --paragraphs --empty-lines --no-markers -o book.txt

Extract specific chapters with line length limit::

    # Chapters 1-5 with max 100 chars per line
    epub2text extract book.epub -c 1-5 --max-length 100 -o excerpt.txt

Get metadata as JSON for scripting::

    epub2text info book.epub --format json | jq '.title'
