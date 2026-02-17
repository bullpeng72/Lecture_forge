"""
Content Writer Agent - Orchestrates lecture content generation with RAG.

This is the refactored version with extracted components:
- ImageSelector: Handles image selection logic
- CodeGenerator: Handles code extraction and generation
- ContentExpander: Handles content expansion
"""

from pathlib import Path
from typing import List

from lecture_forge.agents.base import BaseAgent
from lecture_forge.agents.content_writer.code_generator import CodeGenerator
from lecture_forge.agents.content_writer.content_expander import ContentExpander
from lecture_forge.agents.content_writer.image_selector import ImageSelector
from lecture_forge.config import Config
from lecture_forge.knowledge.vector_store import VectorStore
from lecture_forge.models.curriculum import Curriculum, Section
from lecture_forge.models.lecture import SectionContent
from lecture_forge.utils import logger
from lecture_forge.utils.content_metrics import (
    calculate_target_metrics,
    evaluate_content_quality,
    format_quality_report,
)
from lecture_forge.utils.language_utils import detect_language
from lecture_forge.utils.prompt_manager import load_prompt


class ContentWriterAgent(BaseAgent):
    """Agent for writing lecture content with RAG."""

    def __init__(self, vector_store: VectorStore = None) -> None:
        """
        Initialize Content Writer Agent.

        Args:
            vector_store: Vector store for RAG queries
        """
        super().__init__()
        logger.info("Initializing Content Writer Agent")
        self.vector_store = vector_store

        # Global image tracking for deduplication across sections
        self.used_image_ids = set()
        self.image_usage_count = {}

        # Initialize helper components
        self.image_selector = ImageSelector(
            keyword_expander=self._expand_keywords,
            keyword_translator=self._get_keyword_translations
        )
        self.code_generator = CodeGenerator(vector_store=vector_store)
        self.content_expander = ContentExpander(vector_store=vector_store)

    def extract_code_blocks(self, markdown: str) -> List:
        """Delegate to CodeGenerator.extract_code_blocks()."""
        return self.code_generator.extract_code_blocks(markdown)

    def write_all_sections(
        self,
        curriculum: Curriculum,
        available_images: List[dict] = None,
    ) -> List[SectionContent]:
        """
        Write content for all sections in curriculum with global image deduplication.

        Args:
            curriculum: Curriculum plan
            available_images: List of available images with metadata

        Returns:
            List of section contents
        """
        logger.info(f"📝 Writing content for {len(curriculum.sections)} sections with image deduplication")

        section_contents = []

        # Initialize global image tracking
        self.used_image_ids.clear()
        self.image_usage_count.clear()

        for i, section in enumerate(curriculum.sections):
            logger.info(f"\n{'='*60}")
            logger.info(f"Section {i+1}/{len(curriculum.sections)}: {section.title}")
            logger.info(f"{'='*60}")

            # Filter available images (exclude already used ones)
            available_for_section = [img for img in (available_images or []) if img.get("id") not in self.used_image_ids]

            logger.info(
                f"   📷 Available images: {len(available_for_section)} " f"(filtered from {len(available_images or [])})"
            )

            content = self.write_section(
                section=section,
                curriculum=curriculum,
                available_images=available_for_section,
            )

            # Track used images
            for img_ref in content.images:
                self.used_image_ids.add(img_ref.image_id)
                self.image_usage_count[img_ref.image_id] = self.image_usage_count.get(img_ref.image_id, 0) + 1

            logger.info(f"   ✅ Used {len(content.images)} images in this section")
            logger.info(f"   📊 Total unique images used so far: {len(self.used_image_ids)}")

            section_contents.append(content)

        # Final statistics
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 Image Usage Statistics:")
        logger.info(f"{'='*60}")
        logger.info(f"   • Total images available: {len(available_images or [])}")
        logger.info(f"   • Unique images used: {len(self.used_image_ids)}")
        logger.info(f"   • Images reused: {sum(1 for c in self.image_usage_count.values() if c > 1)}")
        logger.info(f"   • Unused images: {len(available_images or []) - len(self.used_image_ids)}")

        logger.info(f"Completed writing {len(section_contents)} sections")
        return section_contents


    def write_section(
        self,
        section: Section,
        curriculum: Curriculum,
        available_images: List[dict] = None,
    ) -> SectionContent:
        """
        Write content for a single section using RAG.

        Args:
            section: Section to write content for
            curriculum: Full curriculum for context
            available_images: Available images

        Returns:
            Section content
        """
        # 1. RAG query to get relevant context
        contexts, context_metadatas = self._query_knowledge(section)

        # 2. Select relevant images FIRST (for accurate quality evaluation)
        images = self.image_selector.select_images(section, available_images or [], context_metadatas)
        logger.info(f"   🖼️  Selected {len(images)} images for quality evaluation")

        # 3. Generate markdown content with LLM (pass image count for quality evaluation)
        markdown_content = self._generate_content(
            section=section,
            curriculum=curriculum,
            contexts=contexts,
            available_image_count=len(images),  # Pass actual image count
        )

        # 4. Extract code blocks (if any)
        code_blocks = self.code_generator.extract_code_blocks(markdown_content)

        # 5. Count words
        word_count = len(markdown_content.split())

        content = SectionContent(
            section_id=section.id,
            title=section.title,
            markdown_content=markdown_content,
            code_blocks=code_blocks,
            images=images,
            diagrams=[],  # Diagrams will be added by DiagramGenerator
            word_count=word_count,
            estimated_time=section.estimated_time,
            difficulty_level=section.difficulty_level,
        )

        logger.info(f"Section '{section.title}': {word_count} words, {len(code_blocks)} code blocks, {len(images)} images")

        return content


    def _query_knowledge(self, section: Section) -> tuple:
        """Query vector DB for relevant context with increased retrieval.

        Returns:
            Tuple of (documents, metadatas) for RAG context and location-based image matching
        """
        if not self.vector_store:
            return [], []

        # Build comprehensive query from section topics
        query = " ".join(section.topics)

        try:
            # Increase from 5 to 10 for more comprehensive context
            results = self.vector_store.query(query, n_results=10)

            if results and results["documents"]:
                documents = results["documents"][0]
                metadatas = results.get("metadatas", [[]])[0]  # Extract metadatas
                return documents, metadatas
            else:
                return [], []

        except Exception as e:
            logger.warning(f"Error querying vector DB: {e}")
            return [], []


    def _generate_content(
        self,
        section: Section,
        curriculum: Curriculum,
        contexts: List[str],
        available_image_count: int = 0,
    ) -> str:
        """Generate detailed, comprehensive markdown content using LLM with RAG.

        Args:
            section: Section to write
            curriculum: Full curriculum
            contexts: RAG contexts
            available_image_count: Number of images selected for this section (for quality evaluation)
        """
        # Calculate target metrics
        targets = calculate_target_metrics(section.estimated_time, section.difficulty_level)

        # Use more contexts (increase from 8 to 10 for better content)
        context_text = "\n\n---\n\n".join(contexts[:10]) if contexts else "No additional context available."

        # Determine language-aware labels for section headings
        is_korean = detect_language(curriculum.topic) == "ko"
        intro_label = "도입부" if is_korean else "Introduction"
        summary_label = "요약 및 실습" if is_korean else "Summary & Practice"

        # Prepare template variables
        template_vars = {
            # Basic information
            "topic": curriculum.topic,
            "audience_level": curriculum.audience_level,
            "section_title": section.title,
            "estimated_time": section.estimated_time,
            "difficulty_level": section.difficulty_level,
            # Topics and outcomes
            "topics_list": ', '.join(section.topics),
            "learning_outcomes_list": '\n'.join(f'- {outcome}' for outcome in section.learning_outcomes),
            # Target metrics
            "min_words": targets['min_words'],
            "target_words": targets['target_words'],
            "max_words": targets['max_words'],
            "target_subsections": targets['target_subsections'],
            "target_code_examples": targets['target_code_examples'],
            "target_practice_problems": targets['target_practice_problems'],
            # Word count breakdown (using Config constants)
            "intro_words": int(targets['target_words'] * Config.CONTENT_INTRO_RATIO),
            "main_content_words": int(targets['target_words'] * Config.CONTENT_MAIN_RATIO),
            "summary_words": int(targets['target_words'] * Config.CONTENT_SUMMARY_RATIO),
            "words_per_subsection": int(targets['target_words'] * Config.CONTENT_MAIN_RATIO / max(1, targets['target_subsections'])),
            # Language-aware labels
            "intro_label": intro_label,
            "summary_label": summary_label,
            # Context
            "context_text": context_text,
        }

        # Load prompt from template
        prompt = load_prompt("content_generation", **template_vars)

        try:
            response = self.invoke_llm(prompt, phase="content_writing")
            content = response.content.strip()

            # Clean up markdown fences
            if content.startswith("```markdown"):
                content = content.split("```markdown")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()

            # Validate content quality (use actual image count from selected images)
            code_blocks = self.code_generator.extract_code_blocks(content)
            quality = evaluate_content_quality(
                content=content,
                targets=targets,
                code_block_count=len(code_blocks),
                image_count=available_image_count,  # Use actual selected images count
            )

            logger.info(f"  📊 Initial quality score: {quality['overall_score']}/100 (with {available_image_count} images)")

            # CRITICAL: If NO code examples, generate them separately
            if len(code_blocks) == 0 and targets["target_code_examples"] > 0:
                logger.warning(
                    f"  ❌ CRITICAL: No code examples found! Generating {targets['target_code_examples']} code examples..."
                )

                code_examples_content = self.code_generator.generate_code_examples(
                    section=section, curriculum=curriculum, contexts=contexts, num_examples=targets["target_code_examples"]
                )

                # Append code examples to content
                content += "\n\n" + code_examples_content

                # Re-extract code blocks
                code_blocks = self.code_generator.extract_code_blocks(content)
                logger.info(f"  ✅ Added {len(code_blocks)} code examples")

                # Re-evaluate (use actual image count)
                quality = evaluate_content_quality(
                    content=content,
                    targets=targets,
                    code_block_count=len(code_blocks),
                    image_count=available_image_count,  # Use actual selected images count
                )
                logger.info(f"  📊 Quality after adding code: {quality['overall_score']}/100")

            # If quality is too low, try to expand with multiple iterations
            if not quality["meets_requirements"]:
                logger.warning(f"  ⚠️ Content below target. Attempting to expand...")
                logger.info(format_quality_report(quality))

                # Try up to N iterations of expansion (from Config)
                max_iterations = Config.CONTENT_MAX_EXPANSION_ITERATIONS
                previous_quality_score = quality["overall_score"]  # Track for improvement check

                for iteration in range(max_iterations):
                    logger.info(f"  🔄 Expansion attempt {iteration + 1}/{max_iterations}")

                    try:
                        expanded_content = self.content_expander.expand_content(
                            section=section,
                            curriculum=curriculum,
                            contexts=contexts,
                            targets=targets,
                            previous_content=content,
                            previous_quality=quality,
                        )

                        # Check if expansion was successful (content changed)
                        if expanded_content != content and len(expanded_content) > len(content):
                            content = expanded_content

                            # Re-evaluate (use actual image count)
                            code_blocks = self.code_generator.extract_code_blocks(content)
                            quality = evaluate_content_quality(
                                content=content,
                                targets=targets,
                                code_block_count=len(code_blocks),
                                image_count=available_image_count,  # Use actual selected images count
                            )

                            logger.info(f"  📊 Quality after expansion {iteration + 1}: {quality['overall_score']}/100")

                            # Check improvement effectiveness (prevent wasteful iterations)
                            if iteration > 0:
                                improvement = quality["overall_score"] - previous_quality_score
                                if improvement < Config.CONTENT_MIN_QUALITY_IMPROVEMENT:
                                    logger.warning(
                                        f"  ⚠️ Minimal improvement (+{improvement:.1f} points). "
                                        "Stopping early to prevent wasteful iterations."
                                    )
                                    break

                            # Stop if meets requirements
                            if quality["meets_requirements"]:
                                logger.info(f"  ✅ Quality threshold met after {iteration + 1} expansion(s)")
                                break

                            # Update previous score for next iteration comparison
                            previous_quality_score = quality["overall_score"]
                        else:
                            logger.warning(f"  ⚠️ Expansion {iteration + 1} produced no change - stopping")
                            break

                    except Exception as e:
                        logger.error(f"  ❌ Expansion {iteration + 1} failed: {e}")
                        break

            return content

        except Exception as e:
            logger.error(f"Error generating content: {e}")
            return f"# {section.title}\n\n*Content generation error: {str(e)}*"


    def _get_keyword_translations(self) -> dict:
        """Comprehensive Korean-English keyword mapping for AI/ML terms."""
        return {
            # ===== AI/ML General =====
            "인공지능": ["artificial intelligence", "ai"],
            "기계학습": ["machine learning", "ml"],
            "딥러닝": ["deep learning", "dl", "deep neural network"],
            "신경망": ["neural network", "nn", "network"],
            # ===== LLM Related =====
            "대형 언어 모델": ["large language model", "llm", "language model", "transformer"],
            "언어 모델": ["language model", "llm", "lm"],
            "트랜스포머": ["transformer", "attention", "self-attention"],
            "어텐션": ["attention", "attention mechanism", "self-attention"],
            "파인튜닝": ["fine-tuning", "finetuning", "fine tuning", "finetune", "training"],
            "프롬프트": ["prompt", "prompting", "prompt engineering"],
            "프롬프트 엔지니어링": ["prompt engineering", "prompting", "prompt design"],
            "컨텍스트": ["context", "contextual", "context window"],
            "컨텍스트 엔지니어링": ["context engineering", "context", "contextual"],
            # ===== Models =====
            "GPT": ["gpt", "generative pre-trained transformer"],
            "BERT": ["bert", "bidirectional encoder"],
            "ChatGPT": ["chatgpt", "chat gpt", "gpt"],
            "LLM": ["llm", "large language model", "language model"],
            # ===== RAG & Vector DB =====
            "RAG": ["rag", "retrieval augmented generation", "retrieval", "augmented"],
            "정보 검색": ["retrieval", "information retrieval", "search", "ir"],
            "검색": ["search", "retrieval", "query", "lookup"],
            "임베딩": ["embedding", "embeddings", "vector embedding", "word embedding"],
            "벡터": ["vector", "vectors", "vectorization"],
            "벡터 데이터베이스": ["vector database", "vector db", "vectordb", "embedding database"],
            "데이터베이스": ["database", "db", "datastore", "storage"],
            "색인": ["index", "indexing"],
            "유사도": ["similarity", "cosine similarity", "distance"],
            # ===== AI Agents =====
            "에이전트": ["agent", "agents", "ai agent", "autonomous"],
            "AI 에이전트": ["ai agent", "agent", "autonomous agent"],
            "자율": ["autonomous", "automation", "automatic"],
            "계획": ["planning", "plan", "strategy"],
            "도구": ["tool", "tools", "function", "api"],
            "실행": ["execution", "execute", "action"],
            "추론": ["reasoning", "inference", "thinking"],
            "의사결정": ["decision making", "decision"],
            # ===== Generation Parameters =====
            "파라미터": ["parameter", "parameters", "hyperparameter", "config"],
            "하이퍼파라미터": ["hyperparameter", "hyper-parameter", "parameter"],
            "온도": ["temperature", "temp", "sampling"],
            "토큰": ["token", "tokens", "tokenization"],
            "생성": ["generation", "generate", "output", "inference"],
            "생성 파라미터": ["generation parameters", "sampling", "decoding"],
            "샘플링": ["sampling", "sample", "decoding"],
            "빔 서치": ["beam search", "beam"],
            "탐욕": ["greedy", "greedy search"],
            # ===== Reinforcement Learning =====
            "강화학습": ["reinforcement learning", "rl", "reward", "policy"],
            "보상": ["reward", "rewards"],
            "정책": ["policy", "policies"],
            "가치함수": ["value function", "value"],
            "Q-학습": ["q-learning", "q learning"],
            "병목": ["bottleneck", "constraint"],
            "병목 현상": ["bottleneck", "bottleneck problem"],
            # ===== Architecture =====
            "아키텍처": ["architecture", "model architecture", "structure"],
            "레이어": ["layer", "layers", "hidden layer"],
            "인코더": ["encoder", "encoding"],
            "디코더": ["decoder", "decoding"],
            "어텐션 메커니즘": ["attention mechanism", "attention", "self-attention"],
            "순환 신경망": ["recurrent neural network", "rnn"],
            "합성곱": ["convolution", "convolutional", "cnn"],
            "완전 연결": ["fully connected", "dense", "fc"],
            # ===== Training Process =====
            "학습": ["training", "learning", "train"],
            "훈련": ["training", "train"],
            "사전학습": ["pre-training", "pretraining", "pretrain"],
            "사전 학습": ["pre-training", "pretraining", "pretrain"],
            "미세조정": ["fine-tuning", "finetuning", "fine tuning"],
            "미세 조정": ["fine-tuning", "finetuning", "fine tuning"],
            "튜닝": ["tuning", "fine-tuning"],
            "최적화": ["optimization", "optimizer", "optimize"],
            "손실함수": ["loss function", "loss", "objective"],
            "손실": ["loss", "loss function"],
            "경사하강": ["gradient descent", "backpropagation", "gradient"],
            "역전파": ["backpropagation", "backprop"],
            "배치": ["batch", "batching", "mini-batch"],
            "에포크": ["epoch", "epochs"],
            # ===== Evaluation =====
            "평가": ["evaluation", "eval", "assessment", "metric"],
            "성능": ["performance", "accuracy", "precision"],
            "정확도": ["accuracy", "acc"],
            "정밀도": ["precision"],
            "재현율": ["recall"],
            "F1": ["f1", "f1-score"],
            "지표": ["metric", "metrics", "measure"],
            # ===== Data =====
            "데이터": ["data", "dataset"],
            "데이터셋": ["dataset", "data", "corpus"],
            "말뭉치": ["corpus", "corpora", "dataset"],
            "전처리": ["preprocessing", "preprocess", "data cleaning"],
            "정규화": ["normalization", "normalize"],
            "토큰화": ["tokenization", "tokenize"],
            "레이블": ["label", "labels", "annotation"],
            # ===== Common CS Terms =====
            "알고리즘": ["algorithm", "algo"],
            "모델": ["model", "models"],
            "예측": ["prediction", "inference", "predict"],
            "분류": ["classification", "classify"],
            "회귀": ["regression"],
            "군집화": ["clustering", "cluster"],
            "차원": ["dimension", "dimensional"],
            "특징": ["feature", "features"],
            # ===== Visualization =====
            "다이어그램": ["diagram", "chart", "visualization"],
            "그래프": ["graph", "plot", "chart"],
            "시각화": ["visualization", "visual", "plot"],
            "플롯": ["plot", "plotting"],
            # ===== Domain Specific =====
            "자연어처리": ["natural language processing", "nlp", "language processing"],
            "컴퓨터비전": ["computer vision", "cv", "image processing"],
            "이미지 처리": ["image processing", "computer vision"],
            "음성인식": ["speech recognition", "speech", "audio"],
            "텍스트 생성": ["text generation", "generation"],
            "번역": ["translation", "machine translation"],
            # ===== Concepts =====
            "개념": ["concept", "concepts"],
            "원리": ["principle", "principles"],
            "방법": ["method", "methods", "approach"],
            "기법": ["technique", "techniques"],
            "전략": ["strategy", "strategies"],
            "패턴": ["pattern", "patterns"],
            "구조": ["structure", "structures"],
            "시스템": ["system", "systems"],
            "프레임워크": ["framework", "frameworks"],
            "라이브러리": ["library", "libraries"],
        }


    def _expand_keywords(self, topic: str, keyword_map: dict) -> List[str]:
        """Expand topic with English translations and variations."""
        keywords = [topic]  # Original topic

        # Add mapped translations
        for ko_term, en_terms in keyword_map.items():
            if ko_term in topic:
                keywords.extend(en_terms)

        # Extract acronyms (e.g., "LLM" from "대형 언어 모델(LLM)")
        import re

        acronyms = re.findall(r"\b[A-Z]{2,}\b", topic)
        keywords.extend([a.lower() for a in acronyms])

        # Extract English words already in topic
        english_words = re.findall(r"\b[a-zA-Z]{3,}\b", topic)
        keywords.extend([w.lower() for w in english_words])

        # Remove duplicates and empty strings
        keywords = list(set(k for k in keywords if k))

        return keywords

