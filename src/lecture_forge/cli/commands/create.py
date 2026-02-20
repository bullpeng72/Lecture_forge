"""
Create command - Generate lecture materials from various sources.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import yaml
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from lecture_forge.agents.content_analyzer import ContentAnalyzerAgent
from lecture_forge.agents.content_collector import ContentCollectorAgent
from lecture_forge.agents.content_writer import ContentWriterAgent
from lecture_forge.agents.curriculum_designer import CurriculumDesignerAgent
from lecture_forge.agents.diagram_generator import DiagramGeneratorAgent
from lecture_forge.agents.html_assembler import HTMLAssemblerAgent
from lecture_forge.agents.image_collector import ImageCollectorAgent
from lecture_forge.agents.quality_evaluator import QualityEvaluatorAgent
from lecture_forge.agents.revision_agent import RevisionAgent
from lecture_forge.cli.commands.create_async import _create_async  # Async version
from lecture_forge.cli.utils import (
    collect_inputs_interactive,
    console,
    display_token_usage,
    print_banner,
)
from lecture_forge.config import Config
from lecture_forge.models.lecture import Lecture
from lecture_forge.utils import logger
from lecture_forge.utils.token_tracker import get_tracker


def parse_html_to_lecture(html_path: str) -> Optional['Lecture']:
    """
    Parse HTML file back to Lecture object.

    Args:
        html_path: Path to HTML file

    Returns:
        Lecture object or None if parsing fails
    """
    from bs4 import BeautifulSoup
    from lecture_forge.models.lecture import Lecture, SectionContent, CodeBlock, MermaidDiagram

    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, "html.parser")

        # Extract metadata
        title = soup.find("h1")
        title_text = title.get_text() if title else "Untitled Lecture"

        # Extract learning objectives
        objectives_div = soup.find("div", class_="bg-blue-50")
        objectives = []
        if objectives_div:
            obj_items = objectives_div.find_all("li")
            objectives = [item.get_text() for item in obj_items]

        # Extract sections
        sections = []
        for section_elem in soup.find_all("section", id=True):
            section_id = section_elem.get("id")

            # Get section title
            h2 = section_elem.find("h2")
            if not h2:
                continue

            section_title = h2.get_text()
            # Remove section number (e.g., "1. Title" -> "Title")
            if ". " in section_title:
                section_title = section_title.split(". ", 1)[1]

            # Get content (all text except code blocks and diagrams)
            content_parts = []
            for elem in section_elem.find_all(["p", "h3", "ul", "ol"]):
                content_parts.append(elem.get_text())

            markdown_content = "\n\n".join(content_parts)

            # Extract code blocks
            code_blocks = []
            for pre in section_elem.find_all("pre"):
                code = pre.find("code")
                if code:
                    code_blocks.append(CodeBlock(language="python", code=code.get_text(), caption=None))

            # Extract diagrams
            diagrams = []
            for i, mermaid_div in enumerate(section_elem.find_all("div", class_="mermaid")):
                diagrams.append(
                    MermaidDiagram(
                        id=f"{section_id}_diagram_{i}",
                        title=f"Diagram {i + 1}",
                        mermaid_code=mermaid_div.get_text().strip(),
                        diagram_type="flowchart",
                    )
                )

            section = SectionContent(
                section_id=section_id,
                title=section_title,
                markdown_content=markdown_content,
                code_blocks=code_blocks,
                images=[],
                diagrams=diagrams,
                word_count=len(markdown_content.split()),
            )

            sections.append(section)

        # Create lecture object
        lecture = Lecture(
            title=title_text,
            topic=title_text,
            duration=180,  # Default
            audience_level="intermediate",  # Default
            learning_objectives=objectives,
            sections=sections,
            total_word_count=sum(s.word_count for s in sections),
            total_images=0,
            total_diagrams=sum(len(s.diagrams) for s in sections),
        )

        return lecture

    except Exception as e:
        logger.error(f"Failed to parse HTML: {e}")
        return None


def generate_lecture(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate lecture using the multi-agent pipeline.

    Args:
        inputs: Dictionary with lecture parameters

    Returns:
        Dictionary with generation results
    """
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

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Phase 1: Content Collection
        task1 = progress.add_task("[cyan]📚 Phase 1: Collecting content...", total=None)

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
                progress.update(task1, completed=True)
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
                progress.update(task1, completed=True)
                total_after = content_agent.vector_store.get_stats()["document_count"]
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
            progress.update(task1, completed=True)
            console.print(
                f"   ✅ Content collected: {content_result['metadata']['total_docs']} docs, "
                f"{content_result['metadata']['total_chunks']} chunks"
            )

        # Phase 2: Image Collection
        task2 = progress.add_task("[cyan]🖼️  Phase 2: Collecting images...", total=None)
        image_agent = ImageCollectorAgent(
            session_id=collection_name, vector_store=content_agent.vector_store  # Share vector store for RAG integration
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
            f"   ✅ Analysis complete: {len(analysis_result.key_topics)} topics, " f"{len(analysis_result.entities)} entities"
        )

        # Phase 3b: Curriculum Design
        task3b = progress.add_task("[cyan]📋 Phase 3b: Designing curriculum...", total=None)
        designer = CurriculumDesignerAgent(vector_store=content_agent.vector_store)
        curriculum = designer.design(
            analysis_result=analysis_result,
            topic=inputs["topic"],
            duration=inputs["duration"],
            audience_level=inputs["audience_level"],
        )
        progress.update(task3b, completed=True)
        console.print(
            f"   ✅ Curriculum designed: {len(curriculum.sections)} sections, " f"{curriculum.total_estimated_time} min"
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
        total_words = sum(s.word_count for s in section_contents)
        total_code_blocks = sum(len(s.code_blocks) for s in section_contents)
        console.print(
            f"   ✅ Content written: {len(section_contents)} sections, "
            f"{total_words} words, {total_code_blocks} code blocks"
        )

        # Phase 4b: Diagram Generation
        task4b = progress.add_task("[cyan]📊 Phase 4b: Generating diagrams...", total=None)
        diagram_gen = DiagramGeneratorAgent()
        section_contents = diagram_gen.generate_diagrams(section_contents)
        progress.update(task4b, completed=True)
        total_diagrams = sum(len(s.diagrams) for s in section_contents)
        console.print(f"   ✅ Diagrams generated: {total_diagrams}")

        # Phase 4c: HTML Assembly
        task4c = progress.add_task("[cyan]🎨 Phase 4c: Assembling HTML...", total=None)
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
            output_path=inputs.get("output_name"),
            image_search_enabled=inputs.get("image_search", True),
        )
        progress.update(task4c, completed=True)
        console.print(f"   ✅ HTML assembled: {html_path}")

        # Phase 5: Quality Assurance (optional but enabled by default)
        quality_threshold = {"lenient": 70, "balanced": 80, "strict": 90}.get(inputs.get("quality_level", "balanced"), 80)
        max_iterations = Config.MAX_ITERATIONS

        # Import quality agents
        from lecture_forge.agents.quality_evaluator import QualityEvaluatorAgent
        from lecture_forge.agents.revision_agent import RevisionAgent

        with_code = inputs.get("with_code", False)
        evaluator = QualityEvaluatorAgent(with_code=with_code)
        revision_agent = RevisionAgent(with_code=with_code)

        task5 = progress.add_task(f"[cyan]✅ Phase 5: Quality assurance (threshold: {quality_threshold})...", total=None)

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
                output_path=inputs.get("output_name"),
                image_search_enabled=inputs.get("image_search", True),
            )
            lecture = improved_lecture

        progress.update(task5, completed=True)

        if iteration >= max_iterations:
            console.print(f"   ⚠️  Reached max iterations ({max_iterations})")

        if final_evaluation:
            console.print(f"   📊 Final quality score: {final_evaluation.overall_score:.1f}/100\n")

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
@click.option("--config", "-c", type=click.Path(exists=True), help="Configuration YAML file with lecture parameters")
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
    "--include-pdf-images/--no-include-pdf-images",
    default=True,
    help="Extract images from PDFs with location-based matching (default: enabled since v0.2.0)",
    show_default=True,
)
@click.option(
    "--auto-describe-images/--no-auto-describe-images",
    default=True,
    help="Automatically generate descriptions for PDF images using GPT-4o-mini (only if --include-pdf-images is enabled)",
    show_default=True,
)
@click.option(
    "--async-mode",
    is_flag=True,
    help="🚀 Use async I/O for faster content collection (70% speedup, experimental)",
)
@click.option(
    "--with-code",
    is_flag=True,
    default=False,
    help="Include code examples in lecture content (default: excluded)",
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
    include_pdf_images: bool,
    auto_describe_images: bool,
    async_mode: bool,
    with_code: bool,
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

      # Include code examples in lecture
      $ lecture-forge create --with-code

      # Reuse an existing knowledge base (read-only)
      $ lecture-forge create --existing-kb data/vector_db/MyLecture_20260219 --kb-mode reuse_only

      # Extend an existing knowledge base with new sources
      $ lecture-forge create --existing-kb data/vector_db/MyLecture_20260219 --kb-mode extend

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
      with_code: false

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
                with_code=with_code,
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
    inputs["with_code"] = with_code
    inputs["existing_kb_path"] = existing_kb if existing_kb else inputs.get("existing_kb_path")
    inputs["kb_mode"] = kb_mode if existing_kb else inputs.get("kb_mode", "new")

    # Generate lecture
    try:
        result = generate_lecture(inputs)

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
