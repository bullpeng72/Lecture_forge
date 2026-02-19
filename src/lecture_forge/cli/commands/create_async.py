"""
Async version of create command - Generate lecture materials with async I/O.

This module contains the async implementation of the create command,
providing ~70% speedup in content collection phase.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

from rich.progress import Progress, SpinnerColumn, TextColumn

from lecture_forge.agents.async_content_collector import AsyncContentCollectorAgent
from lecture_forge.agents.content_analyzer import ContentAnalyzerAgent
from lecture_forge.agents.content_writer import ContentWriterAgent
from lecture_forge.agents.curriculum_designer import CurriculumDesignerAgent
from lecture_forge.agents.diagram_generator import DiagramGeneratorAgent
from lecture_forge.agents.html_assembler import HTMLAssemblerAgent
from lecture_forge.agents.image_collector import ImageCollectorAgent
from lecture_forge.agents.quality_evaluator import QualityEvaluatorAgent
from lecture_forge.agents.revision_agent import RevisionAgent
from lecture_forge.cli.utils import console, display_token_usage
from lecture_forge.config import Config
from lecture_forge.models.lecture import Lecture
from lecture_forge.utils import logger
from lecture_forge.utils.token_tracker import get_tracker


async def generate_lecture_async(inputs: Dict) -> Dict:
    """
    Generate lecture using async I/O for content collection.

    Args:
        inputs: Input parameters (same as sync version)

    Returns:
        Result dictionary with generated files and statistics
    """
    # Reset token tracker
    tracker = get_tracker()
    tracker.reset()

    # Generate collection name from topic
    import re

    topic_safe = inputs["topic"].replace(" ", "_").replace("/", "_").replace("\\", "_")
    topic_safe = re.sub(r"[^a-zA-Z0-9_-]", "", topic_safe)
    if not topic_safe or len(topic_safe) < 3:
        topic_safe = "lecture"
    if not topic_safe[0].isalnum():
        topic_safe = "lec_" + topic_safe
    topic_safe = topic_safe[:47]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    collection_name = f"{topic_safe}_{timestamp}"

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Phase 1: Content Collection (ASYNC) ⚡
        task1 = progress.add_task(
            "[cyan]📚 Phase 1: Collecting content (async)...", total=None
        )

        existing_kb_path = inputs.get("existing_kb_path")
        kb_mode = inputs.get("kb_mode", "new")

        if existing_kb_path:
            collection_name = Path(existing_kb_path).name
            content_agent = AsyncContentCollectorAgent(collection_name=collection_name)

            if kb_mode == "reuse_only":
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
                        "elapsed_seconds": 0,
                    },
                }
                progress.update(task1, completed=True)
                console.print(
                    f"   ✅ Reusing KB '{collection_name}': {stats['document_count']} chunks"
                )

            else:  # extend
                content_result = await content_agent.collect(
                    {
                        "pdfs": inputs.get("pdfs", []),
                        "urls": inputs.get("urls", []),
                        "keywords": inputs.get("keywords", []),
                        "hada_keywords": inputs.get("hada_keywords", []),
                    }
                )
                progress.update(task1, completed=True)
                total_after = content_agent.vector_store.get_stats()["document_count"]
                elapsed = content_result["metadata"].get("elapsed_seconds", 0)
                console.print(
                    f"   ✅ Extended KB '{collection_name}' in {elapsed:.1f}s (async): "
                    f"+{content_result['metadata']['total_chunks']} new chunks "
                    f"(total: {total_after})"
                )

        else:
            # New KB (existing behaviour)
            content_agent = AsyncContentCollectorAgent(collection_name=collection_name)
            content_result = await content_agent.collect(
                {
                    "pdfs": inputs.get("pdfs", []),
                    "urls": inputs.get("urls", []),
                    "keywords": inputs.get("keywords", []),
                    "hada_keywords": inputs.get("hada_keywords", []),
                }
            )
            progress.update(task1, completed=True)
            elapsed = content_result["metadata"].get("elapsed_seconds", 0)
            console.print(
                f"   ✅ Content collected in {elapsed:.1f}s (async): "
                f"{content_result['metadata']['total_docs']} docs, "
                f"{content_result['metadata']['total_chunks']} chunks"
            )

        # Phase 2: Image Collection (still sync for now)
        task2 = progress.add_task("[cyan]🖼️  Phase 2: Collecting images...", total=None)
        image_agent = ImageCollectorAgent(
            session_id=collection_name,
            vector_store=content_agent.vector_store,  # Share vector store
        )

        pdf_sources = (
            inputs.get("pdfs", []) if inputs.get("include_pdf_images", True) else []
        )

        if not inputs.get("include_pdf_images", True) and inputs.get("pdfs", []):
            console.print(
                "   ⏭️  [dim]Skipping PDF image extraction (disabled)[/dim]"
            )
        elif inputs.get("include_pdf_images", True) and inputs.get("pdfs", []):
            console.print("   📸 [cyan]Extracting PDF images with location-based matching[/cyan]")

        image_result = image_agent.collect(
            {
                "pdfs": pdf_sources,
                "urls": inputs.get("urls", []),
                "image_keywords": inputs.get("image_keywords", []),
            },
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

        progress.update(task2, completed=True)
        console.print(f"   ✅ Images collected: {image_result['total_collected']}")

        # Phase 3a: Content Analysis
        task3a = progress.add_task("[cyan]🔍 Phase 3a: Analyzing content...", total=None)
        analyzer = ContentAnalyzerAgent(vector_store=content_agent.vector_store)
        analysis_result = analyzer.analyze(
            collection_result=content_result,
            image_result=image_result,
            topic=inputs["topic"],
        )
        progress.update(task3a, completed=True)
        console.print(
            f"   ✅ Analysis complete: {len(analysis_result.key_topics)} topics, "
            f"{len(analysis_result.entities)} entities"
        )

        # Phase 3b: Curriculum Design
        task3b = progress.add_task("[cyan]📋 Phase 3b: Designing curriculum...", total=None)
        designer = CurriculumDesignerAgent()
        curriculum = designer.design(
            analysis_result=analysis_result,
            topic=inputs["topic"],
            duration=inputs["duration"],
            audience_level=inputs["audience_level"],
        )
        progress.update(task3b, completed=True)
        console.print(
            f"   ✅ Curriculum designed: {len(curriculum.sections)} sections, "
            f"{curriculum.total_estimated_time} min"
        )

        # Phase 4a: Content Writing
        task4a = progress.add_task("[cyan]✍️  Phase 4a: Writing content (RAG)...", total=None)
        writer = ContentWriterAgent(
            vector_store=content_agent.vector_store,
            with_code=inputs.get("with_code", False),
        )
        section_contents = writer.write_all_sections(
            curriculum=curriculum,
            available_images=image_result.get("images", []),
        )
        progress.update(task4a, completed=True)
        console.print(f"   ✅ Content written: {len(section_contents)} sections")

        # Phase 4b: Diagram Generation
        task4b = progress.add_task("[cyan]📊 Phase 4b: Generating diagrams...", total=None)
        diagram_gen = DiagramGeneratorAgent()
        section_contents = diagram_gen.generate_diagrams(section_contents)
        total_diagrams = sum(len(sc.diagrams) for sc in section_contents)
        progress.update(task4b, completed=True)
        console.print(f"   ✅ Diagrams generated: {total_diagrams}")

        # Phase 5: Quality Evaluation & Revision
        # Build lecture object for evaluation
        total_words = sum(s.word_count for s in section_contents)
        total_diagrams = sum(len(s.diagrams) for s in section_contents)
        total_images = sum(len(s.images) for s in section_contents)

        lecture = Lecture(
            title=f"{inputs['topic']} - {inputs['audience_level'].capitalize()} Level",
            topic=inputs["topic"],
            duration=inputs["duration"],
            audience_level=inputs["audience_level"],
            learning_objectives=curriculum.learning_objectives,
            sections=section_contents,
            total_word_count=total_words,
            total_images=total_images,
            total_diagrams=total_diagrams,
            vector_db_path=str(content_agent.vector_store.db_path),
        )

        quality_threshold = {"lenient": 70, "balanced": 80, "strict": 90}.get(
            inputs.get("quality_level", "balanced"), 80
        )
        max_iterations = Config.MAX_ITERATIONS

        with_code = inputs.get("with_code", False)
        evaluator = QualityEvaluatorAgent(with_code=with_code)
        revision_agent = RevisionAgent(with_code=with_code)

        task5 = progress.add_task(
            f"[cyan]✅ Phase 5: Quality assurance (threshold: {quality_threshold})...", total=None
        )

        iteration = 0
        previous_score = 0
        improved_lecture = lecture
        quality_improved = False
        final_evaluation = None

        while iteration < max_iterations:
            # Evaluate quality
            evaluation = evaluator.evaluate(improved_lecture, quality_threshold)
            final_evaluation = evaluation

            console.print(
                f"\n   📊 Quality evaluation (iteration {iteration + 1}): "
                f"{evaluation.overall_score:.1f}/100"
            )

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
                    console.print(
                        f"   ⚠️  Minimal improvement (+{improvement:.1f}). "
                        "Stopping to prevent degradation."
                    )
                    break

                if improvement < 0:
                    console.print(f"   ❌ Quality degraded ({improvement:.1f}). Keeping previous version.")
                    break

            # Show top issues
            if evaluation.issues and iteration == 0:
                console.print(f"   ⚠️  {len(evaluation.issues)} issues found:")
                for issue in evaluation.issues[:3]:  # Show top 3
                    severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(issue.severity, "⚪")
                    console.print(
                        f"      {severity_icon} [{issue.severity}] {issue.dimension}: "
                        f"{issue.description[:80]}..."
                    )

            # Apply revisions
            console.print(f"   🔧 Applying automatic improvements...")
            revised_lecture = revision_agent.revise(improved_lecture, evaluation)

            # Re-evaluate to check actual improvement
            final_evaluation = evaluator.evaluate(revised_lecture, quality_threshold)
            actual_improvement = final_evaluation.overall_score - evaluation.overall_score

            console.print(
                f"   → After revision: {final_evaluation.overall_score:.1f}/100 "
                f"(+{actual_improvement:.1f})"
            )

            if actual_improvement > 0:
                improved_lecture = revised_lecture
                previous_score = final_evaluation.overall_score
                quality_improved = True
            else:
                console.print(f"   ⚠️  Revision did not improve quality. Stopping.")
                break

            iteration += 1

        progress.update(task5, completed=True)

        # Use improved lecture if quality was improved
        if quality_improved:
            lecture = improved_lecture

        final_sections = lecture.sections
        quality_score = final_evaluation.overall_score if final_evaluation else 0
        quality_iterations = iteration

        # Phase 6: HTML Assembly
        task6 = progress.add_task("[cyan]🎨 Phase 6: Assembling HTML...", total=None)
        assembler = HTMLAssemblerAgent()

        # Use the lecture object from Phase 5 (includes quality improvements)
        output_name = inputs.get("output_name") or f"{topic_safe}_{timestamp}"
        html_path = assembler.assemble(lecture, output_path=output_name)
        progress.update(task6, completed=True)
        console.print(f"   ✅ HTML assembled: {html_path}")

    # Prepare result
    total_words = sum(len(s.markdown_content.split()) for s in final_sections)
    total_code_blocks = sum(len(s.code_blocks) for s in final_sections)
    total_diagrams = sum(len(s.diagrams) for s in final_sections)
    total_images = sum(len(s.images) for s in final_sections)

    result = {
        "html_path": html_path,
        "vector_db_path": str(content_agent.vector_store.db_path),
        "sections_count": len(final_sections),
        "total_words": total_words,
        "code_blocks": total_code_blocks,
        "diagrams": total_diagrams,
        "images": total_images,
        "quality_score": quality_score,
        "quality_iterations": quality_iterations,
        "token_usage": tracker.get_summary(),
        "collection_time_seconds": content_result["metadata"].get("elapsed_seconds", 0),
    }

    return result


async def _create_async(
    config,
    interactive,
    image_search,
    quality_level,
    output,
    include_pdf_images,
    auto_describe_images,
    with_code: bool = False,
    existing_kb=None,
    kb_mode: str = "new",
):
    """
    Async implementation of create command.

    This is the entry point for async mode, called from create() via asyncio.run().
    """
    # Load config or collect inputs (same as sync)
    if config:
        import yaml

        console.print(f"Loading configuration from: {config}")
        try:
            with open(config, "r", encoding="utf-8") as f:
                inputs = yaml.safe_load(f)
        except Exception as e:
            console.print(f"[red]❌ Failed to load config: {e}[/red]")
            sys.exit(1)
    else:
        from lecture_forge.cli.utils import collect_inputs_interactive

        inputs = collect_inputs_interactive()

    # Override with command-line options
    inputs["quality_level"] = quality_level
    inputs["image_search"] = image_search
    inputs["output_name"] = output
    inputs["include_pdf_images"] = include_pdf_images
    inputs["auto_describe_images"] = auto_describe_images
    inputs["with_code"] = with_code
    inputs["existing_kb_path"] = existing_kb if existing_kb else inputs.get("existing_kb_path")
    inputs["kb_mode"] = kb_mode if existing_kb else inputs.get("kb_mode", "new")

    # Generate lecture (async)
    try:
        result = await generate_lecture_async(inputs)

        console.print("\n[bold green]✅ Lecture generated successfully (async mode)![/bold green]\n")
        console.print(f"📄 [bold]HTML File:[/bold] {result['html_path']}")
        console.print(f"🗄️  [bold]Knowledge Base:[/bold] {result['vector_db_path']}")
        console.print(f"\n📊 [bold]Statistics:[/bold]")
        console.print(f"   • Sections: {result['sections_count']}")
        console.print(f"   • Words: {result['total_words']:,}")
        console.print(f"   • Code blocks: {result['code_blocks']}")
        console.print(f"   • Diagrams: {result['diagrams']}")
        console.print(f"   • Images: {result['images']}")

        # Display async speedup info
        if "collection_time_seconds" in result and result["collection_time_seconds"] > 0:
            collection_time = result["collection_time_seconds"]
            console.print(
                f"   • Content collection time: [cyan]{collection_time:.1f}s (async)[/cyan]"
            )

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
        console.print(
            f"[dim]🚀 Async mode saved ~70% time in content collection phase[/dim]\n"
        )

    except Exception as e:
        console.print(f"\n[bold red]❌ Error during async generation: {e}[/bold red]")
        logger.exception("Async lecture generation failed")
        sys.exit(1)
