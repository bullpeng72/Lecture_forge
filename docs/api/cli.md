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
├── __init__.py (146 lines) - Main entry point
├── utils/ - Shared utilities
│   ├── formatters.py - Output formatting
│   ├── helpers.py - Helper functions
│   └── input_handlers.py - User input
└── commands/ - Individual commands
    ├── init.py - Configuration setup
    ├── init_helpers.py - Init helpers (file copy, env template)
    ├── create.py - Lecture generation (sync)
    ├── create_async.py - Lecture generation (async, --async-mode)
    ├── translate.py - PDF translation (English PDF → Korean HTML)
    ├── chat.py - Q&A mode
    ├── cleanup.py - KB management
    ├── cleanup_helpers.py - Cleanup helpers
    ├── improve.py - Enhancement & slide conversion
    ├── edit.py - Web-based lecture editor (v0.5.0+)
    ├── edit_images.py - Image editing (CLI)
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

### translate

**Location**: `lecture_forge/cli/commands/translate.py`
**Added**: v0.4.1

Translate an English PDF into a Korean lecture material (HTML). Extracts chapter structure from the PDF, translates each chapter to Korean, assigns PDF images by page location, and assembles a fully formatted HTML file.

#### Command

```bash
lecture-forge translate PDF_PATH [OPTIONS]
```

**Arguments:**
- `PDF_PATH`: Path to the English PDF file

**Options:**
- `-o, --output TEXT`: Output filename without extension (auto-generated if omitted: `<stem>_ko.html`)
- `--quality-level [lenient|balanced|strict]`: Quality threshold — lenient(70), balanced(80), strict(90) (default: `balanced`)
- `--audience-level [beginner|intermediate|advanced]`: Target audience level affecting content depth (default: `intermediate`)
- `--with-slides`: Also convert result to Reveal.js presentation slides
- `--no-translate`: Skip translation — keep original English text (for structure debugging, much faster)
- `--with-diagrams`: Generate Mermaid diagrams (disabled by default; PDF images are used instead)

#### Pipeline Phases

| Phase | Description |
|-------|-------------|
| 1 | Extract PDF chapter structure (TOC → font size → page groups) |
| 2 | Collect PDF images with GPT-4o Vision descriptions |
| 3 | Build curriculum from PDF order (bypasses CurriculumDesigner) |
| 4 | Translate chapters to Korean (or keep original if `--no-translate`) |
| 5 | Assign images to sections by page range |
| 6 | Generate Mermaid diagrams (only if `--with-diagrams`) |
| 7 | Assemble HTML |
| 8 | Quality assurance loop (max 3 iterations) |

#### Python API

```python
from lecture_forge.cli.commands.translate import translate_lecture

result = translate_lecture(
    pdf_path="paper.pdf",
    output_name=None,           # auto-generated: paper_ko.html
    quality_level="balanced",
    audience_level="intermediate",
    with_slides=False,
    no_translate=False,
    with_diagrams=False,        # Mermaid diagrams opt-in
)

print(f"HTML: {result['html_path']}")
print(f"Sections: {result['sections_count']}")
print(f"Words: {result['total_words']:,}")
print(f"Images: {result['images']}")
print(f"Quality: {result['quality_score']:.1f}/100")
```

**Function Signature:**
```python
def translate_lecture(
    pdf_path: str,
    output_name: Optional[str],
    quality_level: str,
    audience_level: str,
    with_slides: bool,
    no_translate: bool,
    with_diagrams: bool = False,
) -> dict:
    """Core translate pipeline."""
```

**Returns:**
```python
{
    "html_path": str,           # Path to generated HTML file
    "sections_count": int,      # Number of sections
    "total_words": int,         # Total word count
    "diagrams": int,            # Number of Mermaid diagrams
    "images": int,              # Number of images assigned
    "quality_score": float,     # Final quality score (0-100)
    "token_usage": dict,        # Token usage summary
}
```

#### Translation Features

- **Technical terms**: Korean + English parenthetical (e.g., `신경망(Neural Network)`)
- **Code blocks**: Preserved unchanged using `__CODE_BLOCK_N__` placeholder method
- **AI/ML terminology**: 25 standard terms in `_TERM_GLOSSARY` (consistent translation)
- **Hallucination guard**: `⛔ 절대 금지` rules in translation prompts
- **PDF artifact removal**: Page numbers, domain watermarks, short fragment lines
- **TOC detection**: Table of contents pages automatically excluded (>40% dot-leader pattern)
- **Empty section filtering**: Sections with <30 words automatically excluded
- **Cross-section image deduplication**: `globally_used_ids` set prevents duplicate images

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

