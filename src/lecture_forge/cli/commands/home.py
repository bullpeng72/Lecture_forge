"""
Home command - Home.
"""

import platform
import subprocess
from pathlib import Path

import click

from lecture_forge.cli.utils import console
from lecture_forge.config import Config


@click.command()
@click.argument(
    "target",
    required=False,
    default="",
    type=click.Choice(["", "data", "outputs", "kb", "env"]),
)
def home(target: str) -> None:
    """
    Open LectureForge directory in file manager or editor.

    Navigate to various LectureForge directories quickly using system file manager.
    This command provides easy access to configuration, data, and outputs.

    \b
    Targets:
      (none)    Open main directory (~/Documents/LectureForge/)
      data      Open data directory (vector_db, images, cache)
      outputs   Open outputs directory (generated lectures)
      kb        Open latest knowledge base directory
      env       Open .env configuration file in text editor

    \b
    Directory Structure:
      ~/Documents/LectureForge/
      ├── .env                    (configuration)
      ├── data/
      │   ├── vector_db/         (knowledge bases)
      │   ├── images/            (collected images)
      │   └── cache/             (RAG query cache)
      └── outputs/               (generated lectures)

    \b
    Examples:
      # Open main LectureForge folder
      $ lecture-forge home

      # Open outputs folder (to view generated lectures)
      $ lecture-forge home outputs

      # Open latest knowledge base folder
      $ lecture-forge home kb

      # Edit .env configuration file
      $ lecture-forge home env

      # Open data folder (vector_db, images, cache)
      $ lecture-forge home data

    \b
    Platform Support:
      • macOS:   Uses 'open' command (Finder)
      • Windows: Uses 'explorer' command (File Explorer)
      • Linux:   Uses 'xdg-open' command (default file manager)

    \b
    Notes:
      • Creates directory if it doesn't exist
      • 'env' target opens .env in default text editor
      • 'kb' selects the most recently modified knowledge base
      • All paths are displayed before opening for confirmation
    """
    import platform
    import subprocess

    from lecture_forge.config import Config

    console.print()

    # Determine target path
    if not target or target == "":
        path = Config.USER_CONFIG_DIR
        desc = "main directory"
    elif target == "data":
        path = Config.DATA_DIR
        desc = "data directory"
    elif target == "outputs":
        path = Config.OUTPUT_DIR
        desc = "outputs directory"
    elif target == "kb":
        # Find latest knowledge base
        kb_dir = Config.VECTOR_DB_PATH
        if not kb_dir.exists():
            console.print("[yellow]⚠️  No knowledge bases found[/yellow]")
            console.print("[dim]Generate a lecture first to create a knowledge base[/dim]")
            console.print(f"[dim]Expected location: {kb_dir}[/dim]\n")
            return

        kb_dirs = [d for d in kb_dir.iterdir() if d.is_dir()]
        if not kb_dirs:
            console.print("[yellow]⚠️  No knowledge bases found[/yellow]")
            console.print(f"[dim]Directory exists but is empty: {kb_dir}[/dim]\n")
            return

        # Get latest
        kb_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        path = kb_dirs[0]
        desc = f"knowledge base: {path.name}"
    elif target == "env":
        # Open .env in editor
        env_path = Config.get_recommended_env_path()
        if not env_path.exists():
            console.print("[yellow]⚠️  .env file not found at:[/yellow]")
            console.print(f"[yellow]   {env_path}[/yellow]")
            console.print("\n[cyan]💡 Run: lecture-forge init[/cyan]\n")
            return

        console.print("[cyan]📝 Opening .env file in editor...[/cyan]")
        console.print(f"[dim]   {env_path}[/dim]\n")

        # Open in default editor
        try:
            if platform.system() == "Darwin":  # macOS
                subprocess.run(["open", "-t", str(env_path)], check=True)
            elif platform.system() == "Windows":
                subprocess.run(["notepad", str(env_path)], check=True)
            else:  # Linux
                subprocess.run(["xdg-open", str(env_path)], check=True)
            console.print("[green]✓ Opened in default editor[/green]\n")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]❌ Failed to open editor: {e}[/red]\n")
        except FileNotFoundError:
            console.print("[red]❌ No default editor found[/red]")
            console.print(f"[dim]   Please manually edit: {env_path}[/dim]\n")
        return
    else:
        # Should not reach here due to click.Choice validation
        console.print(f"[red]❌ Unknown target: {target}[/red]\n")
        return

    # Ensure directory exists
    if not path.exists():
        console.print(f"[yellow]⚠️  Directory not found:[/yellow]")
        console.print(f"[yellow]   {path}[/yellow]")
        console.print("\n[cyan]Creating directory...[/cyan]\n")
        try:
            path.mkdir(parents=True, exist_ok=True)
            console.print("[green]✓ Directory created[/green]\n")
        except Exception as e:
            console.print(f"[red]❌ Failed to create directory: {e}[/red]\n")
            return

    # Open in file manager
    console.print(f"[cyan]📂 Opening {desc}...[/cyan]")
    console.print(f"[dim]   {path}[/dim]\n")

    try:
        if platform.system() == "Darwin":  # macOS
            subprocess.run(["open", str(path)], check=True)
        elif platform.system() == "Windows":
            subprocess.run(["explorer", str(path)], check=True)
        else:  # Linux
            subprocess.run(["xdg-open", str(path)], check=True)
        console.print("[green]✓ Opened in file manager[/green]\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Failed to open file manager: {e}[/red]\n")
    except FileNotFoundError:
        console.print("[red]❌ File manager command not found[/red]")
        console.print(f"[dim]   Please manually navigate to: {path}[/dim]\n")

