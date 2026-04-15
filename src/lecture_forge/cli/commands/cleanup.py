"""
Cleanup command - Cleanup.
"""

import shutil
from datetime import datetime
from pathlib import Path

import click
from rich.prompt import Confirm, Prompt
from rich.table import Table

from lecture_forge.cli.utils import console, format_size, get_dir_size
from lecture_forge.config import Config


@click.command()
@click.option(
    "--all",
    "-a",
    is_flag=True,
    help="Delete ALL knowledge bases without confirmation (DANGEROUS)",
)
def cleanup(all: bool) -> None:
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
    import shutil

    console.print("\n[bold red]🗑️  Knowledge Base Cleanup[/bold red]")
    console.print("━" * 50 + "\n")

    # Get vector DB directory
    vector_db_dir = Path(Config.VECTOR_DB_PATH)

    if not vector_db_dir.exists():
        console.print(f"[yellow]⚠️  No knowledge bases found at {vector_db_dir}[/yellow]\n")
        return

    # List all available knowledge bases
    kb_dirs = [d for d in vector_db_dir.iterdir() if d.is_dir()]

    if not kb_dirs:
        console.print(f"[yellow]⚠️  No knowledge bases found in {vector_db_dir}[/yellow]\n")
        return

    # Sort by modification time (newest first)
    kb_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    if all:
        # Delete all - requires confirmation
        console.print(f"[bold red]⚠️  WARNING: This will delete ALL {len(kb_dirs)} knowledge bases![/bold red]\n")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Name", style="green")
        table.add_column("Size", style="yellow")
        table.add_column("Modified", style="cyan")

        total_size = 0
        for kb_dir in kb_dirs:
            size = get_dir_size(kb_dir)
            total_size += size
            name = kb_dir.name
            modified = datetime.fromtimestamp(kb_dir.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            table.add_row(name, format_size(size), modified)

        console.print(table)
        console.print(f"\n[bold]Total size: {format_size(total_size)}[/bold]\n")

        if not Confirm.ask("[bold red]Are you SURE you want to delete ALL knowledge bases?[/bold red]", default=False):
            console.print("\n[green]✓ Cancelled[/green]\n")
            return

        # Delete all
        deleted_count = 0
        for kb_dir in kb_dirs:
            try:
                shutil.rmtree(kb_dir)
                deleted_count += 1
                console.print(f"[red]✗[/red] Deleted: {kb_dir.name}")
            except Exception as e:
                console.print(f"[yellow]⚠️  Failed to delete {kb_dir.name}: {e}[/yellow]")

        console.print(f"\n[green]✓ Deleted {deleted_count} knowledge base(s)[/green]")
        console.print(f"[green]✓ Freed up {format_size(total_size)}[/green]\n")

    else:
        # Interactive deletion
        console.print("[bold cyan]📚 Available Knowledge Bases[/bold cyan]\n")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("No.", style="cyan", width=4)
        table.add_column("Name", style="green")
        table.add_column("Size", style="yellow")
        table.add_column("Modified", style="cyan")

        for i, kb_dir in enumerate(kb_dirs, 1):
            size = get_dir_size(kb_dir)
            name = kb_dir.name
            modified = datetime.fromtimestamp(kb_dir.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            table.add_row(str(i), name, format_size(size), modified)

        console.print(table)
        console.print()

        # Let user select which to delete
        console.print("[dim]💡 Tip: You can select multiple numbers separated by commas (e.g., 1,3,5)[/dim]")
        console.print("[dim]💡 Tip: Use '--all' flag to delete all at once[/dim]\n")

        choice = Prompt.ask(
            "[bold]Select knowledge base number(s) to delete[/bold] (or press Enter to cancel)",
            default="",
        )

        if not choice:
            console.print("\n[green]✓ Cancelled[/green]\n")
            return

        # Parse selection
        try:
            selected_indices = [int(x.strip()) - 1 for x in choice.split(",")]
            selected_kbs = [kb_dirs[i] for i in selected_indices if 0 <= i < len(kb_dirs)]

            if not selected_kbs:
                console.print("\n[yellow]⚠️  No valid selections[/yellow]\n")
                return

            # Show what will be deleted
            console.print("\n[bold red]⚠️  The following will be deleted:[/bold red]\n")
            total_size = 0
            for kb_dir in selected_kbs:
                size = get_dir_size(kb_dir)
                total_size += size
                console.print(f"  • {kb_dir.name} ({format_size(size)})")

            console.print(f"\n[bold]Total size to free: {format_size(total_size)}[/bold]\n")

            # Confirm
            if not Confirm.ask("[bold]Proceed with deletion?[/bold]", default=False):
                console.print("\n[green]✓ Cancelled[/green]\n")
                return

            # Delete selected
            deleted_count = 0
            for kb_dir in selected_kbs:
                try:
                    shutil.rmtree(kb_dir)
                    deleted_count += 1
                    console.print(f"[red]✗[/red] Deleted: {kb_dir.name}")
                except Exception as e:
                    console.print(f"[yellow]⚠️  Failed to delete {kb_dir.name}: {e}[/yellow]")

            console.print(f"\n[green]✓ Deleted {deleted_count} knowledge base(s)[/green]")
            console.print(f"[green]✓ Freed up {format_size(total_size)}[/green]\n")

        except (ValueError, IndexError) as e:
            console.print(f"\n[red]❌ Invalid selection: {e}[/red]\n")


