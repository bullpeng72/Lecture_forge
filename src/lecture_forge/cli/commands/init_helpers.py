"""
Helper functions for init command.

This module contains extracted functions from init.py to improve
maintainability and testability.
"""

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from lecture_forge.utils import logger

# ──────────────────────────────────────────────────────────
# Quality level ↔ threshold mapping
# ──────────────────────────────────────────────────────────
_QUALITY_LEVELS = {
    "lenient": 70,
    "balanced": 80,
    "strict": 90,
}
_THRESHOLD_TO_LEVEL = {v: k for k, v in _QUALITY_LEVELS.items()}

# ──────────────────────────────────────────────────────────
# Preset OpenAI model choices (user may still type custom)
# ──────────────────────────────────────────────────────────
_OPENAI_MODEL_PRESETS = ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "o1-mini"]


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
    template_text: str,
    api_keys: Dict[str, Optional[str]],
    llm_settings: Optional[Dict[str, str]] = None,
    quality_settings: Optional[Dict[str, str]] = None,
) -> str:
    """
    Populate template with API keys and optional LLM / quality settings.

    Args:
        template_text: Template string with placeholders
        api_keys: Dictionary of API keys
        llm_settings: Optional LLM provider / model / temperature settings
        quality_settings: Optional quality threshold / iteration settings

    Returns:
        Populated template string
    """
    # Replace placeholder values with user input
    env_content = re.sub(
        r"OPENAI_API_KEY=.*", f"OPENAI_API_KEY={api_keys['openai']}", template_text
    )
    env_content = re.sub(
        r"SERPER_API_KEY=.*", f"SERPER_API_KEY={api_keys['serper']}", env_content
    )

    # Replace optional image-search keys
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

    # LLM settings — replace in-template vars first, then append extras
    if llm_settings:
        # Vars that exist in the default template
        for var in ("DEFAULT_MODEL", "TEMPERATURE"):
            if var in llm_settings:
                env_content = re.sub(
                    rf"^{var}=.*",
                    f"{var}={llm_settings[var]}",
                    env_content,
                    flags=re.MULTILINE,
                )

        # Build an extra section for vars not in the template
        extra_llm: List[str] = []
        template_vars = set(re.findall(r"^([A-Z_]+)=", env_content, re.MULTILINE))
        for var, val in llm_settings.items():
            if var not in template_vars:
                extra_llm.append(f"{var}={val}")

        if extra_llm:
            env_content += "\n# ===== LLM Provider =====\n"
            env_content += "\n".join(extra_llm) + "\n"

    # Quality settings — replace in-template vars
    if quality_settings:
        for var in ("QUALITY_THRESHOLD", "MAX_ITERATIONS"):
            if var in quality_settings:
                env_content = re.sub(
                    rf"^{var}=.*",
                    f"{var}={quality_settings[var]}",
                    env_content,
                    flags=re.MULTILINE,
                )

    # Add generation metadata at the top
    metadata = (
        f"# LectureForge Configuration\n"
        f"# Generated by: lecture-forge init\n"
        f"# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"# Platform: {sys.platform}\n\n"
    )
    env_content = metadata + env_content

    return env_content


# ──────────────────────────────────────────────────────────
# New helpers: env parsing, masking, LLM / quality prompts
# ──────────────────────────────────────────────────────────


def load_current_env(env_path: Path) -> Dict[str, str]:
    """
    Parse an existing .env file into a key → value dict.

    Comments and blank lines are ignored.  Only the first ``=`` is used
    as the separator so values that contain ``=`` are preserved.

    Args:
        env_path: Path to the .env file

    Returns:
        Dict of variable names to their string values (may be empty)
    """
    if not env_path.exists():
        return {}

    result: Dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        result[key.strip()] = value.strip()
    return result


def mask_api_key(key: str) -> str:
    """
    Return a display-safe masked version of an API key.

    Keys shorter than 12 characters are fully masked as ``****``.
    Longer keys show the first 8 and last 4 characters separated by ``****``.

    Examples::

        "sk-proj-abcdefghijklmnopBaYA"  →  "sk-proj-****BaYA"
        "short"                          →  "****"
    """
    if not key:
        return "설정 안 됨"
    if len(key) < 12:
        return "****"
    return key[:8] + "****" + key[-4:]


