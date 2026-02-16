"""
Helper functions for cleanup command.

This module contains extracted functions from cleanup.py to improve
maintainability and testability.
"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table


def get_knowledge_bases(vector_db_dir: Path) -> List[Path]:
    """
    Get list of all knowledge base directories.

    Args:
        vector_db_dir: Path to vector database directory

    Returns:
        List of knowledge base directories, sorted by modification time (newest first)
    """
    if not vector_db_dir.exists():
        return []

    kb_dirs = [d for d in vector_db_dir.iterdir() if d.is_dir()]

    # Sort by modification time (newest first)
    kb_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    return kb_dirs


def create_kb_table(
    kb_dirs: List[Path],
    get_dir_size_fn,
    format_size_fn,
    show_numbers: bool = False
) -> Tuple[Table, int]:
    """
    Create a Rich table showing knowledge bases.

    Args:
        kb_dirs: List of knowledge base directories
        get_dir_size_fn: Function to get directory size
        format_size_fn: Function to format size
        show_numbers: Whether to show row numbers (for interactive mode)

    Returns:
        Tuple of (table, total_size)
    """
    table = Table(show_header=True, header_style="bold magenta")

    if show_numbers:
        table.add_column("No.", style="cyan", width=4)

    table.add_column("Name", style="green")
    table.add_column("Size", style="yellow")
    table.add_column("Modified", style="cyan")

    total_size = 0
    for i, kb_dir in enumerate(kb_dirs, 1):
        size = get_dir_size_fn(kb_dir)
        total_size += size
        name = kb_dir.name
        modified = datetime.fromtimestamp(kb_dir.stat().st_mtime).strftime(
            "%Y-%m-%d %H:%M"
        )

        if show_numbers:
            table.add_row(str(i), name, format_size_fn(size), modified)
        else:
            table.add_row(name, format_size_fn(size), modified)

    return table, total_size


def parse_user_selection(choice: str, max_items: int) -> List[int]:
    """
    Parse user selection string into list of indices.

    Args:
        choice: User input (e.g., "1,3,5" or "1-3,5")
        max_items: Maximum number of items

    Returns:
        List of zero-based indices

    Raises:
        ValueError: If selection is invalid
    """
    if not choice.strip():
        return []

    indices = []
    parts = choice.split(",")

    for part in parts:
        part = part.strip()
        if "-" in part:
            # Range: "1-3"
            start, end = part.split("-", 1)
            start_idx = int(start.strip()) - 1
            end_idx = int(end.strip()) - 1

            if not (0 <= start_idx < max_items and 0 <= end_idx < max_items):
                raise ValueError(f"Range {part} out of bounds")

            indices.extend(range(start_idx, end_idx + 1))
        else:
            # Single number: "1"
            idx = int(part) - 1
            if not (0 <= idx < max_items):
                raise ValueError(f"Number {part} out of bounds")
            indices.append(idx)

    # Remove duplicates and sort
    return sorted(set(indices))


def delete_knowledge_bases(
    kb_dirs: List[Path], console: Console
) -> Tuple[int, int]:
    """
    Delete knowledge base directories.

    Args:
        kb_dirs: List of directories to delete
        console: Rich console for output

    Returns:
        Tuple of (deleted_count, failed_count)
    """
    deleted_count = 0
    failed_count = 0

    for kb_dir in kb_dirs:
        try:
            shutil.rmtree(kb_dir)
            deleted_count += 1
            console.print(f"[red]✗[/red] Deleted: {kb_dir.name}")
        except Exception as e:
            failed_count += 1
            console.print(
                f"[yellow]⚠️  Failed to delete {kb_dir.name}: {e}[/yellow]"
            )

    return deleted_count, failed_count


def confirm_deletion_all(
    kb_dirs: List[Path],
    console: Console,
    get_dir_size_fn,
    format_size_fn,
) -> bool:
    """
    Show confirmation dialog for deleting all KBs.

    Args:
        kb_dirs: List of all knowledge base directories
        console: Rich console for output
        get_dir_size_fn: Function to get directory size
        format_size_fn: Function to format size

    Returns:
        True if user confirms, False otherwise
    """
    console.print(
        f"[bold red]⚠️  WARNING: This will delete ALL {len(kb_dirs)} knowledge bases![/bold red]\n"
    )

    table, total_size = create_kb_table(
        kb_dirs, get_dir_size_fn, format_size_fn, show_numbers=False
    )

    console.print(table)
    console.print(f"\n[bold]Total size: {format_size_fn(total_size)}[/bold]\n")

    return Confirm.ask(
        "[bold red]Are you SURE you want to delete ALL knowledge bases?[/bold red]",
        default=False,
    )


def interactive_selection(
    kb_dirs: List[Path],
    console: Console,
    get_dir_size_fn,
    format_size_fn,
) -> List[Path]:
    """
    Interactive selection of knowledge bases to delete.

    Args:
        kb_dirs: List of all knowledge base directories
        console: Rich console for output
        get_dir_size_fn: Function to get directory size
        format_size_fn: Function to format size

    Returns:
        List of selected knowledge base directories
    """
    console.print("[bold cyan]📚 Available Knowledge Bases[/bold cyan]\n")

    table, _ = create_kb_table(
        kb_dirs, get_dir_size_fn, format_size_fn, show_numbers=True
    )

    console.print(table)
    console.print()

    # Tips
    console.print(
        "[dim]💡 Tip: You can select multiple numbers separated by commas (e.g., 1,3,5)[/dim]"
    )
    console.print("[dim]💡 Tip: Use '--all' flag to delete all at once[/dim]\n")

    choice = Prompt.ask(
        "[bold]Select knowledge base number(s) to delete[/bold] (or press Enter to cancel)",
        default="",
    )

    if not choice:
        return []

    try:
        selected_indices = parse_user_selection(choice, len(kb_dirs))
        selected_kbs = [kb_dirs[i] for i in selected_indices]

        if not selected_kbs:
            console.print("\n[yellow]⚠️  No valid selections[/yellow]\n")
            return []

        # Show what will be deleted
        console.print("\n[bold red]⚠️  The following will be deleted:[/bold red]\n")
        total_size = 0
        for kb_dir in selected_kbs:
            size = get_dir_size_fn(kb_dir)
            total_size += size
            console.print(f"  • {kb_dir.name} ({format_size_fn(size)})")

        console.print(f"\n[bold]Total size to free: {format_size_fn(total_size)}[/bold]\n")

        # Confirm
        if not Confirm.ask("[bold]Proceed with deletion?[/bold]", default=False):
            return []

        return selected_kbs

    except (ValueError, IndexError) as e:
        console.print(f"\n[red]❌ Invalid selection: {e}[/red]\n")
        return []


def display_cleanup_results(
    deleted_count: int,
    total_size: int,
    console: Console,
    format_size_fn,
) -> None:
    """
    Display results after cleanup.

    Args:
        deleted_count: Number of KBs deleted
        total_size: Total size freed
        console: Rich console for output
        format_size_fn: Function to format size
    """
    console.print(f"\n[green]✓ Deleted {deleted_count} knowledge base(s)[/green]")
    console.print(f"[green]✓ Freed up {format_size_fn(total_size)}[/green]\n")
