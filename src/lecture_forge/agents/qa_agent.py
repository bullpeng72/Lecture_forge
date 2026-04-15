"""
Q&A Agent - Answers questions using knowledge base.
"""

import datetime
from pathlib import Path
from typing import Dict

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style as PromptStyle
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from lecture_forge.agents.base import BaseAgent
from lecture_forge.config import Config
from lecture_forge.constants import QAConfig
from lecture_forge.knowledge.vector_store import VectorStore
from lecture_forge.utils import detect_language, get_language_name, logger, translate_to_english, translate_to_korean


class QAAgent(BaseAgent):
    """Agent for answering questions using RAG."""

    def __init__(self, knowledge_base_path: str):
        # Lower temperature for RAG: prioritise factual accuracy over creativity
        super().__init__(temperature=0.3)
        self.knowledge_base_path = Path(knowledge_base_path)

        # Load vector store
        collection_name = self.knowledge_base_path.name
        self.vector_store = VectorStore(collection_name=collection_name)

        logger.info(f"Initializing Q&A Agent with KB: {knowledge_base_path}")

        # Setup prompt session with history and auto-suggest
        lf_dir = Config.USER_CONFIG_DIR
        lf_dir.mkdir(parents=True, exist_ok=True)
        self.conversation_log_path = lf_dir / "conversation_log.txt"
        self._session_header_written = False

        self.prompt_session = PromptSession(
            history=InMemoryHistory(),
            auto_suggest=AutoSuggestFromHistory(),  # Suggest previous questions
            enable_history_search=True,  # Ctrl+R to search history
            multiline=False,  # Single-line input
            vi_mode=False,  # Emacs-style editing (Ctrl+A, Ctrl+E, etc.)
        )

        # Prompt style for colored prompt
        self.prompt_style = PromptStyle.from_dict(
            {
                "prompt": "cyan bold",
            }
        )

    def answer(self, question: str, enable_translation: bool = True) -> Dict:
        """
        Answer a question using the knowledge base with multilingual support.

        Args:
            question: User question
            enable_translation: Enable Dual Query with translation (default: True)

        Returns:
            Answer with sources and language info
        """
        logger.info(f"Answering question: {question}")

        # 1. Detect query language
        query_language = detect_language(question, default="unknown")
        logger.info(f"Detected query language: {get_language_name(query_language)}")

        # 2. Dual Query: Original + Translated
        try:
            # Query 1: Original language
            results_original = self.vector_store.query(question, n_results=Config.RAG_QA_N_RESULTS)

            # Query 2: Translated (if enabled and language is known)
            results_translated = None
            translated_query = None

            if enable_translation and query_language in ["ko", "en"]:
                # Translate to opposite language
                if query_language == "ko":
                    translated_query = translate_to_english(question)
                    logger.info(f"[Translation] English query: {translated_query}")
                elif query_language == "en":
                    translated_query = translate_to_korean(question)
                    logger.info(f"[Translation] Korean query: {translated_query}")

                if translated_query and translated_query != question:
                    results_translated = self.vector_store.query(translated_query, n_results=Config.RAG_QA_N_RESULTS)

            # 3. Merge and re-rank results
            merged_results = self._merge_and_rerank(
                question=question,
                query_language=query_language,
                results_original=results_original,
                results_translated=results_translated,
                top_k=Config.RAG_QA_TOP_K,
            )

            if not merged_results:
                return {
                    "answer": "죄송합니다. 관련 정보를 찾을 수 없습니다.",
                    "sources": [],
                    "confidence": 0.0,
                    "query_language": query_language,
                }

            # 4. Build context from merged results
            contexts = [r["document"] for r in merged_results]
            metadatas = [r["metadata"] for r in merged_results]
            scores = [r["score"] for r in merged_results]

            # Format context with source, page, relevance info
            formatted_contexts = []
            for i, (ctx, meta, score) in enumerate(zip(contexts, metadatas, scores), 1):
                source = meta.get("source", "Unknown")
                page = meta.get("page_number")
                lang = get_language_name(meta.get("language", "unknown"))
                relevance_pct = int(min(score, 1.0) * 100)
                source_info = f"{source} (page {page})" if page else source

                formatted_ctx = (
                    f"[Context {i} | Source: {source_info} | Lang: {lang} | Relevance: {relevance_pct}%]\n"
                    f"{ctx}"
                )
                formatted_contexts.append(formatted_ctx)

            context_text = "\n\n---\n\n".join(formatted_contexts)

            # 5. Generate answer (in query language)
            answer_language = "한국어" if query_language == "ko" else "English"

            num_contexts = len(merged_results)
            min_refs = min(num_contexts, QAConfig.MIN_CONTEXT_REFS)

            # Comprehensive, structured answer prompt with explicit length / format requirements
            prompt = f"""You are an expert educational assistant. Produce a **comprehensive, well-structured answer** in {answer_language} using the provided context.

## Question
{question}

## Context ({num_contexts} chunks, ordered by relevance)
{context_text}

## Mandatory Answer Requirements

**Length:** Write at least **{QAConfig.MIN_ANSWER_WORDS} words**. Depth and completeness are more important than brevity.

**Structure — use Markdown headings and lists:**
1. `## 개요` (or `## Overview`) — 2–3 sentence summary of the direct answer
2. `## 상세 설명` (or `## Detailed Explanation`) — thorough explanation of mechanisms, background, reasoning
3. `## 핵심 포인트` (or `## Key Points`) — bulleted or numbered list of the most important facts
4. `## 예시 및 근거` (or `## Examples & Evidence`) — concrete examples, data, or cases from the context
5. `## 추가 고려사항` (or `## Additional Notes`) — related concepts, caveats, or implications (omit if context has nothing relevant)

**Coverage:** Reference information from at least {min_refs} different context chunks. Synthesise across chunks — do not rely on just the first one.

**Rules:**
- Use ONLY information from the provided context
- Do NOT add external knowledge or speculation
- If a section cannot be filled from context, write one sentence explaining what is missing

## Answer"""

            # 6. Generate answer
            response = self.invoke_llm(prompt, phase="qa")
            answer = response.content.strip()

            # 6.5. Post-process and validate answer
            answer = self._post_process_answer(answer, question, contexts, query_language)

            # 7. Extract sources with language info
            sources = []
            for metadata in metadatas:
                if metadata:
                    source_info = metadata.get("source", "Unknown")
                    source_lang = metadata.get("language", "unknown")
                    page_num = metadata.get("page_number")

                    # Format source info
                    if page_num:
                        source_str = f"{source_info} (page {page_num}, {get_language_name(source_lang)})"
                    else:
                        source_str = f"{source_info} ({get_language_name(source_lang)})"

                    sources.append(source_str)

            # Calculate confidence based on result quality
            confidence = self._calculate_confidence(merged_results, answer)

            return {
                "answer": answer,
                "sources": list(dict.fromkeys(sources))[:QAConfig.MAX_SOURCES_RETURNED],
                "confidence": confidence,
                "query_language": query_language,
                "translated_query": translated_query,
                "num_results": len(merged_results),
            }

        except Exception as e:
            logger.error(f"Error answering question: {e}")
            return {
                "answer": f"답변 중 오류가 발생했습니다: {str(e)}",
                "sources": [],
                "confidence": 0.0,
                "query_language": query_language,
            }

    def _merge_and_rerank(
        self,
        question: str,
        query_language: str,
        results_original: Dict,
        results_translated: Dict = None,
        top_k: int = 5,
    ) -> list:
        """
        Merge and re-rank results from original and translated queries.

        Args:
            question: Original question
            query_language: Detected language of the query
            results_original: Results from original query
            results_translated: Results from translated query (optional)
            top_k: Number of top results to return

        Returns:
            List of re-ranked results
        """
        all_results = []
        seen_chunks = set()

        # Process original query results
        if results_original and results_original.get("documents"):
            documents = results_original["documents"][0]
            metadatas = results_original.get("metadatas", [[]])[0]
            distances = results_original.get("distances", [[]])[0]

            for doc, metadata, distance in zip(documents, metadatas, distances):
                if not metadata:
                    continue

                # Create unique chunk ID
                chunk_id = f"{metadata.get('source', '')}_{metadata.get('chunk_index', 0)}"

                if chunk_id in seen_chunks:
                    continue

                # Calculate similarity score (L2 distance → [0,1] similarity)
                # ChromaDB L2 distances are typically in [0, 2] for normalised embeddings
                similarity = max(0.0, 1 - distance / 2)

                # Language matching bonus
                chunk_language = metadata.get("language", "unknown")
                if query_language == chunk_language:
                    similarity += QAConfig.SAME_LANG_BONUS  # 10% bonus for same language

                all_results.append(
                    {
                        "document": doc,
                        "metadata": metadata,
                        "score": similarity,
                        "source_query": "original",
                        "chunk_language": chunk_language,
                    }
                )
                seen_chunks.add(chunk_id)

        # Process translated query results (if available)
        if results_translated and results_translated.get("documents"):
            documents = results_translated["documents"][0]
            metadatas = results_translated.get("metadatas", [[]])[0]
            distances = results_translated.get("distances", [[]])[0]

            for doc, metadata, distance in zip(documents, metadatas, distances):
                if not metadata:
                    continue

                # Create unique chunk ID
                chunk_id = f"{metadata.get('source', '')}_{metadata.get('chunk_index', 0)}"

                if chunk_id in seen_chunks:
                    continue  # Skip duplicates

                # Calculate similarity score (L2 distance → [0,1] similarity)
                similarity = max(0.0, 1 - distance / 2)

                # Small penalty for translated query (-5%)
                similarity -= QAConfig.TRANSLATED_PENALTY

                # Language matching bonus (for different language)
                chunk_language = metadata.get("language", "unknown")
                if query_language != chunk_language and chunk_language in ["ko", "en"]:
                    similarity += QAConfig.CROSS_LINGUAL_BONUS  # 5% bonus for cross-lingual match

                all_results.append(
                    {
                        "document": doc,
                        "metadata": metadata,
                        "score": similarity,
                        "source_query": "translated",
                        "chunk_language": chunk_language,
                    }
                )
                seen_chunks.add(chunk_id)

        # Filter low-quality results (similarity threshold)
        filtered_results = [r for r in all_results if r["score"] >= Config.RAG_SIMILARITY_THRESHOLD]

        if not filtered_results:
            # If all results are filtered out, keep top N anyway
            filtered_results = all_results[:Config.RAG_MIN_FALLBACK_RESULTS]
            logger.warning(
                f"All results below similarity threshold ({Config.RAG_SIMILARITY_THRESHOLD}), "
                f"keeping top {Config.RAG_MIN_FALLBACK_RESULTS}"
            )

        # Sort by score (descending)
        filtered_results.sort(key=lambda x: x["score"], reverse=True)

        # Apply diversity-aware selection
        top_results = self._diversity_selection(filtered_results, top_k)

        logger.info(
            f"Re-ranked {len(all_results)} results → Top {len(top_results)} selected "
            f"(Original: {sum(1 for r in top_results if r['source_query'] == 'original')}, "
            f"Translated: {sum(1 for r in top_results if r['source_query'] == 'translated')})"
        )

        return top_results

    def _diversity_selection(self, ranked_results: list, top_k: int) -> list:
        """
        Select top-k results with diversity consideration.

        Ensures results come from different sources/pages when possible
        to provide comprehensive answers.

        Args:
            ranked_results: Results sorted by score
            top_k: Number of results to select

        Returns:
            Diversified top-k results
        """
        if len(ranked_results) <= top_k:
            return ranked_results

        selected = []
        source_page_count = {}  # Track how many chunks from each source-page

        for result in ranked_results:
            if len(selected) >= top_k:
                break

            # Create source-page key
            metadata = result["metadata"]
            source = metadata.get("source", "unknown")
            page = metadata.get("page_number", "none")
            source_page_key = f"{source}_{page}"

            # Diversity penalty: prefer different source-pages
            current_count = source_page_count.get(source_page_key, 0)

            # Allow up to N chunks from the same source-page (dense topics need more coverage)
            if current_count < Config.RAG_MAX_CHUNKS_PER_SOURCE_PAGE:
                selected.append(result)
                source_page_count[source_page_key] = current_count + 1

        # If we didn't get enough diverse results, fill with remaining high-scoring ones
        if len(selected) < top_k:
            for result in ranked_results:
                if result not in selected and len(selected) < top_k:
                    selected.append(result)

        return selected

    def _calculate_confidence(self, merged_results: list, answer: str) -> float:
        """
        Calculate confidence score based on search results and answer quality.

        Args:
            merged_results: Ranked search results
            answer: Generated answer

        Returns:
            Confidence score (0.0 to 1.0)
        """
        if not merged_results:
            return 0.0

        # Base confidence on top result's score
        top_score = merged_results[0]["score"]

        # Adjust based on number of results
        num_results = len(merged_results)
        result_factor = min(num_results / 12.0, 1.0)  # More results = higher confidence (up to 12)

        # Adjust based on answer length (short answers indicate incomplete response)
        answer_length = len(answer)
        if answer_length < 100:
            length_factor = 0.5
        elif answer_length < 200:
            length_factor = 0.7
        elif answer_length < 400:
            length_factor = 0.85
        else:
            length_factor = 1.0

        # Check if answer indicates uncertainty
        uncertainty_phrases = [
            "don't know", "not sure", "unclear", "cannot find",
            "모르겠", "불확실", "찾을 수 없", "알 수 없"
        ]
        has_uncertainty = any(phrase in answer.lower() for phrase in uncertainty_phrases)
        uncertainty_factor = 0.6 if has_uncertainty else 1.0

        # Calculate final confidence
        confidence = top_score * result_factor * length_factor * uncertainty_factor

        # Clamp between 0.0 and 1.0
        confidence = max(0.0, min(1.0, confidence))

        logger.debug(
            f"Confidence: {confidence:.2f} "
            f"(top_score={top_score:.2f}, results={num_results}, "
            f"length_factor={length_factor:.2f}, uncertainty={uncertainty_factor:.2f})"
        )

        return confidence

    def _post_process_answer(self, answer: str, question: str, contexts: list, query_language: str) -> str:
        """
        Post-process and validate the answer quality.

        Args:
            answer: Generated answer
            question: Original question
            contexts: Retrieved context chunks
            query_language: Detected language

        Returns:
            Improved answer
        """
        # Check if answer is too short (likely incomplete)
        if len(answer.strip()) < 200:
            logger.warning(f"Answer too short ({len(answer)} chars), attempting to expand")
            return self._expand_short_answer(answer, question, contexts, query_language)

        # Check if answer indicates lack of information
        no_info_phrases_ko = ["모르겠습니다", "정보가 없습니다", "찾을 수 없습니다", "알 수 없습니다"]
        no_info_phrases_en = ["don't know", "no information", "cannot find", "not available"]

        no_info_phrases = no_info_phrases_ko if query_language == "ko" else no_info_phrases_en

        if any(phrase in answer.lower() for phrase in no_info_phrases):
            # Answer claims no information, but we have contexts
            # Try to guide LLM to extract partial information
            if len(contexts) > 0:
                logger.info("Answer claims no info, attempting to extract partial information")
                return self._extract_partial_info(question, contexts, query_language)

        # RMC: Self-review answer for hallucinations before returning
        answer = self._review_answer_with_rmc(answer, question, contexts, query_language)

        return answer

    def _review_answer_with_rmc(
        self,
        answer: str,
        question: str,
        contexts: list,
        query_language: str,
    ) -> str:
        """
        RMC (Reflective Meta-Cognition) self-review of generated Q&A answer.

        Layer 1: Identify claims not grounded in the provided context (hallucination risk).
        Layer 2: Re-examine to avoid false positives (removing correct content).
        Returns a cleaned answer, or the original if review fails or the result is too short.
        """
        original_word_count = len(answer.split())
        answer_language = "한국어" if query_language == "ko" else "English"

        # Format up to 5 context snippets (200 chars each) for the prompt
        context_snippets = []
        for i, ctx in enumerate(contexts[:5], 1):
            # Defensive: ctx may be a dict or a str
            if isinstance(ctx, dict):
                text = str(ctx.get("document", ctx))
            else:
                text = str(ctx)
            context_snippets.append(f"[Source {i}]: {text[:200]}")
        context_summary = "\n".join(context_snippets) if context_snippets else "(no context available)"

        # Slice answer to avoid token overload
        answer_slice = answer[:2000] if len(answer) > 2000 else answer

        prompt = f"""You are a strict factual accuracy reviewer for an educational Q&A system.

## Question
{question}

## Available Source Context (summaries)
{context_summary}

## Answer to Review
{answer_slice}

---

## Layer 1 — Grounding Check:
For each major claim in the answer, classify it as:
  ✓ — Clearly supported by the source context above
  ~ — Reasonably inferable from the source context
  ✗ — Not found in the source context (hallucination risk)

List each ✗ item explicitly.

## Layer 2 — Review of the Review:
- Did you incorrectly mark any factually correct, widely-known information as ✗?
- Did you let through any genuinely unsupported claims as ✓ or ~?
- Confirm: only mark ✗ if the claim is truly absent from the context AND could mislead learners.

---

## Instructions:
- Output the answer in {answer_language} with only ✗ items removed or marked as:
  "(강의 자료에서 직접 확인되지 않은 내용입니다)" if Korean, or
  "(This was not directly confirmed in the lecture materials)" if English
- If no ✗ items are found, output the answer UNCHANGED.
- Do NOT add preamble, explanation, or meta-commentary — just output the corrected answer.

## Corrected Answer:"""

        try:
            response = self.invoke_llm(prompt, phase="qa_rmc_review")
            revised = response.content.strip()

            # Validate: revised must be at least 50% of original word count
            # (hallucination removal may legitimately reduce length)
            revised_word_count = len(revised.split())
            min_words = int(original_word_count * 0.5)

            if revised_word_count < min_words:
                logger.warning(
                    f"RMC answer review returned too-short result "
                    f"({revised_word_count} < {min_words} words) — using original"
                )
                return answer

            logger.info(
                f"RMC answer review applied: {original_word_count} → {revised_word_count} words"
            )
            return revised

        except Exception as e:
            logger.warning(f"RMC answer review failed (returning original): {e}")
            return answer

    def _expand_short_answer(self, short_answer: str, question: str, contexts: list, query_language: str) -> str:
        """Expand a too-short answer."""
        answer_language = "한국어" if query_language == "ko" else "English"
        context_text = "\n\n---\n\n".join(contexts[:5])  # Use top 5 contexts

        expansion_prompt = f"""The following answer is too short. Rewrite it as a detailed, structured response of **at least 400 words** using all relevant information from the context.

## Question
{question}

## Incomplete Answer (to expand)
{short_answer}

## Available Context
{context_text}

## Rewrite Instructions
- Language: {answer_language}
- Minimum 400 words
- Use Markdown headings (##) to organise into sections: Overview, Detailed Explanation, Key Points, Examples
- Extract and synthesise information from ALL context chunks above
- Do NOT add information not present in the context

## Expanded Answer"""

        try:
            response = self.invoke_llm(expansion_prompt, phase="qa")
            expanded = response.content.strip()
            if len(expanded) > len(short_answer):
                logger.info(f"Answer expanded from {len(short_answer)} to {len(expanded)} chars")
                return expanded
        except Exception as e:
            logger.error(f"Failed to expand answer: {e}")

        return short_answer

    def _extract_partial_info(self, question: str, contexts: list, query_language: str) -> str:
        """Extract partial information when direct answer is not available."""
        answer_language = "한국어" if query_language == "ko" else "English"
        context_text = "\n\n---\n\n".join(contexts[:5])

        partial_prompt = f"""The context may not directly answer the question, but it likely contains related information.

**Question:** {question}

**Context:**
{context_text}

**Task:**
Extract any relevant information that helps address the question, even if partial:
1. Look for related concepts, definitions, or explanations
2. Identify any examples or cases that relate to the question
3. Provide what information IS available, clearly stating what is covered
4. Be honest about what information is NOT available in the context
5. Answer in {answer_language}

**Format:**
Based on the available context, here's what I can tell you:
[relevant information]

However, the context does not directly address: [missing aspects]

**Response:**"""

        try:
            response = self.invoke_llm(partial_prompt, phase="qa")
            return response.content.strip()
        except Exception as e:
            logger.error(f"Failed to extract partial info: {e}")
            if query_language == "ko":
                return "죄송합니다. 제공된 컨텍스트에서 관련 정보를 찾을 수 없습니다."
            else:
                return "I'm sorry, but I cannot find relevant information in the provided context."

    def _log_session_end(self, question_count: int) -> None:
        """Write session end marker to conversation log (only if any exchange was logged)."""
        if not self._session_header_written:
            return
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.conversation_log_path, "a", encoding="utf-8") as f:
                f.write(f"\n--- Session End: {timestamp} | Questions: {question_count} ---\n")
        except Exception as e:
            logger.warning(f"Failed to write session end to conversation log: {e}")

    def _log_exchange(self, question: str, result: Dict) -> None:
        """Append a Q&A exchange to the conversation log (creates file on first real question)."""
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if not self._session_header_written:
                with open(self.conversation_log_path, "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*60}\n")
                    f.write(f"Session Start: {timestamp}\n")
                    f.write(f"Knowledge Base: {self.knowledge_base_path.name}\n")
                    f.write(f"{'='*60}\n")
                self._session_header_written = True
            confidence = result.get("confidence", 0.0)
            confidence_pct = confidence * 100
            if confidence >= 0.8:
                confidence_label = "High"
            elif confidence >= 0.5:
                confidence_label = "Medium"
            else:
                confidence_label = "Low"

            with open(self.conversation_log_path, "a", encoding="utf-8") as f:
                f.write(f"\n[{timestamp}] You:\n{question}\n\n")
                f.write(f"[{timestamp}] Assistant ({confidence_label} {confidence_pct:.0f}%):\n")
                f.write(result["answer"])
                f.write("\n")
                sources = result.get("sources", [])
                if sources:
                    f.write("\nSources:\n")
                    for source in sources:
                        f.write(f"  - {source}\n")
                f.write("\n" + "-" * 40 + "\n")
        except Exception as e:
            logger.warning(f"Failed to write exchange to conversation log: {e}")

    def start_chat(self) -> None:
        """Start interactive chat mode."""
        logger.info("Starting Q&A chat mode")

        console = Console()

        # Display welcome banner
        welcome = Panel(
            "[bold]💬 Q&A Chat Mode[/bold] [green](Multilingual Support Enabled)[/green]\n\n"
            f"[cyan]Knowledge Base:[/cyan] {self.knowledge_base_path.name}\n\n"
            "[dim]Features:[/dim]\n"
            "  • [bold]🌐 Multilingual Search:[/bold] Ask in Korean or English\n"
            "  • [bold]🔍 Cross-lingual Retrieval:[/bold] Find relevant info in any language\n"
            "  • [bold]⌨️  Enhanced Input:[/bold] History (↑/↓), auto-suggest, full Korean support\n\n"
            "[dim]Available commands:[/dim]\n"
            "  • [bold]/help[/bold] - Show help\n"
            "  • [bold]/exit[/bold] or [bold]/quit[/bold] - Exit chat mode\n"
            "  • [bold]Ctrl+C[/bold] - Quick exit\n"
            "  • [bold]Ctrl+R[/bold] - Search history\n\n"
            "[dim]Just type your question to start![/dim]",
            title="🤖 LectureForge Q&A",
            border_style="blue",
        )
        console.print(welcome)

        question_count = 0

        while True:
            try:
                # Get user question with enhanced input support
                # Uses prompt_toolkit for better Korean input and editing
                console.print()  # Add blank line before prompt
                question = self.prompt_session.prompt(
                    [("class:prompt", "You: ")],
                    style=self.prompt_style,
                )

                # Check for commands
                if question.lower() in ["/exit", "/quit"]:
                    self._log_session_end(question_count)
                    self._show_goodbye(console, question_count)
                    break

                if question.lower() in ["/help", "help", "?"]:
                    self._show_help(console)
                    continue

                if not question.strip():
                    continue

                # Increment question counter
                question_count += 1

                # Get answer with spinner
                with console.status("[bold green]🔍 Searching knowledge base...[/bold green]"):
                    result = self.answer(question)

                # Display translation info if available
                if result.get("translated_query"):
                    query_lang = get_language_name(result.get("query_language", "unknown"))
                    console.print(f"\n[dim]🌐 Detected language: {query_lang}[/dim]")
                    console.print(f"[dim]🔄 Cross-lingual search enabled[/dim]")

                # Display answer with Markdown rendering inside a panel
                answer_md = Markdown(result["answer"])
                console.print(
                    Panel(
                        answer_md,
                        title="[bold yellow]Assistant[/bold yellow]",
                        border_style="yellow",
                        padding=(1, 2),
                    )
                )

                # Display confidence score
                confidence = result.get("confidence", 0.0)
                confidence_pct = confidence * 100

                if confidence >= 0.8:
                    confidence_color = "green"
                    confidence_label = "High"
                elif confidence >= 0.5:
                    confidence_color = "yellow"
                    confidence_label = "Medium"
                else:
                    confidence_color = "red"
                    confidence_label = "Low"

                console.print(
                    f"[dim]🎯 Confidence:[/dim] [{confidence_color}]{confidence_label} ({confidence_pct:.0f}%)[/{confidence_color}]"
                )

                # Display sources if available
                if result["sources"]:
                    console.print("\n[dim]📚 Sources:[/dim]")
                    for source in result["sources"]:
                        console.print(f"  • [dim]{source}[/dim]")

                    # Display search stats
                    num_results = result.get("num_results", 0)
                    if num_results > 0:
                        console.print(f"\n[dim]📊 Retrieved {num_results} relevant chunks[/dim]")
                    console.print()

                # Persist Q&A exchange to conversation log
                self._log_exchange(question, result)

            except KeyboardInterrupt:
                console.print("\n")
                self._log_session_end(question_count)
                self._show_goodbye(console, question_count)
                break
            except Exception as e:
                console.print(f"\n[red]❌ Error: {e}[/red]\n")
                logger.exception("Chat error")

    def _show_help(self, console):
        """Show help message."""
        help_table = Table(title="📖 Q&A Chat Commands", show_header=True, header_style="bold magenta")
        help_table.add_column("Command", style="cyan", width=20)
        help_table.add_column("Description", style="white")

        help_table.add_row("/help, help, ?", "Show this help message")
        help_table.add_row("/exit, /quit", "Exit Q&A mode")
        help_table.add_row("Ctrl+C", "Quick exit (force quit)")
        help_table.add_row("<question>", "Ask any question about the lecture content")

        console.print("\n")
        console.print(help_table)
        console.print("\n[dim]⌨️  Input Features:[/dim]")
        console.print("  • [bold]Korean/English input:[/bold] Full support for multilingual typing")
        console.print("  • [bold]History:[/bold] Use ↑/↓ arrows to navigate previous questions")
        console.print("  • [bold]Auto-suggest:[/bold] Type to see suggestions from history (→ to accept)")
        console.print("  • [bold]Search history:[/bold] Press Ctrl+R to search previous questions")
        console.print("  • [bold]Editing:[/bold] Full support for backspace, delete, left/right arrows")
        console.print("\n[dim]💡 Tips for Better Answers:[/dim]")
        console.print("  • [bold]Be specific[/bold] in your questions for better answers")
        console.print("  • [bold]Ask follow-up questions[/bold] to get more details")
        console.print("  • [bold]Multilingual:[/bold] Ask in Korean or English - cross-lingual search works automatically")
        console.print("  • [bold]Confidence scores:[/bold] High (80%+) = Very reliable, Medium (50-80%) = Useful, Low (<50%) = Limited info")
        console.print("  • [bold]Sources:[/bold] Check sources to verify information and see original language")
        console.print("  • [bold]Retrieval count:[/bold] More chunks retrieved = more comprehensive answer")
        console.print("\n[dim]🎯 Quality Features (v0.3.2+):[/dim]")
        console.print("  • Enhanced prompts with Chain of Thought reasoning")
        console.print("  • Diversity-aware result selection (max 2 chunks per source-page)")
        console.print("  • Automatic answer expansion for incomplete responses")
        console.print("  • Partial information extraction when direct answer unavailable")
        console.print("  • Dynamic confidence scoring based on result quality")
        console.print()

    def _show_goodbye(self, console, question_count):
        """Show goodbye message."""
        console.print("\n" + "─" * 50)
        console.print("[bold green]✅ Q&A Session Complete[/bold green]")
        console.print("─" * 50)
        console.print(f"📊 Questions asked: {question_count}")
        console.print(f"📚 Knowledge base: {self.knowledge_base_path.name}")
        console.print("\n[cyan]Thank you for using LectureForge Q&A![/cyan]")
        console.print("[dim]Run 'lecture-forge chat' to start another session or delete knowledge bases[/dim]\n")