def collect_api_keys_reconfigure(
    console: Console,
    prompt_fn,
    current: Dict[str, str],
) -> Dict[str, Optional[str]]:
    """
    Collect API keys in reconfigure mode.

    Displays the masked current value for each key; pressing Enter keeps
    the existing value.

    Args:
        console: Rich Console instance
        prompt_fn: ``prompt_masked_input`` callable
        current: Existing env vars loaded from .env

    Returns:
        Dict with keys ``openai``, ``serper``, ``pexels``, ``unsplash``
    """
    console.print("[bold cyan]📝 API Keys[/bold cyan]")
    console.print("[dim]Enter 입력 시 현재 값 유지[/dim]\n")

    def _prompt_key(label: str, env_var: str, required: bool = True, validator=None):
        cur = current.get(env_var, "")
        masked = mask_api_key(cur) if cur else "설정 안 됨"
        hint = f"[dim][현재: {masked}][/dim]"
        new_val = prompt_fn(
            console,
            f"   [cyan]{label}[/cyan] {hint}:",
            allow_empty=True,
        )
        if not new_val:
            return cur  # keep existing

        if validator:
            while not validator(new_val):
                console.print("   [red]유효하지 않은 값입니다. 다시 입력하세요.[/red]")
                new_val = prompt_fn(console, f"   [cyan]{label}[/cyan]:", allow_empty=True)
                if not new_val:
                    return cur
        return new_val

    openai_key = _prompt_key(
        "OpenAI API Key",
        "OPENAI_API_KEY",
        validator=lambda k: k.startswith(("sk-", "sk-proj-")),
    )
    serper_key = _prompt_key(
        "Serper API Key",
        "SERPER_API_KEY",
        validator=lambda k: len(k) >= 10,
    )
    pexels_key = _prompt_key("Pexels API Key (선택)", "PEXELS_API_KEY")
    unsplash_key = _prompt_key("Unsplash Access Key (선택)", "UNSPLASH_ACCESS_KEY")

    console.print()
    return {
        "openai": openai_key,
        "serper": serper_key,
        "pexels": pexels_key or None,
        "unsplash": unsplash_key or None,
    }


