"""
Base command utilities for CLI commands.

Provides common functionality for all CLI commands including:
- Environment validation
- Path resolution
- Error handling
- Progress display
- File operations
"""

import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from lecture_forge.config import Config
from lecture_forge.exceptions import MissingAPIKeyError, ConfigurationError
from lecture_forge.utils import logger


class BaseCommand:
    """Base class for CLI commands with common utilities."""

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize base command.

        Args:
            console: Rich console instance (optional)
        """
        self.console = console or Console()
        self.config = None  # Lazy-loaded

    def validate_required_env_vars(self, required_keys: list[str]) -> None:
        """
        Validate that required environment variables are set.

        Args:
            required_keys: List of required config attribute names

        Raises:
            MissingAPIKeyError: If any required key is missing
        """
        if self.config is None:
            self.config = Config()

        missing = []
        for key in required_keys:
            if not getattr(self.config, key, None):
                missing.append(key)

        if missing:
            self.console.print(
                f"[red]❌ Missing required environment variables:[/red]"
            )
            for key in missing:
                self.console.print(f"[red]   • {key}[/red]")
            self.console.print(
                f"\n[yellow]💡 Run 'lecture-forge init' to set up configuration[/yellow]\n"
            )
            raise MissingAPIKeyError(f"Missing: {', '.join(missing)}")

    def resolve_path(self, path: Optional[str], default_dir: Optional[Path] = None) -> Path:
        """
        Resolve a path argument to an absolute Path.

        Args:
            path: User-provided path (optional)
            default_dir: Default directory if path not provided

        Returns:
            Resolved absolute Path
        """
        if path:
            return Path(path).expanduser().resolve()
        elif default_dir:
            return default_dir
        else:
            raise ConfigurationError("No path provided and no default available")

    def ensure_directory(self, directory: Path) -> None:
        """
        Ensure directory exists, creating if necessary.

        Args:
            directory: Path to directory

        Raises:
            ConfigurationError: If directory cannot be created
        """
        try:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Directory ensured: {directory}")
        except Exception as e:
            self.console.print(
                f"[red]❌ Failed to create directory: {directory}[/red]"
            )
            self.console.print(f"[red]   Error: {e}[/red]\n")
            raise ConfigurationError(f"Cannot create directory: {directory}") from e

    def show_banner(self, title: str, border_style: str = "cyan") -> None:
        """
        Display a styled banner.

        Args:
            title: Banner title text
            border_style: Rich style for border
        """
        self.console.print()
        self.console.print(
            Panel.fit(
                f"[bold {border_style}]{title}[/bold {border_style}]",
                border_style=border_style,
            )
        )
        self.console.print()

    def create_progress(self, task_description: str) -> Progress:
        """
        Create a styled progress indicator.

        Args:
            task_description: Description of the task

        Returns:
            Progress instance
        """
        return Progress(
            SpinnerColumn(),
            TextColumn(f"[bold blue]{task_description}..."),
            console=self.console,
        )

    def confirm_overwrite(self, file_path: Path) -> bool:
        """
        Ask user to confirm overwriting an existing file.

        Args:
            file_path: Path to potentially overwrite

        Returns:
            True if user confirms, False otherwise
        """
        from rich.prompt import Confirm

        self.console.print(f"[yellow]⚠️  File already exists:[/yellow]")
        self.console.print(f"[yellow]   {file_path}[/yellow]\n")

        return Confirm.ask("   Overwrite existing file?", default=False)

    def handle_error(self, error: Exception, exit_code: int = 1) -> None:
        """
        Handle error with user-friendly message and exit.

        Args:
            error: Exception that occurred
            exit_code: Exit code (default 1)
        """
        from lecture_forge.exceptions import LectureForgeError

        if isinstance(error, LectureForgeError):
            # LectureForge-specific error with user-friendly message
            self.console.print(f"[red]❌ {error}[/red]\n")
        else:
            # Unexpected error
            self.console.print(f"[red]❌ Unexpected error: {error}[/red]\n")
            logger.exception("Unexpected error in CLI command")

        sys.exit(exit_code)

    def set_file_permissions(self, file_path: Path, mode: int = 0o600) -> None:
        """
        Set file permissions (Unix-like systems only).

        Args:
            file_path: Path to file
            mode: Permission mode (default: 0o600 - owner read/write only)
        """
        if sys.platform == "win32":
            return  # Skip on Windows

        try:
            file_path.chmod(mode)
            self.console.print(
                f"[dim]🔒 File permissions set to owner-only ({oct(mode)[2:]})[/dim]\n"
            )
        except (OSError, PermissionError) as e:
            logger.debug(f"Could not set file permissions: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error setting file permissions: {e}")
