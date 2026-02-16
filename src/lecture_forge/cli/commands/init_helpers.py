"""
Helper functions for init command.

This module contains extracted functions from init.py to improve
maintainability and testability.
"""

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

from rich.console import Console

from lecture_forge.utils import logger


def collect_openai_key(console: Console, prompt_fn) -> str:
    """
    Collect and validate OpenAI API key.

    Args:
        console: Rich console for output
        prompt_fn: Function to prompt for masked input

    Returns:
        Valid OpenAI API key
    """
    console.print("[bold]1. OpenAI API Key[/bold]")
    console.print("   • Get from: [link]https://platform.openai.com[/link]")
    console.print("   • Used for: LLM generation, embeddings")
    console.print("   • Cost: ~$0.10 per 60-min lecture (GPT-4o-mini)\n")

    openai_key = prompt_fn(
        console, "   [cyan]Enter your OpenAI API Key[/cyan] (starts with sk-):"
    )

    while not openai_key or not openai_key.startswith(("sk-", "sk-proj-")):
        console.print(
            "   [red]Invalid format. Should start with 'sk-' or 'sk-proj-'[/red]"
        )
        openai_key = prompt_fn(console, "   [cyan]Enter your OpenAI API Key[/cyan]:")

    console.print(f"   [green]✓ OpenAI key saved ({len(openai_key)} characters)[/green]\n")
    return openai_key


def collect_serper_key(console: Console, prompt_fn) -> str:
    """
    Collect and validate Serper API key.

    Args:
        console: Rich console for output
        prompt_fn: Function to prompt for masked input

    Returns:
        Valid Serper API key
    """
    console.print("[bold]2. Serper API Key[/bold]")
    console.print("   • Get from: [link]https://serper.dev[/link]")
    console.print("   • Used for: Web search")
    console.print("   • Free tier: 2,500 searches/month\n")

    serper_key = prompt_fn(console, "   [cyan]Enter your Serper API Key[/cyan]:")

    while not serper_key or len(serper_key) < 10:
        console.print("   [red]Invalid key. Please check your API key.[/red]")
        serper_key = prompt_fn(console, "   [cyan]Enter your Serper API Key[/cyan]:")

    console.print(f"   [green]✓ Serper key saved ({len(serper_key)} characters)[/green]\n")
    return serper_key


def collect_pexels_key(console: Console, prompt_fn) -> Optional[str]:
    """
    Collect optional Pexels API key.

    Args:
        console: Rich console for output
        prompt_fn: Function to prompt for masked input

    Returns:
        Pexels API key or None if skipped
    """
    console.print("[bold]3. Pexels API Key (Optional)[/bold]")
    console.print("   • Get from: [link]https://pexels.com/api[/link]")
    console.print("   • Free: Unlimited with rate limits\n")

    pexels_key = prompt_fn(
        console,
        "   [cyan]Pexels API Key[/cyan] [dim](or press Enter to skip)[/dim]:",
        allow_empty=True,
    )

    if pexels_key:
        console.print(f"   [green]✓ Pexels key saved ({len(pexels_key)} characters)[/green]\n")
    else:
        console.print("   [dim]⊘ Skipped[/dim]\n")

    return pexels_key


def collect_unsplash_key(console: Console, prompt_fn) -> Optional[str]:
    """
    Collect optional Unsplash API key.

    Args:
        console: Rich console for output
        prompt_fn: Function to prompt for masked input

    Returns:
        Unsplash API key or None if skipped
    """
    console.print("[bold]4. Unsplash Access Key (Optional)[/bold]")
    console.print("   • Get from: [link]https://unsplash.com/developers[/link]")
    console.print("   • Free tier: 50 requests/hour\n")

    unsplash_key = prompt_fn(
        console,
        "   [cyan]Unsplash Access Key[/cyan] [dim](or press Enter to skip)[/dim]:",
        allow_empty=True,
    )

    if unsplash_key:
        console.print(f"   [green]✓ Unsplash key saved ({len(unsplash_key)} characters)[/green]\n")
    else:
        console.print("   [dim]⊘ Skipped[/dim]\n")

    return unsplash_key


