"""Interactive terminal reader for EPUB content."""

import signal
import sys
from dataclasses import dataclass
from typing import Optional

import click
from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from .bookmarks import Bookmark, BookmarkManager
from .models import Chapter


@dataclass
class ReaderState:
    """State returned when reader exits."""

    current_line: int
    chapter_index: int
    percentage: float
    quit_requested: bool


# Key constants for special keys
KEY_UP = "\x1b[A"
KEY_DOWN = "\x1b[B"
KEY_RIGHT = "\x1b[C"
KEY_LEFT = "\x1b[D"
KEY_PAGE_UP = "\x1b[5~"
KEY_PAGE_DOWN = "\x1b[6~"
KEY_HOME = "\x1b[H"
KEY_END = "\x1b[F"
KEY_ESC = "\x1b"

# Help text for modal
HELP_TEXT = """
[bold cyan]Navigation[/bold cyan]
  [yellow]j[/yellow] / [yellow]↓[/yellow]          Scroll down one line
  [yellow]k[/yellow] / [yellow]↑[/yellow]          Scroll up one line
  [yellow]Space[/yellow] / [yellow]PgDn[/yellow]   Next page
  [yellow]b[/yellow] / [yellow]PgUp[/yellow]       Previous page
  [yellow]n[/yellow]              Next chapter
  [yellow]p[/yellow]              Previous chapter
  [yellow]g[/yellow] / [yellow]Home[/yellow]       Go to beginning
  [yellow]G[/yellow] / [yellow]End[/yellow]        Go to end

[bold cyan]Bookmarks[/bold cyan]
  [yellow]m[/yellow]              Save bookmark
  [yellow]'[/yellow]              Jump to bookmark

[bold cyan]Other[/bold cyan]
  [yellow]h[/yellow] / [yellow]?[/yellow]          Show this help
  [yellow]q[/yellow] / [yellow]Esc[/yellow]        Quit

[dim]Press any key to close this help[/dim]
"""


