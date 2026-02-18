"""
Init command - Init.
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.panel import Panel
from rich.prompt import Confirm

from lecture_forge.cli.utils import console, prompt_masked_input
from lecture_forge.config import Config
from lecture_forge.utils import logger


@click.command()
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
                # Fallback: try lecture_forge.templates sub-package directly
                try:
                    template_text = (
                        pkg_resources.files("lecture_forge.templates")
                        .joinpath(".env.example")
                        .read_text(encoding="utf-8")
                    )
                    template_locations.append("package resources (templates sub-package)")
                except (FileNotFoundError, TypeError, ModuleNotFoundError):
                    pass
    except Exception as e:
        # Broad catch acceptable: template loading is non-critical with fallbacks
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
            # Broad catch acceptable: template loading is non-critical with fallbacks
            logger.debug(f"Source directory template loading failed: {e}")

    # Try 3: Project root (fallback for development)
    if not template_text:
        try:
            root_template = Path(__file__).parent.parent.parent / ".env.example"
            if root_template.exists():
                template_text = root_template.read_text(encoding="utf-8")
                template_locations.append(f"project root ({root_template})")
        except Exception as e:
            # Broad catch acceptable: template loading is non-critical with fallbacks
            logger.debug(f"Project root template loading failed: {e}")

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
        except (OSError, PermissionError) as e:
            # Acceptable failure: chmod may not work on all filesystems (e.g., Windows FAT32)
            logger.debug(f"Could not set file permissions: {e}")
        except Exception as e:
            # Unexpected error, but non-critical
            logger.warning(f"Unexpected error setting file permissions: {e}")

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

