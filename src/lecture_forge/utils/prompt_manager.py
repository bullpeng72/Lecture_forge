"""
Prompt Manager - Loads and formats prompt templates.
"""

from pathlib import Path
from typing import Dict, Any

from lecture_forge.config import Config
from lecture_forge.utils import logger


class PromptManager:
    """Manager for loading and formatting prompt templates."""

    def __init__(self, templates_dir: Path = None):
        """
        Initialize the PromptManager.

        Args:
            templates_dir: Directory containing prompt templates (default: Config.TEMPLATES_DIR/prompts)
        """
        if templates_dir is None:
            templates_dir = Config.TEMPLATES_DIR / "prompts"

        self.templates_dir = Path(templates_dir)

        if not self.templates_dir.exists():
            raise FileNotFoundError(f"Prompts directory not found: {self.templates_dir}")

        logger.debug(f"PromptManager initialized with templates from: {self.templates_dir}")

    def load_template(self, template_name: str) -> str:
        """
        Load a prompt template from file.

        Args:
            template_name: Name of the template file (without .txt extension)

        Returns:
            Template content as string

        Raises:
            FileNotFoundError: If template file doesn't exist
        """
        # Support both with and without .txt extension
        if not template_name.endswith(".txt"):
            template_name = f"{template_name}.txt"

        template_path = self.templates_dir / template_name

        if not template_path.exists():
            raise FileNotFoundError(
                f"Template not found: {template_path}\n"
                f"Available templates: {', '.join(self.list_templates())}"
            )

        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        logger.debug(f"Loaded template: {template_name} ({len(content)} characters)")
        return content

    def format_template(self, template_name: str, **kwargs: Any) -> str:
        """
        Load and format a prompt template with variables.

        Args:
            template_name: Name of the template file
            **kwargs: Variables to substitute in the template

        Returns:
            Formatted prompt string

        Example:
            prompt = manager.format_template(
                "content_generation",
                topic="Python Basics",
                min_words=1000,
                target_words=1500,
            )
        """
        template = self.load_template(template_name)

        try:
            formatted = template.format(**kwargs)
            logger.debug(f"Formatted template '{template_name}' with {len(kwargs)} variables")
            return formatted
        except KeyError as e:
            missing_key = str(e).strip("'")
            raise ValueError(
                f"Missing required variable '{missing_key}' for template '{template_name}'\n"
                f"Provided variables: {', '.join(kwargs.keys())}"
            ) from e

    def list_templates(self) -> list[str]:
        """
        List all available prompt templates.

        Returns:
            List of template names (without .txt extension)
        """
        if not self.templates_dir.exists():
            return []

        templates = [
            path.stem  # Get filename without extension
            for path in self.templates_dir.glob("*.txt")
        ]
        return sorted(templates)

    def get_template_variables(self, template_name: str) -> set[str]:
        """
        Extract all variable placeholders from a template.

        Args:
            template_name: Name of the template file

        Returns:
            Set of variable names found in the template

        Example:
            variables = manager.get_template_variables("content_generation")
            # Returns: {'topic', 'min_words', 'target_words', ...}
        """
        template = self.load_template(template_name)

        # Find all {variable} placeholders using simple parsing
        import re

        # Match {variable} and {variable:format} patterns
        pattern = r'\{(\w+)(?::[^}]*)?\}'
        matches = re.findall(pattern, template)

        return set(matches)


# Singleton instance for convenience
_default_manager = None


def get_prompt_manager() -> PromptManager:
    """
    Get the default PromptManager instance (singleton).

    Returns:
        PromptManager instance
    """
    global _default_manager

    if _default_manager is None:
        _default_manager = PromptManager()

    return _default_manager


def load_prompt(template_name: str, **kwargs: Any) -> str:
    """
    Convenience function to load and format a prompt template.

    Args:
        template_name: Name of the template file
        **kwargs: Variables to substitute in the template

    Returns:
        Formatted prompt string

    Example:
        prompt = load_prompt(
            "content_generation",
            topic="Python Basics",
            min_words=1000,
        )
    """
    manager = get_prompt_manager()
    return manager.format_template(template_name, **kwargs)
