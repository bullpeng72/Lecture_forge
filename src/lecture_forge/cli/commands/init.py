"""
Init command - Initialize LectureForge configuration.
"""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.panel import Panel
from rich.prompt import Confirm

from lecture_forge.cli.commands.init_helpers import (
    collect_all_api_keys,
    collect_api_keys_reconfigure,
    collect_llm_settings,
    collect_quality_settings,
    display_success_message,
    generate_minimal_template,
    load_current_env,
    load_env_template,
    populate_template,
    show_current_config,
)
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
@click.option(
    "--reconfigure",
    "-r",
    is_flag=True,
    default=False,
    help="기존 .env 값을 보존하면서 항목별로 수정합니다",
)
@click.option(
    "--show",
    "-s",
    is_flag=True,
    default=False,
    help="현재 설정을 출력합니다 (파일 수정 없음)",
)
def init(path: Optional[str], reconfigure: bool, show: bool) -> None:
    """
    Initialize LectureForge configuration.

    Creates a .env file with your API keys and settings in an easily
    accessible location.  Three modes are available:

    \b
    Modes:
      (기본)            최초 설정  — API 키 + LLM + 품질 설정
      --reconfigure/-r  재설정     — 기존 값 유지하며 항목별 수정
      --show/-s         현재 설정 출력 (파일 수정 없음)

    \b
    Default .env Location:
      • Mac/Linux: ~/Documents/LectureForge/.env
      • Windows:   %USERPROFILE%\\Documents\\LectureForge\\.env

    \b
    Setup Phases:
      Phase 1 — LLM 설정   (provider, 모델, temperature)
      Phase 2 — API Keys   (OpenAI*, Serper 필수 / Pexels, Unsplash 선택)
      Phase 3 — 품질 설정  (품질 레벨, 최대 반복 횟수)
      * Ollama 모드 시 OpenAI Key 불필요

    \b
    Examples:
      $ lecture-forge init                   # 최초 설정
      $ lecture-forge init --reconfigure     # 재설정
      $ lecture-forge init --show            # 현재 설정 확인
      $ lecture-forge init --path /my/dir    # 커스텀 경로

    \b
    After Setup:
      $ lecture-forge create
      $ lecture-forge home env    # .env 파일 직접 편집
    """
    # ── Resolve .env path ─────────────────────────────────
    if path:
        env_dir = Path(path).expanduser().resolve()
    else:
        from lecture_forge.config import get_default_config_dir
        env_dir = get_default_config_dir()

    env_path = env_dir / ".env"

    # ══════════════════════════════════════════════════════
    # Mode: --show
    # ══════════════════════════════════════════════════════
    if show:
        console.print()
        console.print(
            Panel.fit(
                "[bold cyan]📋 LectureForge 현재 설정[/bold cyan]",
                border_style="cyan",
            )
        )
        show_current_config(console, env_path)
        return

    # ══════════════════════════════════════════════════════
    # Shared banner
    # ══════════════════════════════════════════════════════
    console.print()
    if reconfigure:
        console.print(
            Panel.fit(
                "[bold cyan]🔧 LectureForge 설정 수정[/bold cyan]",
                border_style="cyan",
            )
        )
    else:
        console.print(
            Panel.fit(
                "[bold cyan]🚀 LectureForge Configuration Setup[/bold cyan]",
                border_style="cyan",
            )
        )
    console.print()

    console.print(f"📁 [dim]설정 파일 위치: {env_dir}[/dim]\n")

    # ══════════════════════════════════════════════════════
    # Mode: --reconfigure
    # ══════════════════════════════════════════════════════
    if reconfigure:
        if not env_path.exists():
            console.print(
                "[yellow]⚠️  .env 파일이 없습니다. 새로 생성합니다.[/yellow]\n"
            )
            # fall through to normal init
        else:
            current_env = load_current_env(env_path)
            console.print(
                f"[dim]기존 .env 파일을 불러왔습니다 "
                f"({len(current_env)}개 설정).[/dim]\n"
            )

            # Phase 1 — LLM Settings (provider must be known before API key collection)
            llm_settings = collect_llm_settings(console, current=current_env)
            provider = llm_settings.get("LLM_PROVIDER", "openai")

            # Phase 2 — API Keys (OpenAI skipped for Ollama)
            api_keys = collect_api_keys_reconfigure(
                console, prompt_masked_input, current_env, provider=provider
            )

            # Phase 3 — Quality Settings
            quality_settings = collect_quality_settings(console, current=current_env)

            # Load template and populate
            template_text, _ = load_env_template(console)
            if not template_text:
                template_text = generate_minimal_template()

            # In reconfigure mode use the existing file as the base so all
            # previously set values are preserved.
            base_text = env_path.read_text(encoding="utf-8")
            env_content = populate_template(
                base_text, api_keys, llm_settings, quality_settings
            )

            # Count changed settings
            new_env = {}
            for line in env_content.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    k, _, v = stripped.partition("=")
                    new_env[k.strip()] = v.strip()
            changed = sum(
                1 for k, v in new_env.items() if current_env.get(k) != v
            )

            _write_env(env_path, env_content)
            display_success_message(console, env_path, changed_count=changed)
            return

    # ══════════════════════════════════════════════════════
    # Mode: normal (first-time setup)
    # ══════════════════════════════════════════════════════

    # Check if .env already exists
    if env_path.exists():
        console.print(f"[yellow]⚠️  .env 파일이 이미 존재합니다:[/yellow]")
        console.print(f"[yellow]   {env_path}[/yellow]\n")
        overwrite = Confirm.ask("   덮어쓸까요?", default=False)
        if not overwrite:
            console.print("\n[green]✓ 취소되었습니다. 기존 설정을 유지합니다.[/green]")
            console.print(
                "[dim]수정이 필요하다면: lecture-forge init --reconfigure[/dim]\n"
            )
            return
        console.print()

    # Create directory
    try:
        env_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        console.print(f"[red]❌ 디렉토리 생성 실패: {e}[/red]\n")
        sys.exit(1)

    # ── Phase 1: LLM Settings (provider must be known before API key collection) ──
    llm_settings = collect_llm_settings(console)
    provider = llm_settings.get("LLM_PROVIDER", "openai")

    # ── Phase 2: API Keys (OpenAI skipped for Ollama) ────
    api_keys = collect_all_api_keys(console, prompt_masked_input, provider=provider)

    # ── Phase 3: Quality Settings ─────────────────────────
    quality_settings = collect_quality_settings(console)

    # ── Load template and populate ────────────────────────
    template_text, _ = load_env_template(console)
    if not template_text:
        console.print(
            "[yellow]⚠️  템플릿을 찾을 수 없어 최소 설정으로 생성합니다.[/yellow]"
        )
        template_text = generate_minimal_template()

    env_content = populate_template(
        template_text, api_keys, llm_settings, quality_settings
    )

    _write_env(env_path, env_content)
    display_success_message(console, env_path)


# ── Internal helpers ──────────────────────────────────────


def _write_env(env_path: Path, content: str) -> None:
    """Write content to env_path and set secure permissions."""
    try:
        env_path.write_text(content, encoding="utf-8")
    except Exception as e:
        console.print(f"[red]❌ .env 파일 저장 실패: {e}[/red]\n")
        sys.exit(1)

    if sys.platform != "win32":
        try:
            env_path.chmod(0o600)
            console.print("[dim]🔒 파일 권한 설정 완료 (owner-only, 600)[/dim]\n")
        except OSError as e:
            logger.debug(f"Could not set file permissions: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error setting file permissions: {e}")
