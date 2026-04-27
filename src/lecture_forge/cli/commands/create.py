"""
Create command - Generate lecture materials from various sources.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import click
import yaml
from rich.progress import Progress, SpinnerColumn, TextColumn

from lecture_forge.agents.content_analyzer import ContentAnalyzerAgent
from lecture_forge.agents.content_collector import ContentCollectorAgent
from lecture_forge.agents.content_writer import ContentWriterAgent
from lecture_forge.agents.curriculum_designer import CurriculumDesignerAgent
from lecture_forge.agents.diagram_generator import DiagramGeneratorAgent
from lecture_forge.agents.html_assembler import HTMLAssemblerAgent
from lecture_forge.agents.image_collector import ImageCollectorAgent
from lecture_forge.agents.revision_agent import RevisionAgent
from lecture_forge.quality.evaluator import QualityEvaluator
from lecture_forge.cli.commands.create_async import _create_async  # Async version
from lecture_forge.cli.utils import (
    collect_inputs_interactive,
    console,
    display_token_usage,
    print_banner,
)
from lecture_forge.config import Config
from lecture_forge.models.lecture import Lecture
from lecture_forge.utils import logger, reconfigure_logging_console
from lecture_forge.utils.token_tracker import get_tracker


def generate_lecture(
    inputs: Dict[str, Any],
    eval_output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate lecture using the multi-agent pipeline.

    Args:
        inputs:          Dictionary with lecture parameters
        eval_output_dir: agent-evaluator 결과 저장 경로.
                         None(기본값)이면 평가 계측을 건너뛴다.

    Returns:
        Dictionary with generation results
    """
    # agent-evaluator 평가 모니터 초기화 (opt-in)
    _eval_monitor = None
    if eval_output_dir:
        try:
            from lecture_forge.eval import (
                build_lecture_monitor,
                ContentWriterAdapter,
                CurriculumDesignerAdapter,
                ContentAnalyzerAdapter,
                QualityEvaluatorAdapter,
            )
            _eval_monitor = build_lecture_monitor(eval_output_dir)
        except ImportError:
            console.print(
                "[yellow]⚠️  agent-evaluator 미설치 — eval 계측을 건너뜁니다.[/yellow]\n"
                '[dim]설치: pip install "lecture-forge[eval]"[/dim]'
            )

    # Share console between RichHandler and Progress to prevent double-rendering
    reconfigure_logging_console(console)

    # Reset token tracker
    tracker = get_tracker()
    tracker.reset()

    # Generate collection name from topic
    # Sanitize topic name for ChromaDB (ASCII only: alphanumeric, underscore, hyphen)
    import re

    topic_safe = inputs["topic"].replace(" ", "_").replace("/", "_").replace("\\", "_")
    # Remove non-ASCII characters (한글 등)
    topic_safe = re.sub(r"[^a-zA-Z0-9_-]", "", topic_safe)
    # If empty after sanitization, use default
    if not topic_safe or len(topic_safe) < 3:
        topic_safe = "lecture"
    # Ensure it starts with alphanumeric
    if not topic_safe[0].isalnum():
        topic_safe = "lec_" + topic_safe
    # Limit length (ChromaDB max: 63 chars, reserve 16 for timestamp)
    topic_safe = topic_safe[:47]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    collection_name = f"{topic_safe}_{timestamp}"

    # Pre-compute output stem so images land directly in outputs/{stem}_images/
    _raw_output = inputs.get("output_name")
    output_stem = Path(_raw_output).stem if _raw_output else f"{inputs['topic'].replace(' ', '_')}_{timestamp}"
    image_session_id = f"{output_stem}_images"

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Phase 1: Content Collection
        task1 = progress.add_task("[cyan]📚 Phase 1: Collecting content...", total=1)

        existing_kb_path = inputs.get("existing_kb_path")
        kb_mode = inputs.get("kb_mode", "new")

        if existing_kb_path:
            # Use existing KB directory name as collection name
            collection_name = Path(existing_kb_path).name
            content_agent = ContentCollectorAgent(collection_name=collection_name)

            if kb_mode == "reuse_only":
                # Read-only: sample representative documents for analysis
                stats = content_agent.vector_store.get_stats()
                sample_results = content_agent.vector_store.query(inputs["topic"], n_results=20)
                sample_texts = (sample_results.get("documents") or [[]])[0]
                synthetic_docs = [
                    {
                        "text": t,
                        "source": "existing_kb",
                        "source_type": "vector_db",
                        "metadata": {},
                        "pages": [],
                    }
                    for t in sample_texts
                ]
                content_result = {
                    "success": True,
                    "documents": synthetic_docs,
                    "chunks": [],
                    "chunk_ids": [],
                    "metadata": {
                        "total_docs": stats["document_count"],
                        "total_chunks": stats["document_count"],
                        "sources": {"existing_kb": collection_name},
                        "vector_db": stats,
                    },
                }
                progress.update(task1, description="[green]✅ Phase 1: Content collected", advance=1)
                console.print(
                    f"   ✅ Reusing KB '{collection_name}': {stats['document_count']} chunks"
                )

            else:  # extend
                # Add new sources to existing KB in-place
                content_result = content_agent.collect(
                    {
                        "pdfs": inputs.get("pdfs", []),
                        "urls": inputs.get("urls", []),
                        "keywords": inputs.get("keywords", []),
                        "hada_keywords": inputs.get("hada_keywords", []),
                    }
                )
                total_after = content_agent.vector_store.get_stats()["document_count"]
                progress.update(task1, description="[green]✅ Phase 1: Content collected", advance=1)
                console.print(
                    f"   ✅ Extended KB '{collection_name}': "
                    f"+{content_result['metadata']['total_chunks']} new chunks "
                    f"(total: {total_after})"
                )

        else:
            # New KB (existing behaviour)
            content_agent = ContentCollectorAgent(collection_name=collection_name)
            content_result = content_agent.collect(
                {
                    "pdfs": inputs.get("pdfs", []),
                    "urls": inputs.get("urls", []),
                    "keywords": inputs.get("keywords", []),
                    "hada_keywords": inputs.get("hada_keywords", []),
                }
            )
            progress.update(task1, description="[green]✅ Phase 1: Content collected", advance=1)
            console.print(
                f"   ✅ Content collected: {content_result['metadata']['total_docs']} docs, "
                f"{content_result['metadata']['total_chunks']} chunks"
            )

        # Phase 2: Image Collection
        task2 = progress.add_task("[cyan]🖼️  Phase 2: Collecting images...", total=1)
        image_agent = ImageCollectorAgent(
            session_id=image_session_id,
            output_dir=str(Config.OUTPUT_DIR),
            vector_store=content_agent.vector_store,
        )

        # PDF images now recommended with location-based matching (v0.2.0+)
        pdf_sources = inputs.get("pdfs", []) if inputs.get("include_pdf_images", True) else []

        if not inputs.get("include_pdf_images", True) and inputs.get("pdfs", []):
            console.print("   ⏭️  [dim]Skipping PDF image extraction (disabled by --no-include-pdf-images)[/dim]")
        elif inputs.get("include_pdf_images", True) and inputs.get("pdfs", []):
            console.print("   📸 [cyan]Extracting PDF images with location-based matching[/cyan]")

        image_result = image_agent.collect(
            {
                "pdfs": pdf_sources,
                "urls": inputs.get("urls", []),
                "image_keywords": inputs.get("image_keywords", []),
            },
            # max_images_per_keyword: uses Config.MAX_IMAGES_PER_SEARCH by default
            auto_describe_images=inputs.get("auto_describe_images", True),
        )

        # When reusing/extending an existing KB, load images previously stored in vector store
        if existing_kb_path:
            stored_images = image_agent.load_images_from_vector_store()
            if stored_images:
                existing_ids = {img["id"] for img in image_result.get("images", [])}
                new_from_store = [img for img in stored_images if img["id"] not in existing_ids]
                image_result["images"] = image_result.get("images", []) + new_from_store
                image_result["total_collected"] = len(image_result["images"])
                if new_from_store:
                    console.print(f"   📸 Loaded {len(new_from_store)} existing images from KB")

        progress.update(task2, description="[green]✅ Phase 2: Images collected", advance=1)
        console.print(f"   ✅ Images collected: {image_result['total_collected']}")

        # Phase 3a: Content Analysis
        task3a = progress.add_task("[cyan]🔍 Phase 3a: Analyzing content...", total=1)
        analyzer = ContentAnalyzerAgent(vector_store=content_agent.vector_store)
        if _eval_monitor:
            analyzer = ContentAnalyzerAdapter(analyzer, _eval_monitor)
        analysis_result = analyzer.analyze(
            collection_result=content_result,
            image_result=image_result,
            topic=inputs["topic"],
        )
        progress.update(task3a, description="[green]✅ Phase 3a: Analysis complete", advance=1)
        console.print(
            f"   ✅ Analysis complete: {len(analysis_result.key_topics)} topics, " f"{len(analysis_result.entities)} entities"
        )

        # Phase 3b: Curriculum Design
        task3b = progress.add_task("[cyan]📋 Phase 3b: Designing curriculum...", total=1)
        designer = CurriculumDesignerAgent(vector_store=content_agent.vector_store)
        if _eval_monitor:
            designer = CurriculumDesignerAdapter(designer, _eval_monitor)
        curriculum = designer.design(
            analysis_result=analysis_result,
            topic=inputs["topic"],
            duration=inputs["duration"],
            audience_level=inputs["audience_level"],
        )
        progress.update(task3b, description="[green]✅ Phase 3b: Curriculum designed", advance=1)
        console.print(
            f"   ✅ Curriculum designed: {len(curriculum.sections)} sections, " f"{curriculum.total_estimated_time} min"
        )

        # Phase 4a: Content Writing (section-level progress)
        num_sections = len(curriculum.sections)
        task4a = progress.add_task(
            f"[cyan]✍️  Phase 4a: Writing content (0/{num_sections} sections)...",
            total=num_sections,
        )
        writer = ContentWriterAgent(
            vector_store=content_agent.vector_store,
        )
        if _eval_monitor:
            writer = ContentWriterAdapter(
                writer, _eval_monitor,
                learning_objectives=curriculum.learning_objectives,
            )

        # Write sections one by one to update progress incrementally
        section_contents = []
        writer.used_image_ids.clear()
        writer.image_usage_count.clear()
        writer.used_chunk_ids.clear()
        if writer.vector_store:
            writer._pre_assign_chunks_to_sections(curriculum)

        available_images_list = image_result.get("images", [])
        for sec_idx, section in enumerate(curriculum.sections):
            available_for_section = [
                img for img in available_images_list if img.get("id") not in writer.used_image_ids
            ]
            content = writer.write_section(
                section=section,
                curriculum=curriculum,
                available_images=available_for_section,
            )
            for img_ref in content.images:
                writer.used_image_ids.add(img_ref.image_id)
                writer.image_usage_count[img_ref.image_id] = writer.image_usage_count.get(img_ref.image_id, 0) + 1
            section_contents.append(content)
            progress.update(
                task4a,
                description=f"[cyan]✍️  Phase 4a: Writing content ({sec_idx + 1}/{num_sections} sections)...",
                advance=1,
            )

        # Coverage sweep (same as original write_all_sections)
        if writer.vector_store:
            try:
                total_chunks = int(writer.vector_store.get_total_chunk_count())
            except (TypeError, ValueError):
                total_chunks = 0
            if total_chunks > 0:
                coverage_ratio = len(writer.used_chunk_ids) / total_chunks
                for _round in range(2):
                    coverage_ratio = len(writer.used_chunk_ids) / max(1, total_chunks)
                    if coverage_ratio >= Config.RAG_COVERAGE_MIN_RATIO:
                        break
                    writer._expand_sections_for_coverage(section_contents, curriculum)

        progress.update(task4a, description="[green]✅ Phase 4a: Content written")
        total_words = sum(s.word_count for s in section_contents)
        total_code_blocks = sum(len(s.code_blocks) for s in section_contents)
        console.print(
            f"   ✅ Content written: {len(section_contents)} sections, "
            f"{total_words} words, {total_code_blocks} code blocks"
        )

        # Phase 4b: Diagram Generation
        task4b = progress.add_task("[cyan]📊 Phase 4b: Generating diagrams...", total=1)
        diagram_gen = DiagramGeneratorAgent()
        section_contents = diagram_gen.generate_diagrams(section_contents, curriculum=curriculum)
        progress.update(task4b, description="[green]✅ Phase 4b: Diagrams generated", advance=1)
        total_diagrams = sum(len(s.diagrams) for s in section_contents)
        console.print(f"   ✅ Diagrams generated: {total_diagrams}")

        # Phase 4c: HTML Assembly
        task4c = progress.add_task("[cyan]🎨 Phase 4c: Assembling HTML...", total=1)
        lecture = Lecture(
            title=f"{inputs['topic']} - {inputs['audience_level'].capitalize()} Level",
            topic=inputs["topic"],
            duration=inputs["duration"],
            audience_level=inputs["audience_level"],
            learning_objectives=curriculum.learning_objectives,
            sections=section_contents,
            total_word_count=total_words,
            total_images=sum(len(s.images) for s in section_contents),
            total_diagrams=total_diagrams,
            vector_db_path=str(content_agent.vector_store.db_path),
            created_at=datetime.now().isoformat(),
        )

        html_assembler = HTMLAssemblerAgent()
        html_path = html_assembler.assemble(
            lecture,
            output_path=output_stem,
            image_search_enabled=inputs.get("image_search", True),
        )
        progress.update(task4c, description="[green]✅ Phase 4c: HTML assembled", advance=1)
        console.print(f"   ✅ HTML assembled: {html_path}")

        # Phase 5: Quality Assurance (optional but enabled by default)
        quality_threshold = {"lenient": 70, "balanced": 80, "strict": 90}.get(inputs.get("quality_level", "balanced"), 80)
        max_iterations = Config.MAX_ITERATIONS

        from lecture_forge.agents.revision_agent import RevisionAgent

        evaluator = QualityEvaluator()
        if _eval_monitor:
            evaluator = QualityEvaluatorAdapter(evaluator, _eval_monitor)
        revision_agent = RevisionAgent()

        task5 = progress.add_task(f"[cyan]✅ Phase 5: Quality assurance (threshold: {quality_threshold})...", total=1)

        iteration = 0
        previous_score = 0
        improved_lecture = lecture
        quality_improved = False
        final_evaluation = None  # Initialize to avoid UnboundLocalError

        while iteration < max_iterations:
            # Evaluate quality
            evaluation = evaluator.evaluate(improved_lecture, quality_threshold)
            final_evaluation = evaluation  # Save for later use

            console.print(f"\n   📊 Quality evaluation (iteration {iteration + 1}):" f" {evaluation.overall_score:.1f}/100")

            # Check if passed
            if evaluation.passed:
                console.print(f"   ✅ Quality threshold met ({quality_threshold})!")
                if iteration > 0:
                    quality_improved = True
                break

            # Check improvement (prevent infinite loop and degradation)
            if iteration > 0:
                improvement = evaluation.overall_score - previous_score

                if improvement < 2:
                    console.print(f"   ⚠️  Minimal improvement (+{improvement:.1f}). " "Stopping to prevent degradation.")
                    break

                if improvement < 0:
                    console.print(f"   ❌ Quality degraded ({improvement:.1f}). " "Keeping previous version.")
                    # Revert to previous version (would need to be saved)
                    break

            # Show top issues
            if evaluation.issues and iteration == 0:
                console.print(f"   ⚠️  {len(evaluation.issues)} issues found:")
                for issue in evaluation.issues[:3]:  # Show top 3
                    severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(issue.severity, "⚪")
                    console.print(
                        f"      {severity_icon} [{issue.severity}] {issue.dimension}: " f"{issue.description[:80]}..."
                    )

            # Apply revisions
            console.print(f"   🔧 Applying automatic improvements...")
            revised_lecture = revision_agent.revise(improved_lecture, evaluation)

            # Re-evaluate to check actual improvement
            final_evaluation = evaluator.evaluate(revised_lecture, quality_threshold)
            actual_improvement = final_evaluation.overall_score - evaluation.overall_score

            console.print(f"   → After revision: {final_evaluation.overall_score:.1f}/100 " f"(+{actual_improvement:.1f})")

            if actual_improvement > 0:
                improved_lecture = revised_lecture
                previous_score = final_evaluation.overall_score
                quality_improved = True

                # Update word count stats
                total_words = improved_lecture.total_word_count
                total_diagrams = sum(len(s.diagrams) for s in improved_lecture.sections)
            else:
                console.print(f"   ⚠️  Revision did not improve quality. Stopping.")
                break

            iteration += 1

        # Regenerate HTML if improved
        if quality_improved:
            console.print(f"   🎨 Regenerating HTML with improvements...")
            html_path = html_assembler.assemble(
                improved_lecture,
                output_path=output_stem,
                image_search_enabled=inputs.get("image_search", True),
            )
            lecture = improved_lecture

        progress.update(task5, description="[green]✅ Phase 5: Quality assurance done", advance=1)

        if iteration >= max_iterations:
            console.print(f"   ⚠️  Reached max iterations ({max_iterations})")

        if final_evaluation:
            console.print(f"   📊 Final quality score: {final_evaluation.overall_score:.1f}/100\n")

    # agent-evaluator 결과 최종 저장
    if _eval_monitor:
        import re as _re
        _topic_slug = _re.sub(r"[^a-zA-Z0-9가-힣_-]", "_", inputs.get("topic", "lecture"))[:40]
        _eval_filename = f"lecture_eval_{_topic_slug}"
        _eval_monitor.save_to_file(_eval_filename)
        console.print(
            f"\n[bold cyan]📊 agent-evaluator 결과 저장됨:[/bold cyan] "
            f"{eval_output_dir}/{_eval_filename}.json"
        )

    # Get token usage summary
    token_usage = tracker.get_summary()

    return {
        "html_path": html_path,
        "vector_db_path": str(content_agent.vector_store.db_path),
        "sections_count": len(lecture.sections),
        "total_words": lecture.total_word_count,
        "code_blocks": sum(len(s.code_blocks) for s in lecture.sections),
        "diagrams": sum(len(s.diagrams) for s in lecture.sections),
        "images": sum(len(s.images) for s in lecture.sections),
        "quality_score": final_evaluation.overall_score if final_evaluation else 0,
        "quality_iterations": iteration,
        "token_usage": token_usage,
    }