class EpubReader:
    """Interactive terminal reader for EPUB content."""

    def __init__(
        self,
        content: str,
        chapters: list[Chapter],
        title: str,
        epub_path: str,
        page_size: Optional[int] = None,
        show_header: bool = True,
        show_footer: bool = True,
        start_line: int = 0,
        start_chapter: Optional[int] = None,
        bookmark_manager: Optional[BookmarkManager] = None,
        width: Optional[int] = None,
    ) -> None:
        """
        Initialize the EPUB reader.

        Args:
            content: Full text content with chapter titles separated by 4 linebreaks
            chapters: List of Chapter objects
            title: Book title
            epub_path: Path to the EPUB file (for bookmarks)
            page_size: Lines per page (None for auto-detect)
            show_header: Show header with chapter title
            show_footer: Show footer with progress
            start_line: Initial line to display
            start_chapter: Initial chapter index to jump to
            bookmark_manager: Optional bookmark manager instance
            width: Maximum content width (None for full terminal width)
        """
        self.title = title
        self.epub_path = epub_path
        self.chapters = chapters
        self.show_header = show_header
        self.show_footer = show_footer
        self.bookmark_manager = bookmark_manager or BookmarkManager()
        self._width = width

        self.console = Console()
        self._user_page_size = page_size
        self._page_size = page_size or self._calculate_page_size()

        # Process content: detect chapter boundaries and build index
        self._process_content(content)

        # Set initial position
        self.current_line = start_line
        if start_chapter is not None and 0 <= start_chapter < len(self.chapter_offsets):
            self.current_line = self.chapter_offsets[start_chapter]

        # Ensure current_line is valid
        self.current_line = max(0, min(self.current_line, len(self.lines) - 1))

        # State
        self._show_help = False
        self._message: Optional[str] = None
        self._message_style: str = "green"
        self._running = False

        # Handle terminal resize
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for terminal resize."""
        if sys.platform != "win32":
            signal.signal(signal.SIGWINCH, self._handle_resize)

    def _handle_resize(self, signum: int, frame: object) -> None:
        """Handle terminal resize signal."""
        del signum, frame  # Unused but required by signal handler signature
        if self._user_page_size is None:
            self._page_size = self._calculate_page_size()

    def _calculate_page_size(self) -> int:
        """Calculate content area height based on terminal size."""
        height = self.console.size.height
        header_size = 3 if self.show_header else 0
        footer_size = 3 if self.show_footer else 0
        # Account for content panel borders (2 lines: top + bottom)
        return max(5, height - header_size - footer_size - 4)

    def _process_content(self, content: str) -> None:
        """
        Process content, detect chapter boundaries, and build line index.

        Chapter format: A line that appears after 4+ consecutive newlines and is
        followed by 2 newlines is considered a chapter title.
        """
        # Split into lines
        raw_lines = content.split("\n")

        self.lines: list[str] = []
        self.chapter_offsets: list[int] = []  # Line index where each chapter starts
        self.chapter_titles: list[str] = []  # Title for each chapter

        # Track consecutive empty lines to detect chapter boundaries
        i = 0
        while i < len(raw_lines):
            line = raw_lines[i]

            # Check if this could be a chapter title:
            # - Has content
            # - Preceded by 4+ empty lines (or at start)
            # - Followed by 2+ empty lines
            if line.strip():
                # Count empty lines before this line
                empty_before = 0
                j = i - 1
                while j >= 0 and not raw_lines[j].strip():
                    empty_before += 1
                    j -= 1

                # Count empty lines after this line
                empty_after = 0
                j = i + 1
                while j < len(raw_lines) and not raw_lines[j].strip():
                    empty_after += 1
                    j += 1

                # Check if this is a chapter title
                # At start: no requirement for empty_before
                # Otherwise: need 4+ empty lines before
                is_chapter_title = False
                if i == 0 or (empty_before >= 4 and empty_after >= 2):
                    # Also check if next non-empty line exists (content follows)
                    next_content_idx = i + 1 + empty_after
                    if next_content_idx < len(raw_lines):
                        is_chapter_title = True

                if is_chapter_title:
                    # Record chapter start position
                    self.chapter_offsets.append(len(self.lines))
                    self.chapter_titles.append(line.strip())
                    # Don't add the title line to content (it's displayed in header)
                    # Skip the title and following empty lines
                    i += 1 + empty_after
                    continue

            # Regular line - add to content
            if line.strip():
                self.lines.append(line)

            i += 1

        # If no chapters found, create a default one
        if not self.chapter_offsets:
            self.chapter_offsets.append(0)
            self.chapter_titles.append(self.title or "Content")

    def _get_current_chapter(self) -> tuple[int, str]:
        """
        Get current chapter index and title based on line position.

        Returns:
            Tuple of (chapter_index, chapter_title)
        """
        chapter_idx = 0
        for i, offset in enumerate(self.chapter_offsets):
            if self.current_line >= offset:
                chapter_idx = i
            else:
                break
        return chapter_idx, self.chapter_titles[chapter_idx]

    def _get_progress(self) -> tuple[int, int, float]:
        """
        Get current progress.

        Returns:
            Tuple of (current_line, total_lines, percentage)
        """
        total = len(self.lines)
        if total == 0:
            return 0, 0, 0.0
        percentage = (self.current_line / max(1, total - 1)) * 100
        return self.current_line, total, percentage

    def _scroll_lines(self, delta: int) -> None:
        """Scroll by N lines."""
        new_line = self.current_line + delta
        self.current_line = max(0, min(new_line, len(self.lines) - 1))

    def _scroll_page(self, delta: int) -> None:
        """Scroll by N pages."""
        self._scroll_lines(delta * self._page_size)

    def _goto_chapter(self, chapter_idx: int) -> None:
        """Jump to chapter start."""
        if 0 <= chapter_idx < len(self.chapter_offsets):
            self.current_line = self.chapter_offsets[chapter_idx]

    def _goto_start(self) -> None:
        """Go to beginning."""
        self.current_line = 0

    def _goto_end(self) -> None:
        """Go to end."""
        self.current_line = max(0, len(self.lines) - 1)

    def _save_bookmark(self) -> None:
        """Save current position as bookmark."""
        chapter_idx, _ = self._get_current_chapter()
        _, total, percentage = self._get_progress()

        bookmark = Bookmark.create(
            chapter_index=chapter_idx,
            line_offset=self.current_line,
            percentage=percentage,
            title=self.title,
        )
        self.bookmark_manager.save(self.epub_path, bookmark)
        self._message = "Bookmark saved"
        self._message_style = "green"

    def _load_bookmark(self) -> None:
        """Load and jump to bookmark."""
        bookmark = self.bookmark_manager.load(self.epub_path)
        if bookmark:
            self.current_line = min(bookmark.line_offset, len(self.lines) - 1)
            self._message = f"Jumped to bookmark ({bookmark.percentage:.1f}%)"
            self._message_style = "green"
        else:
            self._message = "No bookmark found"
            self._message_style = "yellow"

    def _read_key(self) -> str:
        """
        Read a key, handling escape sequences for special keys.

        Returns:
            Key string (may be multi-character for special keys)
        """
        char = click.getchar()

        # Handle escape sequences
        if char == "\x1b":
            # Try to read more characters for escape sequences
            try:
                # Use a short timeout approach - read what's available
                import select

                if sys.platform != "win32":
                    # On Unix, check if more input is available
                    if select.select([sys.stdin], [], [], 0.05)[0]:
                        char += click.getchar()
                        if char[-1] == "[":
                            # CSI sequence - read more
                            if select.select([sys.stdin], [], [], 0.05)[0]:
                                char += click.getchar()
                                # Handle sequences like [5~ (Page Up)
                                if char[-1].isdigit():
                                    if select.select([sys.stdin], [], [], 0.05)[0]:
                                        char += click.getchar()
                else:
                    # On Windows, just try to read more
                    char += click.getchar()
                    if len(char) > 1 and char[-1] == "[":
                        char += click.getchar()
            except Exception:
                pass

        return char

    def _handle_key(self, key: str) -> bool:
        """
        Handle keyboard input.

        Args:
            key: Key string

        Returns:
            False to quit, True to continue
        """
        # Clear any previous message
        self._message = None

        # Help toggle
        if self._show_help:
            self._show_help = False
            return True

        # Quit
        if key in ("q", "Q", KEY_ESC):
            return False

        # Help
        if key in ("h", "H", "?"):
            self._show_help = True
            return True

        # Navigation - line
        if key in ("j", KEY_DOWN):
            self._scroll_lines(1)
        elif key in ("k", KEY_UP):
            self._scroll_lines(-1)

        # Navigation - page
        elif key in (" ", KEY_PAGE_DOWN):
            self._scroll_page(1)
        elif key in ("b", KEY_PAGE_UP):
            self._scroll_page(-1)

        # Navigation - chapter
        elif key == "n":
            chapter_idx, _ = self._get_current_chapter()
            self._goto_chapter(chapter_idx + 1)
        elif key == "p":
            chapter_idx, _ = self._get_current_chapter()
            self._goto_chapter(max(0, chapter_idx - 1))

        # Navigation - document
        elif key in ("g", KEY_HOME):
            self._goto_start()
        elif key in ("G", KEY_END):
            self._goto_end()

        # Bookmarks
        elif key == "m":
            self._save_bookmark()
        elif key == "'":
            self._load_bookmark()

        return True

    def _get_effective_width(self) -> Optional[int]:
        """Get effective content width, capped by terminal width."""
        if self._width is None:
            return None
        # Cap width to terminal width minus some padding for borders
        terminal_width = self.console.size.width
        return min(self._width, terminal_width - 4)

    def _get_content_width(self) -> int:
        """Get the actual content width (for line wrapping calculations)."""
        effective = self._get_effective_width()
        if effective is not None:
            # Subtract panel borders (2 chars)
            return max(10, effective - 2)
        # Use terminal width minus panel borders
        return max(10, self.console.size.width - 4)

    def _count_visual_lines(self, text: str) -> int:
        """Count how many visual lines a text string will occupy after wrapping."""
        if not text:
            return 1
        content_width = self._get_content_width()
        # Calculate wrapped lines
        return max(1, (len(text) + content_width - 1) // content_width)

    def _render_header(self) -> Panel:
        """Render header with chapter title and progress."""
        chapter_idx, chapter_title = self._get_current_chapter()
        total_chapters = len(self.chapter_offsets)

        header_text = Text()
        header_text.append(f"  {chapter_title}", style="bold white")
        header_text.append(
            f"  [Chapter {chapter_idx + 1}/{total_chapters}]", style="dim cyan"
        )

        return Panel(
            header_text,
            style="cyan",
            height=3,
            width=self._get_effective_width(),
        )

    def _render_footer(self) -> Panel:
        """Render footer with line numbers, percentage, and key hints."""
        current, total, percentage = self._get_progress()

        footer_parts = []

        # Line info - calculate visible range accounting for wrapping
        target_visual_before = self._page_size // 2
        visual_before = 0
        start = current

        while start > 0 and visual_before < target_visual_before:
            start -= 1
            visual_before += self._count_visual_lines(self.lines[start])

        visual_total = 0
        end = start
        while end < total and visual_total < self._page_size:
            visual_total += self._count_visual_lines(self.lines[end])
            end += 1

        while start > 0 and visual_total < self._page_size:
            start -= 1
            visual_total += self._count_visual_lines(self.lines[start])

        footer_parts.append(f"Lines {start + 1}-{end}/{total}")

        # Percentage
        footer_parts.append(f"{percentage:.1f}%")

        # Message or key hints
        if self._message:
            footer_parts.append(f"[{self._message_style}]{self._message}[/]")
        else:
            footer_parts.append("[dim][q]uit [h]elp[/dim]")

        footer_text = "  |  ".join(footer_parts)

        return Panel(
            Text.from_markup(f"  {footer_text}"),
            style="cyan",
            height=3,
            width=self._get_effective_width(),
        )

    def _render_content(self) -> Panel:
        """Render content area with current page, centered on current line."""
        # Calculate which lines to display, accounting for line wrapping
        # We need to find lines that fit in _page_size visual lines

        # First, find the start position by going backwards from current_line
        # to fill roughly half the page
        target_visual_before = self._page_size // 2
        visual_before = 0
        start = self.current_line

        while start > 0 and visual_before < target_visual_before:
            start -= 1
            visual_before += self._count_visual_lines(self.lines[start])
            # Account for chapter separator
            if start in self.chapter_offsets:
                visual_before += 1

        # Now collect lines going forward until we fill the page
        visual_total = 0
        end = start

        while end < len(self.lines) and visual_total < self._page_size:
            # Account for chapter separator
            if end in self.chapter_offsets:
                visual_total += 1
            visual_total += self._count_visual_lines(self.lines[end])
            end += 1

        # If we didn't fill the page and there's room at the start, go back more
        while start > 0 and visual_total < self._page_size:
            start -= 1
            visual_total += self._count_visual_lines(self.lines[start])
            if start in self.chapter_offsets:
                visual_total += 1

        # Get lines for display
        display_lines = self.lines[start:end]

        # Build chapter separator line
        content_width = self._get_content_width()
        chapter_sep = "\u2500" * min(content_width, 40)  # ─ horizontal line

        # Build content with line highlighting and chapter markers
        content_text = Text()
        for i, line in enumerate(display_lines):
            line_num = start + i

            # Add chapter separator if this line starts a chapter
            if line_num in self.chapter_offsets:
                # Chapter title available via self.chapter_titles but not displayed here
                content_text.append(f"{chapter_sep}\n", style="dim cyan")

            # Highlight current line subtly
            if line_num == self.current_line:
                content_text.append(f"{line}\n", style="bold")
            else:
                content_text.append(f"{line}\n")

        return Panel(
            content_text,
            border_style="dim",
            width=self._get_effective_width(),
        )

    def _render_help_overlay(self) -> Panel:
        """Render help modal overlay."""
        return Panel(
            Align.center(Text.from_markup(HELP_TEXT)),
            title="[bold]Help[/bold]",
            border_style="yellow",
            width=50,
        )

    def _render_page(self) -> Layout:
        """Render the full page layout."""
        layout = Layout()

        # Get panels
        header = (
            Align.center(self._render_header())
            if self._width
            else self._render_header()
        )
        footer = (
            Align.center(self._render_footer())
            if self._width
            else self._render_footer()
        )
        content = self._render_content()
        content_centered = Align.center(content) if self._width else content

        if self.show_header and self.show_footer:
            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="body"),
                Layout(name="footer", size=3),
            )
            layout["header"].update(header)
            layout["footer"].update(footer)
        elif self.show_header:
            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="body"),
            )
            layout["header"].update(header)
        elif self.show_footer:
            layout.split_column(
                Layout(name="body"),
                Layout(name="footer", size=3),
            )
            layout["footer"].update(footer)
        else:
            layout.split_column(Layout(name="body"))

        # Render body content or help overlay
        if self._show_help:
            # Show help centered over content
            help_panel = self._render_help_overlay()
            layout["body"].update(
                Group(
                    content_centered,
                    Align.center(help_panel, vertical="middle"),
                )
            )
        else:
            layout["body"].update(content_centered)

        return layout

    def run(self) -> ReaderState:
        """
        Run the interactive reader.

        Returns:
            ReaderState with final position
        """
        self._running = True

        try:
            with Live(
                self._render_page(),
                console=self.console,
                screen=True,
                auto_refresh=False,
            ) as live:
                while self._running:
                    # Update display
                    live.update(self._render_page())
                    live.refresh()

                    # Read and handle key
                    key = self._read_key()
                    if not self._handle_key(key):
                        break

                    # Recalculate page size in case terminal was resized
                    if self._user_page_size is None:
                        self._page_size = self._calculate_page_size()

        except KeyboardInterrupt:
            pass

        chapter_idx, _ = self._get_current_chapter()
        _, _, percentage = self._get_progress()

        return ReaderState(
            current_line=self.current_line,
            chapter_index=chapter_idx,
            percentage=percentage,
            quit_requested=True,
        )