Improve existing lectures: convert to slides or re-evaluate and supplement content from KB.

#### Command

```bash
lecture-forge improve LECTURE_PATH [OPTIONS]
```

**Arguments:**
- `LECTURE_PATH`: Path to lecture HTML file

**Options:**
- `--to-slides`: Convert lecture HTML to a Reveal.js presentation (creates `*_slides.html`); includes per-section LLM rewrite by default — concise bullets ≤35자, no truncation
- `--with-notes`: Auto-generate presenter notes for each slide using LLM (requires `--to-slides`; press **S** in browser to view speaker notes)
- `--re-evaluate`: KB 기반 품질 재평가 후 미반영 내용을 각 섹션 말미에 추가 → `*_enhanced.html` 생성 (v0.4.0+)
- `--quality-level [lenient|balanced|strict]`: 재평가 품질 기준 — lenient(70), balanced(80), strict(90) (기본값: `balanced`, `--re-evaluate`와 함께 사용)
- `--kb PATH`: 지식 DB 경로 — HTML에 `lf:vector_db_path` 메타데이터가 없는 기존 파일에 대한 fallback (v0.4.0+)

#### Python API

```python
from lecture_forge.cli.commands.improve import improve

# Convert to slides
improve(['lecture.html', '--to-slides'])

# Convert with presenter notes
improve(['lecture.html', '--to-slides', '--with-notes'])

# Re-evaluate and supplement (v0.4.0+)
improve(['lecture.html', '--re-evaluate'])

# Re-evaluate with strict threshold + manual KB path
improve([
    'lecture.html',
    '--re-evaluate',
    '--quality-level', 'strict',
    '--kb', '/path/to/vector_db/MyTopic_...',
])
```

---

### edit

**Location**: `lecture_forge/cli/commands/edit.py`
**Added**: v0.5.0

Launch a web-based 3-panel lecture editor. Opens a local Flask server (default port 5757) and auto-launches a browser with a split-screen GUI.

#### Command

```bash
lecture-forge edit HTML_PATH [OPTIONS]
```

**Arguments:**
- `HTML_PATH`: Path to lecture HTML file (Reveal.js `*_slides.html` not supported)

**Options:**
- `--port INTEGER`: Server port (default: 5757)
- `--no-browser`: Start server without auto-opening browser

#### Features

| Feature | Description |
|---------|-------------|
| Section CRUD | Add, delete, reorder sections |
| Markdown Editor | EasyMDE with preview (HTML → Markdown via markdownify) |
| Image Gallery | Browse, search alternatives (RAG), replace, upload |
| Save | Writes changes back to HTML file |

#### API Endpoints (port 5757)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/lecture` | Full lecture metadata |
| GET/POST/DELETE | `/api/sections/<id>` | Section CRUD |
| GET | `/api/elements` | All HTML elements |
| PATCH | `/api/elements/<idx>` | Update element |
| GET | `/api/images/<idx>/alternatives` | RAG alternative images |
| POST | `/api/images/<idx>/replace` | Replace image |
| GET | `/api/gallery` | All images list |
| GET | `/api/images/serve` | Serve image file |
| POST | `/api/images/upload` | Upload new image |
| POST | `/api/save` | Save to HTML file |
| POST | `/api/shutdown` | Stop server |

#### Python API

```python
from lecture_forge.editor.server import run_editor

run_editor(
    html_path="outputs/lecture.html",
    port=5757,
    open_browser=True,
)
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

# LLM cost control (v0.5.2+)
MAX_LLM_TOKENS=4096     # Max tokens per LLM response (default: 4096)
MAX_RMC_ROUNDS=1        # Max RMC self-review iterations per agent (default: 1)

# Search full-page fetch (v0.5.2+)
SEARCH_FETCH_FULL_PAGES=false  # Fetch full page content from top search result URLs (default: false)
SEARCH_FETCH_TOP_N=3           # Number of URLs to fetch in parallel when SEARCH_FETCH_FULL_PAGES=true

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

**Last Updated**: 2026-04-03
**Version**: 0.5.4
