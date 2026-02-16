"""
Cleanup command - Delete knowledge bases to free up disk space.

This is the REFACTORED version demonstrating improved code structure.
"""

from pathlib import Path

import click

from lecture_forge.cli.utils import console, format_size, get_dir_size
from lecture_forge.cli.utils.base_command import BaseCommand
from lecture_forge.cli.commands.cleanup_helpers import (
    confirm_deletion_all,
    create_kb_table,
    delete_knowledge_bases,
    display_cleanup_results,
    get_knowledge_bases,
    interactive_selection,
)
from lecture_forge.config import Config


@click.command()
@click.option(
    "--all",
    "-a",
    is_flag=True,
    help="Delete ALL knowledge bases without confirmation (DANGEROUS)",
)
def cleanup_refactored(all: bool) -> None:
    """
    Delete knowledge bases to free up disk space.

    Manage ChromaDB vector databases created during lecture generation.
    Interactive mode allows selective deletion, while --all flag removes
    everything (use with caution).

    \b
    What Gets Deleted:
      • Vector DB directories (data/vector_db/*)
      • Embeddings and metadata
      • Text chunks and indexes

    \b
    What's Preserved:
      • Generated HTML lecture files (outputs/)
      • Original source files (PDFs, etc.)
      • Configuration files

    \b
    Examples:
      # Interactive selection (recommended)
      $ lecture-forge cleanup

      # Delete all (dangerous - no confirmation!)
      $ lecture-forge cleanup --all

    \b
    Interactive Mode:
      1. Shows list of all knowledge bases
      2. Displays size and creation date
      3. Allows selection of which to delete
      4. Confirms before deletion

    \b
    Typical Sizes:
      • 60-min lecture: ~50MB vector DB
      • 180-min lecture: ~150MB vector DB

    \b
    Note:
      Knowledge bases are needed for 'lecture-forge chat' command.
      Deleting a KB means you can't do Q&A for that lecture anymore.

    \b
    Warning:
      Using --all flag deletes EVERYTHING without confirmation!
      Make sure you have backups if needed.
    """
    cmd = BaseCommand(console)

    # Step 1: Show banner
    console.print("\n[bold red]🗑️  Knowledge Base Cleanup[/bold red]")
    console.print("━" * 50 + "\n")

    # Step 2: Get knowledge bases
    vector_db_dir = Path(Config.VECTOR_DB_PATH)
    kb_dirs = get_knowledge_bases(vector_db_dir)

    if not kb_dirs:
        _show_no_knowledge_bases(vector_db_dir)
        return

    # Step 3: Execute cleanup (--all or interactive)
    if all:
        _cleanup_all_mode(kb_dirs)
    else:
        _cleanup_interactive_mode(kb_dirs)


def _show_no_knowledge_bases(vector_db_dir: Path) -> None:
    """Show message when no knowledge bases found."""
    console.print(
        f"[yellow]⚠️  No knowledge bases found at {vector_db_dir}[/yellow]\n"
    )


def _cleanup_all_mode(kb_dirs: list[Path]) -> None:
    """
    Handle --all mode: delete all knowledge bases after confirmation.

    Args:
        kb_dirs: List of knowledge base directories
    """
    # Confirm deletion
    if not confirm_deletion_all(kb_dirs, console, get_dir_size, format_size):
        console.print("\n[green]✓ Cancelled[/green]\n")
        return

    # Calculate total size before deletion
    total_size = sum(get_dir_size(kb_dir) for kb_dir in kb_dirs)

    # Delete all
    deleted_count, _ = delete_knowledge_bases(kb_dirs, console)

    # Show results
    display_cleanup_results(deleted_count, total_size, console, format_size)


def _cleanup_interactive_mode(kb_dirs: list[Path]) -> None:
    """
    Handle interactive mode: let user select which KBs to delete.

    Args:
        kb_dirs: List of knowledge base directories
    """
    # Get user selection
    selected_kbs = interactive_selection(kb_dirs, console, get_dir_size, format_size)

    if not selected_kbs:
        console.print("\n[green]✓ Cancelled[/green]\n")
        return

    # Calculate total size before deletion
    total_size = sum(get_dir_size(kb_dir) for kb_dir in selected_kbs)

    # Delete selected
    deleted_count, _ = delete_knowledge_bases(selected_kbs, console)

    # Show results
    display_cleanup_results(deleted_count, total_size, console, format_size)


# Backward compatibility: export old name
cleanup = cleanup_refactored
