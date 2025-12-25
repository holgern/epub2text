# epub2text

A niche CLI tool to extract text from EPUB files with smart cleaning capabilities.

## Features

- **Smart Navigation Parsing**: Supports both EPUB3 (NAV HTML) and EPUB2 (NCX) navigation formats
- **Selective Extraction**: Extract specific chapters by range or interactive selection
- **Smart Text Cleaning**: 
  - Remove bracketed footnotes (`[1]`, `[42]`)
  - Remove page numbers (standalone, at line ends, with dashes)
  - Normalize whitespace and paragraph breaks
  - Preserve ordered lists with proper numbering
- **Rich Interactive UI**: Beautiful terminal output with tables and tree views
- **Pipe-Friendly**: Works as both CLI tool and Python library
- **Nested Chapter Support**: Handles hierarchical chapter structures

## Installation

```bash
pip install epub2text
```

For better HTML parsing performance (optional):

```bash
pip install epub2text[lxml]
```

### Development Installation

```bash
git clone https://github.com/holgern/epub2text
cd epub2text
pip install -e .
```

## Usage

### Command Line Interface

#### List Chapters

Display all chapters in an EPUB file:

```bash
# Table format (default)
epub2text list book.epub

# Tree format (shows hierarchy)
epub2text list book.epub --format tree
```

#### Extract Text

Extract all chapters:

```bash
# To stdout
epub2text extract book.epub

# To file
epub2text extract book.epub -o output.txt
```

Extract specific chapters by range:

```bash
# Single chapter
epub2text extract book.epub -c 1

# Multiple chapters
epub2text extract book.epub -c 1,3,5

# Chapter range
epub2text extract book.epub -c 1-5

# Complex range
epub2text extract book.epub -c 1-5,7,9-12 -o selected.txt
```

Interactive chapter selection:

```bash
epub2text extract book.epub --interactive
```

Disable smart cleaning:

```bash
# Keep everything (no cleaning)
epub2text extract book.epub --no-clean

# Keep footnotes
epub2text extract book.epub --keep-footnotes

# Keep page numbers
epub2text extract book.epub --keep-page-numbers
```

#### Show Metadata

Display EPUB metadata and statistics:

```bash
epub2text info book.epub
```

### Python Library

Use epub2text as a library in your Python code:

```python
from epub2text import EPUBParser

# Parse EPUB file
parser = EPUBParser("book.epub")

# Get metadata
metadata = parser.get_metadata()
print(f"Title: {metadata.title}")
print(f"Authors: {', '.join(metadata.authors)}")

# Get all chapters
chapters = parser.get_chapters()
for chapter in chapters:
    print(f"{chapter.title}: {chapter.char_count:,} characters")

# Extract all chapters
full_text = parser.extract_chapters()

# Extract specific chapters
chapter_ids = [chapters[0].id, chapters[2].id]
selected_text = parser.extract_chapters(chapter_ids)
```

With custom text cleaning:

```python
from epub2text import EPUBParser, TextCleaner

parser = EPUBParser("book.epub")
text = parser.extract_chapters()

# Custom cleaning options
cleaner = TextCleaner(
    remove_bracketed_numbers=True,
    remove_page_numbers=True,
    normalize_whitespace=True,
    replace_single_newlines=True,
)
cleaned_text = cleaner.clean(text)
```

## Smart Cleaning Features

The smart text cleaner applies the following transformations by default:

1. **Bracketed Footnotes**: Removes `[1]`, `[42]`, etc.
2. **Page Numbers**: 
   - Standalone page numbers on their own line
   - Page numbers at the end of lines
   - Page numbers with dashes (e.g., `- 42 -`)
3. **Whitespace Normalization**:
   - Collapses multiple spaces into one
   - Standardizes paragraph breaks to double newlines
   - Optionally replaces single newlines with spaces
4. **Chapter Markers**: Removes internal metadata tags

## Chapter Format

Extracted text includes chapter markers in the format:

```
<<CHAPTER: Chapter Title>>

Chapter text content here...

<<CHAPTER: Next Chapter>>

More content...
```

## Requirements

- Python >= 3.9
- click >= 8.0.0
- rich >= 13.0.0
- ebooklib >= 0.18
- beautifulsoup4 >= 4.12.0
- lxml >= 4.9.0 (optional, for better performance)

## Technical Details

### EPUB Parsing Strategy

The parser uses a sophisticated navigation-based approach:

1. Loads EPUB using ebooklib
2. Finds navigation document (prefers NAV HTML, falls back to NCX)
3. Parses navigation structure recursively
4. Maps TOC entries to document positions using fragment IDs
5. Slices HTML content between navigation points
6. Extracts text using BeautifulSoup
7. Applies smart cleaning and normalization

### Navigation Support

- **EPUB3 NAV HTML**: Parses `<nav epub:type="toc">` with nested `<ol>/<li>` structures
- **EPUB2 NCX**: Parses `<navMap>` with `<navPoint>` elements
- **Fragment IDs**: Robust position detection using BeautifulSoup, regex, and string search
- **Nested Structures**: Handles hierarchical chapter organization

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details

## Author

Holger Nahrstaedt

## See Also

- **abogen**: Full-featured audiobook generator with TTS support
- **epub2txt**: Simple EPUB to text converter (different project)
