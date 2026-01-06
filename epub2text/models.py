"""Data models for EPUB chapters, pages, and metadata."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PageSource(Enum):
    """Source of page information."""

    EPUB_PAGE_LIST = "epub_page_list"  # From EPUB page-list navigation
    SYNTHETIC = "synthetic"  # Generated from content


@dataclass
class Page:
    """Represents a single page in an EPUB.

    Pages can come from two sources:
    1. EPUB page-list navigation (original print book pages)
    2. Synthetic generation (arbitrary page size based on characters/words)
    """

    page_number: str  # Can be "i", "ii", "1", "2", etc.
    text: str
    char_count: int
    source: PageSource
    chapter_id: Optional[str] = None  # Which chapter this page belongs to
    chapter_title: Optional[str] = None  # Title of the chapter

    def __str__(self) -> str:
        source_str = "print" if self.source == PageSource.EPUB_PAGE_LIST else "syn"
        return f"Page {self.page_number} ({self.char_count:,} chars, {source_str})"


@dataclass
class Chapter:
    """Represents a single chapter or section in an EPUB."""

    id: str
    title: str
    text: str
    char_count: int
    parent_id: Optional[str] = None
    level: int = 0

    def __str__(self) -> str:
        return f"{self.title} ({self.char_count:,} chars)"


@dataclass
class Metadata:
    """EPUB metadata."""

    title: Optional[str] = None
    authors: list[str] = field(default_factory=list)
    publisher: Optional[str] = None
    publication_year: Optional[str] = None
    description: Optional[str] = None
    # Required EPUB3 metadata
    identifier: Optional[str] = None
    language: Optional[str] = None
    # Optional Dublin Core metadata
    contributors: list[str] = field(default_factory=list)
    rights: Optional[str] = None
    coverage: Optional[str] = None

    def __str__(self) -> str:
        lines = []
        if self.title:
            lines.append(f"Title: {self.title}")
        if self.authors:
            lines.append(f"Author(s): {', '.join(self.authors)}")
        if self.contributors:
            lines.append(f"Contributor(s): {', '.join(self.contributors)}")
        if self.publisher:
            lines.append(f"Publisher: {self.publisher}")
        if self.publication_year:
            lines.append(f"Year: {self.publication_year}")
        if self.identifier:
            lines.append(f"Identifier: {self.identifier}")
        if self.language:
            lines.append(f"Language: {self.language}")
        if self.rights:
            lines.append(f"Rights: {self.rights}")
        if self.coverage:
            lines.append(f"Coverage: {self.coverage}")
        if self.description:
            desc = (
                self.description[:200] + "..."
                if len(self.description) > 200
                else self.description
            )
            lines.append(f"Description: {desc}")
        return "\n".join(lines)
