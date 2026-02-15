"""
CLI utility functions.
"""

from lecture_forge.cli.utils.formatters import (
    console,
    display_token_usage,
    format_size,
    print_banner,
    print_basic_help,
)
from lecture_forge.cli.utils.helpers import (
    find_pdf_files,
    get_dir_size,
    handle_kb_deletion_interactive,
    select_knowledge_base,
    select_pdf_files,
)
from lecture_forge.cli.utils.input_handlers import (
    collect_inputs_interactive,
    prompt_masked_input,
)

__all__ = [
    # Console
    "console",
    # Formatters
    "display_token_usage",
    "format_size",
    "print_banner",
    "print_basic_help",
    # Helpers
    "find_pdf_files",
    "get_dir_size",
    "handle_kb_deletion_interactive",
    "select_knowledge_base",
    "select_pdf_files",
    # Input handlers
    "collect_inputs_interactive",
    "prompt_masked_input",
]
