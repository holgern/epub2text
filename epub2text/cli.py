"""
Command-line interface for epub2text.
"""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.tree import Tree

from . import __version__
from .cleaner import TextCleaner
from .formatters import format_paragraphs, format_sentences, split_long_lines
from .models import Chapter
from .parser import EPUBParser

console = Console()


def parse_chapter_range(range_str: str) -> list[int]:
    """
    Parse chapter range string like "1-5,7,9-12" into list of indices.

    Args:
        range_str: Range string (e.g., "1-5,7,9-12")

    Returns:
        List of chapter indices (0-based)
    """
    indices: set[int] = set()
    parts = range_str.split(",")
    for part in parts:
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            start_idx = int(start.strip()) - 1  # Convert to 0-based
            end_idx = int(end.strip()) - 1
            indices.update(range(start_idx, end_idx + 1))
        else:
            indices.add(int(part) - 1)  # Convert to 0-based
    # Use sorted() directly on the set instead of converting to list first
    return sorted(indices)


def display_chapters_tree(chapters: list[Chapter]) -> None:
    """Display chapters in a tree structure."""
    tree = Tree("📚 [bold]Chapters[/bold]")

    # Build tree structure
    chapter_nodes = {}
    for chapter in chapters:
        # Create label with character count
        label = (
            f"[cyan]{chapter.title}[/cyan] [dim]({chapter.char_count:,} chars)[/dim]"
        )

        if chapter.parent_id is None:
            # Top-level chapter
            node = tree.add(label)
            chapter_nodes[chapter.id] = node
        else:
            # Nested chapter
            parent_node = chapter_nodes.get(chapter.parent_id)
            if parent_node:
                node = parent_node.add(label)
                chapter_nodes[chapter.id] = node
            else:
                # Fallback: add to root if parent not found
                node = tree.add(label)
                chapter_nodes[chapter.id] = node

    console.print(tree)


def display_chapters_table(chapters: list[Chapter]) -> None:
    """Display chapters in a table format."""
    table = Table(title="📚 Chapters", show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=6)
    table.add_column("Title", style="cyan")
    table.add_column("Characters", justify="right", style="green")
    table.add_column("Level", justify="center", style="yellow")

    for idx, chapter in enumerate(chapters, 1):
        indent = "  " * (chapter.level - 1)
        title = f"{indent}{chapter.title}"
        table.add_row(str(idx), title, f"{chapter.char_count:,}", str(chapter.level))

    console.print(table)


def interactive_chapter_selection(chapters: list[Chapter]) -> list[str]:
    """
    Interactively select chapters using rich prompts.

    Args:
        chapters: List of all chapters

    Returns:
        List of selected chapter IDs
    """
    console.print("\n[bold]Interactive Chapter Selection[/bold]")
    console.print(
        "Enter chapter numbers or ranges (e.g., '1-5,7,9-12'), "
        "or 'all' for all chapters:"
    )

    while True:
        selection = Prompt.ask("\n[cyan]Chapters to extract[/cyan]", default="all")

        if selection.lower() == "all":
            return [ch.id for ch in chapters]

        try:
            indices = parse_chapter_range(selection)
            # Validate indices
            valid_indices = [i for i in indices if 0 <= i < len(chapters)]
            if not valid_indices:
                console.print("[red]No valid chapter indices found. Try again.[/red]")
                continue

            selected_chapters = [chapters[i] for i in valid_indices]

            # Show selection summary
            console.print(
                f"\n[green]Selected {len(selected_chapters)} chapter(s):[/green]"
            )
            for chapter in selected_chapters:
                console.print(f"  • {chapter.title}")

            if Confirm.ask("\nProceed with this selection?", default=True):
                return [ch.id for ch in selected_chapters]

        except (ValueError, IndexError) as e:
            console.print(f"[red]Invalid input: {e}. Try again.[/red]")


@click.group()
@click.version_option(version=__version__, prog_name="epub2text")
def cli() -> None:
    """
    epub2text - Extract text from EPUB files with smart cleaning.

    A niche CLI tool for extracting and processing text from EPUB files.
    """
    pass


