"""
Helper utilities for CLI commands.
"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich import box

from lecture_forge.cli.utils.formatters import console, format_size
from lecture_forge.config import Config
from lecture_forge.utils import logger

def get_dir_size(path: Path) -> int:
    """Calculate total size of directory in bytes."""
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    except (OSError, PermissionError) as e:
        # Acceptable: some directories may not be accessible
        logger.debug(f"Could not calculate directory size for {path}: {e}")
    except Exception as e:
        # Unexpected error in size calculation (non-critical display feature)
        logger.debug(f"Unexpected error calculating directory size: {e}")
    return total

def select_knowledge_base() -> Optional[str]:
    """
    List available knowledge bases and let user select one.

    Returns:
        Path to selected knowledge base, or None if cancelled
    """

    while True:  # Loop to allow returning after deletion
        # Get vector DB directory
        vector_db_dir = Path(Config.VECTOR_DB_PATH)

        if not vector_db_dir.exists():
            console.print(f"[yellow]⚠️  No knowledge bases found at {vector_db_dir}[/yellow]")
            console.print("[dim]Generate a lecture first to create a knowledge base[/dim]\n")
            return None

        # List all available knowledge bases
        kb_dirs = [d for d in vector_db_dir.iterdir() if d.is_dir()]

        if not kb_dirs:
            console.print(f"[yellow]⚠️  No knowledge bases found in {vector_db_dir}[/yellow]")
            console.print("[dim]Generate a lecture first to create a knowledge base[/dim]\n")
            return None

        # Sort by modification time (newest first)
        kb_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # Display available knowledge bases
        console.print("\n[bold cyan]📚 Available Knowledge Bases[/bold cyan]")
        console.print("━" * 50 + "\n")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("No.", style="cyan", width=4)
        table.add_column("Name", style="green")
        table.add_column("Size", style="yellow")
        table.add_column("Modified", style="cyan")

        for i, kb_dir in enumerate(kb_dirs, 1):
            name = kb_dir.name
            size = get_dir_size(kb_dir)
            modified = datetime.fromtimestamp(kb_dir.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            table.add_row(str(i), name, format_size(size), modified)

        console.print(table)
        console.print()

        # Show options
        console.print("[dim]💡 Options:[/dim]")
        console.print("[dim]   • Enter a number to select a knowledge base[/dim]")
        console.print("[dim]   • Type 'delete' or 'd' to delete knowledge bases[/dim]")
        console.print("[dim]   • Press Enter to cancel[/dim]\n")

        # Let user select
        choice = Prompt.ask(
            "[bold]Your choice[/bold]",
            default="",
        )

        if not choice:
            return None

        # Handle delete option
        if choice.lower() in ["delete", "d"]:
            delete_result = handle_kb_deletion_interactive(kb_dirs)
            if delete_result == "continue":
                continue  # Return to KB selection
            else:
                return None  # User cancelled

        # Handle number selection
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(kb_dirs):
                selected_kb = kb_dirs[idx]
                console.print(f"\n[green]✓ Selected: {selected_kb.name}[/green]\n")
                return str(selected_kb)
            else:
                console.print(f"[red]Invalid selection. Please choose 1-{len(kb_dirs)}[/red]")
                continue
        except ValueError:
            console.print("[red]Invalid input. Please enter a number, 'delete', or press Enter[/red]")
            continue


def handle_kb_deletion_interactive(kb_dirs: List[Path]) -> str:
    """
    Handle interactive knowledge base deletion.

    Args:
        kb_dirs: List of knowledge base directories

    Returns:
        "continue" to return to selection, "cancelled" if user cancelled
    """
    import shutil

    console.print("\n[bold red]🗑️  Delete Knowledge Bases[/bold red]")
    console.print("━" * 50 + "\n")

    # Show deletion options
    console.print("[dim]💡 Tip: You can select multiple numbers separated by commas (e.g., 1,3,5)[/dim]")
    console.print("[dim]💡 Tip: Type 'all' to delete all knowledge bases[/dim]\n")

    choice = Prompt.ask(
        "[bold]Enter number(s) to delete, 'all', or press Enter to go back[/bold]",
        default="",
    )

    if not choice:
        console.print("\n[green]✓ Returning to knowledge base selection[/green]\n")
        return "continue"

    # Handle 'all' option
    if choice.lower() == "all":
        console.print(f"\n[bold red]⚠️  WARNING: This will delete ALL {len(kb_dirs)} knowledge bases![/bold red]\n")

        # Show what will be deleted
        total_size = 0
        for kb_dir in kb_dirs:
            size = get_dir_size(kb_dir)
            total_size += size
            console.print(f"  • {kb_dir.name} ({format_size(size)})")

        console.print(f"\n[bold]Total size to free: {format_size(total_size)}[/bold]\n")

        if not Confirm.ask("[bold red]Are you SURE you want to delete ALL knowledge bases?[/bold red]", default=False):
            console.print("\n[green]✓ Cancelled[/green]\n")
            return "continue"

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

        # Check if any remain
        remaining = [d for d in Path(Config.VECTOR_DB_PATH).iterdir() if d.is_dir()]
        if remaining:
            return "continue"
        else:
            console.print("[yellow]No knowledge bases remaining. Please generate a lecture first.[/yellow]\n")
            return "cancelled"

    # Handle number selection
    try:
        selected_indices = [int(x.strip()) - 1 for x in choice.split(",")]
        selected_kbs = [kb_dirs[i] for i in selected_indices if 0 <= i < len(kb_dirs)]

        if not selected_kbs:
            console.print("\n[yellow]⚠️  No valid selections[/yellow]\n")
            return "continue"

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
            return "continue"

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

        return "continue"

    except (ValueError, IndexError) as e:
        console.print(f"\n[red]❌ Invalid selection: {e}[/red]\n")
        return "continue"


def find_pdf_files(max_depth: int = 2) -> List[Path]:
    """
    Find PDF files in current directory and subdirectories.

    Args:
        max_depth: Maximum depth to search (default: 2)

    Returns:
        List of PDF file paths with size and modification time
    """
    from pathlib import Path
    from datetime import datetime

    pdf_files = []
    current_dir = Path.cwd()

    # Search for PDF files
    for depth in range(max_depth + 1):
        if depth == 0:
            pattern = "*.pdf"
        else:
            pattern = "*/" * depth + "*.pdf"

        for pdf_path in current_dir.glob(pattern):
            if pdf_path.is_file():
                try:
                    stat = pdf_path.stat()
                    size_mb = stat.st_size / (1024 * 1024)
                    mtime = datetime.fromtimestamp(stat.st_mtime)

                    pdf_files.append(
                        {
                            "path": str(pdf_path),
                            "relative_path": str(pdf_path.relative_to(current_dir)),
                            "size_mb": size_mb,
                            "modified": mtime,
                            "name": pdf_path.name,
                        }
                    )
                except (OSError, ValueError):
                    continue

    # Sort by modification time (newest first)
    pdf_files.sort(key=lambda x: x["modified"], reverse=True)

    return pdf_files


def _find_image_dir_from_html(html_path: Path) -> Path:
    """Extract image directory path from HTML metadata comments."""
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Look for metadata comment: <!-- image_dir: data/images/session_xxx -->
        import re

        match = re.search(r"<!-- image_dir: (.+?) -->", html_content)

        if match:
            image_dir = Path(match.group(1))
            if image_dir.exists():
                return image_dir

        # Fallback: try to infer from filename
        # e.g., AI_Engineering_20260208_111335.html -> data/images/AI_Engineering_20260208_105934/
        filename = html_path.stem
        parts = filename.rsplit("_", 2)
        if len(parts) >= 3:
            topic_part = parts[0]
            date_part = parts[1]

            # Search for matching directories
            image_base = Path(Config.DATA_DIR) / "images"
            if image_base.exists():
                for img_dir in image_base.iterdir():
                    if img_dir.is_dir() and topic_part in img_dir.name and date_part[:8] in img_dir.name:
                        return img_dir

    except Exception as e:
        logger.error(f"Failed to extract image dir from HTML: {e}")

    return None


def select_pdf_files() -> List[str]:
    """
    Display PDF files and allow user to select them interactively.

    Returns:
        List of selected PDF file paths
    """
    console.print("\n[bold cyan]📄 Available PDF Files[/bold cyan]")
    console.print("━" * 80 + "\n")

    # Find PDF files
    pdf_files = find_pdf_files(max_depth=2)

    if not pdf_files:
        console.print("[yellow]No PDF files found in current directory.[/yellow]\n")
        return []

    # Display PDF files in a table
    table = Table(
        show_header=True,
        header_style="bold cyan",
        box=box.ROUNDED,
        title=f"[bold]Found {len(pdf_files)} PDF file(s)[/bold]",
        title_style="bold green",
    )

    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("File Name", style="cyan", no_wrap=False)
    table.add_column("Path", style="dim", no_wrap=False)
    table.add_column("Size", justify="right", style="yellow")
    table.add_column("Modified", style="dim")

    for idx, pdf in enumerate(pdf_files, 1):
        size_str = f"{pdf['size_mb']:.1f} MB" if pdf["size_mb"] >= 1 else f"{pdf['size_mb']*1024:.0f} KB"
        modified_str = pdf["modified"].strftime("%Y-%m-%d %H:%M")

        table.add_row(str(idx), pdf["name"], pdf["relative_path"], size_str, modified_str)

    console.print(table)
    console.print()

    # Selection prompt
    console.print("[bold]Selection Options:[/bold]")
    console.print("  • Enter numbers (e.g., [cyan]1,3,5[/cyan] or [cyan]1-3[/cyan])")
    console.print("  • Enter [cyan]all[/cyan] to select all files")
    console.print("  • Press [cyan]Enter[/cyan] to skip")
    console.print()

    selection = Prompt.ask("[bold]Select PDF files[/bold]", default="")

    if not selection:
        return []

    selection = selection.strip().lower()

    # Handle 'all' selection
    if selection == "all":
        selected_files = [pdf["relative_path"] for pdf in pdf_files]
        console.print(f"[green]✓ Selected all {len(selected_files)} files[/green]\n")
        return selected_files

    # Parse selection
    selected_indices = set()

    try:
        for part in selection.split(","):
            part = part.strip()

            # Handle range (e.g., "1-3")
            if "-" in part:
                start, end = part.split("-")
                start_idx = int(start.strip())
                end_idx = int(end.strip())

                if start_idx < 1 or end_idx > len(pdf_files):
                    console.print(f"[red]✗ Invalid range: {part}[/red]")
                    continue

                selected_indices.update(range(start_idx, end_idx + 1))

            # Handle single number
            else:
                idx = int(part)
                if idx < 1 or idx > len(pdf_files):
                    console.print(f"[red]✗ Invalid number: {idx}[/red]")
                    continue

                selected_indices.add(idx)

    except ValueError:
        console.print(f"[red]✗ Invalid selection format: {selection}[/red]")
        console.print("[yellow]Please use numbers (e.g., 1,3,5 or 1-3)[/yellow]\n")
        return []

    # Get selected files
    selected_files = [pdf_files[idx - 1]["relative_path"] for idx in sorted(selected_indices)]

    if selected_files:
        console.print(f"[green]✓ Selected {len(selected_files)} file(s):[/green]")
        for file in selected_files:
            console.print(f"  • {file}")
        console.print()

    return selected_files



