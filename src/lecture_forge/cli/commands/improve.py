"""
Improve command - Improve.
"""

from pathlib import Path

import click
from rich.panel import Panel

from lecture_forge.cli.utils import console
from lecture_forge.slides import SlideConverter
from lecture_forge.utils import logger


@click.command()
@click.argument("lecture_path", type=click.Path(exists=True))
@click.option("--to-slides", is_flag=True, help="Convert lecture to Reveal.js presentation slides (발표자 노트 자동 포함)")
@click.option("--without-notes", is_flag=True, help="발표자 노트 없이 슬라이드 생성 (--to-slides와 함께 사용)")
@click.option(
    "--re-evaluate",
    is_flag=True,
    help="KB 기반 품질 재평가 및 콘텐츠 보강 (→ *_enhanced.html)",
)
@click.option(
    "--quality-level",
    type=click.Choice(["lenient", "balanced", "strict"]),
    default="balanced",
    show_default=True,
    help="품질 기준 (lenient=70, balanced=80, strict=90)",
)
@click.option(
    "--kb",
    type=click.Path(exists=True),
    help="지식 DB 경로 (HTML에 메타데이터 없는 기존 파일용 fallback)",
)
def improve(
    lecture_path: str,
    to_slides: bool,
    without_notes: bool,
    re_evaluate: bool,
    quality_level: str,
    kb: str,
) -> None:
    """
    Improve existing lecture quality with optional enhancements.

    Apply post-generation improvements to enhance lecture quality:
    - Convert lecture to presentation slides format (발표자 노트 기본 포함)
    - Re-evaluate quality and supplement with KB content

    \b
    Enhancement Options:
      --to-slides           Convert lecture HTML to Reveal.js presentation slides
                            · Creates a separate *_slides.html file
                            · Splits content into slides; preserves images & diagrams
                            · Per-section LLM rewrite included (≤35자, 말줄임표 없음)
                            · 발표자 노트 자동 생성 포함 (기본값)
                            · 노트 제외: --without-notes 추가
      --without-notes       발표자 노트 없이 슬라이드 생성 (--to-slides와 함께 사용)
                            · 기본적으로 노트가 포함되므로, 제외하려면 이 옵션 사용
      --re-evaluate         KB 기반 품질 재평가 후 미반영 내용 보충 추가
                            · 기존 섹션 보존, 누락 청크를 말미에 추가
                            · HTML 메타데이터에서 KB 경로 자동 감지
                            · → *_enhanced.html 생성

    \b
    Slide Keyboard Shortcuts:
      Arrow Keys / Space    - Navigate slides (→ next, ← previous, ↑↓ vertical)
      Home / End            - First / last slide
      Esc / O               - Overview mode (see all slides)
      S                     - Speaker notes (if available)
      F                     - Full screen mode
      B / .                 - Pause/blackout (blank screen)
      Alt+Click             - Zoom to clicked element
      ?                     - Show keyboard shortcuts help

    \b
    Examples:
      # Convert to presentation slides (발표자 노트 자동 포함)
      $ lecture-forge improve outputs/lecture.html --to-slides

    \b
      # Convert WITHOUT presenter notes
      $ lecture-forge improve outputs/lecture.html --to-slides --without-notes

    \b
      # 기본 재평가 및 보강
      $ lecture-forge improve outputs/lecture.html --re-evaluate

    \b
      # 엄격한 기준으로 재평가
      $ lecture-forge improve outputs/lecture.html --re-evaluate --quality-level strict

    \b
      # 기존 파일 (메타데이터 없음) — KB 경로 수동 지정
      $ lecture-forge improve outputs/lecture.html --re-evaluate \\
          --kb ~/Documents/LectureForge/data/vector_db/MyTopic_20260119_...

    \b
      # 보강 + 슬라이드 변환 동시 적용
      $ lecture-forge improve outputs/lecture.html --re-evaluate --to-slides
    """
    console.print()
    console.print(Panel.fit("[bold cyan]🔧 LectureForge - Lecture Improvement[/bold cyan]", border_style="cyan"))
    console.print()

    lecture_path = Path(lecture_path)

    if not lecture_path.exists():
        console.print(f"[red]❌ Lecture file not found: {lecture_path}[/red]")
        return

    if re_evaluate:
        console.print("[bold]KB 기반 품질 재평가 및 콘텐츠 보강[/bold]")
        console.print("━" * 50)
        console.print()

        from lecture_forge.agents.content_enhancer import ContentEnhancer

        enhancer = ContentEnhancer()
        enhanced_path = enhancer.enhance(
            html_path=lecture_path,
            quality_level=quality_level,
            kb_path=kb,
        )

        if enhanced_path:
            console.print(f"[green]✅ 보강 완료: {enhanced_path}[/green]")
        else:
            console.print("[red]❌ 콘텐츠 보강 실패[/red]")
        console.print()

    if to_slides:
        console.print("[bold]Converting to Presentation Slides[/bold]")
        console.print("━" * 50)
        console.print()

        # Notes are ON by default; --without-notes opts out
        with_notes = not without_notes

        slides_path = lecture_path.parent / f"{lecture_path.stem}_slides.html"

        converter = SlideConverter(console=console)
        success = converter.convert(lecture_path, slides_path, with_notes=with_notes)

        if success:
            console.print(f"[green]✅ Slides created: {slides_path}[/green]")
            if with_notes:
                console.print(f"[green]   발표자 노트 포함 — 브라우저에서 S키로 발표자 뷰 열기[/green]")
            else:
                console.print(f"[green]   발표자 노트 없음 (--without-notes)[/green]")
            console.print()
        else:
            console.print(f"[red]❌ Slides conversion failed[/red]")

    if not re_evaluate and not to_slides:
        console.print("[yellow]No improvement options specified[/yellow]")
        console.print("Use --re-evaluate to re-evaluate and supplement content")
        console.print("Use --to-slides to convert to presentation format (발표자 노트 자동 포함)")
