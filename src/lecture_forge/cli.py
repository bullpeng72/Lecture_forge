"""
Command-line interface for LectureForge.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import rich_click as click
from rich_click import RichCommand, RichGroup
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich import box

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
from lecture_forge.agents.content_analyzer import ContentAnalyzerAgent
from lecture_forge.agents.content_collector import ContentCollectorAgent
from lecture_forge.agents.content_writer import ContentWriterAgent
from lecture_forge.agents.curriculum_designer import CurriculumDesignerAgent
from lecture_forge.agents.diagram_generator import DiagramGeneratorAgent
from lecture_forge.agents.html_assembler import HTMLAssemblerAgent


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
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                    break
                elif char in ("\x7f", "\x08"):  # Backspace/Delete
                    if chars:
                        chars.pop()
                        # Clear the last asterisk: move back, write space, move back again
                        sys.stdout.write("\b \b")
                        sys.stdout.flush()
                elif char == "\x03":  # Ctrl+C
                    sys.stdout.write("\n")
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


def display_token_usage(usage_summary: Dict[str, Any]) -> None:
    """
    Display token usage and cost estimate.

    Args:
        usage_summary: Token usage summary from tracker
    """
    console.print(f"\n💰 [bold]Token Usage & Cost Estimate:[/bold]")

    # Total tokens
    total_tokens = usage_summary.get("total_tokens", 0)
    prompt_tokens = usage_summary.get("prompt_tokens", 0)
    completion_tokens = usage_summary.get("completion_tokens", 0)
    api_calls = usage_summary.get("api_calls", 0)

    console.print(f"   • Total Tokens: {total_tokens:,}")
    console.print(f"     - Input: {prompt_tokens:,} tokens")
    console.print(f"     - Output: {completion_tokens:,} tokens")
    console.print(f"   • API Calls: {api_calls}")

    # Tokens by model
    tokens_by_model = usage_summary.get("tokens_by_model", {})
    if tokens_by_model:
        console.print(f"\n   [bold]By Model:[/bold]")
        for model, tokens in tokens_by_model.items():
            console.print(f"     • {model}:")
            console.print(f"       - Input: {tokens['prompt_tokens']:,} tokens")
            console.print(f"       - Output: {tokens['completion_tokens']:,} tokens")
            console.print(f"       - Total: {tokens['total_tokens']:,} tokens")

    # Cost estimate
    cost_info = usage_summary.get("cost_estimate", {})
    total_cost = cost_info.get("total", 0.0)
    input_cost = cost_info.get("input", 0.0)
    output_cost = cost_info.get("output", 0.0)
    by_model = cost_info.get("by_model", {})

    console.print(f"\n   [bold cyan]Estimated Cost:[/bold cyan]")
    console.print(f"     • Total: [bold green]${total_cost:.4f}[/bold green]")
    console.print(f"       - Input cost: ${input_cost:.4f}")
    console.print(f"       - Output cost: ${output_cost:.4f}")

    if by_model:
        console.print(f"\n     [bold]By Model:[/bold]")
        for model, cost in by_model.items():
            console.print(f"       • {model}: ${cost:.4f}")

    # Pricing info
    console.print(f"\n   [dim]ℹ️  Pricing (as of 2026-02-07):[/dim]")
    console.print(f"   [dim]   • gpt-4o-mini: $0.150/1M input, $0.600/1M output[/dim]")
    console.print(f"   [dim]   • gpt-4o: $2.50/1M input, $10.00/1M output[/dim]")


def print_banner() -> None:
    """Print welcome banner."""
    banner = """
    ╔═══════════════════════════════════════════════════════╗
    ║                                                       ║
    ║            📚 LectureForge Pro v{version}                 ║
    ║                                                       ║
    ║     AI-Powered Lecture Material Generator             ║
    ║                                                       ║
    ╚═══════════════════════════════════════════════════════╝
    """.format(
        version=__version__
    )
    console.print(banner, style="bold blue")


def print_basic_help() -> None:
    """Print basic help information when no command is provided."""
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]📚 LectureForge Pro[/bold cyan] v" + __version__ + " [green](Beta)[/green]\n\n"
            "[bold]AI-Powered Lecture Material Generator[/bold]\n\n"
            "Transform PDFs, URLs, and web content into comprehensive lecture materials\n"
            "[dim]10 Agents | 9 Tools | 53+ Tests (45-50%) | $0.22/180min lecture[/dim]",
            border_style="cyan",
        )
    )

    # First-time user notice
    console.print("\n[bold magenta]🎉 First time here?[/bold magenta] Run [bold cyan]lecture-forge init[/bold cyan] to set up your API keys!")

    console.print("\n[bold yellow]🚀 Quick Start:[/bold yellow]")
    console.print("  [bold cyan]1.[/bold cyan] [cyan]lecture-forge init[/cyan]                        [dim]# First-time setup (required)[/dim]")
    console.print("  [bold cyan]2.[/bold cyan] [cyan]lecture-forge create[/cyan]                      [dim]# Generate your first lecture[/dim]")
    console.print("  [bold cyan]3.[/bold cyan] [cyan]lecture-forge home outputs[/cyan]                [dim]# Open results folder[/dim]")
    console.print("  [bold cyan]4.[/bold cyan] [cyan]lecture-forge chat[/cyan]                        [dim]# Q&A with knowledge base[/dim]")

    # Commands Table
    console.print("\n[bold yellow]📖 Commands:[/bold yellow]")
    table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED, padding=(0, 1))
    table.add_column("Command", style="cyan", width=14)
    table.add_column("Description", width=40)
    table.add_column("Key Options", style="green", width=20)

    table.add_row(
        "[bold magenta]init[/bold magenta]",
        "[bold]Set up API keys[/bold] (first-time setup)",
        "--path"
    )
    table.add_row("create", "Generate lecture materials", "--image-search")
    table.add_row("chat", "Interactive Q&A (RAG-based)", "-kb PATH")
    table.add_row("edit-images", "Edit lecture images", "-o FILE")
    table.add_row("improve", "Enhance or convert lecture", "--to-slides")
    table.add_row("cleanup", "Manage knowledge bases", "--all")
    table.add_row("[bold green]home[/bold green]", "[bold]Open folders[/bold] in file manager [cyan](NEW!)[/cyan]", "outputs/data/env")
    console.print(table)

    # Common Options
    console.print("\n[bold yellow]⚙️  Common Options:[/bold yellow]")
    opt_table = Table(show_header=False, box=None, padding=(0, 1))
    opt_table.add_column("Option", style="green", width=22)
    opt_table.add_column("Description", width=50)

    opt_table.add_row("--image-search", "Enable Pexels/Unsplash image search")
    opt_table.add_row("--quality-level LEVEL", "lenient(70) | balanced(80) | strict(90)")
    opt_table.add_row("--config, -c FILE", "Use YAML configuration file")
    opt_table.add_row("--output, -o FILE", "Specify output filename")
    opt_table.add_row("--to-slides", "Convert HTML to Reveal.js presentation")
    console.print(opt_table)

    # Configuration
    console.print("\n[bold yellow]🔧 Environment Configuration (.env):[/bold yellow]")
    console.print("  [dim]Customize behavior without code changes:[/dim]")
    console.print("    [green]SEARCH_NUM_RESULTS=20[/green]        # Search results (default: 10)")
    console.print("    [green]DEEP_CRAWLER_MAX_PAGES=30[/green]    # Crawl depth (default: 10)")
    console.print("    [green]IMAGE_SEARCH_PER_PAGE=15[/green]     # Images per search (default: 10)")
    console.print("    [green]QUALITY_THRESHOLD=90[/green]         # Quality bar (default: 80)")
    console.print("  [dim]See .env.example for 15+ configurable settings[/dim]")

    # Examples
    console.print("\n[bold yellow]💡 Usage Examples:[/bold yellow]")
    console.print("  [dim]# First-time setup (interactive wizard)[/dim]")
    console.print("  $ [bold magenta]lecture-forge init[/bold magenta]")
    console.print()
    console.print("  [dim]# Basic usage (interactive)[/dim]")
    console.print("  $ [cyan]lecture-forge create[/cyan]")
    console.print()
    console.print("  [dim]# Open results in file manager[/dim]")
    console.print("  $ [bold green]lecture-forge home outputs[/bold green]")
    console.print()
    console.print("  [dim]# High-quality with images[/dim]")
    console.print("  $ [cyan]lecture-forge create --image-search --quality-level strict[/cyan]")
    console.print()
    console.print("  [dim]# Edit .env configuration[/dim]")
    console.print("  $ [bold green]lecture-forge home env[/bold green]")
    console.print()
    console.print("  [dim]# Edit generated lecture images[/dim]")
    console.print("  $ [cyan]lecture-forge edit-images outputs/lecture.html[/cyan]")
    console.print()
    console.print("  [dim]# Convert to slides[/dim]")
    console.print("  $ [cyan]lecture-forge improve outputs/lecture.html --to-slides[/cyan]")
    console.print()
    console.print("  [dim]# Q&A with auto-selected knowledge base[/dim]")
    console.print("  $ [cyan]lecture-forge chat[/cyan]")

    # More Help
    console.print("\n[bold yellow]📚 Get More Help:[/bold yellow]")
    console.print("  [cyan]lecture-forge --help[/cyan]              # Full documentation")
    console.print("  [cyan]lecture-forge <command> --help[/cyan]    # Command-specific help")
    console.print("  [cyan]cat README.md[/cyan]                     # Comprehensive guide")

    # Footer
    console.print("\n[dim]💰 Cost: ~$0.10 per 60-min lecture (~$0.22 per 180-min lecture)[/dim]")
    console.print("[dim]📊 Stats: 10 agents | 9 tools | 2,896 lines CLI | 15+ env vars[/dim]\n")


@click.group(cls=RichGroup, invoke_without_command=True)
@click.pass_context
@click.version_option(version=__version__)
def cli(ctx):
    """
    📚 LectureForge Pro v0.3.2 - AI-Powered Lecture Material Generator

    Transform PDFs, URLs, and web content into comprehensive lecture materials.
    Multi-agent pipeline system with RAG-based knowledge management and multilingual support.

    \b
    📊 Stats: 10 Agents | 9 Tools | 89 Tests | ~$0.035 per 60min lecture
    📂 Data: ~/Documents/LectureForge/ (easily accessible folder)
    🌐 Multilingual: Auto language detection, Cross-lingual search (v0.3.2+)

    \b
    🎉 FIRST TIME HERE?
       Run: lecture-forge init
       → Set up your API keys (OpenAI, Serper)
       → Creates config in ~/Documents/LectureForge/.env

    \b
    📚 Commands Overview:
       ┌─────────────┬────────────────────────────────────────┬─────────────┐
       │ Command     │ Description                            │ Key Option  │
       ├─────────────┼────────────────────────────────────────┼─────────────┤
       │ init        │ Configure API keys (first-time)        │ --path      │
       │ create      │ Generate lecture from sources          │ --config    │
       │ chat        │ Interactive Q&A with knowledge base    │ -kb PATH    │
       │ edit-images │ Edit/replace lecture images            │ -o FILE     │
       │ improve     │ Convert to slides or enhance           │ --to-slides │
       │ cleanup     │ Delete knowledge bases (free space)    │ --all       │
       │ home        │ Open folders in file manager (NEW!)    │ outputs/env │
       └─────────────┴────────────────────────────────────────┴─────────────┘

    \b
    🚀 Quick Start:
       1. lecture-forge init              # Configure API keys (one-time)
       2. lecture-forge create            # Generate your first lecture
       3. lecture-forge home outputs      # View results in file manager
       4. lecture-forge chat              # Ask questions about it

    \b
    ⚙️  Key Options:
       --image-search            Enable Pexels/Unsplash image search
       --quality-level LEVEL     lenient(70) | balanced(80) | strict(90)
       --config, -c FILE         Use YAML configuration file
       --output, -o FILE         Specify output filename
       --to-slides               Convert HTML to Reveal.js slides
       -kb, --knowledge-base     Specify knowledge base directory

    \b
    💡 Common Usage Examples:
       # Interactive mode (easiest)
       lecture-forge create
    \b
       # Open results folder
       lecture-forge home outputs
    \b
       # High-quality with web images
       lecture-forge create --image-search --quality-level strict
    \b
       # Edit configuration
       lecture-forge home env
    \b
       # Q&A mode
       lecture-forge chat
    \b
       # Convert to presentation
       lecture-forge improve outputs/lecture.html --to-slides

    \b
    🔧 Environment Config (.env):
       Location: ~/Documents/LectureForge/.env
       Edit: lecture-forge home env
       Customize: SEARCH_NUM_RESULTS, QUALITY_THRESHOLD, etc.

    \b
    📖 More Help:
       lecture-forge <command> --help    # Command-specific help
       cat README.md                     # Full documentation
    """
    # Commands that don't require .env validation
    no_config_commands = ["init"]

    # Validate configuration when a command is actually invoked
    # (skip for --help, --version, init, or when no command is provided)
    if ctx.invoked_subcommand is not None and ctx.invoked_subcommand not in no_config_commands:
        try:
            Config.validate()
            Config.ensure_directories()
        except ValueError as e:
            console.print(f"\n[bold red]❌ Configuration Error:[/bold red]")
            console.print(f"[red]{e}[/red]\n")
            console.print("[yellow]💡 Quick fix: Run 'lecture-forge init' to set up your API keys[/yellow]\n")
            sys.exit(1)
    elif ctx.invoked_subcommand is None:
        # Show basic help when no command is provided
        print_basic_help()


@cli.command()
@click.option("--config", "-c", type=click.Path(exists=True), help="Configuration YAML file with lecture parameters")
@click.option("--interactive", "-i", is_flag=True, help="Enable interactive Q&A mode during generation")
@click.option(
    "--image-search/--no-image-search", default=True, help="Enable image search from web sources (Pexels, default: enabled)"
)
@click.option(
    "--quality-level",
    type=click.Choice(["lenient", "balanced", "strict"]),
    default="balanced",
    help="Quality threshold: lenient(70), balanced(80), strict(90)",
    show_default=True,
)
@click.option("--output", "-o", type=str, help="Output file name without extension (auto-generated if not provided)")
@click.option(
    "--include-pdf-images/--no-include-pdf-images",
    default=True,
    help="Extract images from PDFs with location-based matching (default: enabled since v0.2.0)",
    show_default=True,
)
@click.option(
    "--auto-describe-images/--no-auto-describe-images",
    default=True,
    help="Automatically generate descriptions for PDF images using GPT-4o-mini (only if --include-pdf-images is enabled)",
    show_default=True,
)
def create(
    config: Optional[str],
    interactive: bool,
    image_search: bool,
    quality_level: str,
    output: Optional[str],
    include_pdf_images: bool,
    auto_describe_images: bool,
):
    """
    Create a new lecture material from various sources.

    Generate comprehensive lecture materials using AI-powered multi-agent system.
    Supports PDF files, URLs, web searches, and image collection.

    \b
    Input Sources:
      • PDF files (text extraction only by default)
      • Web URLs (automatic scraping)
      • Web search (via Serper API)
      • Image search (Pexels API - recommended for relevant images)

    \b
    Output:
      • HTML file with lecture content
      • Knowledge base (ChromaDB) for Q&A
      • Embedded code examples and diagrams
      • Token usage and cost estimate

    \b
    Examples:
      # Interactive mode (recommended for first use)
      $ lecture-forge create

      # From config file
      $ lecture-forge create -c my_lecture.yaml

      # With image search enabled
      $ lecture-forge create -c config.yaml --image-search

      # High quality threshold
      $ lecture-forge create --quality-level strict

      # Custom output name
      $ lecture-forge create -o "AI_Basics_2024"

      # Disable PDF images (faster, web images only)
      $ lecture-forge create --no-include-pdf-images

      # High quality with image search (recommended)
      $ lecture-forge create --quality-level strict --image-search

    \b
    Config File Format (YAML):
      topic: "Introduction to Machine Learning"
      duration: 90
      audience_level: "intermediate"
      pdfs:
        - "ml_paper.pdf"
        - "tutorial.pdf"
      urls:
        - "https://example.com/ml-guide"
      keywords:
        - "machine learning basics"
        - "supervised learning"

    \b
    Quality Levels:
      • lenient  (70): Fast, accepts lower quality
      • balanced (80): Recommended, good quality
      • strict   (90): High quality, may take longer

    \b
    Cost:
      Typical 60-min lecture: ~$0.05-0.10 (using GPT-4o-mini)
        • Text generation: ~$0.05
        • Search images (Pexels/Unsplash): Free
        • PDF image extraction: DISABLED by default (poor relevance)
      Execution time: 3-5 minutes
    """
    print_banner()

    console.print("\n[bold]Starting lecture generation...[/bold]\n")

    # Collect inputs
    if config:
        console.print(f"Loading configuration from: {config}")

        # Load from YAML config file
        import yaml

        try:
            with open(config, "r", encoding="utf-8") as f:
                inputs = yaml.safe_load(f)

            # Validate required fields
            required_fields = ["topic", "duration", "audience_level"]
            missing_fields = [f for f in required_fields if f not in inputs]

            if missing_fields:
                console.print(f"[red]❌ Error: Missing required fields in config: {', '.join(missing_fields)}[/red]\n")
                console.print("[yellow]Required fields: topic, duration, audience_level[/yellow]\n")
                sys.exit(1)

            # Set defaults for optional fields
            inputs.setdefault("pdfs", [])
            inputs.setdefault("urls", [])
            inputs.setdefault("keywords", [])
            inputs.setdefault("hada_keywords", [])
            inputs.setdefault("image_keywords", [])

            console.print("[green]✓ Configuration loaded successfully[/green]\n")
            console.print(f"[cyan]Topic:[/cyan] {inputs['topic']}")
            console.print(f"[cyan]Duration:[/cyan] {inputs['duration']} minutes")
            console.print(f"[cyan]Audience:[/cyan] {inputs['audience_level']}\n")

        except yaml.YAMLError as e:
            console.print(f"[red]❌ Error parsing YAML config: {e}[/red]\n")
            sys.exit(1)
        except FileNotFoundError:
            console.print(f"[red]❌ Config file not found: {config}[/red]\n")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]❌ Error loading config: {e}[/red]\n")
            sys.exit(1)
    else:
        inputs = collect_inputs_interactive()

    # Apply settings
    inputs["interactive_mode"] = interactive
    inputs["image_search"] = image_search
    inputs["quality_level"] = quality_level
    inputs["output_name"] = output
    inputs["include_pdf_images"] = include_pdf_images
    inputs["auto_describe_images"] = auto_describe_images

    # Generate lecture
    try:
        result = generate_lecture(inputs)

        console.print("\n[bold green]✅ Lecture generated successfully![/bold green]\n")
        console.print(f"📄 [bold]HTML File:[/bold] {result['html_path']}")
        console.print(f"🗄️  [bold]Knowledge Base:[/bold] {result['vector_db_path']}")
        console.print(f"\n📊 [bold]Statistics:[/bold]")
        console.print(f"   • Sections: {result['sections_count']}")
        console.print(f"   • Words: {result['total_words']:,}")
        console.print(f"   • Code blocks: {result['code_blocks']}")
        console.print(f"   • Diagrams: {result['diagrams']}")
        console.print(f"   • Images: {result['images']}")

        # Display quality metrics
        if "quality_score" in result and result["quality_score"] > 0:
            score = result["quality_score"]
            color = "green" if score >= 80 else "yellow" if score >= 60 else "red"
            console.print(f"   • Quality score: [{color}]{score:.1f}/100[/{color}]")

            if "quality_iterations" in result:
                iterations = result["quality_iterations"]
                if iterations > 0:
                    console.print(f"   • Quality improvements: {iterations} iteration(s)")

        # Display token usage and cost estimate
        if "token_usage" in result:
            display_token_usage(result["token_usage"])

        console.print(f"\n[dim]💡 Open the HTML file in a browser to view the lecture![/dim]\n")

    except Exception as e:
        console.print(f"\n[bold red]❌ Error during generation: {e}[/bold red]")
        logger.exception("Lecture generation failed")
        sys.exit(1)


@cli.command()
@click.option(
    "--knowledge-base",
    "-kb",
    type=click.Path(exists=True),
    help="Path to knowledge base directory (e.g., data/vector_db/my_lecture)",
)
def chat(knowledge_base: Optional[str]):
    """
    Start interactive Q&A mode with knowledge base.

    Chat with AI about the content in your generated lecture using RAG
    (Retrieval Augmented Generation). The AI will answer questions based
    on the knowledge base created during lecture generation.

    \b
    Features:
      • Context-aware answers from your lecture content
      • Source citations with references
      • Conversation history support
      • Commands: /exit, /clear, /sources

    \b
    Examples:
      # Interactive selection from available knowledge bases
      $ lecture-forge chat

      # Direct path to knowledge base
      $ lecture-forge chat -kb data/vector_db/AI_Basics_20260207

      # Use tab completion for paths
      $ lecture-forge chat -kb data/vector_db/<TAB>

    \b
    Q&A Commands:
      /exit     - Exit chat mode
      /clear    - Clear conversation history
      /sources  - Show all sources in knowledge base
      /help     - Show available commands

    \b
    Example Session:
      You: What is supervised learning?
      AI: Supervised learning is a type of machine learning where...

          Sources:
          - ml_basics.pdf (page 12)
          - https://example.com/ml-guide

    \b
    Note:
      Knowledge base is created automatically during 'lecture-forge create'
      and stored in data/vector_db/ directory.
    """
    from lecture_forge.agents.qa_agent import QAAgent

    # If no knowledge base provided, list available ones
    if not knowledge_base:
        knowledge_base = select_knowledge_base()
        if not knowledge_base:
            console.print("[yellow]No knowledge base selected. Exiting.[/yellow]\n")
            return

    # Start Q&A agent
    try:
        qa_agent = QAAgent(knowledge_base)
        qa_agent.start_chat()
    except Exception as e:
        console.print(f"[bold red]❌ Error starting Q&A mode: {e}[/bold red]")
        logger.exception("Q&A mode failed")
        sys.exit(1)


# NOTE: This 'improve' command is disabled due to name conflict with the newer improve command at line 1201
# TODO: Rename this to 'evaluate' or 'improve-quality' if this functionality is still needed
# @cli.command()
# @click.argument("lecture_path", type=click.Path(exists=True))
# @click.option("--threshold", "-t", type=int, default=80, help="Quality threshold (0-100)", show_default=True)
# @click.option("--max-iterations", "-m", type=int, default=3, help="Maximum revision iterations", show_default=True)
def _improve_quality_DISABLED(lecture_path: str, threshold: int, max_iterations: int):
    """
    Re-evaluate and improve existing lecture.

    Load a previously generated HTML lecture file, evaluate its quality,
    and apply iterative improvements until it meets the specified threshold.

    \b
    Process:
      1. Parse HTML to extract lecture content
      2. Evaluate quality across 6 dimensions
      3. Identify issues and improvement areas
      4. Apply revisions (auto-fix or manual)
      5. Re-evaluate and iterate

    \b
    Quality Dimensions:
      • Content Completeness (25%)
      • Logical Flow (20%)
      • Time Alignment (10%)
      • Level Appropriateness (20%)
      • Visual Quality (15%)
      • Technical Accuracy (10%)

    \b
    Examples:
      # Re-evaluate with default threshold (80)
      $ lecture-forge improve outputs/my_lecture.html

      # Higher quality threshold
      $ lecture-forge improve outputs/lecture.html -t 90

      # Limit iterations to prevent long processing
      $ lecture-forge improve outputs/lecture.html -m 2

      # Strict quality with more iterations
      $ lecture-forge improve outputs/lecture.html -t 90 -m 5

    \b
    Output:
      • Updated HTML file (overwrites original)
      • Quality report with scores
      • List of applied improvements
      • Token usage and cost

    \b
    Note:
      Original file is overwritten. Make a backup if needed:
      $ cp outputs/lecture.html outputs/lecture_backup.html
    """
    from lecture_forge.agents.quality_evaluator import QualityEvaluatorAgent
    from lecture_forge.agents.revision_agent import RevisionAgent
    from lecture_forge.agents.html_assembler import HTMLAssemblerAgent

    console.print("\n[bold blue]🔄 Improving Lecture[/bold blue]")
    console.print(f"File: {lecture_path}\n")

    try:
        # Parse HTML to extract lecture data
        lecture = parse_html_to_lecture(lecture_path)

        if not lecture:
            console.print("[red]❌ Failed to parse lecture file[/red]\n")
            return

        console.print(f"[cyan]Lecture:[/cyan] {lecture.title}")
        console.print(f"[cyan]Sections:[/cyan] {len(lecture.sections)}")
        console.print(f"[cyan]Word count:[/cyan] {lecture.total_word_count}\n")

        # Quality evaluation loop
        evaluator = QualityEvaluatorAgent()
        revision_agent = RevisionAgent()
        iteration = 0

        while iteration < max_iterations:
            console.print(f"[bold]Iteration {iteration + 1}/{max_iterations}[/bold]")

            # Evaluate
            with console.status("[cyan]Evaluating quality...[/cyan]"):
                evaluation = evaluator.evaluate(lecture, threshold)

            # Display results
            console.print(f"\n[bold]Quality Score: {evaluation.overall_score:.1f}/100[/bold]")
            console.print(f"Status: {evaluation.get_quality_level()}\n")

            # Show dimension scores
            table = Table(title="Dimension Scores", show_header=True)
            table.add_column("Dimension", style="cyan")
            table.add_column("Score", style="yellow", justify="right")

            for dim, score in evaluation.dimension_scores.items():
                color = "green" if score >= 80 else "yellow" if score >= 60 else "red"
                table.add_row(dim.replace("_", " ").title(), f"[{color}]{score:.1f}[/{color}]")

            console.print(table)
            console.print()

            # Check if passed
            if evaluation.passed:
                console.print("[green]✅ Lecture meets quality standards![/green]\n")
                break

            # Show issues
            if evaluation.issues:
                console.print(f"[yellow]Issues found: {len(evaluation.issues)}[/yellow]")
                for i, issue in enumerate(evaluation.issues[:5], 1):  # Show top 5
                    severity_color = {"high": "red", "medium": "yellow", "low": "blue"}.get(issue.severity, "white")
                    console.print(
                        f"  [{severity_color}]{i}. [{issue.severity.upper()}] {issue.description}[/{severity_color}]"
                    )
                    console.print(f"     💡 {issue.suggestion}")
                console.print()

            # Ask user if they want to continue
            if iteration == 0:
                if not Confirm.ask("[bold]Apply automatic improvements?[/bold]", default=True):
                    console.print("[yellow]Improvement cancelled[/yellow]\n")
                    return

            # Apply revisions
            with console.status("[cyan]Applying improvements...[/cyan]"):
                lecture = revision_agent.revise(lecture, evaluation)

            console.print("[green]✓ Improvements applied[/green]\n")
            iteration += 1

        # Save improved lecture
        if iteration > 0:
            output_path = lecture_path.replace(".html", "_improved.html")
            html_assembler = HTMLAssemblerAgent()

            with console.status("[cyan]Generating improved HTML...[/cyan]"):
                html_assembler.assemble(lecture, output_path=output_path)

            console.print(f"[green]✅ Improved lecture saved: {output_path}[/green]")
            console.print(f"[cyan]Final score: {evaluation.overall_score:.1f}/100[/cyan]\n")
        else:
            console.print("[green]No improvements needed![/green]\n")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        logger.exception("Improvement failed")
        sys.exit(1)


@cli.command()
@click.option(
    "--all",
    "-a",
    is_flag=True,
    help="Delete ALL knowledge bases without confirmation (DANGEROUS)",
)
def cleanup(all: bool):
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


@cli.command()
@click.option(
    "--path",
    type=click.Path(),
    default=None,
    help="Custom directory for .env file (default: platform-specific user directory)",
)
def init(path: Optional[str]) -> None:
    """
    Initialize LectureForge configuration.

    Creates a .env file with your API keys in an easily accessible location.
    This command guides you through setting up required and optional API keys.

    \b
    Default .env Location (v0.3.1+):
      • Windows: %USERPROFILE%\\Documents\\LectureForge\\.env
                 (e.g., C:\\Users\\username\\Documents\\LectureForge\\.env)
      • Mac/Linux: ~/Documents/LectureForge/.env
                   (e.g., /Users/username/Documents/LectureForge/.env)

      ✨ NEW: Visible folder! Accessible from Finder/Explorer.

    \b
    What This Command Does:
      1. Creates configuration directory if it doesn't exist
      2. Prompts for required API keys (OpenAI, Serper)
      3. Optionally prompts for image search APIs (Pexels, Unsplash)
      4. Creates .env file with your settings
      5. Sets secure file permissions (Unix/Mac only)

    \b
    Required API Keys:
      • OpenAI API Key
        - Get from: https://platform.openai.com
        - Used for: Content generation, analysis, embeddings
        - Cost: Pay-per-use (~$0.10 per 60-min lecture)

      • Serper API Key
        - Get from: https://serper.dev
        - Used for: Web search
        - Free tier: 2,500 searches/month

    \b
    Optional API Keys:
      • Pexels API Key (https://pexels.com/api)
        - Free unlimited searches (with rate limits)
        - Used for: Royalty-free stock images

      • Unsplash Access Key (https://unsplash.com/developers)
        - Free tier: 50 requests/hour
        - Used for: High-quality stock photos

    \b
    Examples:
      # Use default location (recommended)
      $ lecture-forge init

      # Use custom directory
      $ lecture-forge init --path /path/to/custom/dir

      # Use current directory
      $ lecture-forge init --path .

    \b
    After Setup:
      Once configured, you can start generating lectures:
        $ lecture-forge create
        $ lecture-forge home outputs      # View results in file manager
        $ lecture-forge home env          # Edit .env file

    \b
    Notes:
      • Existing .env files will prompt for overwrite confirmation
      • API keys are stored locally and never uploaded
      • Edit anytime: lecture-forge home env
      • File permissions are set to owner-only (Unix/Mac)
      • Auto-migration from old ~/.lecture-forge/ (if exists)
    """
    import shutil
    from datetime import datetime

    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]🚀 LectureForge Configuration Setup[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()

    # Determine target path
    if path:
        env_dir = Path(path).expanduser().resolve()
        env_path = env_dir / ".env"
        console.print(f"📁 [dim]Using custom directory: {env_dir}[/dim]\n")
    else:
        from lecture_forge.config import get_default_config_dir

        env_dir = get_default_config_dir()
        env_path = env_dir / ".env"
        console.print(f"📁 [dim]Using default directory: {env_dir}[/dim]\n")

    # Check if already exists
    if env_path.exists():
        console.print(f"[yellow]⚠️  .env file already exists at:[/yellow]")
        console.print(f"[yellow]   {env_path}[/yellow]\n")
        overwrite = Confirm.ask("   Overwrite existing file?", default=False)
        if not overwrite:
            console.print("\n[green]✓ Setup cancelled[/green]\n")
            return
        console.print()

    # Create directory
    try:
        env_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        console.print(f"[red]❌ Failed to create directory: {e}[/red]\n")
        sys.exit(1)

    # Collect API keys
    console.print("[bold cyan]📝 Required API Keys[/bold cyan]\n")

    # OpenAI
    console.print("[bold]1. OpenAI API Key[/bold]")
    console.print("   • Get from: [link]https://platform.openai.com[/link]")
    console.print("   • Used for: LLM generation, embeddings")
    console.print("   • Cost: ~$0.10 per 60-min lecture (GPT-4o-mini)\n")

    openai_key = prompt_masked_input(
        console, "   [cyan]Enter your OpenAI API Key[/cyan] (starts with sk-):"
    )

    while not openai_key or not openai_key.startswith(("sk-", "sk-proj-")):
        console.print(
            "   [red]Invalid format. Should start with 'sk-' or 'sk-proj-'[/red]"
        )
        openai_key = prompt_masked_input(console, "   [cyan]Enter your OpenAI API Key[/cyan]:")

    console.print(f"   [green]✓ OpenAI key saved ({len(openai_key)} characters)[/green]\n")

    # Serper
    console.print("[bold]2. Serper API Key[/bold]")
    console.print("   • Get from: [link]https://serper.dev[/link]")
    console.print("   • Used for: Web search")
    console.print("   • Free tier: 2,500 searches/month\n")

    serper_key = prompt_masked_input(console, "   [cyan]Enter your Serper API Key[/cyan]:")

    while not serper_key or len(serper_key) < 10:
        console.print("   [red]Invalid key. Please check your API key.[/red]")
        serper_key = prompt_masked_input(console, "   [cyan]Enter your Serper API Key[/cyan]:")

    console.print(f"   [green]✓ Serper key saved ({len(serper_key)} characters)[/green]\n")

    # Optional keys
    console.print("[bold cyan]📸 Optional: Image Search APIs[/bold cyan]")
    console.print("[dim]Press Enter to skip if you don't need web image search[/dim]\n")

    # Pexels
    console.print("[bold]3. Pexels API Key (Optional)[/bold]")
    console.print("   • Get from: [link]https://pexels.com/api[/link]")
    console.print("   • Free: Unlimited with rate limits\n")

    pexels_key = prompt_masked_input(
        console,
        "   [cyan]Pexels API Key[/cyan] [dim](or press Enter to skip)[/dim]:",
        allow_empty=True,
    )

    if pexels_key:
        console.print(f"   [green]✓ Pexels key saved ({len(pexels_key)} characters)[/green]\n")
    else:
        console.print("   [dim]⊘ Skipped[/dim]\n")

    # Unsplash
    console.print("[bold]4. Unsplash Access Key (Optional)[/bold]")
    console.print("   • Get from: [link]https://unsplash.com/developers[/link]")
    console.print("   • Free tier: 50 requests/hour\n")

    unsplash_key = prompt_masked_input(
        console,
        "   [cyan]Unsplash Access Key[/cyan] [dim](or press Enter to skip)[/dim]:",
        allow_empty=True,
    )

    if unsplash_key:
        console.print(f"   [green]✓ Unsplash key saved ({len(unsplash_key)} characters)[/green]\n")
    else:
        console.print("   [dim]⊘ Skipped[/dim]\n")

    # Load .env.example template from multiple locations
    template_text = None
    template_locations = []

    # Try 1: Package resources (installed package)
    try:
        import importlib.resources as pkg_resources
        try:
            # Python 3.9+ - Try templates directory first (most reliable)
            template_text = pkg_resources.files("lecture_forge").joinpath("templates/.env.example").read_text(encoding="utf-8")
            template_locations.append("package resources (templates)")
        except (AttributeError, FileNotFoundError):
            try:
                # Try root package directory
                template_text = pkg_resources.files("lecture_forge").joinpath(".env.example").read_text(encoding="utf-8")
                template_locations.append("package resources (root)")
            except (AttributeError, FileNotFoundError):
                # Python 3.7-3.8 fallback
                try:
                    with pkg_resources.path("lecture_forge.templates", ".env.example") as template_path:
                        template_text = template_path.read_text(encoding="utf-8")
                        template_locations.append("package resources (legacy)")
                except (FileNotFoundError, TypeError, ModuleNotFoundError):
                    pass
    except Exception:
        pass

    # Try 2: Source directory (development mode)
    if not template_text:
        try:
            # Try templates directory first
            src_template = Path(__file__).parent / "templates" / ".env.example"
            if src_template.exists():
                template_text = src_template.read_text(encoding="utf-8")
                template_locations.append(f"source templates ({src_template})")
            else:
                # Fallback to parent directory
                src_template = Path(__file__).parent / ".env.example"
                if src_template.exists():
                    template_text = src_template.read_text(encoding="utf-8")
                    template_locations.append(f"source directory ({src_template})")
        except Exception:
            pass

    # Try 3: Project root (fallback for development)
    if not template_text:
        try:
            root_template = Path(__file__).parent.parent.parent / ".env.example"
            if root_template.exists():
                template_text = root_template.read_text(encoding="utf-8")
                template_locations.append(f"project root ({root_template})")
        except Exception:
            pass

    # Final fallback: minimal hardcoded version
    if not template_text:
        console.print(f"[yellow]⚠️  Template not found in any location, using minimal config[/yellow]")
        template_text = f"""# LectureForge Configuration
# Generated by: lecture-forge init
# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# ===== Required API Keys =====
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SERPER_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ===== Optional Image Search APIs =====
UNSPLASH_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
PEXELS_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# For more settings, see: https://github.com/bullpeng72/Lecture_forge
"""
    else:
        # Debug: show where template was loaded from (commented out for production)
        # console.print(f"[dim]Loaded template from: {template_locations[0]}[/dim]")
        pass

    # Replace placeholder values with user input
    # Use regex for more flexible replacement (handles both xxxxx and your_key_here patterns)
    import re

    env_content = re.sub(
        r"OPENAI_API_KEY=.*",
        f"OPENAI_API_KEY={openai_key}",
        template_text
    )
    env_content = re.sub(
        r"SERPER_API_KEY=.*",
        f"SERPER_API_KEY={serper_key}",
        env_content
    )

    # Replace optional keys
    if unsplash_key:
        env_content = re.sub(
            r"UNSPLASH_ACCESS_KEY=.*",
            f"UNSPLASH_ACCESS_KEY={unsplash_key}",
            env_content
        )

    if pexels_key:
        env_content = re.sub(
            r"PEXELS_API_KEY=.*",
            f"PEXELS_API_KEY={pexels_key}",
            env_content
        )

    # Add generation metadata at the top
    metadata = f"""# LectureForge Configuration
# Generated by: lecture-forge init
# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# Platform: {sys.platform}

"""
    env_content = metadata + env_content

    # Write .env file
    try:
        env_path.write_text(env_content, encoding="utf-8")
    except Exception as e:
        console.print(f"[red]❌ Failed to write .env file: {e}[/red]\n")
        sys.exit(1)

    # Set appropriate permissions (Unix-like systems)
    if sys.platform != "win32":
        try:
            env_path.chmod(0o600)  # Read/write for owner only
            console.print("[dim]🔒 File permissions set to owner-only (600)[/dim]\n")
        except Exception:
            pass

    # Success message
    console.print("[bold green]✅ Configuration completed successfully![/bold green]\n")
    console.print(f"📄 Configuration saved to: [cyan]{env_path}[/cyan]\n")

    # Next steps
    console.print("[bold cyan]🎉 Next Steps:[/bold cyan]")
    console.print("   1. Start generating lectures:")
    console.print("      [bold]$ lecture-forge create[/bold]\n")
    console.print("   2. Or see all available commands:")
    console.print("      [bold]$ lecture-forge --help[/bold]\n")

    # Tips
    console.print("[bold cyan]💡 Tips:[/bold cyan]")
    console.print(f"   • Edit settings: [dim]{env_path}[/dim]")
    console.print("   • Generate with images: [dim]lecture-forge create --image-search[/dim]")
    console.print("   • High quality mode: [dim]lecture-forge create --quality-level strict[/dim]\n")


def get_dir_size(path: Path) -> int:
    """Calculate total size of directory in bytes."""
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    except Exception:
        pass
    return total


def format_size(bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes < 1024.0:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.1f} TB"


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


@cli.command()
@click.argument("lecture_path", type=click.Path(exists=True))
@click.option(
    "--enhance-pdf-images",
    is_flag=True,
    help="Generate descriptions for PDF images using page text (costs ~$0.04 per 400 images)",
)
@click.option("--source-pdf", type=click.Path(exists=True), help="Source PDF file (required for --enhance-pdf-images)")
@click.option("--to-slides", is_flag=True, help="Convert lecture to presentation slides format (Reveal.js)")
def improve(lecture_path: str, enhance_pdf_images: bool, source_pdf: str, to_slides: bool):
    """
    Improve existing lecture quality with optional enhancements.

    Apply post-generation improvements to enhance lecture quality:
    - Generate descriptions for PDF images using page text inference
    - Re-match images with better descriptions
    - Update HTML with additional images
    - Convert lecture to presentation slides format

    \b
    Enhancement Options:
      --enhance-pdf-images: Generate descriptions for PDF-extracted images
                            Uses GPT-4o-mini to infer image content from page text
                            Cost: ~$0.04 per 400 images (384 pages)
                            Expected improvement: +50% PDF image usage

      --to-slides:          Convert lecture HTML to Reveal.js slides
                            Creates separate slides.html file
                            Automatically splits content into slides
                            Preserves images, code, and diagrams

    \b
    Slide Keyboard Shortcuts:
      Arrow Keys / Space    - Navigate slides (→ next, ← previous, ↑↓ vertical)
      Home / End            - First / last slide
      Esc / O               - Overview mode (see all slides)
      S                     - Speaker notes (if available)
      F                     - Full screen mode
      B / .                 - Pause/blackout (blank screen)
      Alt+Click             - Zoom to clicked element
      ?                     - Show keyboard shortcuts help

    \b
    Examples:
      # Enhance PDF images with descriptions
      $ lecture-forge improve outputs/lecture.html \\
          --enhance-pdf-images \\
          --source-pdf "AI Engineering Guidebook.pdf"

    \b
      # Convert to presentation slides
      $ lecture-forge improve outputs/lecture.html --to-slides

    \b
      # Combine both enhancements
      $ lecture-forge improve outputs/lecture.html \\
          --enhance-pdf-images --source-pdf "doc.pdf" --to-slides

    \b
    Note:
      - As of v0.1.0, auto-describe is enabled by default during creation
      - This command is for legacy lectures or re-enhancement
      - HTML must be generated by lecture-forge (contains metadata)
      - Source PDF required for --enhance-pdf-images
      - Original lecture file will be backed up before modification
    """
    console.print()
    console.print(Panel.fit("[bold cyan]🔧 LectureForge - Lecture Improvement[/bold cyan]", border_style="cyan"))
    console.print()

    lecture_path = Path(lecture_path)

    if not lecture_path.exists():
        console.print(f"[red]❌ Lecture file not found: {lecture_path}[/red]")
        return

    if enhance_pdf_images:
        if not source_pdf:
            console.print("[red]❌ --source-pdf required when using --enhance-pdf-images[/red]")
            console.print("   Example: --source-pdf 'document.pdf'")
            return

        source_pdf = Path(source_pdf)
        if not source_pdf.exists():
            console.print(f"[red]❌ Source PDF not found: {source_pdf}[/red]")
            return

        # Run PDF image enhancement
        console.print("[bold]Step 1: Enhancing PDF Images[/bold]")
        console.print("━" * 50)

        # Find image directory from HTML metadata
        image_dir = _find_image_dir_from_html(lecture_path)

        if not image_dir:
            console.print("[red]❌ Could not find image directory from HTML metadata[/red]")
            console.print("   Make sure the HTML was generated by lecture-forge")
            return

        console.print(f"   PDF: {source_pdf.name}")
        console.print(f"   Images: {image_dir}")
        console.print()

        # Confirm cost
        console.print("[yellow]⚠️  This will use GPT-4o-mini API (estimated cost: $0.40)[/yellow]")
        if not Confirm.ask("   Proceed with image enhancement?", default=True):
            console.print("\n[green]✓ Cancelled[/green]")
            return

        # Run enhancement
        from lecture_forge.tools.pdf_image_describer import PDFImageDescriber

        describer = PDFImageDescriber()

        with console.status("[bold green]Generating image descriptions..."):
            result = describer.enhance_images(pdf_path=str(source_pdf), image_dir=str(image_dir))

        if not result["success"]:
            console.print(f"[red]❌ Enhancement failed: {result.get('error', 'Unknown error')}[/red]")
            return

        console.print(f"[green]✅ Enhanced {result['enhanced_count']} images[/green]")
        console.print(f"[green]💰 Actual cost: ${result['estimated_cost']:.4f}[/green]")
        console.print()

        # Step 2: Reload and re-generate HTML with new descriptions
        console.print("[bold]Step 2: Re-matching Images[/bold]")
        console.print("━" * 50)
        console.print("   This feature is coming soon!")
        console.print("   Descriptions have been saved to:")
        console.print(f"   {result['descriptions_file']}")
        console.print()
        console.print("[yellow]💡 Tip: For now, you can regenerate the lecture to use new descriptions[/yellow]")

    if to_slides:
        # Run slides conversion
        console.print("[bold]Converting to Presentation Slides[/bold]")
        console.print("━" * 50)
        console.print()

        slides_path = lecture_path.parent / f"{lecture_path.stem}_slides.html"

        with console.status("[bold green]Generating slides..."):
            success = _convert_to_slides(lecture_path, slides_path)

        if success:
            console.print(f"[green]✅ Slides created: {slides_path}[/green]")
            console.print(f"[green]   Open in browser and press 's' for speaker notes[/green]")
            console.print()
        else:
            console.print(f"[red]❌ Slides conversion failed[/red]")

    if not enhance_pdf_images and not to_slides:
        console.print("[yellow]No improvement options specified[/yellow]")
        console.print("Use --enhance-pdf-images to generate PDF image descriptions")
        console.print("Use --to-slides to convert to presentation format")


@cli.command()
@click.argument(
    "target",
    required=False,
    default="",
    type=click.Choice(["", "data", "outputs", "kb", "env"]),
)
def home(target: str):
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


def parse_html_to_lecture(html_path: str):
    """
    Parse HTML file back to Lecture object.

    Args:
        html_path: Path to HTML file

    Returns:
        Lecture object or None if parsing fails
    """
    from bs4 import BeautifulSoup
    from lecture_forge.models.lecture import Lecture, SectionContent, CodeBlock, MermaidDiagram

    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, "html.parser")

        # Extract metadata
        title = soup.find("h1")
        title_text = title.get_text() if title else "Untitled Lecture"

        # Extract learning objectives
        objectives_div = soup.find("div", class_="bg-blue-50")
        objectives = []
        if objectives_div:
            obj_items = objectives_div.find_all("li")
            objectives = [item.get_text() for item in obj_items]

        # Extract sections
        sections = []
        for section_elem in soup.find_all("section", id=True):
            section_id = section_elem.get("id")

            # Get section title
            h2 = section_elem.find("h2")
            if not h2:
                continue

            section_title = h2.get_text()
            # Remove section number (e.g., "1. Title" -> "Title")
            if ". " in section_title:
                section_title = section_title.split(". ", 1)[1]

            # Get content (all text except code blocks and diagrams)
            content_parts = []
            for elem in section_elem.find_all(["p", "h3", "ul", "ol"]):
                content_parts.append(elem.get_text())

            markdown_content = "\n\n".join(content_parts)

            # Extract code blocks
            code_blocks = []
            for pre in section_elem.find_all("pre"):
                code = pre.find("code")
                if code:
                    code_blocks.append(CodeBlock(language="python", code=code.get_text(), caption=None))

            # Extract diagrams
            diagrams = []
            for i, mermaid_div in enumerate(section_elem.find_all("div", class_="mermaid")):
                diagrams.append(
                    MermaidDiagram(
                        id=f"{section_id}_diagram_{i}",
                        title=f"Diagram {i + 1}",
                        mermaid_code=mermaid_div.get_text().strip(),
                        diagram_type="flowchart",
                    )
                )

            section = SectionContent(
                section_id=section_id,
                title=section_title,
                markdown_content=markdown_content,
                code_blocks=code_blocks,
                images=[],
                diagrams=diagrams,
                word_count=len(markdown_content.split()),
            )

            sections.append(section)

        # Create lecture object
        lecture = Lecture(
            title=title_text,
            topic=title_text,
            duration=180,  # Default
            audience_level="intermediate",  # Default
            learning_objectives=objectives,
            sections=sections,
            total_word_count=sum(s.word_count for s in sections),
            total_images=0,
            total_diagrams=sum(len(s.diagrams) for s in sections),
        )

        return lecture

    except Exception as e:
        logger.error(f"Failed to parse HTML: {e}")
        return None


def generate_lecture(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate lecture using the multi-agent pipeline.

    Args:
        inputs: Dictionary with lecture parameters

    Returns:
        Dictionary with generation results
    """
    # Reset token tracker
    tracker = get_tracker()
    tracker.reset()

    # Generate collection name from topic
    # Sanitize topic name for ChromaDB (ASCII only: alphanumeric, underscore, hyphen)
    import re

    topic_safe = inputs["topic"].replace(" ", "_").replace("/", "_").replace("\\", "_")
    # Remove non-ASCII characters (한글 등)
    topic_safe = re.sub(r"[^a-zA-Z0-9_-]", "", topic_safe)
    # If empty after sanitization, use default
    if not topic_safe or len(topic_safe) < 3:
        topic_safe = "lecture"
    # Ensure it starts with alphanumeric
    if not topic_safe[0].isalnum():
        topic_safe = "lec_" + topic_safe
    # Limit length (ChromaDB max: 63 chars, reserve 16 for timestamp)
    topic_safe = topic_safe[:47]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    collection_name = f"{topic_safe}_{timestamp}"

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Phase 1: Content Collection
        task1 = progress.add_task("[cyan]📚 Phase 1: Collecting content...", total=None)
        content_agent = ContentCollectorAgent(collection_name=collection_name)
        content_result = content_agent.collect(
            {
                "pdfs": inputs.get("pdfs", []),
                "urls": inputs.get("urls", []),
                "keywords": inputs.get("keywords", []),
                "hada_keywords": inputs.get("hada_keywords", []),
            }
        )
        progress.update(task1, completed=True)
        console.print(
            f"   ✅ Content collected: {content_result['metadata']['total_docs']} docs, "
            f"{content_result['metadata']['total_chunks']} chunks"
        )

        # Phase 2: Image Collection
        task2 = progress.add_task("[cyan]🖼️  Phase 2: Collecting images...", total=None)
        image_agent = ImageCollectorAgent(
            session_id=collection_name, vector_store=content_agent.vector_store  # Share vector store for RAG integration
        )

        # PDF images now recommended with location-based matching (v0.2.0+)
        pdf_sources = inputs.get("pdfs", []) if inputs.get("include_pdf_images", True) else []

        if not inputs.get("include_pdf_images", True) and inputs.get("pdfs", []):
            console.print("   ⏭️  [dim]Skipping PDF image extraction (disabled by --no-include-pdf-images)[/dim]")
        elif inputs.get("include_pdf_images", True) and inputs.get("pdfs", []):
            console.print("   📸 [cyan]Extracting PDF images with location-based matching[/cyan]")

        image_result = image_agent.collect(
            {
                "pdfs": pdf_sources,
                "urls": inputs.get("urls", []),
                "image_keywords": inputs.get("image_keywords", []),
            },
            # max_images_per_keyword: uses Config.MAX_IMAGES_PER_SEARCH by default
            auto_describe_images=inputs.get("auto_describe_images", True),
        )
        progress.update(task2, completed=True)
        console.print(f"   ✅ Images collected: {image_result['total_collected']}")

        # Phase 3a: Content Analysis
        task3a = progress.add_task("[cyan]🔍 Phase 3a: Analyzing content...", total=None)
        analyzer = ContentAnalyzerAgent(vector_store=content_agent.vector_store)
        analysis_result = analyzer.analyze(
            collection_result=content_result,
            image_result=image_result,
            topic=inputs["topic"],
        )
        progress.update(task3a, completed=True)
        console.print(
            f"   ✅ Analysis complete: {len(analysis_result.key_topics)} topics, " f"{len(analysis_result.entities)} entities"
        )

        # Phase 3b: Curriculum Design
        task3b = progress.add_task("[cyan]📋 Phase 3b: Designing curriculum...", total=None)
        designer = CurriculumDesignerAgent()
        curriculum = designer.design(
            analysis_result=analysis_result,
            topic=inputs["topic"],
            duration=inputs["duration"],
            audience_level=inputs["audience_level"],
        )
        progress.update(task3b, completed=True)
        console.print(
            f"   ✅ Curriculum designed: {len(curriculum.sections)} sections, " f"{curriculum.total_estimated_time} min"
        )

        # Phase 4a: Content Writing
        task4a = progress.add_task("[cyan]✍️  Phase 4a: Writing content (RAG)...", total=None)
        writer = ContentWriterAgent(vector_store=content_agent.vector_store)
        section_contents = writer.write_all_sections(
            curriculum=curriculum,
            available_images=image_result.get("images", []),
        )
        progress.update(task4a, completed=True)
        total_words = sum(s.word_count for s in section_contents)
        total_code_blocks = sum(len(s.code_blocks) for s in section_contents)
        console.print(
            f"   ✅ Content written: {len(section_contents)} sections, "
            f"{total_words} words, {total_code_blocks} code blocks"
        )

        # Phase 4b: Diagram Generation
        task4b = progress.add_task("[cyan]📊 Phase 4b: Generating diagrams...", total=None)
        diagram_gen = DiagramGeneratorAgent()
        section_contents = diagram_gen.generate_diagrams(section_contents)
        progress.update(task4b, completed=True)
        total_diagrams = sum(len(s.diagrams) for s in section_contents)
        console.print(f"   ✅ Diagrams generated: {total_diagrams}")

        # Phase 4c: HTML Assembly
        task4c = progress.add_task("[cyan]🎨 Phase 4c: Assembling HTML...", total=None)
        lecture = Lecture(
            title=f"{inputs['topic']} - {inputs['audience_level'].capitalize()} Level",
            topic=inputs["topic"],
            duration=inputs["duration"],
            audience_level=inputs["audience_level"],
            learning_objectives=curriculum.learning_objectives,
            sections=section_contents,
            total_word_count=total_words,
            total_images=sum(len(s.images) for s in section_contents),
            total_diagrams=total_diagrams,
            vector_db_path=str(content_agent.vector_store.db_path),
            created_at=datetime.now().isoformat(),
        )

        html_assembler = HTMLAssemblerAgent()
        html_path = html_assembler.assemble(lecture, output_path=inputs.get("output_name"))
        progress.update(task4c, completed=True)
        console.print(f"   ✅ HTML assembled: {html_path}")

        # Phase 5: Quality Assurance (optional but enabled by default)
        quality_threshold = {"lenient": 70, "balanced": 80, "strict": 90}.get(inputs.get("quality_level", "balanced"), 80)
        max_iterations = Config.MAX_ITERATIONS

        # Import quality agents
        from lecture_forge.agents.quality_evaluator import QualityEvaluatorAgent
        from lecture_forge.agents.revision_agent import RevisionAgent

        evaluator = QualityEvaluatorAgent()
        revision_agent = RevisionAgent()

        task5 = progress.add_task(f"[cyan]✅ Phase 5: Quality assurance (threshold: {quality_threshold})...", total=None)

        iteration = 0
        previous_score = 0
        improved_lecture = lecture
        quality_improved = False
        final_evaluation = None  # Initialize to avoid UnboundLocalError

        while iteration < max_iterations:
            # Evaluate quality
            evaluation = evaluator.evaluate(improved_lecture, quality_threshold)
            final_evaluation = evaluation  # Save for later use

            console.print(f"\n   📊 Quality evaluation (iteration {iteration + 1}):" f" {evaluation.overall_score:.1f}/100")

            # Check if passed
            if evaluation.passed:
                console.print(f"   ✅ Quality threshold met ({quality_threshold})!")
                if iteration > 0:
                    quality_improved = True
                break

            # Check improvement (prevent infinite loop and degradation)
            if iteration > 0:
                improvement = evaluation.overall_score - previous_score

                if improvement < 2:
                    console.print(f"   ⚠️  Minimal improvement (+{improvement:.1f}). " "Stopping to prevent degradation.")
                    break

                if improvement < 0:
                    console.print(f"   ❌ Quality degraded ({improvement:.1f}). " "Keeping previous version.")
                    # Revert to previous version (would need to be saved)
                    break

            # Show top issues
            if evaluation.issues and iteration == 0:
                console.print(f"   ⚠️  {len(evaluation.issues)} issues found:")
                for issue in evaluation.issues[:3]:  # Show top 3
                    severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(issue.severity, "⚪")
                    console.print(
                        f"      {severity_icon} [{issue.severity}] {issue.dimension}: " f"{issue.description[:80]}..."
                    )

            # Apply revisions
            console.print(f"   🔧 Applying automatic improvements...")
            revised_lecture = revision_agent.revise(improved_lecture, evaluation)

            # Re-evaluate to check actual improvement
            final_evaluation = evaluator.evaluate(revised_lecture, quality_threshold)
            actual_improvement = final_evaluation.overall_score - evaluation.overall_score

            console.print(f"   → After revision: {final_evaluation.overall_score:.1f}/100 " f"(+{actual_improvement:.1f})")

            if actual_improvement > 0:
                improved_lecture = revised_lecture
                previous_score = final_evaluation.overall_score
                quality_improved = True

                # Update word count stats
                total_words = improved_lecture.total_word_count
                total_diagrams = sum(len(s.diagrams) for s in improved_lecture.sections)
            else:
                console.print(f"   ⚠️  Revision did not improve quality. Stopping.")
                break

            iteration += 1

        # Regenerate HTML if improved
        if quality_improved:
            console.print(f"   🎨 Regenerating HTML with improvements...")
            html_path = html_assembler.assemble(improved_lecture, output_path=inputs.get("output_name"))
            lecture = improved_lecture

        progress.update(task5, completed=True)

        if iteration >= max_iterations:
            console.print(f"   ⚠️  Reached max iterations ({max_iterations})")

        if final_evaluation:
            console.print(f"   📊 Final quality score: {final_evaluation.overall_score:.1f}/100\n")

    # Get token usage summary
    token_usage = tracker.get_summary()

    return {
        "html_path": html_path,
        "vector_db_path": str(content_agent.vector_store.db_path),
        "sections_count": len(lecture.sections),
        "total_words": lecture.total_word_count,
        "code_blocks": sum(len(s.code_blocks) for s in lecture.sections),
        "diagrams": sum(len(s.diagrams) for s in lecture.sections),
        "images": sum(len(s.images) for s in lecture.sections),
        "quality_score": final_evaluation.overall_score if final_evaluation else 0,
        "quality_iterations": iteration,
        "token_usage": token_usage,
    }


def _convert_to_bullet_points(text: str) -> List[str]:
    """Convert narrative text to concise bullet points for presentation.

    Args:
        text: Narrative text to convert

    Returns:
        List of bullet point strings
    """
    try:
        import re
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage

        # Skip if text is already short or already in bullet format
        if len(text) < 100 or text.strip().startswith(("•", "-", "*")):
            return [text]

        llm = ChatOpenAI(model=Config.DEFAULT_MODEL, temperature=0.3, api_key=Config.OPENAI_API_KEY)

        prompt = f"""다음 서술식 텍스트를 프레젠테이션 슬라이드에 적합한 개조식 표현으로 변환해주세요.

요구사항:
- 핵심 내용만 간결하게 추출
- 각 포인트는 한 줄로 요약
- 불필요한 접속사나 서술어 제거
- 명사형 종결 또는 간결한 동사형 사용
- 3-5개의 bullet points로 정리
- 각 bullet point는 한글 50자 이내

원문:
{text}

개조식 bullet points (각 줄을 구분하여 출력):"""

        response = llm.invoke([HumanMessage(content=prompt)])
        bullet_text = response.content.strip()

        # Parse bullet points
        bullets = []
        for line in bullet_text.split("\n"):
            line = line.strip()
            # Remove bullet markers if present
            line = line.lstrip("•-*").strip()
            # Remove numbering if present
            line = re.sub(r"^\d+[\.)]\s*", "", line)
            if line and len(line) > 5:  # Filter out very short lines
                bullets.append(line)

        return bullets if bullets else [text]

    except Exception as e:
        logger.warning(f"Failed to convert to bullet points: {e}")
        # Fallback: split by sentences
        import re

        sentences = re.split(r"[.!?]\s+", text)
        return [s.strip() for s in sentences if len(s.strip()) > 10][:5]


def _convert_to_slides(lecture_html_path: Path, output_path: Path) -> bool:
    """Convert lecture HTML to Reveal.js presentation slides.

    Args:
        lecture_html_path: Path to the lecture HTML file
        output_path: Path for the output slides HTML

    Returns:
        True if successful, False otherwise
    """
    try:
        from bs4 import BeautifulSoup
        import re

        console.print("\n[cyan]📊 슬라이드 변환 중...[/cyan]")
        console.print("   • 서술식 텍스트를 개조식으로 변환합니다...")

        # Read the lecture HTML
        with open(lecture_html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, "html.parser")

        # Extract lecture metadata
        title_tag = soup.find("h1", class_="lecture-title")
        title = title_tag.text.strip() if title_tag else "Lecture Slides"

        subtitle_tag = soup.find("p", class_="lecture-subtitle")
        subtitle = subtitle_tag.text.strip() if subtitle_tag else ""

        # Extract sections - find all <section> tags with id
        sections = []
        section_elements = soup.find_all("section", id=True)

        logger.debug(f"Found {len(section_elements)} sections in HTML")

        # Track conversion progress
        total_sections = len(section_elements)
        converted_paragraphs = 0

        for idx, section_elem in enumerate(section_elements, 1):
            console.print(f"   • 섹션 {idx}/{total_sections} 처리 중...", end="\r")
            # Find section title (h2)
            section_title_tag = section_elem.find("h2")
            if not section_title_tag:
                logger.debug(f"Skipping section without h2: {section_elem.get('id')}")
                continue

            # Extract title and remove numbering (e.g., "1. Introduction" -> "Introduction")
            section_title_raw = section_title_tag.text.strip()

            # Remove leading number and dot (e.g., "1. ", "2. ", etc.)
            section_title = re.sub(r"^\d+\.\s*", "", section_title_raw)

            logger.debug(f"Processing section: {section_title_raw} -> {section_title}")

            # Extract content blocks directly from section element
            content_blocks = []

            # Find content directly in section (not in nested div)
            # The structure is: <section><h2/><h4/><p/>...</section>
            # Look for all content elements but exclude the section title (h2)
            for elem in section_elem.find_all(["h3", "h4", "p", "ul", "ol", "pre"]):
                if elem.name == "h3":
                    content_blocks.append({"type": "subsection", "content": elem.text.strip()})
                elif elem.name == "h4":
                    text = elem.text.strip()
                    # Skip empty h4 tags
                    if text:
                        content_blocks.append({"type": "subsubsection", "content": text})
                elif elem.name == "p":
                    text = elem.text.strip()
                    # Filter out very short paragraphs and paragraphs inside code blocks
                    if text and len(text) > 20 and not elem.find_parent("pre"):
                        # Convert narrative text to bullet points for presentation
                        bullet_points = _convert_to_bullet_points(text)
                        converted_paragraphs += 1
                        if len(bullet_points) > 1:
                            # Multiple bullet points - add as list
                            content_blocks.append({"type": "list", "items": bullet_points, "ordered": False})
                        else:
                            # Single point or short text - keep as paragraph
                            content_blocks.append({"type": "paragraph", "content": bullet_points[0]})
                elif elem.name in ["ul", "ol"]:
                    # Extract list items (already in bullet format)
                    items = [li.text.strip() for li in elem.find_all("li", recursive=False)]
                    if items:
                        content_blocks.append({"type": "list", "items": items, "ordered": elem.name == "ol"})
                elif elem.name == "pre":
                    code_elem = elem.find("code")
                    if code_elem:
                        code = code_elem.text.strip()
                        language = "python"  # default
                        if "class" in code_elem.attrs:
                            for cls in code_elem["class"]:
                                if cls.startswith("language-"):
                                    language = cls.replace("language-", "")
                                    break
                        if code:  # Only add non-empty code blocks
                            content_blocks.append({"type": "code", "content": code, "language": language})

            # Find images (figure elements)
            for figure in section_elem.find_all("figure"):
                img = figure.find("img")
                if img:
                    img_src = img.get("src", "")
                    img_alt = img.get("alt", "")
                    caption_elem = figure.find("figcaption")
                    caption = caption_elem.text.strip() if caption_elem else ""
                    if img_src:
                        content_blocks.append({"type": "image", "src": img_src, "alt": img_alt, "caption": caption})

            # Find diagrams (mermaid divs)
            for diagram_div in section_elem.find_all("div", class_="mermaid"):
                mermaid_code = diagram_div.text.strip()
                if mermaid_code:
                    content_blocks.append({"type": "diagram", "content": mermaid_code})

            sections.append({"title": section_title, "blocks": content_blocks})

        # Clear progress line
        console.print(" " * 80, end="\r")
        console.print(f"   ✅ {converted_paragraphs}개 단락을 개조식으로 변환했습니다.")

        # Generate Reveal.js HTML
        console.print("   • 슬라이드 HTML 생성 중...")
        slides_html = _generate_reveal_html(title, subtitle, sections)

        # Write to output file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(slides_html)

        return True

    except Exception as e:
        logger.error(f"Error converting to slides: {e}")
        return False


def _generate_reveal_html(title: str, subtitle: str, sections: List[dict]) -> str:
    """Generate Reveal.js HTML from lecture content.

    Args:
        title: Lecture title
        subtitle: Lecture subtitle
        sections: List of section dictionaries

    Returns:
        Complete HTML string for Reveal.js presentation
    """
    slides_content = []

    # Title slide (Korean)
    slides_content.append(
        f"""
    <section data-transition="zoom">
        <h1>{title}</h1>
        {f'<p class="subtitle">{subtitle}</p>' if subtitle else ''}
        <p><small>LectureForge로 생성됨</small></p>
    </section>
    """
    )

    # Section slides
    for section in sections:
        section_title = section["title"]
        blocks = section["blocks"]

        # Section title slide
        slides_content.append(
            f"""
    <section data-transition="convex">
        <h2>{section_title}</h2>
    </section>
        """
        )

        # Content slides - group content into logical slides
        current_slide_content = []
        slide_item_count = 0
        max_items_per_slide = 3  # Reduced from 4 to 3 for better presentation
        max_bullet_points = 5  # Maximum bullet points per slide

        # Slide composition strategy:
        # - h3 (subsection): Always starts new slide
        # - h4 (subsubsection): Stay with following content via look-ahead
        # - Avoid orphaned h4 at slide end (look-ahead prevents this)

        for idx, block in enumerate(blocks):
            block_type = block["type"]

            if block_type == "subsection":
                # Subsection starts a new slide (always)
                if current_slide_content:
                    slides_content.append(_create_content_slide(current_slide_content))
                    current_slide_content = []
                    slide_item_count = 0

                # Create a dedicated title slide for subsection (presentation style)
                slides_content.append(
                    f"""
    <section data-transition="slide">
        <h2>{block['content']}</h2>
    </section>
                    """
                )

            elif block_type == "subsubsection":
                # h4 acts as slide title - always start a new slide
                if current_slide_content:
                    slides_content.append(_create_content_slide(current_slide_content))
                    current_slide_content = []
                    slide_item_count = 0

                # Add h4 as the slide title
                current_slide_content.append(f"<h3>{block['content']}</h3>")
                slide_item_count += 1  # Count as 1 item (title)

            elif block_type == "paragraph":
                current_slide_content.append(f"<p>{block['content']}</p>")
                slide_item_count += 1

            elif block_type == "list":
                # Format list - split if too long
                list_items = block["items"]
                list_tag = "ol" if block.get("ordered", False) else "ul"

                # If list is too long, split it into multiple slides
                if len(list_items) > max_bullet_points:
                    # Split the list
                    for i in range(0, len(list_items), max_bullet_points):
                        chunk = list_items[i:i + max_bullet_points]

                        # If current slide has content, finish it first
                        if current_slide_content:
                            slides_content.append(_create_content_slide(current_slide_content))
                            current_slide_content = []
                            slide_item_count = 0

                        # Create slide with list chunk
                        items_html = "".join(f"<li>{item}</li>" for item in chunk)
                        current_slide_content.append(f"<{list_tag}>{items_html}</{list_tag}>")

                        # Add continuation indicator if needed
                        if i + max_bullet_points < len(list_items):
                            current_slide_content.append("<p><em>(계속...)</em></p>")

                        # Finish this slide
                        slides_content.append(_create_content_slide(current_slide_content))
                        current_slide_content = []
                        slide_item_count = 0
                else:
                    # Short list - add to current slide
                    items_html = "".join(f"<li>{item}</li>" for item in list_items)
                    current_slide_content.append(f"<{list_tag}>{items_html}</{list_tag}>")
                    slide_item_count += 1

            elif block_type == "code":
                # Code blocks take a full slide
                if current_slide_content:
                    slides_content.append(_create_content_slide(current_slide_content))
                    current_slide_content = []
                    slide_item_count = 0

                language = block.get("language", "")
                # Add a title for code slides
                code_title = "코드 예제" if language == "python" else f"{language.upper()} 코드"
                slides_content.append(
                    f"""
    <section>
        <h3>{code_title}</h3>
        <pre><code class="language-{language}" data-trim data-noescape>
{block['content']}
        </code></pre>
    </section>
                """
                )

            elif block_type == "image":
                # Images take a full slide
                if current_slide_content:
                    slides_content.append(_create_content_slide(current_slide_content))
                    current_slide_content = []
                    slide_item_count = 0

                caption = block.get("caption", "")
                slides_content.append(
                    f"""
    <section>
        <img src="{block['src']}" alt="{block['alt']}" style="max-height: 500px; max-width: 90%;">
        {f'<p><small>{caption}</small></p>' if caption else ''}
    </section>
                """
                )

            elif block_type == "diagram":
                # Diagrams take a full slide
                if current_slide_content:
                    slides_content.append(_create_content_slide(current_slide_content))
                    current_slide_content = []
                    slide_item_count = 0

                # Clean and escape mermaid code

                mermaid_code = block["content"].strip()

                # Wrap in pre tag for better rendering
                slides_content.append(
                    f"""
    <section>
        <div class="mermaid">
{mermaid_code}
        </div>
    </section>
                """
                )

            # Check if we should start a new slide (smarter logic)
            should_break = False

            # Break if we've reached the item limit
            if slide_item_count >= max_items_per_slide:
                should_break = True

            # Don't break if next item is closely related
            if should_break and idx + 1 < len(blocks):
                next_block = blocks[idx + 1]
                # Don't break before a new subsection or subsubsection (they handle their own breaks)
                if next_block["type"] in ["subsection", "subsubsection", "code", "image", "diagram"]:
                    should_break = False

            if should_break and current_slide_content:
                slides_content.append(_create_content_slide(current_slide_content))
                current_slide_content = []
                slide_item_count = 0

        # Add remaining content
        if current_slide_content:
            slides_content.append(_create_content_slide(current_slide_content))

    # End slide (Korean)
    slides_content.append(
        """
    <section data-transition="zoom">
        <h2>감사합니다!</h2>
        <p>질문이 있으신가요?</p>
        <p><small>LectureForge로 생성됨</small></p>
    </section>
    """
    )

    # Complete HTML template (Korean)
    html_template = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - 슬라이드</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.5.0/reveal.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.5.0/theme/white.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.5.0/plugin/highlight/monokai.min.css">
    <style>
        /* 한국어 폰트 및 스타일 */
        .reveal {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Malgun Gothic", "맑은 고딕", "Apple SD Gothic Neo", sans-serif;
        }}
        .reveal h1, .reveal h2, .reveal h3, .reveal h4 {{
            text-transform: none;
            font-weight: bold;
            margin-bottom: 0.8em;
        }}
        .reveal h1 {{
            font-size: 2.5em;
        }}
        .reveal h2 {{
            font-size: 2em;
            color: #2c3e50;
        }}
        .reveal h3 {{
            font-size: 1.6em;
            color: #34495e;
            margin-top: 0.5em;
        }}
        .reveal h4 {{
            font-size: 1.3em;
            color: #7f8c8d;
        }}
        .reveal p {{
            text-align: left;
            line-height: 1.8;
            font-size: 0.9em;
            margin: 0.6em 0;
        }}
        .reveal ul, .reveal ol {{
            text-align: left;
            line-height: 2.2;
            font-size: 0.85em;
            margin: 1em 0;
        }}
        .reveal li {{
            margin: 0.8em 0;
        }}
        .reveal ul li::marker {{
            color: #3498db;
            font-size: 1.2em;
        }}
        .reveal em {{
            color: #95a5a6;
            font-style: italic;
        }}
        .reveal pre {{
            width: 100%;
            font-size: 0.5em;
            margin: 1.5em 0;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        .reveal code {{
            max-height: 520px;
            font-family: "Monaco", "Menlo", "Consolas", "Courier New", monospace;
            line-height: 1.5;
            padding: 1.5em;
        }}
        .reveal .slides section {{
            text-align: left;
            /* Reduced scroll, better presentation fit */
            height: auto !important;
            max-height: 700px;
            overflow-y: auto;
            overflow-x: hidden;
            padding: 40px 50px;
            box-sizing: border-box;
            display: flex !important;
            flex-direction: column;
            justify-content: flex-start;
            align-items: flex-start;
        }}
        /* Center-aligned slides (title, subsection) */
        .reveal .slides section[data-transition="zoom"],
        .reveal .slides section[data-transition="slide"] {{
            justify-content: center;
            align-items: center;
            text-align: center;
        }}
        .reveal .slides section[data-transition="zoom"] {{
            text-align: center;
        }}
        /* 스크롤바 스타일 (WebKit 브라우저: Chrome, Safari, Edge) */
        .reveal .slides section::-webkit-scrollbar {{
            width: 8px;
        }}
        .reveal .slides section::-webkit-scrollbar-track {{
            background: rgba(0, 0, 0, 0.1);
            border-radius: 4px;
        }}
        .reveal .slides section::-webkit-scrollbar-thumb {{
            background: rgba(0, 0, 0, 0.3);
            border-radius: 4px;
        }}
        .reveal .slides section::-webkit-scrollbar-thumb:hover {{
            background: rgba(0, 0, 0, 0.5);
        }}
        /* Firefox 스크롤바 스타일 */
        .reveal .slides section {{
            scrollbar-width: thin;
            scrollbar-color: rgba(0, 0, 0, 0.3) rgba(0, 0, 0, 0.1);
        }}
        /* Mermaid 다이어그램 스타일 */
        .reveal .mermaid {{
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            max-height: 600px;
            overflow: auto;
        }}
        /* 긴 리스트 스크롤 지원 */
        .reveal ul, .reveal ol {{
            max-height: none; /* section에서 스크롤 처리 */
        }}
        /* 코드 블록 스크롤 */
        .reveal pre {{
            max-height: 550px;
            overflow-y: auto;
        }}
        .reveal pre::-webkit-scrollbar {{
            width: 6px;
            height: 6px;
        }}
        .reveal pre::-webkit-scrollbar-thumb {{
            background: rgba(255, 255, 255, 0.3);
            border-radius: 3px;
        }}
    </style>
</head>
<body>
    <div class="reveal">
        <div class="slides">
{''.join(slides_content)}
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.5.0/reveal.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.5.0/plugin/highlight/highlight.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.5.0/plugin/markdown/markdown.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.5.0/plugin/notes/notes.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script>
        // Reveal.js 초기화
        Reveal.initialize({{
            hash: true,
            transition: 'slide',
            plugins: [ RevealHighlight, RevealMarkdown, RevealNotes ],
            slideNumber: 'c/t',  // 현재/전체
            controls: true,
            progress: true,
            center: false,  // 좌측 정렬 (스크롤 지원)
            mouseWheel: false,
            width: 1280,
            height: 720,
            margin: 0.04,
            minScale: 0.2,
            maxScale: 2.0,
            // 슬라이드 레이아웃 설정
            display: 'block',
            // 스크롤 가능 슬라이드 지원
            scrollActivationWidth: null,
        }}).then(() => {{
            // Reveal.js 초기화 후 Mermaid 초기화
            mermaid.initialize({{
                startOnLoad: true,
                theme: 'default',
                securityLevel: 'loose',
                flowchart: {{
                    useMaxWidth: true,
                    htmlLabels: true,
                    curve: 'basis'
                }}
            }});

            // 모든 mermaid 다이어그램 렌더링
            mermaid.contentLoaded();

            // 스크롤 인디케이터 관리 함수
            const updateScrollIndicator = (section) => {{
                if (!section) return;

                // 기존 인디케이터 제거
                const oldIndicator = section.querySelector('.scroll-indicator');
                if (oldIndicator) {{
                    oldIndicator.remove();
                }}

                // 스크롤이 필요한지 확인 (여유 20px)
                const needsScroll = section.scrollHeight > (section.clientHeight + 20);

                if (needsScroll) {{
                    const indicator = document.createElement('div');
                    indicator.className = 'scroll-indicator';
                    indicator.innerHTML = '↓ 아래로 스크롤하세요 ↓';
                    indicator.style.cssText = `
                        position: fixed;
                        bottom: 40px;
                        left: 50%;
                        transform: translateX(-50%);
                        background: rgba(0, 0, 0, 0.7);
                        color: white;
                        padding: 8px 16px;
                        border-radius: 20px;
                        font-size: 0.8em;
                        animation: pulse 2s infinite;
                        pointer-events: none;
                        z-index: 1000;
                        transition: opacity 0.3s;
                    `;
                    document.body.appendChild(indicator);

                    // 스크롤 시 인디케이터 숨기기
                    const scrollHandler = () => {{
                        const scrollPercent = (section.scrollTop / (section.scrollHeight - section.clientHeight)) * 100;
                        if (scrollPercent > 5) {{
                            indicator.style.opacity = '0';
                        }} else {{
                            indicator.style.opacity = '1';
                        }}

                        // 스크롤이 맨 아래면 인디케이터 제거
                        if (scrollPercent > 95) {{
                            indicator.remove();
                            section.removeEventListener('scroll', scrollHandler);
                        }}
                    }};

                    section.addEventListener('scroll', scrollHandler);

                    // 슬라이드 변경 시 인디케이터 제거
                    const cleanup = () => {{
                        indicator.remove();
                        section.removeEventListener('scroll', scrollHandler);
                    }};

                    section.dataset.cleanupIndicator = 'registered';
                    Reveal.on('slidechanged', cleanup);
                }}
            }};

            // 슬라이드 변경 시 처리
            Reveal.on('slidechanged', event => {{
                // 현재 슬라이드의 스크롤을 맨 위로
                event.currentSlide.scrollTop = 0;

                // 모든 기존 인디케이터 제거
                document.querySelectorAll('.scroll-indicator').forEach(ind => ind.remove());

                // 새 슬라이드에 인디케이터 추가
                setTimeout(() => {{
                    updateScrollIndicator(event.currentSlide);
                }}, 100);
            }});

            // 초기 슬라이드에 인디케이터 추가
            Reveal.on('ready', () => {{
                setTimeout(() => {{
                    const currentSlide = Reveal.getCurrentSlide();
                    updateScrollIndicator(currentSlide);
                }}, 300);
            }});
        }});

        // 펄스 애니메이션 추가
        const style = document.createElement('style');
        style.textContent = `
            @keyframes pulse {{
                0%, 100% {{ opacity: 0.6; }}
                50% {{ opacity: 1; }}
            }}
        `;
        document.head.appendChild(style);
    </script>
</body>
</html>
    """

    return html_template


def _create_content_slide(content_items: List[str]) -> str:
    """Create a content slide from a list of HTML elements.

    Args:
        content_items: List of HTML strings

    Returns:
        Complete section HTML
    """
    return f"""
    <section>
{''.join(content_items)}
    </section>
    """


@cli.command("edit-images")
@click.argument("html_path", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output file path (default: <original>_edited.html)")
def edit_images(html_path: str, output: str):
    """
    Edit images in generated HTML lecture (interactive mode).

    Provides an interactive interface to:
    - View all images in the lecture
    - Delete unwanted images
    - Replace images with alternatives from Vector DB
    - Save changes to new HTML file

    \b
    Features:
      • Real-time preview of all images in the lecture
      • Delete unwanted images (d <number>)
      • Undo deletions (u <number>)
      • Replace images with RAG-based alternatives (r <number>)
      • Save changes to new file (preserves original)

    \b
    Examples:
      # Interactive editing mode
      $ lecture-forge edit-images outputs/lecture.html

    \b
      # Specify output file
      $ lecture-forge edit-images lecture.html -o new_lecture.html

    \b
    Interactive Commands:
      d <number>    - Delete image (e.g., d 3)
      u <number>    - Undo deletion (e.g., u 3)
      r <number>    - Replace image (search alternatives)
      s             - Save changes
      q             - Quit without saving
      h             - Show help
    """
    from rich.console import Console
    from rich.prompt import Prompt, Confirm
    from lecture_forge.tools.image_editor import ImageEditor

    console = Console()

    try:
        # Initialize editor
        console.print("\n[bold cyan]📸 강의 이미지 편집 모드[/bold cyan]")
        console.print("━" * 60)

        with console.status("[bold green]HTML 로딩 중..."):
            editor = ImageEditor(html_path)

        # Display summary
        console.print(f"\n[bold]HTML:[/bold] {Path(html_path).name}")
        console.print(f"[bold]총 이미지:[/bold] {len(editor.images)}개\n")

        # Main loop
        while True:
            # Display current images
            _display_image_table(console, editor)

            # Display help
            console.print("\n[bold cyan]명령어:[/bold cyan]")
            console.print("  [bold]d <번호>[/bold]     - 이미지 삭제 (예: d 3)")
            console.print("  [bold]u <번호>[/bold]     - 삭제 취소 (예: u 3)")
            console.print("  [bold]r <번호>[/bold]     - 이미지 교체 (대안 검색)")
            console.print("  [bold]s[/bold]            - 변경사항 저장")
            console.print("  [bold]q[/bold]            - 취소 및 종료")
            console.print("  [bold]h[/bold]            - 도움말 표시\n")

            # Get command
            command = Prompt.ask("[bold yellow]명령 입력[/bold yellow]").strip().lower()

            if not command:
                continue

            # Parse command
            parts = command.split()
            cmd = parts[0]
            args = parts[1:] if len(parts) > 1 else []

            # Handle commands
            if cmd == "q" or cmd == "quit" or cmd == "exit":
                if editor.get_summary()["to_delete"] > 0 or editor.get_summary()["to_replace"] > 0:
                    if Confirm.ask("[yellow]변경사항이 저장되지 않았습니다. 종료하시겠습니까?[/yellow]"):
                        console.print("[red]변경사항 취소됨[/red]")
                        break
                else:
                    break

            elif cmd == "d" or cmd == "delete":
                if not args:
                    console.print("[red]❌ 이미지 번호를 입력하세요 (예: d 3)[/red]")
                    continue

                try:
                    img_num = int(args[0])
                    if editor.mark_delete(img_num):
                        console.print(f"[green]✅ 이미지 {img_num} 삭제 표시됨[/green]")
                    else:
                        console.print(f"[red]❌ 잘못된 이미지 번호: {img_num}[/red]")
                except ValueError:
                    console.print("[red]❌ 유효한 숫자를 입력하세요[/red]")

            elif cmd == "u" or cmd == "undo" or cmd == "undelete":
                if not args:
                    console.print("[red]❌ 이미지 번호를 입력하세요 (예: u 3)[/red]")
                    continue

                try:
                    img_num = int(args[0])
                    if editor.unmark_delete(img_num):
                        console.print(f"[green]✅ 이미지 {img_num} 삭제 취소됨[/green]")
                    else:
                        console.print(f"[yellow]⚠️ 이미지 {img_num}는 삭제 표시되지 않았습니다[/yellow]")
                except ValueError:
                    console.print("[red]❌ 유효한 숫자를 입력하세요[/red]")

            elif cmd == "r" or cmd == "replace":
                if not args:
                    console.print("[red]❌ 이미지 번호를 입력하세요 (예: r 3)[/red]")
                    continue

                try:
                    img_num = int(args[0])
                    _handle_replace_image(console, editor, img_num)
                except ValueError:
                    console.print("[red]❌ 유효한 숫자를 입력하세요[/red]")

            elif cmd == "s" or cmd == "save":
                _handle_save_changes(console, editor, output)
                break

            elif cmd == "h" or cmd == "help":
                _display_help(console)

            else:
                console.print(f"[red]❌ 알 수 없는 명령어: {cmd}[/red]")
                console.print("[yellow]힌트: 'h' 를 입력하여 도움말 보기[/yellow]")

    except Exception as e:
        console.print(f"\n[bold red]❌ 오류 발생:[/bold red] {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise click.Abort()


def _display_image_table(console, editor):
    """Display image table."""
    images = editor.list_images()

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("번호", style="dim", width=6)
    table.add_column("설명", width=35)
    table.add_column("섹션", width=25)
    table.add_column("페이지", width=8)
    table.add_column("상태", width=10)

    for img in images:
        status_style = "green"
        status_text = "유지"

        if img["status"] == "delete":
            status_style = "red"
            status_text = "🗑️ 삭제"
        elif img["status"] == "replace":
            status_style = "yellow"
            status_text = "🔄 교체"

        table.add_row(
            str(img["index"]),
            img["description"] or "[dim]설명 없음[/dim]",
            img["section"],
            str(img["page"]) if img["page"] else "-",
            f"[{status_style}]{status_text}[/{status_style}]",
        )

    console.print(table)


def _handle_replace_image(console, editor, img_num):
    """Handle image replacement."""
    console.print(f"\n[bold cyan]🔍 이미지 {img_num} 대안 검색 중...[/bold cyan]")

    alternatives = editor.find_alternative_images(img_num, max_results=5)

    if not alternatives:
        console.print("[yellow]⚠️ 대안 이미지를 찾을 수 없습니다[/yellow]")
        console.print("[dim]힌트: Vector DB가 로드되지 않았거나 관련 이미지가 없습니다[/dim]")
        return

    # Display alternatives
    console.print(f"\n[bold green]대안 이미지 ({len(alternatives)}개):[/bold green]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("번호", width=6)
    table.add_column("설명", width=50)
    table.add_column("페이지", width=8)
    table.add_column("출처", width=20)

    for alt in alternatives:
        table.add_row(str(alt["index"]), alt["description"], str(alt["page"]) if alt["page"] else "-", alt["source"])

    console.print(table)

    # Prompt for selection
    console.print("\n[dim]0: 취소[/dim]")
    choice = Prompt.ask("[bold yellow]선택[/bold yellow]", default="0")

    try:
        choice_num = int(choice)
        if choice_num == 0:
            console.print("[yellow]교체 취소됨[/yellow]")
            return

        if 1 <= choice_num <= len(alternatives):
            selected = alternatives[choice_num - 1]
            if editor.replace_image(img_num, selected["path"]):
                console.print(f"[green]✅ 이미지 {img_num} 교체 예정[/green]")
                console.print(f"[dim]   새 이미지: {selected['description'][:60]}[/dim]")
            else:
                console.print("[red]❌ 교체 실패[/red]")
        else:
            console.print("[red]❌ 잘못된 선택[/red]")

    except ValueError:
        console.print("[red]❌ 유효한 숫자를 입력하세요[/red]")


def _handle_save_changes(console, editor, output_path):
    """Handle saving changes."""
    summary = editor.get_summary()

    if summary["to_delete"] == 0 and summary["to_replace"] == 0:
        console.print("\n[yellow]⚠️ 변경사항이 없습니다[/yellow]")
        return

    # Display summary
    console.print("\n[bold cyan]💾 변경사항 요약:[/bold cyan]")
    if summary["to_delete"] > 0:
        console.print(f"  • 삭제: [red]{summary['to_delete']}개[/red]")
    if summary["to_replace"] > 0:
        console.print(f"  • 교체: [yellow]{summary['to_replace']}개[/yellow]")

    console.print()

    # Confirm
    if not Confirm.ask("[bold yellow]변경사항을 저장하시겠습니까?[/bold yellow]"):
        console.print("[yellow]저장 취소됨[/yellow]")
        return

    # Save
    try:
        with console.status("[bold green]저장 중..."):
            saved_path = editor.save_changes(output_path)

        console.print(f"\n[bold green]✅ 저장 완료![/bold green]")
        console.print(f"[bold]파일:[/bold] {saved_path}")

        # Display changes
        if summary["to_delete"] > 0:
            console.print(f"  • [red]삭제됨:[/red] {summary['to_delete']}개 이미지")
        if summary["to_replace"] > 0:
            console.print(f"  • [yellow]교체됨:[/yellow] {summary['to_replace']}개 이미지")

    except Exception as e:
        console.print(f"\n[bold red]❌ 저장 실패:[/bold red] {e}")
        raise


def _display_help(console):
    """Display help message."""
    help_text = """
[bold cyan]📖 이미지 편집 도움말[/bold cyan]

[bold]기본 명령어:[/bold]
  • [bold]d <번호>[/bold]  - 이미지 삭제 표시
    예: d 3 → 3번 이미지 삭제 표시

  • [bold]u <번호>[/bold]  - 삭제 취소
    예: u 3 → 3번 이미지 삭제 취소

  • [bold]r <번호>[/bold]  - 이미지 교체
    예: r 5 → 5번 이미지를 대안 이미지로 교체
    (Vector DB에서 관련 이미지 자동 검색)

  • [bold]s[/bold]         - 변경사항 저장 후 종료

  • [bold]q[/bold]         - 취소 및 종료

[bold yellow]💡 사용 팁:[/bold yellow]
  1. 먼저 강의를 브라우저에서 열어 이미지를 확인하세요
  2. 불필요한 이미지는 'd' 명령어로 삭제 표시
  3. 교체가 필요한 이미지는 'r' 명령어 사용
  4. 모든 변경사항을 검토한 후 's'로 저장

[bold cyan]📋 이미지 상태:[/bold cyan]
  • [green]유지[/green]   - 변경 없음
  • [red]🗑️ 삭제[/red] - 삭제 예정
  • [yellow]🔄 교체[/yellow] - 교체 예정
"""
    console.print(Panel(help_text, border_style="cyan"))


def main():
    """Main entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]⚠️  Interrupted by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]❌ Error: {e}[/bold red]")
        logger.exception("Unexpected error")
        sys.exit(1)


if __name__ == "__main__":
    main()
