"""
Input collection utilities for CLI.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.prompt import Confirm, Prompt

from lecture_forge.cli.utils.formatters import console
from lecture_forge.cli.utils.helpers import select_pdf_files, find_pdf_files

def prompt_masked_input(console: Console, prompt_text: str, mask_char: str = "*", allow_empty: bool = False) -> str:
    """
    Prompt for password input with masked display (shows *** while typing).

    Args:
        console: Rich console instance
        prompt_text: Prompt message to display
        mask_char: Character to use for masking (default: *)
        allow_empty: Whether to allow empty input (default: False)

    Returns:
        User input as string
    """
    import sys

    console.print(prompt_text, end=" ")
    # Flush to ensure prompt is displayed
    sys.stdout.flush()

    # Check platform
    if sys.platform == "win32":
        # Windows implementation using msvcrt
        import msvcrt

        chars = []
        while True:
            char = msvcrt.getwch()

            if char in ("\r", "\n"):  # Enter
                sys.stdout.write("\n")
                sys.stdout.flush()
                break
            elif char == "\b":  # Backspace
                if chars:
                    chars.pop()
                    # Clear the last asterisk: move back, write space, move back again
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
            elif char == "\x03":  # Ctrl+C
                sys.stdout.write("\n")
                sys.stdout.flush()
                raise KeyboardInterrupt
            else:
                chars.append(char)
                sys.stdout.write(mask_char)
                sys.stdout.flush()

        result = "".join(chars)
        if not allow_empty and not result:
            console.print("   [dim](Empty input - skipped)[/dim]")
        return result
    else:
        # Unix/Linux/Mac implementation using termios
        import tty
        import termios

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            tty.setraw(fd)
            chars = []

            while True:
                char = sys.stdin.read(1)

                if char in ("\r", "\n"):  # Enter
                    sys.stdout.write("\r\n")  # raw mode: \n alone doesn't carriage-return
                    sys.stdout.flush()
                    break
                elif char in ("\x7f", "\x08"):  # Backspace/Delete
                    if chars:
                        chars.pop()
                        # Clear the last asterisk: move back, write space, move back again
                        sys.stdout.write("\b \b")
                        sys.stdout.flush()
                elif char == "\x03":  # Ctrl+C
                    sys.stdout.write("\r\n")  # raw mode: \n alone doesn't carriage-return
                    sys.stdout.flush()
                    raise KeyboardInterrupt
                elif char >= " ":  # Printable character
                    chars.append(char)
                    sys.stdout.write(mask_char)
                    sys.stdout.flush()

            result = "".join(chars)
            if not allow_empty and not result:
                console.print("   [dim](Empty input - skipped)[/dim]")
            return result
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
from lecture_forge.agents.image_collector import ImageCollectorAgent
from lecture_forge.config import Config
from lecture_forge.models.lecture import Lecture
from lecture_forge.utils import logger
from lecture_forge.utils.token_tracker import get_tracker

console = Console()


def _collect_comma_separated_input(
    console: Console,
    prompt_label: str,
    hint: Optional[str] = None,
) -> List[str]:
    """
    Collect comma-separated input from user.

    Args:
        console: Rich console instance
        prompt_label: Label to display in prompt
        hint: Optional hint to display before prompt

    Returns:
        List of stripped values, or empty list if no input
    """
    if hint:
        console.print(f"[dim]{hint}[/dim]")

    input_text = Prompt.ask(f"[bold]{prompt_label}[/bold] (comma-separated, or press Enter to skip)")

    if input_text:
        return [item.strip().strip('"').strip("'") for item in input_text.split(",")]
    return []



def collect_inputs_interactive() -> Dict[str, Any]:
    """Collect inputs interactively from user."""
    console.print("[bold cyan]📝 Lecture Information[/bold cyan]")
    console.print("━" * 50 + "\n")

    inputs = {}

    # Basic information
    inputs["topic"] = Prompt.ask("[bold]Lecture Topic[/bold]")
    inputs["duration"] = int(Prompt.ask("[bold]Duration (minutes)[/bold]", default="180"))
    inputs["audience_level"] = Prompt.ask(
        "[bold]Audience Level[/bold]",
        choices=["beginner", "intermediate", "advanced"],
        default="intermediate",
    )

    # Knowledge Base Source selection
    console.print("\n[bold cyan]🗄️  Knowledge Base Source[/bold cyan]")
    console.print("━" * 50 + "\n")
    console.print("  [bold][1][/bold] Create new knowledge base  [dim](default)[/dim]")
    console.print("  [bold][2][/bold] Reuse existing KB only     [dim](no new sources)[/dim]")
    console.print("  [bold][3][/bold] Extend existing KB with new sources")
    console.print()

    kb_choice = Prompt.ask(
        "[bold]Knowledge base option[/bold]",
        choices=["1", "2", "3"],
        default="1",
    )

    if kb_choice in ["2", "3"]:
        from lecture_forge.cli.utils.helpers import select_knowledge_base
        kb_path = select_knowledge_base()
        if not kb_path:
            console.print("[yellow]⚠️  No KB selected. Creating new KB.[/yellow]")
            inputs["existing_kb_path"] = None
            inputs["kb_mode"] = "new"
        else:
            inputs["existing_kb_path"] = kb_path
            inputs["kb_mode"] = "reuse_only" if kb_choice == "2" else "extend"
    else:
        inputs["existing_kb_path"] = None
        inputs["kb_mode"] = "new"

    if inputs.get("kb_mode") == "reuse_only":
        # Skip all source collection for reuse-only mode
        inputs["pdfs"] = []
        inputs["urls"] = []
        inputs["keywords"] = []
        inputs["hada_keywords"] = []
        inputs["image_keywords"] = []
        return inputs

    console.print("\n[bold cyan]📂 Content Sources[/bold cyan]")
    console.print("━" * 50 + "\n")

    # PDF files
    console.print("[bold]PDF Files:[/bold]")
    console.print("  [1] Browse and select from current directory")
    console.print("  [2] Enter file paths manually")
    console.print("  [3] Skip PDF files")
    console.print()

    pdf_choice = Prompt.ask("[bold]Choose option[/bold]", choices=["1", "2", "3"], default="1")

    if pdf_choice == "1":
        # Browse and select PDF files
        inputs["pdfs"] = select_pdf_files()

        # Allow adding more files manually
        if inputs["pdfs"]:
            add_more = Confirm.ask("\n[bold]Add more PDF files manually?[/bold]", default=False)
            if add_more:
                additional = _collect_comma_separated_input(
                    console, "Additional PDF files", hint="💡 Tip: For filenames with spaces, just type without quotes"
                )
                inputs["pdfs"].extend(additional)

    elif pdf_choice == "2":
        # Manual input
        console.print("[dim]💡 Tip: For filenames with spaces, just type without quotes[/dim]")
        console.print("[dim]   Example: AI Engineering Guidebook.pdf[/dim]")
        pdf_input = Prompt.ask("[bold]PDF files[/bold] (comma-separated)")
        if pdf_input:
            inputs["pdfs"] = [p.strip().strip('"').strip("'") for p in pdf_input.split(",")]
        else:
            inputs["pdfs"] = []

    else:
        # Skip
        inputs["pdfs"] = []

    # URLs
    inputs["urls"] = _collect_comma_separated_input(console, "URLs")

    # Search keywords
    inputs["keywords"] = _collect_comma_separated_input(console, "Search keywords")

    # Hada.io deep search keywords
    inputs["hada_keywords"] = _collect_comma_separated_input(
        console, "Hada.io search keywords", hint="\n💡 Deep Crawling: Hada.io search will crawl article links too"
    )

    # Image search keywords (if enabled via flag)
    inputs["image_keywords"] = _collect_comma_separated_input(console, "Image search keywords")

    return inputs



