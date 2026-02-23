"""
Translate command - Translate an English PDF into a Korean lecture material (HTML).
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from lecture_forge.cli.utils import console, display_token_usage
from lecture_forge.utils import logger
from lecture_forge.utils.token_tracker import get_tracker


def translate_lecture(
    pdf_path: str,
    output_name: Optional[str],
    quality_level: str,
    audience_level: str,
    with_slides: bool,
    no_translate: bool,
    with_diagrams: bool = False,
) -> dict:
    """
    Core translate pipeline.

    Phases:
      1. Extract PDF chapter structure
      2. Collect PDF images
      3. Build curriculum (bypasses CurriculumDesigner)
      4. Translate chapters (or keep original if no_translate)
      5. Assign images to sections by page range
      6. Generate Mermaid diagrams
      7. Assemble HTML
      8. Quality assurance loop
      (optional) Convert to Reveal.js slides

    Returns:
        Dict with html_path, sections_count, total_words, diagrams, images,
        quality_score, token_usage.
    """
    from lecture_forge.agents.diagram_generator import DiagramGeneratorAgent
    from lecture_forge.agents.html_assembler import HTMLAssemblerAgent
    from lecture_forge.agents.image_collector import ImageCollectorAgent
    from lecture_forge.agents.pdf_translator import PDFTranslatorAgent
    from lecture_forge.agents.revision_agent import RevisionAgent
    from lecture_forge.config import Config
    from lecture_forge.models.lecture import Lecture
    from lecture_forge.quality.evaluator import QualityEvaluator

    tracker = get_tracker()
    tracker.reset()

    pdf_path_obj = Path(pdf_path).resolve()
    topic = pdf_path_obj.stem  # Use filename (without extension) as topic

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_id = f"translate_{timestamp}"

    translator = PDFTranslatorAgent(pdf_path=str(pdf_path_obj))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:

        # ── Phase 1: Extract PDF structure ────────────────────────────────────
        task1 = progress.add_task(
            "[cyan]📖 Phase 1: Extracting PDF structure...", total=None
        )
        chapters = translator.extract_structure()
        progress.update(task1, completed=True)
        console.print(f"   ✅ Extracted {len(chapters)} chapters from PDF")

        # ── Phase 2: Collect PDF images ───────────────────────────────────────
        task2 = progress.add_task(
            "[cyan]🖼️  Phase 2: Collecting PDF images...", total=None
        )
        image_agent = ImageCollectorAgent(session_id=session_id)
        image_result = image_agent.collect(
            {"pdfs": [str(pdf_path_obj)], "urls": [], "image_keywords": []},
            auto_describe_images=True,
        )
        progress.update(task2, completed=True)
        console.print(f"   ✅ Images collected: {image_result['total_collected']}")

        # ── Phase 3: Build curriculum (bypasses CurriculumDesigner) ──────────
        task3 = progress.add_task(
            "[cyan]📋 Phase 3: Building curriculum from PDF order...", total=None
        )
        curriculum, chapter_page_map = translator.build_curriculum(
            chapters, topic=topic, audience_level=audience_level
        )
        progress.update(task3, completed=True)
        console.print(
            f"   ✅ Curriculum built: {len(curriculum.sections)} sections, "
            f"{curriculum.total_estimated_time} min"
        )

        # ── Phase 4: Translate chapters ───────────────────────────────────────
        phase4_label = (
            "⏭️  Phase 4: Processing (no translation)..."
            if no_translate
            else "🌐 Phase 4: Translating chapters..."
        )
        task4 = progress.add_task(f"[cyan]{phase4_label}", total=None)
        section_contents = translator.translate_chapters(
            chapters, curriculum, skip_translation=no_translate
        )
        progress.update(task4, completed=True)
        total_words = sum(s.word_count for s in section_contents)
        action_word = "Processed" if no_translate else "Translated"
        console.print(
            f"   ✅ {action_word}: {len(section_contents)} sections, {total_words:,} words"
        )

        # ── Phase 5: Assign images to sections ────────────────────────────────
        task5 = progress.add_task(
            "[cyan]🖼️  Phase 5: Assigning images by page location...", total=None
        )
        section_contents = translator.assign_images_to_sections(
            section_contents,
            chapter_page_map,
            image_result.get("images", []),
            curriculum,
        )
        progress.update(task5, completed=True)
        total_images = sum(len(s.images) for s in section_contents)
        console.print(f"   ✅ Images assigned: {total_images}")

        # ── Phase 6: Generate diagrams (opt-in only) ──────────────────────────
        task6 = progress.add_task(
            "[cyan]📊 Phase 6: Generating diagrams...", total=None
        )
        if with_diagrams:
            diagram_gen = DiagramGeneratorAgent()
            section_contents = diagram_gen.generate_diagrams(
                section_contents, curriculum=curriculum
            )
            total_diagrams = sum(len(s.diagrams) for s in section_contents)
            console.print(f"   ✅ Diagrams generated: {total_diagrams}")
        else:
            total_diagrams = 0
            console.print("   ⏭️  Diagrams skipped (use --with-diagrams to enable)")
        progress.update(task6, completed=True)

        # ── Phase 7: Assemble HTML ────────────────────────────────────────────
        task7 = progress.add_task(
            "[cyan]🎨 Phase 7: Assembling HTML...", total=None
        )

        lecture_title = (
            f"{topic} (구조 추출)" if no_translate else f"{topic} (한국어 번역)"
        )

        lecture = Lecture(
            title=lecture_title,
            topic=topic,
            duration=curriculum.total_estimated_time,
            audience_level=audience_level,
            learning_objectives=curriculum.learning_objectives,
            sections=section_contents,
            total_word_count=total_words,
            total_images=total_images,
            total_diagrams=total_diagrams,
            created_at=datetime.now().isoformat(),
        )

        if not output_name:
            suffix = "_structure" if no_translate else "_ko"
            output_name = f"{topic}{suffix}"

        html_assembler = HTMLAssemblerAgent()
        html_path = html_assembler.assemble(
            lecture,
            output_path=output_name,
            image_search_enabled=False,  # Translation doesn't use web image search
        )
        progress.update(task7, completed=True)
        console.print(f"   ✅ HTML assembled: {html_path}")

        # ── Phase 8: Quality assurance ────────────────────────────────────────
        quality_threshold = {"lenient": 70, "balanced": 80, "strict": 90}.get(
            quality_level, 80
        )
        task8 = progress.add_task(
            f"[cyan]✅ Phase 8: Quality assurance (threshold: {quality_threshold})...",
            total=None,
        )

        evaluator = QualityEvaluator()
        revision_agent = RevisionAgent()

        iteration = 0
        max_iterations = Config.MAX_ITERATIONS
        previous_score = 0.0
        improved_lecture = lecture
        quality_improved = False
        final_evaluation = None

        while iteration < max_iterations:
            evaluation = evaluator.evaluate(improved_lecture, quality_threshold)
            final_evaluation = evaluation

            console.print(
                f"\n   📊 Quality (iter {iteration + 1}): "
                f"{evaluation.overall_score:.1f}/100"
            )

            if evaluation.passed:
                if iteration > 0:
                    quality_improved = True
                break

            if iteration > 0:
                improvement = evaluation.overall_score - previous_score
                if improvement < 2:
                    console.print(
                        f"   ⚠️  Minimal improvement (+{improvement:.1f}). Stopping."
                    )
                    break
                if improvement < 0:
                    console.print(f"   ❌ Quality degraded. Keeping previous version.")
                    break

            revised_lecture = revision_agent.revise(improved_lecture, evaluation)
            re_eval = evaluator.evaluate(revised_lecture, quality_threshold)
            actual_improvement = re_eval.overall_score - evaluation.overall_score

            console.print(
                f"   → After revision: {re_eval.overall_score:.1f}/100 "
                f"(+{actual_improvement:.1f})"
            )

            if actual_improvement > 0:
                improved_lecture = revised_lecture
                previous_score = re_eval.overall_score
                quality_improved = True
                total_words = improved_lecture.total_word_count
            else:
                console.print("   ⚠️  Revision did not improve quality. Stopping.")
                break

            iteration += 1

        # Regenerate HTML if quality improved
        if quality_improved:
            console.print("   🎨 Regenerating HTML with improvements...")
            html_path = html_assembler.assemble(
                improved_lecture,
                output_path=output_name,
                image_search_enabled=False,
            )
            lecture = improved_lecture

        progress.update(task8, completed=True)

        if iteration >= max_iterations:
            console.print(f"   ⚠️  Reached max iterations ({max_iterations})")

        if final_evaluation:
            console.print(
                f"   📊 Final quality score: {final_evaluation.overall_score:.1f}/100\n"
            )

    # ── Optional: Slides conversion ───────────────────────────────────────────
    if with_slides:
        console.print("\n[bold]Converting to Presentation Slides...[/bold]")
        console.print("━" * 50)
        slides_path = Path(html_path).parent / f"{Path(html_path).stem}_slides.html"
        try:
            from lecture_forge.slides import SlideConverter

            converter = SlideConverter(console=console)
            success = converter.convert(Path(html_path), slides_path, with_notes=False)
            if success:
                console.print(f"[green]✅ Slides created: {slides_path}[/green]")
            else:
                console.print("[red]❌ Slides conversion failed[/red]")
        except Exception as e:
            console.print(f"[yellow]⚠️  Slides conversion skipped: {e}[/yellow]")

    token_usage = tracker.get_summary()

    return {
        "html_path": html_path,
        "sections_count": len(lecture.sections),
        "total_words": lecture.total_word_count,
        "diagrams": sum(len(s.diagrams) for s in lecture.sections),
        "images": sum(len(s.images) for s in lecture.sections),
        "quality_score": final_evaluation.overall_score if final_evaluation else 0,
        "token_usage": token_usage,
    }


@click.command()
@click.argument("pdf_path", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=str,
    default=None,
    help="Output file name without extension (auto-generated if omitted)",
)
@click.option(
    "--quality-level",
    type=click.Choice(["lenient", "balanced", "strict"]),
    default="balanced",
    show_default=True,
    help="Quality threshold: lenient(70), balanced(80), strict(90)",
)
@click.option(
    "--audience-level",
    type=click.Choice(["beginner", "intermediate", "advanced"]),
    default="intermediate",
    show_default=True,
    help="Target audience level (affects content depth and terminology)",
)
@click.option(
    "--with-slides",
    is_flag=True,
    default=False,
    help="Also convert result to Reveal.js presentation slides",
)
@click.option(
    "--no-translate",
    is_flag=True,
    default=False,
    help="Skip translation — keep original English text (for structure debugging)",
)
@click.option(
    "--with-diagrams",
    is_flag=True,
    default=False,
    help="Generate Mermaid diagrams (disabled by default; PDF images are used instead)",
)
def translate(
    pdf_path: str,
    output: Optional[str],
    quality_level: str,
    audience_level: str,
    with_slides: bool,
    no_translate: bool,
    with_diagrams: bool,
) -> None:
    """
    Translate an English PDF into a Korean lecture material (HTML).

    Extracts chapter structure from the PDF, translates each chapter to Korean,
    assigns PDF images by page location, and assembles a fully formatted HTML file.
    CurriculumDesigner is bypassed — original PDF chapter order is preserved.

    \b
    Structure Extraction Priority:
      1. PDF TOC  — most accurate; works for 80%+ of academic PDFs
      2. Font size analysis  — detects headings larger than body text
      3. Page groups (fallback)  — equal-sized page ranges

    \b
    Translation Features:
      • Technical terms: Korean + English parenthetical (e.g. 신경망(Neural Network))
      • Code blocks preserved unchanged (__CODE_BLOCK_N__ placeholder method)
      • Markdown headings translated to Korean
      • Math formulas, URLs, variable names kept as-is
      • Context continuity maintained between consecutive chapters

    \b
    Examples:
      # Basic translation
      $ lecture-forge translate paper.pdf

    \b
      # Custom output name
      $ lecture-forge translate paper.pdf -o my_lecture_ko

    \b
      # Debug structure extraction (no translation, fast)
      $ lecture-forge translate paper.pdf --no-translate

    \b
      # High quality with slides output
      $ lecture-forge translate paper.pdf --quality-level strict --with-slides

    \b
      # Beginner-friendly translation
      $ lecture-forge translate paper.pdf --audience-level beginner
    """
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]🌐 LectureForge - PDF → Korean Translation[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()

    pdf_path_obj = Path(pdf_path)
    console.print(f"[bold]PDF:[/bold]      {pdf_path_obj.name}")
    console.print(
        f"[bold]Mode:[/bold]     "
        f"{'원문 구조만 (번역 없음)' if no_translate else '한국어 번역'}"
    )
    console.print(
        f"[bold]Quality:[/bold]  {quality_level} | "
        f"[bold]Audience:[/bold] {audience_level}"
    )
    if with_slides:
        console.print("[bold]Slides:[/bold]   enabled")
    if with_diagrams:
        console.print("[bold]Diagrams:[/bold] enabled (Mermaid auto-generation)")
    console.print()

    try:
        result = translate_lecture(
            pdf_path=pdf_path,
            output_name=output,
            quality_level=quality_level,
            audience_level=audience_level,
            with_slides=with_slides,
            no_translate=no_translate,
            with_diagrams=with_diagrams,
        )

        console.print("\n[bold green]✅ Translation complete![/bold green]\n")
        console.print(f"📄 [bold]HTML File:[/bold] {result['html_path']}")
        console.print(f"\n📊 [bold]Statistics:[/bold]")
        console.print(f"   • Sections: {result['sections_count']}")
        console.print(f"   • Words: {result['total_words']:,}")
        console.print(f"   • Diagrams: {result['diagrams']}")
        console.print(f"   • Images: {result['images']}")

        if result.get("quality_score", 0) > 0:
            score = result["quality_score"]
            color = "green" if score >= 80 else "yellow" if score >= 60 else "red"
            console.print(f"   • Quality score: [{color}]{score:.1f}/100[/{color}]")

        if result.get("token_usage"):
            display_token_usage(result["token_usage"])

        console.print(
            f"\n[dim]💡 Open the HTML file in a browser to view the lecture![/dim]\n"
        )

    except Exception as e:
        console.print(f"\n[bold red]❌ Error: {e}[/bold red]")
        logger.exception("Translation failed")
        sys.exit(1)
