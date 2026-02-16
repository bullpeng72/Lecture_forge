"""
Init command - Initialize LectureForge configuration.

This is the REFACTORED version demonstrating improved code structure.
The original init.py is preserved for backward compatibility.
"""

from pathlib import Path
from typing import Optional

import click

from lecture_forge.cli.utils import console, prompt_masked_input
from lecture_forge.cli.utils.base_command import BaseCommand
from lecture_forge.cli.commands.init_helpers import (
    collect_all_api_keys,
    display_success_message,
    generate_minimal_template,
    load_env_template,
    populate_template,
)
from lecture_forge.config import get_default_config_dir


@click.command()
@click.option(
    "--path",
    type=click.Path(),
    default=None,
    help="Custom directory for .env file (default: platform-specific user directory)",
)
def init_refactored(path: Optional[str]) -> None:
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
    cmd = BaseCommand(console)

    # Step 1: Show banner
    cmd.show_banner("🚀 LectureForge Configuration Setup")

    # Step 2: Determine target path
    env_dir = _determine_env_directory(cmd, path)
    env_path = env_dir / ".env"

    # Step 3: Check if file exists and handle overwrite
    if env_path.exists() and not cmd.confirm_overwrite(env_path):
        console.print("\n[green]✓ Setup cancelled[/green]\n")
        return

    # Step 4: Ensure directory exists
    cmd.ensure_directory(env_dir)

    # Step 5: Collect API keys
    api_keys = collect_all_api_keys(console, prompt_masked_input)

    # Step 6: Load template and populate
    env_content = _create_env_content(console, api_keys)

    # Step 7: Write .env file
    _write_env_file(cmd, env_path, env_content)

    # Step 8: Set permissions and show success
    cmd.set_file_permissions(env_path)
    display_success_message(console, env_path)


def _determine_env_directory(cmd: BaseCommand, path: Optional[str]) -> Path:
    """
    Determine the target directory for .env file.

    Args:
        cmd: BaseCommand instance
        path: Optional custom path from user

    Returns:
        Path to directory where .env should be created
    """
    if path:
        env_dir = cmd.resolve_path(path)
        console.print(f"📁 [dim]Using custom directory: {env_dir}[/dim]\n")
    else:
        env_dir = get_default_config_dir()
        console.print(f"📁 [dim]Using default directory: {env_dir}[/dim]\n")

    return env_dir


def _create_env_content(console, api_keys: dict) -> str:
    """
    Create .env file content from template and API keys.

    Args:
        console: Rich console for output
        api_keys: Dictionary of collected API keys

    Returns:
        Complete .env file content
    """
    # Load template
    template_text, locations = load_env_template(console)

    if not template_text:
        console.print(
            "[yellow]⚠️  Template not found, using minimal config[/yellow]"
        )
        template_text = generate_minimal_template()

    # Populate with actual keys
    return populate_template(template_text, api_keys)


def _write_env_file(cmd: BaseCommand, env_path: Path, content: str) -> None:
    """
    Write .env file to disk.

    Args:
        cmd: BaseCommand instance
        env_path: Path to .env file
        content: File content to write

    Raises:
        SystemExit: If write fails
    """
    try:
        env_path.write_text(content, encoding="utf-8")
    except Exception as e:
        cmd.handle_error(e)


# Backward compatibility: export old name
init = init_refactored
