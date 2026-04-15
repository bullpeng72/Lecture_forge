"""
Command-line interface for LectureForge.

Modular CLI structure with separated commands and utilities.
"""

import sys

import rich_click as click
from rich_click import RichGroup

# Configure rich-click for beautiful help output
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.USE_MARKDOWN = False
click.rich_click.STYLE_OPTION = "bold cyan"
click.rich_click.STYLE_ARGUMENT = "bold cyan"
click.rich_click.STYLE_COMMAND = "bold green"
click.rich_click.STYLE_SWITCH = "bold magenta"
click.rich_click.STYLE_METAVAR = "bold yellow"
click.rich_click.STYLE_METAVAR_SEPARATOR = "dim"
click.rich_click.STYLE_HEADER_TEXT = "bold yellow"
click.rich_click.STYLE_FOOTER_TEXT = "dim"
click.rich_click.STYLE_USAGE = "bold yellow"
click.rich_click.STYLE_USAGE_COMMAND = "bold"
click.rich_click.STYLE_HELPTEXT_FIRST_LINE = "bold"
click.rich_click.STYLE_HELPTEXT = ""
click.rich_click.STYLE_OPTION_HELP = ""
click.rich_click.STYLE_OPTION_DEFAULT = "dim"
click.rich_click.STYLE_REQUIRED_SHORT = "bold red"
click.rich_click.STYLE_REQUIRED_LONG = "dim"
click.rich_click.MAX_WIDTH = 100
click.rich_click.SHOW_METAVARS_COLUMN = True
click.rich_click.APPEND_METAVARS_HELP = False

from lecture_forge.__version__ import __version__
from lecture_forge.cli.commands import (
    chat,
    cleanup,
    create,
    edit,
    edit_images,
    home,
    improve,
    init,
    translate,
)
from lecture_forge.cli.utils import print_basic_help


@click.group(cls=RichGroup, invoke_without_command=True)
@click.option("--version", is_flag=True, help="Show version and exit")
@click.pass_context
def cli(ctx, version: bool) -> None:
    """
    📚 LectureForge Pro - AI-Powered Lecture Material Generator

    Transform PDFs, URLs, and web content into comprehensive lecture materials.
    Multi-agent pipeline system with RAG-based knowledge management and multilingual support.

    \b
    📊 Stats: 12 Agents | 9 Tools | 1,870+ Tests | ~$0.035 per 60min lecture
    📂 Data: ~/Documents/LectureForge/ (easily accessible folder)
    🌐 Multilingual: Auto language detection, Cross-lingual search (v0.3.2+)
    ⚡ Async I/O: 70% faster content collection with --async-mode (v0.3.4+)
    🎯 RAG Quality: 400-word answers, Markdown rendering, 15+15 retrieval (v0.3.5+)
    🧠 RMC Self-Review: Curriculum logic, content quality, QA hallucination (v0.3.8+)
    🔄 Re-Evaluate: KB-based quality re-evaluation + content supplement (v0.4.0+)
    🌐 PDF Translate: English PDF → Korean lecture, TOC detection, term glossary (v0.4.1+)
    ✏️  Web Editor: 3-panel GUI editor — section CRUD, Markdown, image gallery (v0.5.0+)

    \b
    🎉 FIRST TIME HERE?
       Run: lecture-forge init
       → Set up API keys (OpenAI, Serper), LLM provider, and quality settings
       → Creates config in ~/Documents/LectureForge/.env
       → To reconfigure later: lecture-forge init --reconfigure
       → To view current settings: lecture-forge init --show

    \b
    📚 Commands Overview:
       ┌─────────────┬──────────────────────────────────────┬────────────────────┐
       │ Command     │ Description                          │ Key Option         │
       ├─────────────┼──────────────────────────────────────┼────────────────────┤
       │ init        │ Configure API keys + LLM/quality     │ -r / -s / --path   │
       │ create      │ Generate lecture from sources        │ --image-search     │
       │ translate   │ Translate English PDF to Korean HTML │ --no-translate     │
       │ chat        │ Interactive Q&A with knowledge base  │ -kb PATH           │
       │ edit        │ Web-based lecture editor (GUI)       │ --port --no-browser│
       │ edit-images │ Edit/replace lecture images (CLI)    │ -o FILE            │
       │ improve     │ Slides(노트 포함), re-evaluate, KB   │ --to-slides        │
       │ cleanup     │ Delete knowledge bases (free space)  │ --all              │
       │ home        │ Open folders in file manager         │ outputs/env        │
       └─────────────┴──────────────────────────────────────┴────────────────────┘

    \b
    💡 Quick Start:
       1. lecture-forge init                    # First-time setup
       2. lecture-forge create                  # Generate lecture
       3. lecture-forge home outputs            # View results
       4. lecture-forge chat                    # Q&A mode

    \b
    📖 Documentation:
       • GitHub: https://github.com/bullpeng72/Lecture_forge
       • PyPI: https://pypi.org/project/lecture-forge/
       • Help: lecture-forge COMMAND --help

    Use 'lecture-forge COMMAND --help' for command-specific help.
    """
    # Show version and exit
    if version:
        print(f"LectureForge v{__version__}")
        sys.exit(0)

    # If no command provided, show help
    if ctx.invoked_subcommand is None:
        print_basic_help()


# Register commands
cli.add_command(init)
cli.add_command(create)
cli.add_command(chat)
cli.add_command(edit)
cli.add_command(edit_images, name="edit-images")  # Use hyphenated name
cli.add_command(improve)
cli.add_command(translate)
cli.add_command(cleanup)
cli.add_command(home)


def main() -> None:
    """Main entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