@click.command()
@click.option("--config", "-c", type=click.Path(exists=True, dir_okay=False), help="Configuration YAML file with lecture parameters")
@click.option("--interactive", "-i", is_flag=True, help="Enable interactive Q&A mode during generation")
@click.option(
    "--image-search/--no-image-search", default=True, help="Enable image search from web sources (Pexels, default: enabled)"
)
@click.option(
    "--quality-level",
    type=click.Choice(["lenient", "balanced", "strict"]),
    default="balanced",
    help="Quality threshold: lenient(70), balanced(80), strict(90)",
    show_default=True,
)
@click.option("--output", "-o", type=str, help="Output file name without extension (auto-generated if not provided)")
@click.option(
    "--eval",
    "eval_output_dir",
    type=str,
    default=None,
    help="agent-evaluator 평가 결과 저장 디렉터리 (예: eval_results/). 지정 시 Gate A–G 계측 활성화",
)
@click.option(
    "--include-pdf-images/--no-include-pdf-images",
    default=True,
    help="Extract images from PDFs with location-based matching (default: enabled since v0.2.0)",
    show_default=True,
)
@click.option(
    "--auto-describe-images/--no-auto-describe-images",
    default=True,
    help="Automatically generate descriptions for PDF images using Vision LLM (GPT-4o / Ollama Vision, only if --include-pdf-images is enabled)",
    show_default=True,
)
@click.option(
    "--async-mode",
    is_flag=True,
    help="🚀 Use async I/O for faster content collection (70% speedup, experimental)",
)
@click.option(
    "--existing-kb",
    type=click.Path(exists=True),
    default=None,
    help="Path to an existing knowledge base directory to reuse or extend",
)
@click.option(
    "--kb-mode",
    type=click.Choice(["reuse_only", "extend"]),
    default="reuse_only",
    show_default=True,
    help="How to use --existing-kb: reuse_only (read-only) or extend (add new sources)",
)
def create(
    config: Optional[str],
    interactive: bool,
    image_search: bool,
    quality_level: str,
    output: Optional[str],
    eval_output_dir: Optional[str],
    include_pdf_images: bool,
    auto_describe_images: bool,
    async_mode: bool,
    existing_kb: Optional[str],
    kb_mode: str,
) -> None:
    """
    Create a new lecture material from various sources.

    Generate comprehensive lecture materials using AI-powered multi-agent system.
    Supports PDF files, URLs, web searches, and image collection.

    \b
    Input Sources:
      • PDF files (text extraction only by default)
      • Web URLs (automatic scraping)
      • Web search (via Serper API)
      • Image search (Pexels API - recommended for relevant images)

    \b
    Output:
      • HTML file with lecture content
      • Knowledge base (ChromaDB) for Q&A
      • Embedded code examples and diagrams
      • Token usage and cost estimate

    \b
    Examples:
      # Interactive mode (recommended for first use)
      $ lecture-forge create

      # From config file
      $ lecture-forge create -c my_lecture.yaml

      # With image search enabled
      $ lecture-forge create -c config.yaml --image-search

      # High quality threshold
      $ lecture-forge create --quality-level strict

      # Custom output name
      $ lecture-forge create -o "AI_Basics_2024"

      # Disable PDF images (faster, web images only)
      $ lecture-forge create --no-include-pdf-images

      # High quality with image search (recommended)
      $ lecture-forge create --quality-level strict --image-search

      # Reuse an existing knowledge base (read-only)
      $ lecture-forge create --existing-kb data/vector_db/MyLecture_20260219 --kb-mode reuse_only

      # Extend an existing knowledge base with new sources
      $ lecture-forge create --existing-kb data/vector_db/MyLecture_20260219 --kb-mode extend

      # Enable agent-evaluator pipeline measurement (Gate A–G, v0.6.1+)
      $ lecture-forge create --eval eval_results/
      $ lecture-forge create -c config.yaml --eval eval_results/ --quality-level strict

    \b
    Agent-Evaluator (--eval, v0.6.1+):
      Opt-in pipeline quality measurement using the agent-evaluator framework.
      Records Gate A–G metrics (content coverage, curriculum coherence, RAG
      faithfulness, etc.) as JSON files in the specified directory.
      Requires: pip install "lecture-forge[eval]"  (or: pip install agent-evaluator)
      • Gate A: Content collection coverage
      • Gate B: Curriculum coherence
      • Gate C: RAG faithfulness (writer)
      • Gate D: Quality evaluation accuracy

    \b
    Config File Format (YAML):
      topic: "Introduction to Machine Learning"
      duration: 90
      audience_level: "intermediate"
      pdfs:
        - "ml_paper.pdf"
        - "tutorial.pdf"
      urls:
        - "https://example.com/ml-guide"
      keywords:
        - "machine learning basics"
        - "supervised learning"

    \b
    Quality Levels:
      • lenient  (70): Fast, accepts lower quality
      • balanced (80): Recommended, good quality
      • strict   (90): High quality, may take longer

    \b
    Cost:
      Typical 60-min lecture: ~$0.035 (using GPT-4o-mini, actual measured)
        • Text generation: ~$0.03
        • Embeddings & RAG: ~$0.005
        • Image search (Pexels/Unsplash): Free
        • PDF image extraction: Enabled by default (Location-based matching, v0.2.0+)
      Execution time: 3-5 minutes (sync), 1-2 minutes (async mode)
    """
    print_banner()

    console.print("\n[bold]Starting lecture generation...[/bold]\n")

    # Check if async mode is requested
    if async_mode:
        console.print("   [cyan]🚀 Async I/O mode enabled (experimental)[/cyan]")
        console.print("   [dim]Expected speedup: ~70% faster content collection[/dim]\n")
        # Run async version
        import asyncio
        asyncio.run(
            _create_async(
                config=config,
                interactive=interactive,
                image_search=image_search,
                quality_level=quality_level,
                output=output,
                include_pdf_images=include_pdf_images,
                auto_describe_images=auto_describe_images,
                existing_kb=existing_kb,
                kb_mode=kb_mode,
            )
        )
        return

    # Sync version (existing code continues below)

    # Collect inputs
    if config:
        console.print(f"Loading configuration from: {config}")

        # Load from YAML config file
        import yaml

        try:
            with open(config, "r", encoding="utf-8") as f:
                inputs = yaml.safe_load(f)

            # Validate required fields
            required_fields = ["topic", "duration", "audience_level"]
            missing_fields = [f for f in required_fields if f not in inputs]

            if missing_fields:
                console.print(f"[red]❌ Error: Missing required fields in config: {', '.join(missing_fields)}[/red]\n")
                console.print("[yellow]Required fields: topic, duration, audience_level[/yellow]\n")
                sys.exit(1)

            # Set defaults for optional fields
            inputs.setdefault("pdfs", [])
            inputs.setdefault("urls", [])
            inputs.setdefault("keywords", [])
            inputs.setdefault("hada_keywords", [])
            inputs.setdefault("image_keywords", [])

            console.print("[green]✓ Configuration loaded successfully[/green]\n")
            console.print(f"[cyan]Topic:[/cyan] {inputs['topic']}")
            console.print(f"[cyan]Duration:[/cyan] {inputs['duration']} minutes")
            console.print(f"[cyan]Audience:[/cyan] {inputs['audience_level']}\n")

        except yaml.YAMLError as e:
            console.print(f"[red]❌ Error parsing YAML config: {e}[/red]\n")
            sys.exit(1)
        except FileNotFoundError:
            console.print(f"[red]❌ Config file not found: {config}[/red]\n")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]❌ Error loading config: {e}[/red]\n")
            sys.exit(1)
    else:
        inputs = collect_inputs_interactive()

    # Apply settings
    inputs["interactive_mode"] = interactive
    inputs["image_search"] = image_search
    inputs["quality_level"] = quality_level
    inputs["output_name"] = output
    inputs["include_pdf_images"] = include_pdf_images
    inputs["auto_describe_images"] = auto_describe_images
    inputs["existing_kb_path"] = existing_kb if existing_kb else inputs.get("existing_kb_path")
    inputs["kb_mode"] = kb_mode if existing_kb else inputs.get("kb_mode", "new")

    # Generate lecture
    try:
        result = generate_lecture(inputs, eval_output_dir=eval_output_dir)

        console.print("\n[bold green]✅ Lecture generated successfully![/bold green]\n")
        console.print(f"📄 [bold]HTML File:[/bold] {result['html_path']}")
        console.print(f"🗄️  [bold]Knowledge Base:[/bold] {result['vector_db_path']}")
        console.print(f"\n📊 [bold]Statistics:[/bold]")
        console.print(f"   • Sections: {result['sections_count']}")
        console.print(f"   • Words: {result['total_words']:,}")
        console.print(f"   • Code blocks: {result['code_blocks']}")
        console.print(f"   • Diagrams: {result['diagrams']}")
        console.print(f"   • Images: {result['images']}")

        # Display quality metrics
        if "quality_score" in result and result["quality_score"] > 0:
            score = result["quality_score"]
            color = "green" if score >= 80 else "yellow" if score >= 60 else "red"
            console.print(f"   • Quality score: [{color}]{score:.1f}/100[/{color}]")

            if "quality_iterations" in result:
                iterations = result["quality_iterations"]
                if iterations > 0:
                    console.print(f"   • Quality improvements: {iterations} iteration(s)")

        # Display token usage and cost estimate
        if "token_usage" in result:
            display_token_usage(result["token_usage"])

        console.print(f"\n[dim]💡 Open the HTML file in a browser to view the lecture![/dim]\n")

    except Exception as e:
        console.print(f"\n[bold red]❌ Error during generation: {e}[/bold red]")
        logger.exception("Lecture generation failed")
        sys.exit(1)
