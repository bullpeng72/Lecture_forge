"""
Formatting utilities for CLI output.
"""

from typing import Any, Dict

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from lecture_forge.__version__ import __version__

# Shared console instance
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
            "[dim]10 Agents | 9 Tools | 8 Commands | 1,356+ Tests | ~$0.035 per 60min lecture[/dim]",
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
    table.add_row("translate", "Translate English PDF to Korean HTML", "--no-translate")
    table.add_row("chat", "Interactive Q&A (RAG-based)", "-kb PATH")
    table.add_row("edit-images", "Edit lecture images", "-o FILE")
    table.add_row("improve", "Enhance or convert lecture", "--to-slides")
    table.add_row("cleanup", "Manage knowledge bases", "--all")
    table.add_row("[bold green]home[/bold green]", "[bold]Open folders[/bold] in file manager", "outputs/data/env")
    console.print(table)

    # Common Options (for create command)
    console.print("\n[bold yellow]⚙️  Common Options (create command):[/bold yellow]")
    opt_table = Table(show_header=False, box=None, padding=(0, 1))
    opt_table.add_column("Option", style="green", width=24)
    opt_table.add_column("Description", width=50)

    opt_table.add_row("--image-search", "Enable Pexels/Unsplash image search")
    opt_table.add_row("--quality-level LEVEL", "lenient(70) | balanced(80) | strict(90)")
    opt_table.add_row("--config, -c FILE", "Use YAML configuration file")
    opt_table.add_row("--output, -o FILE", "Specify output filename")
    opt_table.add_row("--async-mode", "🚀 70% faster content collection (v0.3.4+)")
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
    console.print("  [dim]# Fast mode with async I/O (70% faster, v0.3.4+)[/dim]")
    console.print("  $ [cyan]lecture-forge create --async-mode[/cyan]")
    console.print()
    console.print("  [dim]# Translate English PDF to Korean lecture material[/dim]")
    console.print("  $ [cyan]lecture-forge translate paper.pdf[/cyan]")
    console.print()
    console.print("  [dim]# Convert lecture to presentation slides[/dim]")
    console.print("  $ [cyan]lecture-forge improve outputs/lecture.html --to-slides[/cyan]")
    console.print()
    console.print("  [dim]# Chat with knowledge base[/dim]")
    console.print("  $ [cyan]lecture-forge chat -kb ./data/vector_db/AI_Engineering_...[/cyan]")
    console.print()
    console.print("  [dim]# Clean up old knowledge bases[/dim]")
    console.print("  $ [cyan]lecture-forge cleanup[/cyan]")
    console.print()

    # Links
    console.print("[bold yellow]📚 Documentation & Support:[/bold yellow]")
    console.print("  • GitHub: [link]https://github.com/bullpeng72/Lecture_forge[/link]")
    console.print("  • PyPI: [link]https://pypi.org/project/lecture-forge/[/link]")
    console.print("  • Help: Run [cyan]lecture-forge COMMAND --help[/cyan] for command-specific help")
    console.print()


def format_size(bytes: int) -> str:
    """Format bytes to human-readable size.

    Args:
        bytes: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 GB")
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes < 1024.0:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.1f} PB"