@cli.command(name="list")
@click.argument("filepath", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format",
    "-f",
    type=click.Choice(["table", "tree"]),
    default="table",
    help="Display format for chapters",
)
def list_chapters(filepath: Path, format: str) -> None:
    """List all chapters in an EPUB file."""
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(f"Loading {filepath.name}...", total=None)
            parser = EPUBParser(str(filepath))
            chapters = parser.get_chapters()
            progress.stop()

        if not chapters:
            console.print("[yellow]No chapters found in EPUB file.[/yellow]")
            return

        console.print(
            f"\n[bold]Found {len(chapters)} chapter(s) in {filepath.name}[/bold]\n"
        )

        if format == "tree":
            display_chapters_tree(chapters)
        else:
            display_chapters_table(chapters)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("filepath", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file path (default: stdout)",
)
@click.option("--chapters", "-c", type=str, help="Chapter range (e.g., '1-5,7,9-12')")
@click.option("--interactive", "-i", is_flag=True, help="Interactive chapter selection")
@click.option(
    "--paragraphs",
    "-p",
    is_flag=True,
    help="One line per paragraph (collapse internal line breaks)",
)
@click.option(
    "--sentences",
    "-s",
    is_flag=True,
    help="One line per sentence (uses spaCy)",
)
@click.option(
    "--max-length",
    "-m",
    type=int,
    default=None,
    help="Split lines exceeding N chars at clause boundaries (uses spaCy)",
)
@click.option(
    "--empty-lines",
    is_flag=True,
    help="Use empty lines between paragraphs (instead of default separator)",
)
@click.option(
    "--separator",
    type=str,
    default="  ",
    help="Paragraph separator prepended to new paragraphs (default: two spaces)",
)
@click.option("--raw", is_flag=True, help="Disable all text cleaning")
@click.option(
    "--keep-footnotes", is_flag=True, help="Keep bracketed footnotes like [1]"
)
@click.option("--keep-page-numbers", is_flag=True, help="Keep page numbers")
@click.option(
    "--no-markers",
    is_flag=True,
    help="Hide <<CHAPTER: ...>> markers from output",
)
@click.option(
    "--language-model",
    "-l",
    type=str,
    default="en_core_web_sm",
    help="spaCy language model (default: en_core_web_sm)",
)
@click.option(
    "--offset",
    type=int,
    default=0,
    help="Skip the first N lines of output",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Limit output to N lines",
)
@click.option(
    "--line-numbers",
    "-n",
    is_flag=True,
    help="Add line numbers to output",
)
def extract(
    filepath: Path,
    output: Optional[Path],
    chapters: Optional[str],
    interactive: bool,
    paragraphs: bool,
    sentences: bool,
    max_length: Optional[int],
    empty_lines: bool,
    separator: str,
    raw: bool,
    keep_footnotes: bool,
    keep_page_numbers: bool,
    no_markers: bool,
    language_model: str,
    offset: int,
    limit: Optional[int],
    line_numbers: bool,
) -> None:
    """
    Extract text from EPUB file.

    By default, extracts all chapters with smart cleaning. Paragraphs are
    separated by a separator (default: two spaces at start of new paragraph).

    Examples:

        epub2text extract book.epub

        epub2text extract book.epub --paragraphs --sentences

        epub2text extract book.epub --max-length 80

        epub2text extract book.epub -o output.txt --chapters 1-5
    """
    try:
        # Determine effective separator
        effective_separator = "" if empty_lines else separator

        # Load EPUB - always use double newlines for paragraph detection
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(f"Loading {filepath.name}...", total=None)
            parser = EPUBParser(str(filepath), paragraph_separator="\n\n")
            all_chapters = parser.get_chapters()
            progress.stop()

        if not all_chapters:
            console.print("[yellow]No chapters found in EPUB file.[/yellow]")
            return

        # Determine which chapters to extract
        chapter_ids = None
        if interactive:
            display_chapters_table(all_chapters)
            chapter_ids = interactive_chapter_selection(all_chapters)
        elif chapters:
            try:
                indices = parse_chapter_range(chapters)
                chapter_ids = [
                    all_chapters[i].id for i in indices if 0 <= i < len(all_chapters)
                ]
            except (ValueError, IndexError) as e:
                console.print(f"[red]Invalid chapter range: {e}[/red]")
                sys.exit(1)

        # Extract text
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Extracting chapters...", total=None)
            text = parser.extract_chapters(chapter_ids)
            progress.stop()

        # Remove chapter markers if requested (do this early)
        if no_markers:
            import re

            text = re.sub(r"<<CHAPTER:[^>]*>>\n*", "", text)

        # Apply cleaning if enabled
        if not raw:
            cleaner = TextCleaner(
                remove_footnotes=not keep_footnotes,
                remove_page_numbers=not keep_page_numbers,
                preserve_single_newlines=True,  # Keep structure for formatting
            )
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("Cleaning text...", total=None)
                text = cleaner.clean(text)
                progress.stop()

        # Apply formatting based on options
        if sentences:
            # One sentence per line
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("Formatting sentences...", total=None)
                try:
                    text = format_sentences(
                        text,
                        separator=effective_separator,
                        language_model=language_model,
                    )
                except (ImportError, OSError) as e:
                    console.print(f"[red]Error: {e}[/red]")
                    sys.exit(1)
                progress.stop()
        elif paragraphs or not empty_lines:
            # Format paragraphs with separator
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("Formatting paragraphs...", total=None)
                text = format_paragraphs(
                    text,
                    separator=effective_separator,
                    one_line_per_paragraph=paragraphs,
                )
                progress.stop()

        # Apply max-length splitting if requested
        if max_length is not None:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("Splitting long lines...", total=None)
                try:
                    text = split_long_lines(
                        text,
                        max_length=max_length,
                        separator=effective_separator,
                        language_model=language_model,
                    )
                except (ImportError, OSError) as e:
                    console.print(f"[red]Error: {e}[/red]")
                    sys.exit(1)
                progress.stop()

        # Apply offset and limit to lines
        if offset > 0 or limit is not None or line_numbers:
            lines = text.splitlines()
            total_lines = len(lines)

            # Apply offset
            if offset > 0:
                if offset >= total_lines:
                    lines = []
                else:
                    lines = lines[offset:]

            # Apply limit
            if limit is not None and limit > 0:
                lines = lines[:limit]

            # Add line numbers if requested
            if line_numbers:
                start_line = offset + 1
                end_line = start_line + len(lines)
                width = len(str(end_line))
                lines = [
                    f"{start_line + i:{width}d}\t{line}" for i, line in enumerate(lines)
                ]

            text = "\n".join(lines)

        # Output
        if output:
            output.write_text(text, encoding="utf-8")
            console.print(
                f"\n[green]✓[/green] Extracted {len(text):,} characters to {output}"
            )
        else:
            # Write to stdout (bypass rich console)
            print(text)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("filepath", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format",
    "-f",
    type=click.Choice(["panel", "table", "json"]),
    default="panel",
    help="Display format for metadata (default: panel)",
)
def info(filepath: Path, format: str) -> None:
    """Display metadata information about an EPUB file."""
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(f"Loading {filepath.name}...", total=None)
            parser = EPUBParser(str(filepath))
            metadata = parser.get_metadata()
            chapters = parser.get_chapters()
            progress.stop()

        # Calculate summary stats
        total_chars = sum(ch.char_count for ch in chapters)

        if format == "table":
            # Display as table
            table = Table(
                title=f"📖 {filepath.name}",
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="white")

            if metadata.title:
                table.add_row("Title", metadata.title)
            if metadata.authors:
                table.add_row("Authors", ", ".join(metadata.authors))
            if metadata.contributors:
                table.add_row("Contributors", ", ".join(metadata.contributors))
            if metadata.publisher:
                table.add_row("Publisher", metadata.publisher)
            if metadata.publication_year:
                table.add_row("Year", metadata.publication_year)
            if metadata.identifier:
                table.add_row("Identifier", metadata.identifier)
            if metadata.language:
                table.add_row("Language", metadata.language)
            if metadata.rights:
                table.add_row("Rights", metadata.rights)
            if metadata.coverage:
                table.add_row("Coverage", metadata.coverage)
            if metadata.description:
                desc = (
                    metadata.description[:200] + "..."
                    if len(metadata.description) > 200
                    else metadata.description
                )
                table.add_row("Description", desc)
            table.add_row("Chapters", str(len(chapters)))
            table.add_row("Total Characters", f"{total_chars:,}")

            console.print(table)
        elif format == "json":
            # Display as JSON
            import json

            data = {
                "file": filepath.name,
                "title": metadata.title,
                "authors": metadata.authors,
                "contributors": metadata.contributors,
                "publisher": metadata.publisher,
                "publication_year": metadata.publication_year,
                "identifier": metadata.identifier,
                "language": metadata.language,
                "rights": metadata.rights,
                "coverage": metadata.coverage,
                "description": metadata.description,
                "chapters": len(chapters),
                "total_characters": total_chars,
            }
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            # Display as panel (default)
            info_lines = []
            if metadata.title:
                info_lines.append(f"[bold]Title:[/bold] {metadata.title}")
            if metadata.authors:
                authors_str = ", ".join(metadata.authors)
                info_lines.append(f"[bold]Authors:[/bold] {authors_str}")
            if metadata.contributors:
                contributors_str = ", ".join(metadata.contributors)
                info_lines.append(f"[bold]Contributors:[/bold] {contributors_str}")
            if metadata.publisher:
                info_lines.append(f"[bold]Publisher:[/bold] {metadata.publisher}")
            if metadata.publication_year:
                info_lines.append(f"[bold]Year:[/bold] {metadata.publication_year}")
            if metadata.identifier:
                info_lines.append(f"[bold]Identifier:[/bold] {metadata.identifier}")
            if metadata.language:
                info_lines.append(f"[bold]Language:[/bold] {metadata.language}")
            if metadata.rights:
                info_lines.append(f"[bold]Rights:[/bold] {metadata.rights}")
            if metadata.coverage:
                info_lines.append(f"[bold]Coverage:[/bold] {metadata.coverage}")
            if metadata.description:
                desc = (
                    metadata.description[:200] + "..."
                    if len(metadata.description) > 200
                    else metadata.description
                )
                info_lines.append(f"[bold]Description:[/bold] {desc}")

            info_lines.append(f"\n[bold]Chapters:[/bold] {len(chapters)}")
            info_lines.append(f"[bold]Total Characters:[/bold] {total_chars:,}")

            panel = Panel(
                "\n".join(info_lines), title=f"📖 {filepath.name}", border_style="cyan"
            )
            console.print(panel)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


def main() -> None:
    """Main entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
