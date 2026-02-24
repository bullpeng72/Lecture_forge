# Agents API Reference

Complete reference for all agents in the LectureForge multi-agent system (10 task agents + 1 async variant).

## Table of Contents

1. [Overview](#overview)
2. [Base Agent](#base-agent)
   - [BaseAgent](#baseagent)
   - [AsyncBaseAgent](#asyncbaseagent) (v0.3.4+)
3. [Content Collection](#content-collection)
   - [ContentCollectorAgent](#contentcollectoragent)
   - [AsyncContentCollectorAgent](#asynccontentcollectoragent) (v0.3.4+)
   - [ImageCollectorAgent](#imagecollectoragent)
4. [Content Analysis](#content-analysis)
   - [ContentAnalyzerAgent](#contentanalyzeragent)
   - [CurriculumDesignerAgent](#curriculumdesigneragent)
5. [Content Generation](#content-generation)
   - [ContentWriterAgent](#contentwriteragent)
   - [DiagramGeneratorAgent](#diagramgeneratoragent)
   - [HTMLAssemblerAgent](#htmlassembleragent)
6. [Quality Assurance](#quality-assurance)
   - [QualityEvaluator](#qualityevaluatoragent)
   - [RevisionAgent](#revisionagent)
7. [Interactive Q&A](#interactive-qa)
   - [QAAgent](#qaagent)

---

## Overview

The LectureForge agent system follows a **multi-agent pipeline pattern** where each agent has a specific responsibility in the lecture generation workflow.

### Agent Hierarchy

```
BaseAgent (abstract)
├── ContentCollectorAgent
├── ImageCollectorAgent
├── ContentAnalyzerAgent
├── CurriculumDesignerAgent
├── ContentWriterAgent (refactored into 4 components)
├── DiagramGeneratorAgent
├── HTMLAssemblerAgent
├── QualityEvaluator  (alias: QualityEvaluatorAgent)
├── RevisionAgent
└── QAAgent

AsyncBaseAgent (abstract, v0.3.4+)
└── AsyncContentCollectorAgent (70% faster)
```

### Common Patterns

All agents inherit from `BaseAgent` and follow these patterns:

- **Initialization**: `__init__(self, ...)`
- **Main Method**: Primary entry point (e.g., `collect()`, `write_section()`)
- **LLM Integration**: Access to OpenAI client via `self.llm`
- **Logging**: Structured logging via `logger`

---

## Base Agent

### BaseAgent

**Location**: `lecture_forge/agents/base.py`

Abstract base class for all agents.

```python
from lecture_forge.agents.base import BaseAgent

class MyCustomAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        # Custom initialization
```

**Attributes:**
- `llm`: OpenAI LLM client (ChatOpenAI instance)
- `embedding_model`: Embedding model name (default: "text-embedding-3-small")

**Methods:**
- `__init__(self) -> None`: Initialize base agent with LLM client

### AsyncBaseAgent

**Location**: `lecture_forge/agents/async_base.py` (v0.3.4+)

Abstract base class for async agents with parallel I/O support.

```python
from lecture_forge.agents.async_base import AsyncBaseAgent

class MyAsyncAgent(AsyncBaseAgent):
    def __init__(self, max_workers=None):
        super().__init__(max_workers=max_workers)
        # Custom initialization

    async def my_async_method(self):
        # Use helper methods
        result = await self.run_in_executor(cpu_bound_func, args)
        results = await self.gather_with_concurrency(tasks, max_concurrent=5)
```

**Attributes:**
- `executor`: ThreadPoolExecutor for CPU-bound tasks
- `_rate_limiters`: Dictionary of rate limiters per service

**Methods:**
- `__init__(self, max_workers: Optional[int] = None) -> None`: Initialize with thread pool
- `run_in_executor(func, *args, **kwargs) -> Any`: Run CPU-bound function in thread pool
- `gather_with_concurrency(tasks, max_concurrent) -> List[Any]`: Run tasks with concurrency limit
- `retry_async(func, max_retries=3) -> Any`: Retry async function with exponential backoff

**Usage Pattern:**
```python
# Parallel I/O operations
tasks = [self._fetch_url(url) for url in urls]
results = await self.gather_with_concurrency(tasks, max_concurrent=5)

# CPU-bound operations (PDF parsing)
result = await self.run_in_executor(parse_pdf, pdf_path)
```

---

## Content Collection

### ContentCollectorAgent

**Location**: `lecture_forge/agents/content_collector.py`

Collects text content from PDFs, URLs, and web searches, then stores in vector DB.

#### Initialization

```python
from lecture_forge.agents.content_collector import ContentCollectorAgent

agent = ContentCollectorAgent(collection_name="my_lecture_20260215")
```

**Parameters:**
- `collection_name` (str): Name for ChromaDB collection

**Attributes:**
- `vector_store` (VectorStore): ChromaDB vector store instance
- `collection_name` (str): Collection name

#### Main Method

```python
result = agent.collect(sources: Dict[str, Any]) -> Dict[str, Any]
```

**Parameters:**
- `sources` (dict): Dictionary containing:
  - `pdfs` (List[str]): List of PDF file paths
  - `urls` (List[str]): List of URLs to scrape
  - `keywords` (List[str]): Search keywords
  - `hada_keywords` (List[str]): Additional keywords

**Returns:**
Dictionary with:
- `success` (bool): Success status
- `vector_store` (VectorStore): Initialized vector store
- `metadata` (dict): Collection statistics
  - `total_docs` (int): Number of documents
  - `total_chunks` (int): Number of text chunks
  - `sources` (dict): Source breakdown

**Example:**

```python
agent = ContentCollectorAgent("ml_lecture_001")

result = agent.collect({
    "pdfs": ["ml_textbook.pdf"],
    "urls": ["https://example.com/ml-tutorial"],
    "keywords": ["machine learning", "neural networks"],
    "hada_keywords": []
})

print(f"Collected {result['metadata']['total_chunks']} chunks")
# Output: Collected 245 chunks
```

### AsyncContentCollectorAgent

**Location**: `lecture_forge/agents/async_content_collector.py` (v0.3.4+)

Async version of ContentCollectorAgent with **70% performance improvement** through parallel I/O.

#### Initialization

```python
from lecture_forge.agents.async_content_collector import AsyncContentCollectorAgent

agent = AsyncContentCollectorAgent(collection_name="my_lecture_20260216")
```

**Parameters:**
- `collection_name` (str): Name for ChromaDB collection
- `max_workers` (int, optional): Max thread pool workers (default: None = auto)

#### Main Method: `collect()`

```python
async def collect(sources: Dict[str, List[str]]) -> Dict[str, Any]
```

**Parameters:**
- `sources["pdfs"]` (List[str]): PDF file paths
- `sources["urls"]` (List[str]): Web URLs
- `sources["keywords"]` (List[str]): Search keywords
- `sources["hada_keywords"]` (List[str]): Hada.io keywords

**Returns:**
Dictionary with:
- `success` (bool): Operation success
- `documents` (List[Document]): Collected documents
- `metadata` (Dict): Stats including `elapsed_seconds`

#### Usage Example

```python
import asyncio
from lecture_forge.agents.async_content_collector import AsyncContentCollectorAgent

async def main():
    agent = AsyncContentCollectorAgent(collection_name="ai_basics")

    # Collect from multiple sources in parallel
    result = await agent.collect({
        "pdfs": ["book1.pdf", "book2.pdf", "book3.pdf"],
        "urls": ["https://site1.com", "https://site2.com"],
        "keywords": ["machine learning", "deep learning"],
        "hada_keywords": [],
    })

    print(f"Collected in {result['metadata']['elapsed_seconds']:.1f}s")
    print(f"Total: {result['metadata']['total_docs']} docs")

asyncio.run(main())
# Output: Collected in 8.2s (vs 28s sync = 70% faster)
```

**Performance:**
- Single source: Same as sync (~no benefit)
- Multiple sources: **70% faster** through parallel execution
- Example: 3 PDFs + 5 URLs: sync 80s → async 24s

**CLI Usage:**
```bash
lecture-forge create --async-mode  # Enable async collection
```

---

### ImageCollectorAgent

**Location**: `lecture_forge/agents/image_collector.py`

Collects images from PDFs, URLs, and image search APIs (Pexels/Unsplash).

#### Initialization

```python
from lecture_forge.agents.image_collector import ImageCollectorAgent

agent = ImageCollectorAgent(
    session_id="ml_lecture_001",
    vector_store=vector_store  # Optional: share vector store
)
```

**Parameters:**
- `session_id` (str): Session identifier for image directory
- `vector_store` (VectorStore, optional): Vector store for RAG integration

#### Main Method

```python
result = agent.collect(
    sources: Dict[str, Any],
    auto_describe_images: bool = True
) -> Dict[str, Any]
```

**Parameters:**
- `sources` (dict): Dictionary containing:
  - `pdfs` (List[str]): PDF files for image extraction
  - `urls` (List[str]): URLs for image extraction
  - `image_keywords` (List[str]): Keywords for image search
- `auto_describe_images` (bool): Auto-generate descriptions with GPT-4o

**Returns:**
Dictionary with:
- `images` (List[dict]): List of collected images
- `total_collected` (int): Total images collected
- `image_dir` (Path): Directory where images are saved
- `metadata` (dict): Collection statistics

**Example:**

```python
agent = ImageCollectorAgent(session_id="ml_001")

result = agent.collect(
    sources={
        "pdfs": ["ml_book.pdf"],
        "urls": [],
        "image_keywords": ["neural network diagram", "ml workflow"]
    },
    auto_describe_images=True
)

print(f"Collected {result['total_collected']} images")
```

---

## Content Analysis

### ContentAnalyzerAgent

**Location**: `lecture_forge/agents/content_analyzer.py`

Analyzes collected content to extract key topics, entities, and difficulty level.

#### Initialization

```python
from lecture_forge.agents.content_analyzer import ContentAnalyzerAgent

agent = ContentAnalyzerAgent(vector_store=vector_store)
```

#### Main Method

```python
analysis = agent.analyze(
    collection_result: Dict[str, Any],
    image_result: Dict[str, Any],
    topic: str
) -> AnalysisResult
```

**Returns:**
`AnalysisResult` object with:
- `key_topics` (List[str]): Extracted main topics
- `entities` (List[str]): Named entities
- `difficulty_level` (str): Estimated difficulty
- `summary` (str): Content summary

---

### CurriculumDesignerAgent

**Location**: `lecture_forge/agents/curriculum_designer.py`

Designs lecture curriculum structure with sections and time allocation.

#### Main Method

```python
curriculum = agent.design(
    analysis_result: AnalysisResult,
    topic: str,
    duration: int,
    audience_level: str
) -> Curriculum
```

**Returns:**
`Curriculum` object with:
- `sections` (List[Section]): List of lecture sections
- `duration` (int): Total duration in minutes
- `audience_level` (str): Target audience level

#### RMC Self-Review (v0.3.8)

After generating the `Curriculum`, `design()` automatically calls `_review_with_rmc()`:

```python
# Internal — called automatically by design()
curriculum = agent._review_with_rmc(curriculum, analysis_result)
```

**Layer 1 — Curriculum Review:**
1. Difficulty progression (simpler → complex)
2. Time consistency (section sum ≈ total duration)
3. Objective coverage (each learning objective → at least one section)
4. Redundancy (overlapping or too-broad sections)
5. Prerequisite order (foundational topics placed first)

**Layer 2 — Review of the Review:**
- Calibrated for target audience level?
- Over-correction? Good curriculum already sound?

**Returned JSON → applied if valid:**
- `section_reorder`: Re-sorts `curriculum.sections` list
- `revised_objectives`: Replaces `curriculum.learning_objectives`
- `no_changes: true`: Skips all modifications

**Failure mode**: try/except — returns original `Curriculum` unmodified.

---

## Content Generation

### ContentWriterAgent

**Location**: `lecture_forge/agents/content_writer/` (refactored)

Writes lecture content using RAG with modular components.

#### Structure

The ContentWriterAgent has been refactored into:
- **agent.py**: Main orchestrator (~1,170 lines, includes RMC self-review + structural section prompt)
- **image_selector.py**: Image selection logic (~970 lines, includes y0-spatial proximity sorting)
- **code_generator.py**: Code extraction/generation (~130 lines)
- **content_expander.py**: Quality improvement (~290 lines, includes token-aware trimming)

#### Initialization

```python
from lecture_forge.agents.content_writer import ContentWriterAgent

agent = ContentWriterAgent(vector_store=vector_store)
```

#### Main Method

```python
sections = agent.write_all_sections(
    curriculum: Curriculum,
    available_images: List[dict] = None
) -> List[SectionContent]
```

**Returns:**
List of `SectionContent` objects with:
- `markdown` (str): Generated markdown content
- `images` (List[ImageReference]): Selected images
- `code_blocks` (List[CodeBlock]): Code examples

#### Components

##### ImageSelector

Handles intelligent image selection:

```python
from lecture_forge.agents.content_writer.image_selector import ImageSelector

selector = ImageSelector(keyword_expander=expand_func)
images = selector.select_images(section, available_images, context_metadatas)
```

**Methods:**
- `select_images()`: Main selection with location-based matching
- `_evaluate_image_quality_simple()`: Quality scoring (threshold applied before bonuses)
- `_match_images_by_location()`: Page-based matching with y0 spatial proximity
- `_expand_to_adjacent_pages()`: Fallback to neighbouring pages

**Image Selection Improvements (v0.3.8)**:
- **Spatial proximity (y0-based sorting)**: Images within each page are sorted top-to-bottom using `y0` from `page.get_image_rects(xref)` (PyMuPDF). The position score `(1/(idx+1)) × 0.10` now reliably rewards images that appear higher on the page, matching them to the surrounding text content.
- **Intra-section dedup (P1 fix)**: A `selected_ids` set tracks all images chosen across the PDF, web, and keyword phases of `_select_images()`, preventing the same image from being placed twice within one section.
- **Per-type scoring weights (P2 fix)**: Separate Config constants for screenshot vs photo quality/importance weights (`IMAGE_WEIGHT_QUALITY_SCREENSHOT`, `IMAGE_WEIGHT_IMPORTANCE_SCREENSHOT`, etc.). Quality threshold is enforced before bonuses are applied.

##### CodeGenerator

Handles code extraction and generation:

```python
from lecture_forge.agents.content_writer.code_generator import CodeGenerator

generator = CodeGenerator(llm_client=llm, vector_store=vs)
code_blocks = generator.extract_code_blocks(markdown)
```

##### ContentExpander

Handles quality improvement:

```python
from lecture_forge.agents.content_writer.content_expander import ContentExpander

expander = ContentExpander(llm_client=llm, vector_store=vs)
improved = expander.expand_content(section, curriculum, content, contexts)
```

#### RMC Self-Review (v0.3.8)

After the initial LLM generation pass, `_generate_content()` automatically calls `_review_content_with_rmc()`:

```python
# Internal — called automatically after content generation
content = agent._review_content_with_rmc(content, section, curriculum, targets)
```

**Layer 1 — Educational Quality Review:**
1. Conceptual leaps (concepts appearing without prior explanation)
2. Explanation clarity (sentences too difficult for target audience)
3. Code-text connection (sufficient explanation before/after code blocks)
4. Flow breaks (logical gaps between subheadings)
5. Repetition (duplicate explanations)

**Layer 2 — Review of the Review:**
- Audience calibration (beginner/intermediate/advanced appropriate?)
- Severity check (is the issue actually disruptive?)
- Good content preservation (avoid unnecessary edits)

**Validation**: `revised_word_count >= original_word_count × 0.8` — else original is used (guards against LLM returning meta-evaluation instead of content).

**Failure mode**: try/except — returns original content string unmodified.

---

### DiagramGeneratorAgent

**Location**: `lecture_forge/agents/diagram_generator.py`

Generates Mermaid diagrams for lecture content.

#### Main Method

```python
diagrams = agent.generate_diagrams(
    section: Section,
    content: str
) -> List[MermaidDiagram]
```

---

### HTMLAssemblerAgent

**Location**: `lecture_forge/agents/html_assembler.py`

Assembles final HTML lecture from all components.

#### Main Method

```python
html_path = agent.assemble(
    lecture: Lecture,
    output_path: Path
) -> Path
```

---

## Quality Assurance

### QualityEvaluator

**Location**: `lecture_forge/quality/evaluator.py`

> **Note**: `QualityEvaluatorAgent` (from `lecture_forge.agents.quality_evaluator`) is a backward-compatible alias for this class.

Evaluates lecture quality across 6 dimensions.

#### Main Method

```python
evaluation = agent.evaluate(
    lecture: Lecture,
    curriculum: Curriculum
) -> QualityEvaluation
```

**Returns:**
`QualityEvaluation` with scores for:
- Completeness
- Flow
- Time allocation
- Difficulty match
- Visual aids
- Accuracy

---

### RevisionAgent

**Location**: `lecture_forge/agents/revision_agent.py`

Revises content based on quality evaluation.

#### Main Method

```python
revised = agent.revise(
    lecture: Lecture,
    evaluation: QualityEvaluation
) -> Lecture
```

---

## Interactive Q&A

### QAAgent

**Location**: `lecture_forge/agents/qa_agent.py`

Provides interactive Q&A using RAG with enhanced quality (v0.3.5).

#### Initialization

```python
from lecture_forge.agents.qa_agent import QAAgent

agent = QAAgent(knowledge_base_path="ml_lecture_001")
```

#### Main Method

```python
answer = agent.answer(
    question: str,
) -> Dict[str, Any]
```

**Returns:**
Dictionary with:
- `answer` (str): Generated answer (400+ words, 5 Markdown sections)
- `sources` (List[dict]): Source documents with pages
- `confidence` (float): Confidence score (0.0–1.0, correctly calculated)
- `query_language` (str): Detected language

**RAG Configuration (v0.3.5):**
- `n_results`: **15** per query (up from 10 in v0.3.2)
- `top_k`: **12** after reranking (up from 8)
- `temperature`: **0.3** (down from 0.7, for accuracy)
- Diversity limit: **3** chunks per source-page (up from 2)
- Confidence: `max(0.0, 1 - distance / 2)` (ChromaDB L2 fix)

**Enhanced Features (v0.3.5):**
- **400-word minimum**: Forces comprehensive structured answers
- **5 Mandatory sections**: 개요 / 상세 설명 / 핵심 포인트 / 예시 및 근거 / 추가 고려사항
- **Rich Markdown rendering**: Answers displayed in terminal Panel
- **15+15 dual-query**: Original + translated queries both use n_results=15
- Cross-lingual search (Korean ↔ English)
- Dynamic confidence scoring (fixed ChromaDB L2 distance conversion)
- Automatic answer expansion for short answers (< 200 chars)

#### RMC Self-Review (v0.3.8)

After `_post_process_answer()` completes, `_review_answer_with_rmc()` runs automatically:

```python
# Internal — called automatically before returning the final answer
answer = agent._review_answer_with_rmc(answer, question, contexts, query_language)
```

**Layer 1 — Grounding Verification:**

Each major claim is classified against source contexts (up to 5 snippets, 200 chars each):
- ✓ — Clearly supported in sources
- ~ — Reasonably inferable from sources
- ✗ — No source support (hallucination risk)

✗ items are either removed or marked with a language-appropriate disclaimer:
- Korean: `"(강의 자료에서 직접 확인되지 않은 내용입니다)"`
- English: `"(This information was not directly found in the lecture materials)"`

**Layer 2 — Review of the Review:**
- Avoid marking widely-known facts as ✗
- Avoid approving genuinely unsupported claims as ✓/~

**Validation**: `revised_word_count >= original_word_count × 0.5` — accepts shorter answers (hallucination removal legitimately reduces length). Falls back to original if threshold not met.

**Failure mode**: try/except — returns original answer string unmodified.

**Example:**

```python
agent = QAAgent("ml_lecture_001")

result = agent.answer("What is supervised learning?")

print(result["answer"])   # 400+ word structured answer
print(f"Confidence: {result['confidence']:.0%}")
print(f"Sources: {len(result['sources'])} documents")
```

---

## Usage Examples

### Complete Pipeline

```python
from lecture_forge.agents import *

# Step 1: Collect content
collector = ContentCollectorAgent("lecture_001")
content = collector.collect({
    "pdfs": ["book.pdf"],
    "urls": ["https://example.com"],
    "keywords": ["topic"]
})

# Step 2: Collect images
image_collector = ImageCollectorAgent("lecture_001", content["vector_store"])
images = image_collector.collect({"pdfs": ["book.pdf"]})

# Step 3: Analyze
analyzer = ContentAnalyzerAgent(content["vector_store"])
analysis = analyzer.analyze(content, images, "My Topic")

# Step 4: Design curriculum
designer = CurriculumDesignerAgent()
curriculum = designer.design(analysis, "My Topic", 60, "beginner")

# Step 5: Write content
writer = ContentWriterAgent(content["vector_store"])
sections = writer.write_all_sections(curriculum, images["images"])

# Step 6: Evaluate
from lecture_forge.quality.evaluator import QualityEvaluator

evaluator = QualityEvaluator()
evaluation = evaluator.evaluate(lecture, curriculum)

# Step 7: Revise if needed
if evaluation.overall_score < 80:
    revisor = RevisionAgent()
    lecture = revisor.revise(lecture, evaluation)

# Step 8: Assemble HTML
assembler = HTMLAssemblerAgent()
html_path = assembler.assemble(lecture, output_path)
```

---

## Best Practices

1. **Vector Store Sharing**: Share vector store between ContentCollector and ImageCollector for better integration
2. **Error Handling**: Wrap agent calls in try-except blocks
3. **Logging**: Enable logging to track agent execution
4. **Resource Cleanup**: Close vector stores when done
5. **API Limits**: Monitor token usage and API costs

---

**Last Updated**: 2026-02-24
**Version**: 0.4.2
