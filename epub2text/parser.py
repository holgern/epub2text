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
from .models import Chapter, Metadata

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

    def get_chapters(self) -> list[Chapter]:
        """
        Extract all chapters from the EPUB using navigation.

        Returns:
            List of Chapter objects
        """
        # First, process the navigation structure
        self._process_epub_content_nav()

        # Convert the navigation structure to Chapter objects
        chapters: list[Chapter] = []
        self._build_chapters_from_nav(self.processed_nav_structure, chapters, level=1)

        return chapters

    def _build_chapters_from_nav(
        self,
        nav_structure: list[dict[str, Any]],
        chapters: list[Chapter],
        parent_id: Optional[str] = None,
        level: int = 1,
    ) -> None:
        """
        Recursively build Chapter objects from navigation structure.

        Args:
            nav_structure: List of navigation entries
            chapters: List to append Chapter objects to
            parent_id: ID of parent chapter (for nested chapters)
            level: Depth level in the chapter hierarchy
        """
        for _idx, entry in enumerate(nav_structure):
            src: Optional[str] = entry.get("src")
            title: str = entry.get("title", "Untitled")
            children: list[dict[str, Any]] = entry.get("children", [])

            # Generate a unique ID for this chapter
            chapter_id = src if src else f"chapter_{len(chapters)}"

            # Get the text content if available
            text = self.content_texts.get(src, "") if src else ""
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
                    children, chapters, parent_id=chapter_id, level=level + 1
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
                except Exception:
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
                    except Exception:
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
                except Exception:
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
                    start = int(ol.get("start", 1))
                    for i, li in enumerate(ol.find_all("li", recursive=False)):
                        number_text = f"{start + i}) "
                        if li.string:
                            li.string.replace_with(number_text + li.string)
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

    def extract_chapters(self, chapter_ids: Optional[list[str]] = None) -> str:
        """
        Extract text from selected chapters.

        Args:
            chapter_ids: List of chapter IDs to extract. If None, extract all.

        Returns:
            Combined text from all selected chapters
        """
        chapters = self.get_chapters()

        if chapter_ids is None:
            # Extract all chapters
            selected = chapters
        else:
            # Filter by chapter IDs
            selected = [ch for ch in chapters if ch.id in chapter_ids]

        # Combine text with chapter markers
        parts = []
        for chapter in selected:
            if chapter.text:
                parts.append(f"<<CHAPTER: {chapter.title}>>\n\n{chapter.text}")

        return "\n\n".join(parts)
