epub2text Documentation
=======================

A niche CLI tool to extract text from EPUB files with smart cleaning capabilities.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   usage
   api
   changelog

Features
--------

- **Smart Navigation Parsing**: Supports both EPUB3 (NAV HTML) and EPUB2 (NCX) navigation formats
- **Selective Extraction**: Extract specific chapters by range or interactive selection
- **Flexible Output Formatting**:
  - One paragraph per line with customizable separators
  - One sentence per line using spaCy NLP
  - Automatic line splitting at clause boundaries for long lines
- **Smart Text Cleaning**:
  - Remove bracketed footnotes (``[1]``, ``[42]``)
  - Remove page numbers (standalone, at line ends, with dashes)
  - Normalize whitespace and paragraph breaks
  - Preserve ordered lists with proper numbering
- **Rich Interactive UI**: Beautiful terminal output with tables and tree views
- **Pipe-Friendly**: Works as both CLI tool and Python library
- **Nested Chapter Support**: Handles hierarchical chapter structures
- **Full Dublin Core Metadata**: Extract all EPUB metadata fields

Quick Start
-----------

Install epub2text::

    pip install epub2text

Extract text from an EPUB file::

    epub2text extract book.epub

List chapters::

    epub2text list book.epub

Show metadata::

    epub2text info book.epub

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
