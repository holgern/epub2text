"""
EPUB parser for extracting chapters and metadata.
Adapted from abogen's book_handler.py with navigation support.
"""

import logging
import re
import urllib.parse
from pathlib import Path
from typing import Any, Optional

import ebooklib  # type: ignore[import-untyped]
from bs4 import BeautifulSoup, NavigableString  # type: ignore[import-untyped]
from ebooklib import epub

from .cleaner import calculate_text_length, clean_text
from .models import Chapter, Metadata, Page, PageSource

logger = logging.getLogger(__name__)


class EPUBParser:
    """
    Parse EPUB files to extract chapters and metadata.

    Supports both NAV HTML (EPUB3) and NCX (EPUB2) navigation formats.
    Handles nested chapter structures and accurately slices content between
    navigation points.
    """

    def __init__(self, filepath: str, paragraph_separator: str = "\n\n"):
        """
        Initialize parser with EPUB file.

        Args:
            filepath: Path to the EPUB file
            paragraph_separator: String to use between paragraphs (default: "\\n\\n")

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is not a valid EPUB
        """
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        self.paragraph_separator = paragraph_separator
        self.book: Any = None
        self.doc_content: dict[str, str] = {}
        self.content_texts: dict[str, str] = {}
        self.content_lengths: dict[str, int] = {}
        self.processed_nav_structure: list[dict[str, Any]] = []
        self._metadata: Optional[Metadata] = None

        self._load_epub()

    def _load_epub(self) -> None:
        """Load and parse the EPUB file."""
        try:
            self.book = epub.read_epub(str(self.filepath))
            logger.info(f"Loaded EPUB: {self.filepath.name}")
        except Exception as e:
            raise ValueError(f"Failed to read EPUB file: {e}") from e

    def _get_single_metadata(self, field: str) -> Optional[str]:
        """Extract a single metadata value from Dublin Core field."""
        try:
            items = self.book.get_metadata("DC", field)
            if items and len(items) > 0:
                value: str = items[0][0]
                return value
        except Exception as e:
            logger.warning(f"Error extracting {field}: {e}")
        return None

    def _get_list_metadata(self, field: str) -> list[str]:
        """Extract a list of metadata values from Dublin Core field."""
        try:
            items = self.book.get_metadata("DC", field)
            if items:
                return [item[0] for item in items if len(item) > 0]
        except Exception as e:
            logger.warning(f"Error extracting {field}: {e}")
        return []

    def get_metadata(self) -> Metadata:
        """
        Extract metadata from EPUB.

        Returns:
            Metadata object with title, authors, etc.
        """
        if self._metadata is not None:
            return self._metadata

        # Extract publication year with special date parsing
        publication_year = None
        date_str = self._get_single_metadata("date")
        if date_str:
            year_match = re.search(r"\b(19|20)\d{2}\b", date_str)
            publication_year = year_match.group(0) if year_match else date_str

        self._metadata = Metadata(
            title=self._get_single_metadata("title"),
            authors=self._get_list_metadata("creator"),
            description=self._get_single_metadata("description"),
            publisher=self._get_single_metadata("publisher"),
            publication_year=publication_year,
            identifier=self._get_single_metadata("identifier"),
            language=self._get_single_metadata("language"),
            contributors=self._get_list_metadata("contributor"),
            rights=self._get_single_metadata("rights"),
            coverage=self._get_single_metadata("coverage"),
        )
        return self._metadata

    def get_chapters(self, include_text: bool = True) -> list[Chapter]:
        """
        Extract all chapters from the EPUB using navigation.

        Args:
            include_text: If True, include full chapter text. If False, return only
                metadata (title, id, level, char_count). Default: True.

        Returns:
            List of Chapter objects
        """
        # First, process the navigation structure
        self._process_epub_content_nav()

        # Convert the navigation structure to Chapter objects
        chapters: list[Chapter] = []
        self._build_chapters_from_nav(
            self.processed_nav_structure, chapters, level=1, include_text=include_text
        )

        return chapters

    def _build_chapters_from_nav(
        self,
        nav_structure: list[dict[str, Any]],
        chapters: list[Chapter],
        parent_id: Optional[str] = None,
        level: int = 1,
        include_text: bool = True,
    ) -> None:
        """
        Recursively build Chapter objects from navigation structure.

        Args:
            nav_structure: List of navigation entries
            chapters: List to append Chapter objects to
            parent_id: ID of parent chapter (for nested chapters)
            level: Depth level in the chapter hierarchy
            include_text: If True, include full text; if False, only metadata
        """
        for entry in nav_structure:
            src: Optional[str] = entry.get("src")
            title: str = entry.get("title", "Untitled")
            children: list[dict[str, Any]] = entry.get("children", [])

            # Generate a unique ID for this chapter
            chapter_id = src if src else f"chapter_{len(chapters)}"

            # Get the text content if available and requested
            if include_text:
                text = self.content_texts.get(src, "") if src else ""
            else:
                text = ""
            char_count = self.content_lengths.get(src, 0) if src else 0

            # Create Chapter object
            chapter = Chapter(
                id=chapter_id,
                title=title,
                text=text,
                char_count=char_count,
                parent_id=parent_id,
                level=level,
            )
            chapters.append(chapter)

            # Process children recursively
            if children:
                self._build_chapters_from_nav(
                    children,
                    chapters,
                    parent_id=chapter_id,
                    level=level + 1,
                    include_text=include_text,
                )

    def _process_epub_content_nav(self) -> None:  # noqa: C901
        """
        Process EPUB content using ITEM_NAVIGATION (NAV HTML) or ITEM_NCX.
        Globally orders navigation entries and slices content between them.
        """
        logger.info("Processing EPUB using navigation document (NAV/NCX)...")
        nav_item = None
        nav_type = None

        # 1. Check ITEM_NAVIGATION for NAV HTML
        nav_items = list(self.book.get_items_of_type(ebooklib.ITEM_NAVIGATION))
        if nav_items:
            # Prefer files named 'nav.xhtml' or similar
            preferred_nav = next(
                (
                    item
                    for item in nav_items
                    if "nav" in item.get_name().lower()
                    and item.get_name().lower().endswith((".xhtml", ".html"))
                ),
                None,
            )
            if preferred_nav:
                nav_item = preferred_nav
                nav_type = "html"
                logger.info(f"Found preferred NAV HTML: {nav_item.get_name()}")
            else:
                # Check if any ITEM_NAVIGATION is HTML
                html_nav = next(
                    (
                        item
                        for item in nav_items
                        if item.get_name().lower().endswith((".xhtml", ".html"))
                    ),
                    None,
                )
                if html_nav:
                    nav_item = html_nav
                    nav_type = "html"
                    logger.info(f"Found NAV HTML: {html_nav.get_name()}")

        # 2. Check for NCX in ITEM_NAVIGATION
        if not nav_item and nav_items:
            ncx_in_nav = next(
                (
                    item
                    for item in nav_items
                    if item.get_name().lower().endswith(".ncx")
                ),
                None,
            )
            if ncx_in_nav:
                nav_item = ncx_in_nav
                nav_type = "ncx"
                logger.info(f"Found NCX via ITEM_NAVIGATION: {ncx_in_nav.get_name()}")

        # 3. Check for NCX constant
        ncx_constant = getattr(epub, "ITEM_NCX", None)
        if not nav_item and ncx_constant is not None:
            ncx_items = list(self.book.get_items_of_type(ncx_constant))
            if ncx_items:
                nav_item = ncx_items[0]
                nav_type = "ncx"
                logger.info(f"Found NCX via ITEM_NCX: {nav_item.get_name()}")

        # 4. Fallback: search all documents for NAV HTML
        if not nav_item:
            for item in self.book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                try:
                    html_content = item.get_content().decode("utf-8", errors="ignore")
                    if "<nav" in html_content and 'epub:type="toc"' in html_content:
                        soup = BeautifulSoup(html_content, "html.parser")
                        nav_tag = soup.find("nav", attrs={"epub:type": "toc"})
                        if nav_tag:
                            nav_item = item
                            nav_type = "html"
                            logger.info(f"Found NAV HTML in: {item.get_name()}")
                            break
                except (AttributeError, UnicodeDecodeError):
                    continue

        # If no navigation found, raise error
        if not nav_item or not nav_type:
            logger.warning("No navigation document found")
            raise ValueError("No navigation document (NAV HTML or NCX) found")

        # Parse navigation content
        parser_type = "html.parser" if nav_type == "html" else "xml"
        logger.info(f"Using parser: '{parser_type}' for {nav_item.get_name()}")

        try:
            nav_content = nav_item.get_content().decode("utf-8", errors="ignore")
            nav_soup = BeautifulSoup(nav_content, parser_type)
        except Exception as e:
            logger.error(f"Failed to parse navigation: {e}")
            raise ValueError(f"Failed to parse navigation content: {e}") from e

        # Cache all document HTML and determine spine order
        self.doc_content = {}
        spine_docs = []
        for spine_item_tuple in self.book.spine:
            item_id = spine_item_tuple[0]
            item = self.book.get_item_with_id(item_id)
            if item:
                spine_docs.append(item.get_name())
            else:
                logger.warning(f"Spine item with id '{item_id}' not found")

        doc_order = {href: i for i, href in enumerate(spine_docs)}
        doc_order_decoded = {
            urllib.parse.unquote(href): i for href, i in doc_order.items()
        }

        # Load document content
        self.content_texts = {}
        self.content_lengths = {}

        for item in self.book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            href = item.get_name()
            if href in doc_order or any(
                href in nav_point.get("src", "")
                for nav_point in nav_soup.find_all(["content", "a"])
            ):
                try:
                    html_content = item.get_content().decode("utf-8", errors="ignore")
                    self.doc_content[href] = html_content
                except Exception as e:
                    logger.error(f"Error decoding content for {href}: {e}")
                    self.doc_content[href] = ""

        # Extract and order navigation entries
        ordered_nav_entries: list[dict[str, Any]] = []
        self.processed_nav_structure = []

        # Parse based on nav_type
        parse_successful = False
        if nav_type == "ncx":
            nav_map = nav_soup.find("navMap")
            if nav_map:
                logger.info("Parsing NCX <navMap>...")
                for nav_point in nav_map.find_all("navPoint", recursive=False):
                    self._parse_ncx_navpoint(
                        nav_point,
                        ordered_nav_entries,
                        doc_order,
                        doc_order_decoded,
                        self.processed_nav_structure,
                    )
                parse_successful = bool(ordered_nav_entries)
            else:
                logger.warning("Could not find <navMap> in NCX")
        elif nav_type == "html":
            logger.info("Parsing NAV HTML...")
            toc_nav = nav_soup.find("nav", attrs={"epub:type": "toc"})
            if not toc_nav:
                # Fallback: look for any <nav> with <ol>
                all_navs = nav_soup.find_all("nav")
                for nav in all_navs:
                    if nav.find("ol"):
                        toc_nav = nav
                        logger.info("Found fallback TOC in <nav> with <ol>")
                        break
            if toc_nav:
                top_ol = toc_nav.find("ol", recursive=False)
                if top_ol:
                    for li in top_ol.find_all("li", recursive=False):
                        self._parse_html_nav_li(
                            li,
                            ordered_nav_entries,
                            doc_order,
                            doc_order_decoded,
                            self.processed_nav_structure,
                        )
                    parse_successful = bool(ordered_nav_entries)
                else:
                    logger.warning("Found <nav> but no top-level <ol>")
            else:
                logger.warning("Could not find TOC structure in NAV HTML")

        if not parse_successful:
            logger.warning("No valid navigation entries found")
            raise ValueError("No valid navigation entries found after parsing")

        # Sort entries by document order and position
        ordered_nav_entries.sort(key=lambda x: (x["doc_order"], x["position"]))
        logger.info(f"Sorted {len(ordered_nav_entries)} navigation entries")

        # Slice content between TOC entries
        num_entries = len(ordered_nav_entries)
        for i in range(num_entries):
            current_entry = ordered_nav_entries[i]
            current_src = current_entry["src"]
            current_doc = current_entry["doc_href"]
            current_pos = current_entry["position"]
            current_doc_html = self.doc_content.get(current_doc, "")

            start_slice_pos = current_pos
            slice_html = ""

            next_entry = ordered_nav_entries[i + 1] if (i + 1) < num_entries else None

            if next_entry:
                next_doc = next_entry["doc_href"]
                next_pos = next_entry["position"]

                if current_doc == next_doc:
                    slice_html = current_doc_html[start_slice_pos:next_pos]
                else:
                    # Collect content across multiple documents
                    slice_html = current_doc_html[start_slice_pos:]
                    docs_between = []
                    try:
                        idx_current = spine_docs.index(current_doc)
                        idx_next = spine_docs.index(next_doc)
                        if idx_current < idx_next:
                            for doc_idx in range(idx_current + 1, idx_next):
                                docs_between.append(spine_docs[doc_idx])
                        elif idx_current > idx_next:
                            for doc_idx in range(idx_current + 1, len(spine_docs)):
                                docs_between.append(spine_docs[doc_idx])
                            for doc_idx in range(0, idx_next):
                                docs_between.append(spine_docs[doc_idx])
                    except ValueError:
                        # Document not found in spine_docs
                        pass
                    for doc_href in docs_between:
                        slice_html += self.doc_content.get(doc_href, "")
                    next_doc_html = self.doc_content.get(next_doc, "")
                    slice_html += next_doc_html[:next_pos]
            else:
                # Last entry: include all remaining content
                slice_html = current_doc_html[start_slice_pos:]
                try:
                    idx_current = spine_docs.index(current_doc)
                    for doc_idx in range(idx_current + 1, len(spine_docs)):
                        intermediate_doc_href = spine_docs[doc_idx]
                        slice_html += self.doc_content.get(intermediate_doc_href, "")
                except ValueError:
                    # Document not found in spine_docs
                    pass

            # Fallback: if empty, use whole file
            if not slice_html.strip() and current_doc_html:
                logger.warning(f"No content for '{current_src}', using full file")
                slice_html = current_doc_html

            if slice_html.strip():
                slice_soup = BeautifulSoup(slice_html, "html.parser")

                # Add line breaks after paragraphs
                for tag in slice_soup.find_all(["p", "div"]):
                    tag.append(self.paragraph_separator)

                # Handle ordered lists
                for ol in slice_soup.find_all("ol"):
                    start_attr = ol.get("start")  # type: ignore[union-attr]
                    start_num = int(start_attr) if start_attr else 1  # type: ignore[arg-type]
                    for li_idx, li in enumerate(ol.find_all("li", recursive=False)):
                        number_text = f"{start_num + li_idx}) "
                        if li.string:
                            li.string.replace_with(number_text + str(li.string))  # type: ignore[union-attr]
                        else:
                            li.insert(0, NavigableString(number_text))

                # Remove footnote tags
                for tag in slice_soup.find_all(["sup", "sub"]):
                    tag.decompose()

                text = clean_text(
                    slice_soup.get_text(),
                    preserve_single_newlines=(self.paragraph_separator == "\n"),
                ).strip()
                if text:
                    self.content_texts[current_src] = text
                    self.content_lengths[current_src] = calculate_text_length(text)
                else:
                    self.content_texts[current_src] = ""
                    self.content_lengths[current_src] = 0
            else:
                self.content_texts[current_src] = ""
                self.content_lengths[current_src] = 0

        # Handle content before first TOC entry
        if ordered_nav_entries:
            first_entry = ordered_nav_entries[0]
            first_doc_href = first_entry["doc_href"]
            first_pos = first_entry["position"]
            first_doc_order = first_entry["doc_order"]
            prefix_html = ""

            for doc_idx in range(first_doc_order):
                if doc_idx < len(spine_docs):
                    intermediate_doc_href = spine_docs[doc_idx]
                    prefix_html += self.doc_content.get(intermediate_doc_href, "")

            first_doc_html = self.doc_content.get(first_doc_href, "")
            prefix_html += first_doc_html[:first_pos]

            if prefix_html.strip():
                prefix_soup = BeautifulSoup(prefix_html, "html.parser")
                for tag in prefix_soup.find_all(["sup", "sub"]):
                    tag.decompose()
                prefix_text = clean_text(prefix_soup.get_text()).strip()

                if prefix_text:
                    prefix_chapter_src = "internal:prefix_content"
                    self.content_texts[prefix_chapter_src] = prefix_text
                    self.content_lengths[prefix_chapter_src] = len(prefix_text)
                    self.processed_nav_structure.insert(
                        0,
                        {
                            "src": prefix_chapter_src,
                            "title": "Introduction",
                            "children": [],
                        },
                    )
                    logger.info("Added prefix content chapter")

        logger.info(f"Finished processing. Found {len(self.content_texts)} sections")

    def _find_doc_key(
        self,
        base_href: str,
        doc_order: dict[str, int],
        doc_order_decoded: dict[str, int],
    ) -> tuple[Optional[str], Optional[int]]:
        """Find the best matching doc_key for a given base_href."""
        import os

        candidates = [
            base_href,
            urllib.parse.unquote(base_href),
        ]
        base_name = os.path.basename(base_href).lower()
        for k in list(doc_order.keys()) + list(doc_order_decoded.keys()):
            if os.path.basename(k).lower() == base_name:
                candidates.append(k)
        for candidate in candidates:
            if candidate in doc_order:
                return candidate, doc_order[candidate]
            elif candidate in doc_order_decoded:
                return candidate, doc_order_decoded[candidate]
        return None, None

    def _parse_ncx_navpoint(
        self,
        nav_point: Any,
        ordered_entries: list[dict[str, Any]],
        doc_order: dict[str, int],
        doc_order_decoded: dict[str, int],
        tree_structure_list: list[dict[str, Any]],
    ) -> None:
        """Parse NCX navPoint recursively."""
        nav_label = nav_point.find("navLabel")
        content = nav_point.find("content")
        title = (
            nav_label.find("text").get_text(strip=True)
            if nav_label and nav_label.find("text")
            else "Untitled Section"
        )
        src = content["src"] if content and "src" in content.attrs else None

        current_entry_node: dict[str, Any] = {
            "title": title,
            "src": src,
            "children": [],
        }

        if src:
            base_href, fragment = src.split("#", 1) if "#" in src else (src, None)
            doc_key, doc_idx = self._find_doc_key(
                base_href, doc_order, doc_order_decoded
            )
            if not doc_key:
                logger.warning(f"Entry '{title}' points to '{base_href}' not in spine")
                current_entry_node["has_content"] = False
            else:
                position = self._find_position_robust(doc_key, fragment)
                entry_data = {
                    "src": src,
                    "title": title,
                    "doc_href": doc_key,
                    "position": position,
                    "doc_order": doc_idx,
                }
                ordered_entries.append(entry_data)
                current_entry_node["has_content"] = True
        else:
            logger.warning(f"Entry '{title}' has no 'src' attribute")
            current_entry_node["has_content"] = False

        # Process children
        child_navpoints = nav_point.find_all("navPoint", recursive=False)
        if child_navpoints:
            for child_np in child_navpoints:
                self._parse_ncx_navpoint(
                    child_np,
                    ordered_entries,
                    doc_order,
                    doc_order_decoded,
                    current_entry_node["children"],
                )

        if title and (
            current_entry_node.get("has_content", False)
            or current_entry_node["children"]
        ):
            tree_structure_list.append(current_entry_node)

    def _parse_html_nav_li(
        self,
        li_element: Any,
        ordered_entries: list[dict[str, Any]],
        doc_order: dict[str, int],
        doc_order_decoded: dict[str, int],
        tree_structure_list: list[dict[str, Any]],
    ) -> None:
        """Parse HTML NAV <li> recursively."""
        link = li_element.find("a", recursive=False)
        span_text = li_element.find("span", recursive=False)
        title = "Untitled Section"
        src: Optional[str] = None
        current_entry_node: dict[str, Any] = {"children": []}

        if link and "href" in link.attrs:
            src = link["href"]
            title = link.get_text(strip=True) or title
            if not title.strip() and span_text:
                title = span_text.get_text(strip=True) or title
            if not title.strip():
                li_text = "".join(
                    t for t in li_element.contents if isinstance(t, NavigableString)
                ).strip()
                title = li_text or title
        elif span_text:
            title = span_text.get_text(strip=True) or title
            if not title.strip():
                li_text = "".join(
                    t for t in li_element.contents if isinstance(t, NavigableString)
                ).strip()
                title = li_text or title
        else:
            li_text = "".join(
                t for t in li_element.contents if isinstance(t, NavigableString)
            ).strip()
            title = li_text or title

        current_entry_node["title"] = title
        current_entry_node["src"] = src

        doc_key = None
        doc_idx = None
        position = 0
        fragment = None
        if src:
            base_href, fragment = src.split("#", 1) if "#" in src else (src, None)
            doc_key, doc_idx = self._find_doc_key(
                base_href, doc_order, doc_order_decoded
            )
            if doc_key is not None:
                position = self._find_position_robust(doc_key, fragment)
                entry_data = {
                    "src": src,
                    "title": title,
                    "doc_href": doc_key,
                    "position": position,
                    "doc_order": doc_idx,
                }
                ordered_entries.append(entry_data)
                current_entry_node["has_content"] = True
            else:
                logger.warning(f"Entry '{title}' points to '{base_href}' not in spine")
                current_entry_node["has_content"] = False
        else:
            current_entry_node["has_content"] = False

        # Process children
        for child_ol in li_element.find_all("ol", recursive=False):
            for child_li in child_ol.find_all("li", recursive=False):
                self._parse_html_nav_li(
                    child_li,
                    ordered_entries,
                    doc_order,
                    doc_order_decoded,
                    current_entry_node["children"],
                )
        tree_structure_list.append(current_entry_node)

    def _find_position_robust(self, doc_href: str, fragment_id: Optional[str]) -> int:
        """
        Find the position of a fragment ID within a document.

        Args:
            doc_href: Document href/filename
            fragment_id: Fragment ID to find (e.g., 'chapter1')

        Returns:
            Position (character index) in the HTML, or 0 if not found
        """
        if doc_href not in self.doc_content:
            logger.warning(f"Document '{doc_href}' not found in cached content")
            return 0
        html_content = self.doc_content[doc_href]
        if not fragment_id:
            return 0

        # Try BeautifulSoup first
        try:
            temp_soup = BeautifulSoup(f"<div>{html_content}</div>", "html.parser")
            target_element = temp_soup.find(id=fragment_id)
            if target_element:
                tag_str = str(target_element)
                pos = html_content.find(tag_str[: min(len(tag_str), 200)])
                if pos != -1:
                    logger.debug(f"Found position for id='{fragment_id}': {pos}")
                    return pos
        except Exception as e:
            logger.warning(f"BeautifulSoup failed to find id='{fragment_id}': {e}")

        # Try regex pattern
        safe_fragment_id = re.escape(fragment_id)
        id_name_pattern = re.compile(
            f"<[^>]+(?:id|name)\\s*=\\s*[\"']{safe_fragment_id}[\"']", re.IGNORECASE
        )
        match = id_name_pattern.search(html_content)
        if match:
            pos = match.start()
            logger.debug(f"Found position for id/name='{fragment_id}' (regex): {pos}")
            return pos

        # Try simple string search
        id_match_str = f'id="{fragment_id}"'
        name_match_str = f'name="{fragment_id}"'
        id_pos = html_content.find(id_match_str)
        name_pos = html_content.find(name_match_str)

        pos = -1
        if id_pos != -1 and name_pos != -1:
            pos = min(id_pos, name_pos)
        elif id_pos != -1:
            pos = id_pos
        elif name_pos != -1:
            pos = name_pos

        if pos != -1:
            tag_start_pos = html_content.rfind("<", 0, pos)
            final_pos = tag_start_pos if tag_start_pos != -1 else 0
            logger.debug(f"Found position for id/name='{fragment_id}': {final_pos}")
            return final_pos

        logger.warning(f"Anchor '{fragment_id}' not found in {doc_href}")
        return 0

    def _remove_duplicate_title_line(self, text: str, title: str) -> str:
        """
        Remove first line if it matches the chapter title.

        Handles various scenarios:
        1. Exact match: "ONE\\nThe morning..." -> "The morning..."
        2. Same-line match: "ONE The morning..." -> "The morning..."
        3. Case-insensitive matches

        Args:
            text: Chapter text content
            title: Chapter title from navigation

        Returns:
            Text with duplicate title line removed (if found)
        """
        if not text or not title:
            return text

        lines = text.split("\n", 1)
        if not lines:
            return text

        first_line = lines[0].strip()
        title_clean = title.strip()

        # No title to compare
        if not title_clean:
            return text

        # Check various matching scenarios

        # 1. Exact match (entire first line is the title)
        if first_line == title_clean:
            return lines[1] if len(lines) > 1 else ""

        # 2. Case-insensitive match
        if first_line.lower() == title_clean.lower():
            return lines[1] if len(lines) > 1 else ""

        # 3. First line starts with title followed by space (e.g., "ONE The morning...")
        if first_line.startswith(title_clean + " "):
            # Remove only the title part, keep the rest
            remainder = first_line[len(title_clean) :].lstrip()
            if len(lines) > 1:
                return remainder + "\n" + lines[1]
            return remainder

        # 4. Case-insensitive version of #3
        if first_line.lower().startswith(title_clean.lower() + " "):
            remainder = first_line[len(title_clean) :].lstrip()
            if len(lines) > 1:
                return remainder + "\n" + lines[1]
            return remainder

        # No match - return original
        return text

    def extract_chapters(
        self,
        chapter_ids: Optional[list[str]] = None,
        deduplicate_chapter_titles: bool = True,
        skip_toc: bool = False,
    ) -> str:
        """
        Extract text from selected chapters.

        Args:
            chapter_ids: List of chapter IDs to extract. If None, extract all.
            deduplicate_chapter_titles: If True, removes duplicate chapter titles
                that appear as the first line of chapter content (default: True)
            skip_toc: If True, skip TOC and front matter chapters (default: False)

        Returns:
            Combined text from all selected chapters with chapter titles separated
            by 4 linebreaks before the title and 2 linebreaks after.
        """
        chapters = self.get_chapters()

        if chapter_ids is None:
            # Extract all chapters
            selected = chapters
        else:
            # Filter by chapter IDs
            selected = [ch for ch in chapters if ch.id in chapter_ids]

        # Skip TOC/front matter if requested
        if skip_toc:
            # Create temporary Page objects to use the same detection logic
            filtered = []
            for chapter in selected:
                temp_page = Page(
                    page_number="temp",
                    text=chapter.text,
                    char_count=chapter.char_count,
                    chapter_title=chapter.title,
                    source=PageSource.SYNTHETIC,
                )
                if not self._is_toc_or_front_matter(temp_page):
                    filtered.append(chapter)
            selected = filtered

        # Combine text with chapter titles
        parts = []
        for i, chapter in enumerate(selected):
            if chapter.text:
                # Remove duplicate title if requested
                if deduplicate_chapter_titles:
                    cleaned_text = self._remove_duplicate_title_line(
                        chapter.text, chapter.title
                    )
                else:
                    cleaned_text = chapter.text

                # Format: 4 linebreaks (if not first), chapter title,
                # 2 linebreaks, content
                if i == 0:
                    # First chapter: no leading linebreaks
                    parts.append(f"{chapter.title}\n\n{cleaned_text}")
                else:
                    # Subsequent chapters: 4 linebreaks before title
                    parts.append(f"\n\n\n\n{chapter.title}\n\n{cleaned_text}")

        return "".join(parts)

    def get_pages(
        self,
        synthetic_page_size: int = 2000,
        use_words: bool = False,
    ) -> list[Page]:
        """
        Extract pages from the EPUB.

        First attempts to use EPUB page-list navigation (original print pages).
        If no page-list is found, generates synthetic pages based on content.

        Args:
            synthetic_page_size: Size of synthetic pages in characters (default: 2000)
                                 or words if use_words=True (default: ~350 words)
            use_words: If True, synthetic_page_size is interpreted as word count

        Returns:
            List of Page objects
        """
        # Try to get pages from EPUB page-list first
        pages = self._get_epub_page_list()

        if pages:
            logger.info(f"Found {len(pages)} pages from EPUB page-list")
            return pages

        # Fall back to synthetic page generation
        logger.info("No page-list found, generating synthetic pages")
        return self._generate_synthetic_pages(synthetic_page_size, use_words)

    def has_page_list(self) -> bool:
        """
        Check if the EPUB contains a page-list navigation.

        Returns:
            True if page-list navigation exists, False otherwise
        """
        return bool(self._find_page_list_nav())

    def _find_page_list_nav(self) -> Optional[tuple[Any, str]]:
        """
        Find the page-list navigation element in the EPUB.

        Returns:
            Tuple of (nav_soup, nav_type) or None if not found
        """
        # Check ITEM_NAVIGATION for NAV HTML with page-list
        nav_items = list(self.book.get_items_of_type(ebooklib.ITEM_NAVIGATION))

        for nav_item in nav_items:
            if nav_item.get_name().lower().endswith((".xhtml", ".html")):
                try:
                    nav_content = nav_item.get_content().decode(
                        "utf-8", errors="ignore"
                    )
                    if 'epub:type="page-list"' in nav_content:
                        nav_soup = BeautifulSoup(nav_content, "html.parser")
                        page_list_nav = nav_soup.find(
                            "nav", attrs={"epub:type": "page-list"}
                        )
                        if page_list_nav:
                            logger.info(
                                f"Found page-list in NAV HTML: {nav_item.get_name()}"
                            )
                            return (page_list_nav, "html")
                except (AttributeError, UnicodeDecodeError):
                    continue

        # Check for NCX pageList
        ncx_item = None
        for nav_item in nav_items:
            if nav_item.get_name().lower().endswith(".ncx"):
                ncx_item = nav_item
                break

        if not ncx_item:
            ncx_constant = getattr(epub, "ITEM_NCX", None)
            if ncx_constant is not None:
                ncx_items = list(self.book.get_items_of_type(ncx_constant))
                if ncx_items:
                    ncx_item = ncx_items[0]

        if ncx_item:
            try:
                ncx_content = ncx_item.get_content().decode("utf-8", errors="ignore")
                ncx_soup = BeautifulSoup(ncx_content, "xml")
                page_list = ncx_soup.find("pageList")
                if page_list:
                    logger.info(f"Found pageList in NCX: {ncx_item.get_name()}")
                    return (page_list, "ncx")
            except (AttributeError, UnicodeDecodeError):
                pass

        # Fallback: search all documents for embedded page-list
        for item in self.book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            try:
                html_content = item.get_content().decode("utf-8", errors="ignore")
                if 'epub:type="page-list"' in html_content:
                    soup = BeautifulSoup(html_content, "html.parser")
                    page_list_nav = soup.find("nav", attrs={"epub:type": "page-list"})
                    if page_list_nav:
                        logger.info(f"Found page-list in document: {item.get_name()}")
                        return (page_list_nav, "html")
            except (AttributeError, UnicodeDecodeError):
                continue

        return None

    def _get_epub_page_list(self) -> list[Page]:
        """
        Extract pages from EPUB page-list navigation.

        Returns:
            List of Page objects from the page-list, or empty list if not found
        """
        nav_result = self._find_page_list_nav()
        if not nav_result:
            return []

        page_list_nav, nav_type = nav_result
        pages: list[Page] = []

        # Ensure chapters are processed for chapter mapping
        if not self.content_texts:
            self._process_epub_content_nav()

        # Build document order for position finding
        spine_docs = []
        for spine_item_tuple in self.book.spine:
            item_id = spine_item_tuple[0]
            item = self.book.get_item_with_id(item_id)
            if item:
                spine_docs.append(item.get_name())

        doc_order = {href: i for i, href in enumerate(spine_docs)}
        doc_order_decoded = {
            urllib.parse.unquote(href): i for href, i in doc_order.items()
        }

        # Parse page entries
        page_entries: list[dict[str, Any]] = []

        if nav_type == "html":
            # EPUB3 NAV HTML format
            ol = page_list_nav.find("ol")
            if ol:
                for li in ol.find_all("li", recursive=False):
                    link = li.find("a")
                    if link and "href" in link.attrs:
                        page_num = link.get_text(strip=True)
                        src = link["href"]
                        page_entries.append({"page_number": page_num, "src": src})
        elif nav_type == "ncx":
            # EPUB2 NCX format
            for page_target in page_list_nav.find_all("pageTarget"):
                nav_label = page_target.find("navLabel")
                content = page_target.find("content")
                if nav_label and content:
                    text_elem = nav_label.find("text")
                    page_num = text_elem.get_text(strip=True) if text_elem else ""
                    src = content.get("src", "")
                    if page_num and src:
                        page_entries.append({"page_number": page_num, "src": src})

        if not page_entries:
            return []

        # Sort entries by document order and position
        for entry in page_entries:
            src = entry["src"]
            base_href, fragment = src.split("#", 1) if "#" in src else (src, None)
            doc_key, doc_idx = self._find_doc_key(
                base_href, doc_order, doc_order_decoded
            )
            if doc_key is not None:
                position = self._find_position_robust(doc_key, fragment)
                entry["doc_href"] = doc_key
                entry["doc_order"] = doc_idx
                entry["position"] = position
            else:
                entry["doc_href"] = base_href
                entry["doc_order"] = 999999
                entry["position"] = 0

        page_entries.sort(key=lambda x: (x.get("doc_order", 0), x.get("position", 0)))

        # Extract text for each page (between page markers)
        num_entries = len(page_entries)
        chapters = self.get_chapters()
        chapter_map = self._build_chapter_position_map(chapters, doc_order)

        for i in range(num_entries):
            current = page_entries[i]
            next_entry = page_entries[i + 1] if i + 1 < num_entries else None

            text = self._extract_text_between_positions(current, next_entry, spine_docs)

            # Find which chapter this page belongs to
            chapter_id, chapter_title = self._find_chapter_for_position(
                current.get("doc_href", ""),
                current.get("position", 0),
                chapter_map,
            )

            page = Page(
                page_number=current["page_number"],
                text=text,
                char_count=calculate_text_length(text),
                source=PageSource.EPUB_PAGE_LIST,
                chapter_id=chapter_id,
                chapter_title=chapter_title,
            )
            pages.append(page)

        return pages

    def _generate_synthetic_pages(self, page_size: int, use_words: bool) -> list[Page]:
        """
        Generate synthetic pages from the EPUB content.

        Pages are split at sentence boundaries to avoid breaking sentences
        across pages.

        Args:
            page_size: Size of pages in characters or words
            use_words: If True, page_size is word count; otherwise character count

        Returns:
            List of synthetic Page objects
        """
        chapters = self.get_chapters()
        if not chapters:
            return []

        pages: list[Page] = []
        page_num = 1
        current_sentences: list[str] = []
        current_size = 0  # Current size in chars or words
        current_chapter_id: Optional[str] = None
        current_chapter_title: Optional[str] = None

        def get_size(text: str) -> int:
            """Get size of text in chars or words."""
            if use_words:
                return len(text.split())
            return len(text)

        def save_page() -> None:
            """Save current accumulated sentences as a page."""
            nonlocal page_num, current_sentences, current_size

            if current_sentences:
                # Join sentences, preserving paragraph breaks
                page_text_parts = []
                for s in current_sentences:
                    if s == "\n\n":
                        page_text_parts.append("\n\n")
                    else:
                        page_text_parts.append(s)

                # Build page text with proper spacing
                page_text = ""
                for i, part in enumerate(page_text_parts):
                    if part == "\n\n":
                        page_text += "\n\n"
                    elif i > 0 and page_text_parts[i - 1] != "\n\n":
                        page_text += " " + part
                    else:
                        page_text += part

                page_text = page_text.strip()

                pages.append(
                    Page(
                        page_number=str(page_num),
                        text=page_text,
                        char_count=calculate_text_length(page_text),
                        source=PageSource.SYNTHETIC,
                        chapter_id=current_chapter_id,
                        chapter_title=current_chapter_title,
                    )
                )
                page_num += 1
                current_sentences = []
                current_size = 0

        for chapter in chapters:
            if not chapter.text:
                continue

            # If chapter changes and we have accumulated content, save
            # current page first
            if (
                current_chapter_id is not None
                and (
                    chapter.id != current_chapter_id
                    or chapter.title != current_chapter_title
                )
                and current_sentences
            ):
                save_page()

            current_chapter_id = chapter.id
            current_chapter_title = chapter.title

            # Split chapter into sentences
            sentences = self._split_into_sentences(chapter.text)

            for sentence in sentences:
                # Handle paragraph break markers
                if sentence == "\n\n":
                    current_sentences.append("\n\n")
                    continue

                sentence = sentence.strip()
                if not sentence:
                    continue

                sentence_size = get_size(sentence)

                # If single sentence exceeds page size, we have to include it anyway
                # (we don't split sentences)
                if sentence_size > page_size and not current_sentences:
                    # Single oversized sentence - create its own page
                    pages.append(
                        Page(
                            page_number=str(page_num),
                            text=sentence,
                            char_count=calculate_text_length(sentence),
                            source=PageSource.SYNTHETIC,
                            chapter_id=current_chapter_id,
                            chapter_title=current_chapter_title,
                        )
                    )
                    page_num += 1
                    continue

                # Check if adding this sentence would exceed page size
                if current_size + sentence_size > page_size and current_sentences:
                    # Save current page and start new one
                    save_page()

                # Add sentence to current page
                current_sentences.append(sentence)
                current_size += sentence_size

        # Don't forget the last page
        save_page()

        return pages

    def _split_into_sentences(self, text: str) -> list[str]:
        """
        Split text into sentences using regex, preserving paragraph breaks.

        Handles common abbreviations and edge cases to avoid incorrect splits.
        Paragraph breaks (\\n\\n) are preserved within the sentence list.

        Args:
            text: Text to split into sentences

        Returns:
            List of sentences (may include empty strings representing paragraph breaks)
        """
        if not text or not text.strip():
            return []

        sentences: list[str] = []

        # Split by paragraphs first to preserve structure
        paragraphs = text.split("\n\n")

        for para_idx, paragraph in enumerate(paragraphs):
            if not paragraph.strip():
                continue

            # Normalize whitespace within paragraph (but not between paragraphs)
            paragraph = re.sub(r"[ \t]+", " ", paragraph)
            paragraph = paragraph.replace("\n", " ")

            # Common abbreviations that shouldn't end sentences
            abbreviations = {
                "Mr",
                "Mrs",
                "Ms",
                "Dr",
                "Prof",
                "Sr",
                "Jr",
                "vs",
                "etc",
                "Inc",
                "Ltd",
                "Corp",
                "Co",
                "St",
                "Ave",
                "Blvd",
                "Rd",
                "Fig",
                "No",
                "Vol",
                "pp",
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
                "e.g",
                "i.e",
            }

            current_sentence: list[str] = []

            # Split by whitespace and process word by word
            words = paragraph.split()

            for i, word in enumerate(words):
                current_sentence.append(word)

                # Check if this word ends a sentence
                if word and word[-1] in ".!?":
                    # Check if it's an abbreviation
                    word_without_punct = word.rstrip(".!?")
                    is_abbreviation = word_without_punct in abbreviations

                    # Check for ellipsis (... or . . .)
                    is_ellipsis = word == "..." or (
                        word == "."
                        and i >= 2
                        and words[i - 1] == "."
                        and words[i - 2] == "."
                    )

                    # Check if next word starts with capital (if exists)
                    next_word_capital = False
                    if i + 1 < len(words):
                        next_word = words[i + 1]
                        if next_word and next_word[0].isupper():
                            next_word_capital = True

                    # End sentence if:
                    # - Not an abbreviation
                    # - Not an ellipsis
                    # - Either at end of text or next word starts with capital
                    if (
                        not is_abbreviation
                        and not is_ellipsis
                        and (i + 1 >= len(words) or next_word_capital)
                    ):
                        sentence = " ".join(current_sentence)
                        if sentence.strip():
                            sentences.append(sentence.strip())
                        current_sentence = []

            # Add any remaining text as final sentence
            if current_sentence:
                sentence = " ".join(current_sentence)
                if sentence.strip():
                    sentences.append(sentence.strip())

            # Add paragraph break marker after each paragraph (except the last)
            if para_idx < len(paragraphs) - 1:
                sentences.append("\n\n")  # Paragraph break marker

        return sentences

    def _build_chapter_position_map(
        self,
        chapters: list[Chapter],
        doc_order: dict[str, int],
    ) -> list[tuple[str, int, str, str]]:
        """
        Build a sorted list of chapter positions for lookup.

        Returns:
            List of (doc_href, position, chapter_id, chapter_title) tuples
        """
        chapter_positions: list[tuple[str, int, str, str]] = []

        for chapter in chapters:
            src = chapter.id
            if not src or src.startswith("internal:"):
                continue

            base_href, fragment = src.split("#", 1) if "#" in src else (src, None)

            # Try to find the document
            doc_key = None
            for key in doc_order:
                if key == base_href or key.endswith("/" + base_href):
                    doc_key = key
                    break
                decoded = urllib.parse.unquote(key)
                if decoded == base_href or decoded.endswith("/" + base_href):
                    doc_key = key
                    break

            if doc_key:
                position = self._find_position_robust(doc_key, fragment)
                chapter_positions.append((doc_key, position, chapter.id, chapter.title))

        # Sort by document order and position
        chapter_positions.sort(key=lambda x: (doc_order.get(x[0], 999999), x[1]))

        return chapter_positions

    def _find_chapter_for_position(
        self,
        doc_href: str,
        position: int,
        chapter_map: list[tuple[str, int, str, str]],
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Find which chapter a given position belongs to.

        Returns:
            Tuple of (chapter_id, chapter_title) or (None, None)
        """
        result_id: Optional[str] = None
        result_title: Optional[str] = None

        for ch_doc, ch_pos, ch_id, ch_title in chapter_map:
            if ch_doc == doc_href and ch_pos <= position:
                result_id = ch_id
                result_title = ch_title
            elif ch_doc == doc_href and ch_pos > position:
                break

        return result_id, result_title

    def _extract_text_between_positions(
        self,
        current: dict[str, Any],
        next_entry: Optional[dict[str, Any]],
        spine_docs: list[str],
    ) -> str:
        """
        Extract text between two page positions.

        Args:
            current: Current page entry with doc_href and position
            next_entry: Next page entry, or None for last page
            spine_docs: List of document hrefs in spine order

        Returns:
            Extracted and cleaned text
        """
        current_doc = current.get("doc_href", "")
        current_pos = current.get("position", 0)
        current_doc_html = self.doc_content.get(current_doc, "")

        if not current_doc_html:
            return ""

        slice_html = ""

        if next_entry:
            next_doc = next_entry.get("doc_href", "")
            next_pos = next_entry.get("position", 0)

            if current_doc == next_doc:
                slice_html = current_doc_html[current_pos:next_pos]
            else:
                # Content spans multiple documents
                slice_html = current_doc_html[current_pos:]

                try:
                    idx_current = spine_docs.index(current_doc)
                    idx_next = spine_docs.index(next_doc)

                    for doc_idx in range(idx_current + 1, idx_next):
                        slice_html += self.doc_content.get(spine_docs[doc_idx], "")

                    next_doc_html = self.doc_content.get(next_doc, "")
                    slice_html += next_doc_html[:next_pos]
                except ValueError:
                    pass
        else:
            # Last page: include all remaining content
            slice_html = current_doc_html[current_pos:]

            try:
                idx_current = spine_docs.index(current_doc)
                for doc_idx in range(idx_current + 1, len(spine_docs)):
                    slice_html += self.doc_content.get(spine_docs[doc_idx], "")
            except ValueError:
                pass

        if not slice_html.strip():
            return ""

        # Parse and clean HTML
        slice_soup = BeautifulSoup(slice_html, "html.parser")

        for tag in slice_soup.find_all(["p", "div"]):
            tag.append(self.paragraph_separator)

        for tag in slice_soup.find_all(["sup", "sub"]):
            tag.decompose()

        text = clean_text(
            slice_soup.get_text(),
            preserve_single_newlines=(self.paragraph_separator == "\n"),
        ).strip()

        return text

    def extract_pages(
        self,
        page_numbers: Optional[list[str]] = None,
        deduplicate_chapter_titles: bool = True,
        skip_toc: bool = False,
    ) -> str:
        """
        Extract text from selected pages.

        Args:
            page_numbers: List of page numbers to extract. If None, extract all.
            deduplicate_chapter_titles: If True, removes duplicate chapter titles
                that appear as the first line of page content (default: True)
            skip_toc: If True, skip pages from TOC/Introduction chapter (default: False)

        Returns:
            Combined text from all selected pages with chapter titles separated
            by 4 linebreaks before the title and 2 linebreaks after.
        """
        pages = self.get_pages()

        if page_numbers is None:
            selected = pages
        else:
            selected = [p for p in pages if p.page_number in page_numbers]

        # Note: We don't filter out entire pages here anymore
        # Instead, we strip TOC content from pages below

        parts = []
        current_chapter: Optional[str] = None

        for page in selected:
            if not page.text:
                continue

            # Strip TOC content from beginning of page if requested
            page_text = page.text
            if skip_toc:
                # Check if this is a front matter chapter by title
                front_matter_keywords = {
                    "INTRODUCTION",
                    "TABLE OF CONTENTS",
                    "CONTENTS",
                    "TOC",
                    "ACKNOWLEDGEMENTS",
                    "ACKNOWLEDGMENTS",
                    "FOREWORD",
                    "PREFACE",
                }
                if (
                    page.chapter_title
                    and page.chapter_title.upper() in front_matter_keywords
                ):
                    # Skip entire page if it's a known front matter chapter
                    continue

                # First check if this is a pure TOC page (no real content)
                if self._is_toc_or_front_matter(page):
                    # Try to strip TOC and see if anything remains
                    stripped = self._strip_toc_from_page(page_text)
                    if not stripped.strip():
                        # Pure TOC page with no content - skip it
                        continue
                    # Has content after TOC - use stripped version
                    page_text = stripped
                else:
                    # Not primarily a TOC page, but might have TOC at start
                    page_text = self._strip_toc_from_page(page_text)

                # Skip page if nothing remains after stripping
                if not page_text.strip():
                    continue

            # Add chapter title when chapter changes
            if page.chapter_title and page.chapter_title != current_chapter:
                current_chapter = page.chapter_title
                # Add chapter title with proper formatting
                if parts:
                    # Not the first chapter: 4 linebreaks before title
                    parts.append(f"\n\n\n\n{current_chapter}\n\n")
                else:
                    # First chapter: no leading linebreaks
                    parts.append(f"{current_chapter}\n\n")

            # Apply title deduplication if requested
            if deduplicate_chapter_titles and page.chapter_title:
                cleaned_text = self._remove_duplicate_title_line(
                    page_text, page.chapter_title
                )
            else:
                cleaned_text = page_text

            parts.append(f"<<PAGE: {page.page_number}>>\n\n{cleaned_text}")

        return "\n\n".join(parts)

    def _is_toc_or_front_matter(self, page: Page) -> bool:
        """
        Detect if a page is likely TOC or front matter content.

        Strategy:
        1. Check if chapter title is a known front matter keyword
        2. Check if page content contains many chapter titles (indicating TOC listing)

        Args:
            page: Page object to check

        Returns:
            True if page appears to be TOC or front matter
        """
        if not page.text:
            return False

        # Check if chapter title itself is front matter
        front_matter_keywords = {
            "INTRODUCTION",
            "TABLE OF CONTENTS",
            "CONTENTS",
            "TOC",
            "ACKNOWLEDGEMENTS",
            "ACKNOWLEDGMENTS",
            "FOREWORD",
            "PREFACE",
        }

        if page.chapter_title and page.chapter_title.upper() in front_matter_keywords:
            return True

        # Build list of terms to look for in TOC
        search_terms = []

        # Add book title
        metadata = self.get_metadata()
        if metadata.title:
            search_terms.append(metadata.title.upper())

        # Add all chapter titles
        chapters = self.get_chapters()
        for chapter in chapters:
            if chapter.title:
                search_terms.append(chapter.title.upper())

        if not search_terms:
            return False

        # Check if this page contains many of these terms (indicating it's a TOC)
        text_upper = page.text[:2000].upper()  # Check first 2000 chars
        lines = text_upper.split("\n")

        # Count how many search terms appear as standalone lines
        matches = 0
        for line in lines:
            line_stripped = line.strip()
            if line_stripped in search_terms:
                matches += 1

        # If more than 3 chapter/title names appear as lines, it's likely TOC
        if matches > 3:
            return True

        return False

    def _strip_toc_from_page(self, page_text: str) -> str:
        """
        Strip TOC chapter listing from the beginning of page text.

        This removes the table of contents (list of chapter names) but keeps
        other front matter like acknowledgements, dedications, etc.

        Args:
            page_text: The page text to process

        Returns:
            Text with TOC chapter listing removed
        """
        if not page_text:
            return page_text

        # Build list of chapter titles to detect TOC
        chapters = self.get_chapters()
        chapter_titles = {ch.title.upper() for ch in chapters if ch.title}

        if not chapter_titles:
            return page_text

        lines = page_text.split("\n")
        toc_entries = []

        # Find lines that are chapter titles (exact match or at start of line)
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            line_upper = line_stripped.upper()

            # Check if line is exactly a chapter title
            if line_upper in chapter_titles and len(line_upper) < 30:
                toc_entries.append((i, line_stripped, True))  # True = exact match
            else:
                # Check if line starts with a chapter title followed by other text
                for title in chapter_titles:
                    if line_upper.startswith(title + " ") and len(title) < 30:
                        # Found chapter title at start of line
                        toc_entries.append((i, line_stripped, False))  # False = partial
                        break

        # If we found 5+ chapter titles in sequence, it's the TOC chapter listing
        if len(toc_entries) >= 5:
            # Check if they're consecutive (dense listing)
            first_idx = toc_entries[0][0]
            last_idx = toc_entries[-1][0]

            # If entries are within 3 lines per entry on average, it's a TOC
            if (last_idx - first_idx) / len(toc_entries) < 3:
                # Handle the last entry specially if it's a partial match
                last_entry_idx, last_entry_line, is_exact = toc_entries[-1]

                # Build result
                before_toc = lines[:first_idx]

                if is_exact:
                    # Last entry is exact match - skip entire line
                    after_toc = lines[last_entry_idx + 1 :]
                else:
                    # Last entry has content after chapter name - keep the remainder
                    # Find where the chapter title ends
                    line_upper = last_entry_line.upper()
                    for title in chapter_titles:
                        if line_upper.startswith(title + " "):
                            # Remove the chapter title part, keep the rest
                            remainder = last_entry_line[len(title) :].lstrip()
                            after_toc = [remainder] + lines[last_entry_idx + 1 :]
                            break
                    else:
                        after_toc = lines[last_entry_idx + 1 :]

                # Combine, skipping leading empty lines
                result_lines = before_toc
                started = False
                for line in after_toc:
                    if line.strip() or started:
                        result_lines.append(line)
                        started = True

                return "\n".join(result_lines)

        return page_text