def collect_llm_settings(
    console: Console,
    current: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Interactively collect LLM provider / model / temperature settings.

    Supports two providers:

    * **openai** — asks for model name (preset list + free text) and temperature.
    * **ollama** — asks for base URL, model name, and embedding model.

    Args:
        console: Rich Console instance
        current: Existing env vars (used as defaults in reconfigure mode)

    Returns:
        Dict of setting names → string values ready for .env substitution
    """
    cur = current or {}
    is_reconfig = bool(current)

    console.print("[bold cyan]🤖 LLM 설정[/bold cyan]")
    if is_reconfig:
        console.print("[dim]Enter 입력 시 현재 값 유지[/dim]")
    console.print()

    # ── Provider ──────────────────────────────────────────
    cur_provider = cur.get("LLM_PROVIDER", "openai")
    provider = Prompt.ask(
        "   LLM Provider",
        choices=["openai", "ollama"],
        default=cur_provider,
        console=console,
    )

    settings: Dict[str, str] = {"LLM_PROVIDER": provider}

    # ── Provider-specific settings ────────────────────────
    if provider == "ollama":
        cur_url = cur.get("OLLAMA_BASE_URL", "http://localhost:11434")
        base_url = Prompt.ask("   Ollama Base URL", default=cur_url, console=console)
        settings["OLLAMA_BASE_URL"] = base_url.strip() or cur_url

        cur_model = cur.get("OLLAMA_MODEL", "llama3.2")
        model = Prompt.ask("   Ollama 모델명", default=cur_model, console=console)
        settings["OLLAMA_MODEL"] = model.strip() or cur_model

        cur_embed = cur.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
        embed = Prompt.ask("   Ollama 임베딩 모델", default=cur_embed, console=console)
        settings["OLLAMA_EMBEDDING_MODEL"] = embed.strip() or cur_embed

        cur_vision = cur.get("OLLAMA_VISION_MODEL", "llama3.2-vision")
        vision = Prompt.ask("   Ollama Vision 모델", default=cur_vision, console=console)
        settings["OLLAMA_VISION_MODEL"] = vision.strip() or cur_vision
    else:
        cur_model = cur.get("DEFAULT_MODEL", "gpt-4o-mini")
        preset_hint = "/".join(_OPENAI_MODEL_PRESETS)
        model = Prompt.ask(
            f"   기본 모델 [dim]({preset_hint})[/dim]",
            default=cur_model,
            console=console,
        )
        settings["DEFAULT_MODEL"] = model.strip() or cur_model

    # ── Temperature (common) ─────────────────────────────
    cur_temp = cur.get("TEMPERATURE", "0.7")
    while True:
        temp_str = Prompt.ask(
            "   Temperature [dim](0.0 ~ 1.0)[/dim]",
            default=cur_temp,
            console=console,
        )
        if not temp_str:          # stdin EOF / empty → keep current
            temp_str = cur_temp
        try:
            temp_val = float(temp_str)
            if 0.0 <= temp_val <= 1.0:
                settings["TEMPERATURE"] = f"{temp_val}"
                break
        except ValueError:
            pass
        console.print("   [red]0.0 ~ 1.0 사이의 숫자를 입력하세요.[/red]")

    console.print("   [green]✓ LLM 설정 완료[/green]\n")
    return settings


def collect_quality_settings(
    console: Console,
    current: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Interactively collect quality threshold and iteration settings.

    Args:
        console: Rich Console instance
        current: Existing env vars (used as defaults in reconfigure mode)

    Returns:
        Dict with ``QUALITY_THRESHOLD`` and ``MAX_ITERATIONS``
    """
    cur = current or {}
    is_reconfig = bool(current)

    console.print("[bold cyan]⚙️  품질 설정[/bold cyan]")
    if is_reconfig:
        console.print("[dim]Enter 입력 시 현재 값 유지[/dim]")
    console.print()

    # ── Quality level ─────────────────────────────────────
    cur_threshold = cur.get("QUALITY_THRESHOLD", "80")
    try:
        cur_level = _THRESHOLD_TO_LEVEL.get(int(cur_threshold), "balanced")
    except ValueError:
        cur_level = "balanced"

    level = Prompt.ask(
        "   기본 품질 레벨 [dim](lenient=70 / balanced=80 / strict=90)[/dim]",
        choices=["lenient", "balanced", "strict"],
        default=cur_level,
        console=console,
    )
    threshold = str(_QUALITY_LEVELS[level])

    # ── Max iterations ────────────────────────────────────
    cur_iter = cur.get("MAX_ITERATIONS", "3")
    while True:
        iter_str = Prompt.ask(
            "   최대 품질 개선 반복 횟수 [dim](1 ~ 5)[/dim]",
            default=cur_iter,
            console=console,
        )
        if not iter_str:          # stdin EOF / empty → keep current
            iter_str = cur_iter
        try:
            iter_val = int(iter_str)
            if 1 <= iter_val <= 5:
                break
        except ValueError:
            pass
        console.print("   [red]1 ~ 5 사이의 정수를 입력하세요.[/red]")

    console.print("   [green]✓ 품질 설정 완료[/green]\n")
    return {
        "QUALITY_THRESHOLD": threshold,
        "MAX_ITERATIONS": str(iter_val),
    }


def show_current_config(console: Console, env_path: Path) -> None:
    """
    Display the current .env settings in a formatted Rich table.

    API key values are masked for security.

    Args:
        console: Rich Console instance
        env_path: Path to the .env file to read
    """
    if not env_path.exists():
        console.print(f"[yellow]⚠️  .env 파일이 없습니다: {env_path}[/yellow]")
        console.print("[dim]먼저 lecture-forge init 을 실행하세요.[/dim]\n")
        return

    env = load_current_env(env_path)

    # ── API Keys table ────────────────────────────────────
    console.print()
    console.print("[bold cyan]🔑 API Keys[/bold cyan]")
    key_table = Table(show_header=False, box=None, padding=(0, 2))
    key_table.add_column("var", style="dim")
    key_table.add_column("value")

    _api_vars = [
        ("OPENAI_API_KEY", "OpenAI"),
        ("SERPER_API_KEY", "Serper"),
        ("PEXELS_API_KEY", "Pexels"),
        ("UNSPLASH_ACCESS_KEY", "Unsplash"),
    ]
    for var, label in _api_vars:
        val = env.get(var, "")
        if val and not val.startswith(("xxx", "your_", "sk-proj-xxx")):
            display = f"[green]✅[/green] {mask_api_key(val)}"
        else:
            display = "[yellow]⚠️  설정 안 됨[/yellow]"
        key_table.add_row(label, display)
    console.print(key_table)

    # ── LLM Settings table ────────────────────────────────
    console.print()
    console.print("[bold cyan]🤖 LLM 설정[/bold cyan]")
    llm_table = Table(show_header=False, box=None, padding=(0, 2))
    llm_table.add_column("var", style="dim")
    llm_table.add_column("value")

    provider = env.get("LLM_PROVIDER", "openai")
    llm_table.add_row("Provider", f"[cyan]{provider}[/cyan]")
    if provider == "ollama":
        llm_table.add_row("Ollama Base URL", env.get("OLLAMA_BASE_URL", "http://localhost:11434"))
        llm_table.add_row("Ollama 모델", env.get("OLLAMA_MODEL", "llama3.2"))
        llm_table.add_row("Ollama 임베딩", env.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"))
        llm_table.add_row("Ollama Vision", env.get("OLLAMA_VISION_MODEL", "llama3.2-vision"))
    else:
        llm_table.add_row("기본 모델", env.get("DEFAULT_MODEL", "gpt-4o-mini"))
        llm_table.add_row("Vision 모델", env.get("VISION_MODEL", "gpt-4o"))
    llm_table.add_row("Temperature", env.get("TEMPERATURE", "0.7"))
    llm_table.add_row("Max Tokens", env.get("MAX_LLM_TOKENS", "4096"))
    console.print(llm_table)

    # ── Quality Settings table ────────────────────────────
    console.print()
    console.print("[bold cyan]⚙️  품질 설정[/bold cyan]")
    q_table = Table(show_header=False, box=None, padding=(0, 2))
    q_table.add_column("var", style="dim")
    q_table.add_column("value")

    threshold_raw = env.get("QUALITY_THRESHOLD", "80")
    try:
        level_label = _THRESHOLD_TO_LEVEL.get(int(threshold_raw), "custom")
    except ValueError:
        level_label = "custom"
    q_table.add_row("품질 레벨", f"{level_label} (threshold: {threshold_raw})")
    q_table.add_row("최대 반복", env.get("MAX_ITERATIONS", "3"))
    console.print(q_table)

    # ── Footer ────────────────────────────────────────────
    console.print()
    console.print(f"[dim].env 경로: {env_path}[/dim]")
    console.print("[dim]수정: lecture-forge init --reconfigure[/dim]\n")


def display_success_message(
    console: Console, env_path: Path, changed_count: int = 0
) -> None:
    """
    Display success message and next steps.

    Args:
        console: Rich console for output
        env_path: Path to created .env file
        changed_count: Number of changed settings (used in reconfigure mode)
    """
    if changed_count:
        console.print(
            f"[bold green]✅ 설정이 업데이트되었습니다! "
            f"({changed_count}개 항목 변경)[/bold green]\n"
        )
    else:
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
    console.print(f"   • 설정 확인:  [dim]lecture-forge init --show[/dim]")
    console.print(f"   • 설정 수정:  [dim]lecture-forge init --reconfigure[/dim]")
    console.print(
        "   • 이미지 포함 생성: [dim]lecture-forge create --image-search[/dim]"
    )
    console.print(
        "   • 고품질 모드: [dim]lecture-forge create --quality-level strict[/dim]\n"
    )
