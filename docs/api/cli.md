# CLI API Reference

Complete reference for the refactored CLI module structure.

## Table of Contents

1. [Overview](#overview)
2. [Module Structure](#module-structure)
3. [Commands](#commands)
4. [Utilities](#utilities)
5. [Usage Examples](#usage-examples)

---

## Overview

The CLI module has been refactored (v0.3+) from a single 3,603-line file into a clean modular structure with separated commands and utilities.

### Refactoring Summary

**Before (v0.2)**:
```
cli.py (3,603 lines)
```

**After (v0.3+)**:
```
cli/
├── __init__.py (133 lines) - Main entry point
├── utils/ - Shared utilities
│   ├── formatters.py - Output formatting
│   ├── helpers.py - Helper functions
│   └── input_handlers.py - User input
└── commands/ - Individual commands
    ├── init.py - Configuration setup
    ├── create.py - Lecture generation
    ├── chat.py - Q&A mode
    ├── cleanup.py - KB management
    ├── improve.py - Enhancement
    ├── edit_images.py - Image editing
    └── home.py - Folder navigation
```

---

## Module Structure

### Main Entry Point

**Location**: `lecture_forge/cli/__init__.py`

```python
from lecture_forge.cli import cli, main

# As a module
cli(['create', '--help'])

# As entry point
if __name__ == "__main__":
    main()
```

**Functions:**
- `cli()`: Main Click group with all commands
- `main()`: Entry point with error handling

### Utilities

#### formatters.py

Output formatting and display utilities.

```python
from lecture_forge.cli.utils import (
    console,
    display_token_usage,
    print_banner,
    print_basic_help,
    format_size,
)
```

**Functions:**

##### `console`
Rich Console instance for styled output.

```python
from lecture_forge.cli.utils import console

console.print("[bold green]Success![/bold green]")
```

##### `display_token_usage(usage_summary: Dict[str, Any]) -> None`
Display token usage and cost estimate.

```python
usage = {
    "total_tokens": 15000,
    "prompt_tokens": 10000,
    "completion_tokens": 5000,
    "estimated_cost": 0.045
}
display_token_usage(usage)
```

##### `print_banner() -> None`
Display LectureForge banner.

##### `format_size(bytes: int) -> str`
Format bytes to human-readable size.

```python
size_str = format_size(1024 * 1024 * 50)  # "50.0 MB"
```

#### helpers.py

Helper functions for file operations and KB management.

```python
from lecture_forge.cli.utils import (
    get_dir_size,
    select_knowledge_base,
    handle_kb_deletion_interactive,
    find_pdf_files,
)
```

**Functions:**

##### `get_dir_size(path: Path) -> int`
Calculate total size of directory.

```python
size = get_dir_size(Path("/data/vector_db"))
```

##### `select_knowledge_base() -> Optional[str]`
Interactive KB selection prompt.

```python
kb_path = select_knowledge_base()
if kb_path:
    print(f"Selected: {kb_path}")
```

##### `find_pdf_files(max_depth: int = 2) -> List[Path]`
Find PDF files in current directory.

```python
pdfs = find_pdf_files(max_depth=3)
for pdf in pdfs:
    print(f"Found: {pdf}")
```

#### input_handlers.py

User input collection utilities.

```python
from lecture_forge.cli.utils import (
    prompt_masked_input,
    collect_inputs_interactive,
)
```

**Functions:**

##### `prompt_masked_input(console: Console, prompt_text: str, mask_char: str = "*", allow_empty: bool = False) -> str`
Prompt for masked input (API keys, passwords).

```python
api_key = prompt_masked_input(
    console,
    "Enter your API key:",
    mask_char="*",
    allow_empty=False
)
```

##### `collect_inputs_interactive() -> Dict[str, Any]`
Collect all lecture generation inputs interactively.

```python
inputs = collect_inputs_interactive()
# Returns: {
#     "topic": "...",
#     "duration": 60,
#     "audience_level": "...",
#     "pdfs": [...],
#     "urls": [...],
#     ...
# }
```

---

## Commands

### init

**Location**: `lecture_forge/cli/commands/init.py`

Initialize configuration and create .env file.

#### Command

```bash
lecture-forge init [OPTIONS]
```

**Options:**
- `--path PATH`: Custom directory for .env (default: ~/Documents/LectureForge/)

#### Python API

```python
from lecture_forge.cli.commands.init import init

# As Click command
init(['--path', '/custom/path'])
```

**Function Signature:**
```python
def init(path: Optional[str]) -> None:
    """Initialize LectureForge configuration."""
```

---

### create

**Location**: `lecture_forge/cli/commands/create.py`

Generate lecture materials from sources.

#### Command

```bash
lecture-forge create [OPTIONS]
```

**Options:**
- `-c, --config PATH`: Configuration YAML file
- `-i, --interactive`: Enable interactive mode
- `--image-search/--no-image-search`: Enable image search from web sources — Pexels (default: enabled)
- `--quality-level [lenient|balanced|strict]`: Quality threshold — lenient(70), balanced(80), strict(90) (default: balanced)
- `-o, --output TEXT`: Output filename without extension (auto-generated if omitted)
- `--include-pdf-images/--no-include-pdf-images`: Extract images from PDFs with location-based matching (default: enabled)
- `--auto-describe-images/--no-auto-describe-images`: Auto-generate GPT-4o-mini descriptions for PDF images (default: enabled, requires `--include-pdf-images`)
- `--async-mode`: **[v0.3.4+]** Use async I/O for 70% faster content collection (experimental)
- `--with-code`: Include code examples in lecture content (default: excluded)
- `--existing-kb PATH`: Reuse or extend an existing knowledge base directory instead of building a new one
- `--kb-mode [reuse_only|extend]`: How to use `--existing-kb` — `reuse_only` (read-only, default) or `extend` (add new sources to the KB)

#### Python API

```python
from lecture_forge.cli.commands.create import create, generate_lecture

# Generate lecture programmatically
result = generate_lecture({
    "topic": "Machine Learning",
    "duration": 60,
    "audience_level": "beginner",
    "pdfs": ["ml_book.pdf"],
    "urls": ["https://example.com"],
    "keywords": ["machine learning"],
    "image_search": True,
    "quality_level": "balanced",
    "include_pdf_images": True,
    "auto_describe_images": True,
    "with_code": False,
    # Optional: reuse an existing knowledge base
    # "existing_kb_path": "/path/to/vector_db/my_kb",
    # "kb_mode": "reuse_only",  # or "extend"
})

print(f"HTML: {result['html_path']}")
print(f"KB: {result['vector_db_path']}")
```

**Function Signature:**
```python
def generate_lecture(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Generate lecture using multi-agent pipeline."""
```

---

### chat

**Location**: `lecture_forge/cli/commands/chat.py`

Interactive Q&A mode with knowledge base.

#### Command

```bash
lecture-forge chat [OPTIONS]
```

**Options:**
- `-kb, --knowledge-base PATH`: Path to knowledge base directory

#### Python API

```python
from lecture_forge.cli.commands.chat import chat

# As Click command
chat(['-kb', '/path/to/kb'])
```

---

### cleanup

**Location**: `lecture_forge/cli/commands/cleanup.py`

Delete knowledge bases to free disk space.

#### Command

```bash
lecture-forge cleanup [OPTIONS]
```

**Options:**
- `-a, --all`: Delete ALL knowledge bases without confirmation (DANGEROUS)

#### Python API

```python
from lecture_forge.cli.commands.cleanup import cleanup

# Interactive cleanup
cleanup([])

# Delete all (dangerous!)
cleanup(['--all'])
```

---

### improve

**Location**: `lecture_forge/cli/commands/improve.py`

Improve existing lectures or convert to slides.

#### Command

```bash
lecture-forge improve LECTURE_PATH [OPTIONS]
```

**Arguments:**
- `LECTURE_PATH`: Path to lecture HTML file

**Options:**
- `--enhance-pdf-images`: (Legacy) Re-generate descriptions for PDF images using page text. Mainly useful for lectures created before v0.2.4 when auto-describe was not the default.
- `--source-pdf PATH`: Source PDF file (required with `--enhance-pdf-images`)
- `--to-slides`: Convert lecture HTML to a Reveal.js presentation (creates `*_slides.html`)
- `--with-notes`: Auto-generate presenter notes for each slide using LLM (requires `--to-slides`; press **S** in browser to view speaker notes)
- `--slide-rewrite`: Per-section LLM rewrite for slide optimization — eliminates truncated bullets ending in "…", produces concise complete bullets ≤35자 (requires `--to-slides`; adds ~15 seconds)

#### Python API

```python
from lecture_forge.cli.commands.improve import improve

# Convert to slides
improve(['lecture.html', '--to-slides'])

# Enhance PDF images
improve([
    'lecture.html',
    '--enhance-pdf-images',
    '--source-pdf', 'book.pdf'
])
```

---

### edit-images

**Location**: `lecture_forge/cli/commands/edit_images.py`

Interactive image editing for generated lectures.

#### Command

```bash
lecture-forge edit-images HTML_PATH [OPTIONS]
```

**Arguments:**
- `HTML_PATH`: Path to lecture HTML file

**Options:**
- `-o, --output PATH`: Output file path

#### Python API

```python
from lecture_forge.cli.commands.edit_images import edit_images

# Interactive editing
edit_images(['lecture.html'])

# Specify output
edit_images(['lecture.html', '-o', 'edited_lecture.html'])
```

---

### home

**Location**: `lecture_forge/cli/commands/home.py`

Open LectureForge directories in file manager.

#### Command

```bash
lecture-forge home [TARGET]
```

**Arguments:**
- `TARGET`: Optional target directory
  - (empty): Main directory
  - `data`: Data directory
  - `outputs`: Outputs directory
  - `kb`: Latest knowledge base
  - `env`: Open .env file in editor

#### Python API

```python
from lecture_forge.cli.commands.home import home

# Open main directory
home([])

# Open outputs
home(['outputs'])

# Open .env in editor
home(['env'])
```

---

## Usage Examples

### Programmatic Usage

```python
from lecture_forge.cli.commands.create import generate_lecture
from lecture_forge.cli.commands.chat import chat
from lecture_forge.cli.utils import display_token_usage

# 1. Generate lecture
result = generate_lecture({
    "topic": "Python Programming",
    "duration": 90,
    "audience_level": "beginner",
    "pdfs": ["python_book.pdf"],
    "urls": [],
    "keywords": ["python basics", "programming"],
    "image_search": True,
    "quality_level": "balanced",
    "include_pdf_images": True,
    "auto_describe_images": True,
    "with_code": True,
    # "existing_kb_path": "/path/to/vector_db/existing_kb",
    # "kb_mode": "reuse_only",
})

# 2. Display results
print(f"✅ Lecture generated: {result['html_path']}")
print(f"📚 Knowledge base: {result['vector_db_path']}")
print(f"📊 Sections: {result['sections_count']}")
print(f"💬 Words: {result['total_words']:,}")

# 3. Show token usage
if "token_usage" in result:
    display_token_usage(result["token_usage"])

# 4. Start Q&A (would open interactive mode)
# chat(['-kb', result['vector_db_path']])
```

### Testing Commands

```python
from click.testing import CliRunner
from lecture_forge.cli import cli

runner = CliRunner()

# Test help
result = runner.invoke(cli, ['--help'])
assert result.exit_code == 0

# Test create with config
result = runner.invoke(cli, ['create', '-c', 'config.yaml'])
# Check result.output for success message
```

### Custom Command Integration

```python
import click
from lecture_forge.cli import cli
from lecture_forge.cli.utils import console

@cli.command()
@click.argument('name')
def custom_command(name: str):
    """Custom command example."""
    console.print(f"[green]Hello, {name}![/green]")

# Now available as: lecture-forge custom-command NAME
```

---

## Error Handling

All commands use structured exception handling:

```python
from lecture_forge.exceptions import (
    LectureForgeError,
    ConfigurationError,
    MissingAPIKeyError,
)

try:
    result = generate_lecture(inputs)
except MissingAPIKeyError as e:
    console.print(f"[red]Missing API key: {e}[/red]")
except ConfigurationError as e:
    console.print(f"[red]Configuration error: {e}[/red]")
except LectureForgeError as e:
    console.print(f"[red]Error: {e}[/red]")
```

---

## Configuration

### Environment Variables

CLI commands respect these environment variables (loaded from .env):

```bash
# Required
OPENAI_API_KEY=sk-proj-...
SERPER_API_KEY=...

# Optional
PEXELS_API_KEY=...
UNSPLASH_ACCESS_KEY=...

# Model settings
DEFAULT_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

# Quality settings
QUALITY_THRESHOLD=80
MAX_ITERATIONS=3

# Paths
OUTPUT_DIR=./outputs
DATA_DIR=./data
```

### Config Class

```python
from lecture_forge.config import Config

# Access configuration
print(Config.OPENAI_API_KEY)
print(Config.OUTPUT_DIR)
print(Config.QUALITY_THRESHOLD)
```

---

## Testing

### Unit Tests

```python
# tests/integration/test_cli_commands.py

def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert "LectureForge" in result.output

def test_create_command_help():
    runner = CliRunner()
    result = runner.invoke(cli, ['create', '--help'])
    assert result.exit_code == 0
```

### Integration Tests

See `tests/integration/test_cli_commands.py` for comprehensive CLI testing examples.

---

**Last Updated**: 2026-02-19
**Version**: 0.3.8