def collect_all_api_keys(console: Console, prompt_fn) -> Dict[str, Optional[str]]:
    """
    Collect all API keys (required and optional).

    Args:
        console: Rich console for output
        prompt_fn: Function to prompt for masked input

    Returns:
        Dictionary of API keys
    """
    console.print("[bold cyan]📝 Required API Keys[/bold cyan]\n")

    openai_key = collect_openai_key(console, prompt_fn)
    serper_key = collect_serper_key(console, prompt_fn)

    console.print("[bold cyan]📸 Optional: Image Search APIs[/bold cyan]")
    console.print("[dim]Press Enter to skip if you don't need web image search[/dim]\n")

    pexels_key = collect_pexels_key(console, prompt_fn)
    unsplash_key = collect_unsplash_key(console, prompt_fn)

    return {
        "openai": openai_key,
        "serper": serper_key,
        "pexels": pexels_key,
        "unsplash": unsplash_key,
    }


def load_env_template(console: Console) -> Tuple[Optional[str], list[str]]:
    """
    Load .env template from multiple possible locations.

    Tries in order:
    1. Package resources (installed package)
    2. Source directory (development mode)
    3. Project root (fallback)

    Args:
        console: Rich console for output

    Returns:
        Tuple of (template_text, locations_tried)
    """
    import importlib.resources as pkg_resources

    template_text = None
    template_locations = []

    # Try 1: Package resources (installed package)
    try:
        try:
            # Python 3.9+ - Try templates directory first (most reliable)
            template_text = (
                pkg_resources.files("lecture_forge")
                .joinpath("templates/.env.example")
                .read_text(encoding="utf-8")
            )
            template_locations.append("package resources (templates)")
        except (AttributeError, FileNotFoundError):
            try:
                # Try root package directory
                template_text = (
                    pkg_resources.files("lecture_forge")
                    .joinpath(".env.example")
                    .read_text(encoding="utf-8")
                )
                template_locations.append("package resources (root)")
            except (AttributeError, FileNotFoundError):
                # Python 3.7-3.8 fallback
                try:
                    with pkg_resources.path(
                        "lecture_forge.templates", ".env.example"
                    ) as template_path:
                        template_text = template_path.read_text(encoding="utf-8")
                        template_locations.append("package resources (legacy)")
                except (FileNotFoundError, TypeError, ModuleNotFoundError):
                    pass
    except Exception as e:
        logger.debug(f"Package resource template loading failed: {e}")

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
        except Exception as e:
            logger.debug(f"Source directory template loading failed: {e}")

    # Try 3: Project root (fallback for development)
    if not template_text:
        try:
            root_template = Path(__file__).parent.parent.parent / ".env.example"
            if root_template.exists():
                template_text = root_template.read_text(encoding="utf-8")
                template_locations.append(f"project root ({root_template})")
        except Exception as e:
            logger.debug(f"Project root template loading failed: {e}")

    return template_text, template_locations


def generate_minimal_template() -> str:
    """
    Generate minimal .env template as fallback.

    Returns:
        Minimal template string
    """
    return f"""# LectureForge Configuration
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


def populate_template(
    template_text: str, api_keys: Dict[str, Optional[str]]
) -> str:
    """
    Populate template with actual API keys.

    Args:
        template_text: Template string with placeholders
        api_keys: Dictionary of API keys

    Returns:
        Populated template
    """
    # Replace placeholder values with user input
    env_content = re.sub(
        r"OPENAI_API_KEY=.*", f"OPENAI_API_KEY={api_keys['openai']}", template_text
    )
    env_content = re.sub(
        r"SERPER_API_KEY=.*", f"SERPER_API_KEY={api_keys['serper']}", env_content
    )

    # Replace optional keys
    if api_keys.get("unsplash"):
        env_content = re.sub(
            r"UNSPLASH_ACCESS_KEY=.*",
            f"UNSPLASH_ACCESS_KEY={api_keys['unsplash']}",
            env_content,
        )

    if api_keys.get("pexels"):
        env_content = re.sub(
            r"PEXELS_API_KEY=.*", f"PEXELS_API_KEY={api_keys['pexels']}", env_content
        )

    # Add generation metadata at the top
    metadata = f"""# LectureForge Configuration
# Generated by: lecture-forge init
# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# Platform: {sys.platform}

"""
    env_content = metadata + env_content

    return env_content


def display_success_message(console: Console, env_path: Path) -> None:
    """
    Display success message and next steps.

    Args:
        console: Rich console for output
        env_path: Path to created .env file
    """
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
    console.print(
        "   • Generate with images: [dim]lecture-forge create --image-search[/dim]"
    )
    console.print(
        "   • High quality mode: [dim]lecture-forge create --quality-level strict[/dim]\n"
    )
