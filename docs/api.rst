API Reference
=============

This section documents the Python API for using epub2text as a library.

Core Classes
------------

EPUBParser
~~~~~~~~~~

.. autoclass:: epub2text.EPUBParser
   :members:
   :undoc-members:
   :show-inheritance:

Data Models
-----------

Chapter
~~~~~~~

.. autoclass:: epub2text.Chapter
   :members:
   :undoc-members:

Metadata
~~~~~~~~

.. autoclass:: epub2text.Metadata
   :members:
   :undoc-members:

Text Cleaning
-------------

TextCleaner
~~~~~~~~~~~

.. autoclass:: epub2text.TextCleaner
   :members:
   :undoc-members:

clean_text
~~~~~~~~~~

.. autofunction:: epub2text.clean_text

Text Formatting
---------------

format_paragraphs
~~~~~~~~~~~~~~~~~

.. autofunction:: epub2text.formatters.format_paragraphs

format_sentences
~~~~~~~~~~~~~~~~

.. autofunction:: epub2text.formatters.format_sentences

split_long_lines
~~~~~~~~~~~~~~~~

.. autofunction:: epub2text.formatters.split_long_lines

Usage Examples
--------------

Basic Usage
~~~~~~~~~~~

Parse an EPUB file and extract metadata::

    from epub2text import EPUBParser

    parser = EPUBParser("book.epub")

    # Get metadata
    metadata = parser.get_metadata()
    print(f"Title: {metadata.title}")
    print(f"Authors: {', '.join(metadata.authors)}")
    print(f"Language: {metadata.language}")

    # Get all chapters
    chapters = parser.get_chapters()
    for chapter in chapters:
        print(f"{chapter.title}: {chapter.char_count:,} characters")

    # Extract all text
    full_text = parser.extract_chapters()

Chapter Selection
~~~~~~~~~~~~~~~~~

Extract specific chapters::

    from epub2text import EPUBParser

    parser = EPUBParser("book.epub")
    chapters = parser.get_chapters()

    # Extract first 3 chapters
    chapter_ids = [chapters[0].id, chapters[1].id, chapters[2].id]
    text = parser.extract_chapters(chapter_ids)

Custom Text Cleaning
~~~~~~~~~~~~~~~~~~~~

Apply custom cleaning options::

    from epub2text import EPUBParser, TextCleaner

    parser = EPUBParser("book.epub")
    text = parser.extract_chapters()

    # Custom cleaning
    cleaner = TextCleaner(
        remove_bracketed_numbers=True,
        remove_page_numbers=True,
        normalize_whitespace=True,
        replace_single_newlines=True,
    )
    cleaned_text = cleaner.clean(text)

Sentence Formatting
~~~~~~~~~~~~~~~~~~~

Format text with one sentence per line::

    from epub2text import EPUBParser
    from epub2text.formatters import format_sentences

    parser = EPUBParser("book.epub")
    text = parser.extract_chapters()

    # One sentence per line
    formatted = format_sentences(text, separator="  ")

Line Splitting
~~~~~~~~~~~~~~

Split long lines at clause boundaries::

    from epub2text import EPUBParser
    from epub2text.formatters import split_long_lines

    parser = EPUBParser("book.epub")
    text = parser.extract_chapters()

    # Split lines exceeding 80 characters
    split_text = split_long_lines(text, max_length=80)

Full Metadata Access
~~~~~~~~~~~~~~~~~~~~

Access all Dublin Core metadata fields::

    from epub2text import EPUBParser

    parser = EPUBParser("book.epub")
    metadata = parser.get_metadata()

    print(f"Title: {metadata.title}")
    print(f"Authors: {metadata.authors}")
    print(f"Contributors: {metadata.contributors}")
    print(f"Publisher: {metadata.publisher}")
    print(f"Publication Year: {metadata.publication_year}")
    print(f"Identifier: {metadata.identifier}")
    print(f"Language: {metadata.language}")
    print(f"Rights: {metadata.rights}")
    print(f"Coverage: {metadata.coverage}")
    print(f"Description: {metadata.description}")

Module Index
------------

epub2text
~~~~~~~~~

Main package exports:

- ``EPUBParser`` - Main parser class
- ``Chapter`` - Chapter data model
- ``Metadata`` - Metadata data model
- ``TextCleaner`` - Text cleaning class
- ``clean_text`` - Convenience function for text cleaning

epub2text.formatters
~~~~~~~~~~~~~~~~~~~~

Text formatting utilities:

- ``format_paragraphs`` - Format text with paragraph separators
- ``format_sentences`` - One sentence per line formatting
- ``split_long_lines`` - Split long lines at clause boundaries
- ``split_into_paragraphs`` - Split text into paragraph list
- ``collapse_paragraph`` - Collapse paragraph to single line

epub2text.cleaner
~~~~~~~~~~~~~~~~~

Text cleaning utilities:

- ``TextCleaner`` - Configurable text cleaner class
- ``clean_text`` - Convenience function
- ``calculate_text_length`` - Calculate text length excluding markers
