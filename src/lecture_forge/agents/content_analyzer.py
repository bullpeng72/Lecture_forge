"""
Content Analyzer Agent - Analyzes collected content and builds knowledge graph.
"""

import json
from typing import Dict, List

from lecture_forge.agents.base import BaseAgent
from lecture_forge.knowledge.vector_store import VectorStore
from lecture_forge.models.analysis import (
    AnalysisResult,
    ConceptRelation,
    Entity,
    TopicCluster,
)
from lecture_forge.utils import logger


class ContentAnalyzerAgent(BaseAgent):
    """Agent for analyzing content and extracting key concepts."""

    def __init__(self, vector_store: VectorStore = None):
        """
        Initialize Content Analyzer Agent.

        Args:
            vector_store: Vector store to query for content
        """
        super().__init__()
        logger.info("Initializing Content Analyzer Agent")
        self.vector_store = vector_store

    def analyze(
        self,
        collection_result: Dict,
        image_result: Dict = None,
        topic: str = "",
    ) -> AnalysisResult:
        """
        Analyze collected content.

        Args:
            collection_result: Result from ContentCollector
            image_result: Result from ImageCollector (optional)
            topic: Main topic of the lecture

        Returns:
            AnalysisResult with entities, knowledge graph, etc.
        """
        logger.info("Analyzing collected content")

        documents = collection_result.get("documents", [])
        total_chunks = collection_result.get("metadata", {}).get("total_chunks", 0)

        if not documents:
            logger.warning("No documents to analyze")
            return AnalysisResult()

        # Build analysis text: prefer diverse sampling from vector DB,
        # fall back to concatenating raw documents if no vector store is available.
        all_text = self._build_analysis_text(documents, topic)

        # 1. Extract key topics using LLM
        logger.info("Extracting key topics...")
        key_topics = self._extract_key_topics(all_text, topic)

        # 2. Extract entities/concepts
        logger.info("Extracting entities...")
        entities = self._extract_entities(all_text, key_topics)

        # 3. Assess difficulty levels
        logger.info("Assessing difficulty levels...")
        difficulty_scores = self._assess_difficulty(key_topics, all_text)

        # 4. Build concept relationships
        logger.info("Building concept relationships...")
        concept_relations = self._build_relationships(entities, all_text)

        # 5. Create topic clusters
        logger.info("Creating topic clusters...")
        topic_clusters = self._create_clusters(entities, concept_relations)

        # 6. Recommend images for concepts
        logger.info("Recommending images...")
        image_recommendations = self._recommend_images(key_topics, entities, image_result)

        result = AnalysisResult(
            entities=entities,
            key_topics=key_topics,
            topic_clusters=topic_clusters,
            concept_relations=concept_relations,
            difficulty_scores=difficulty_scores,
            image_recommendations=image_recommendations,
            metadata={
                "total_documents": len(documents),
                "total_chunks": total_chunks,
                "total_entities": len(entities),
                "total_topics": len(key_topics),
                "total_clusters": len(topic_clusters),
            },
        )

        logger.info(f"Analysis complete: {len(entities)} entities, {len(key_topics)} topics")
        return result

    def _build_analysis_text(self, documents: List[Dict], topic: str) -> str:
        """
        Build the text sample used for topic extraction.

        Strategy (in priority order):
        1. If a vector_store is available, issue diverse queries to sample chunks
           spread across the entire knowledge base (not just the first few pages).
        2. Fall back to concatenating raw document texts (old behaviour) when no
           vector store is available.

        The goal is to give the LLM a representative cross-section of the full
        content rather than only the very beginning of the first document.
        """
        # ── Path 1: diverse vector DB sampling ──────────────────────────────
        if self.vector_store:
            try:
                stats = self.vector_store.get_stats()
                total = stats.get("document_count", 0)

                if total > 0:
                    # Probe queries that tend to surface different parts of any document
                    probe_queries = [
                        topic,
                        "introduction overview",
                        "core concept definition",
                        "advanced technique method",
                        "example application case study",
                        "summary conclusion",
                    ]

                    # How many results per probe (scale with DB size, cap at 10)
                    per_probe = min(10, max(3, total // max(1, len(probe_queries) * 5)))

                    seen_ids: set = set()
                    sampled_chunks: List[str] = []

                    for probe in probe_queries:
                        try:
                            results = self.vector_store.query(probe, n_results=per_probe)
                            docs = (results.get("documents") or [[]])[0]
                            metas = (results.get("metadatas") or [[]])[0]
                            ids = (results.get("ids") or [[]])[0]

                            for doc, meta, chunk_id in zip(docs, metas, ids):
                                if chunk_id not in seen_ids:
                                    seen_ids.add(chunk_id)
                                    sampled_chunks.append(doc)
                        except Exception as probe_err:
                            logger.debug(f"Probe query '{probe[:30]}' failed: {probe_err}")

                    if sampled_chunks:
                        logger.info(
                            f"   📊 Analysis sampling: {len(sampled_chunks)} diverse chunks "
                            f"from {total} total (was: first 8,000 chars only)"
                        )
                        return "\n\n---\n\n".join(sampled_chunks)

            except Exception as e:
                logger.warning(f"Vector DB sampling failed, falling back to raw text: {e}")

        # ── Path 2: raw document concatenation (fallback) ────────────────────
        all_text = "\n\n".join([doc["text"] for doc in documents])
        logger.info(f"   📊 Analysis text: {len(all_text):,} chars from {len(documents)} raw docs")
        return all_text

    def _extract_key_topics(self, text: str, main_topic: str) -> List[str]:
        """Extract key topics from text using LLM."""
        # Limit text length for LLM — generous limit since text is now
        # built from diverse KB samples rather than just the first document.
        text_sample = text[:20000] if len(text) > 20000 else text

        prompt = f"""Analyze the following educational content about "{main_topic}" and identify the 5-10 most important topics or concepts that should be covered in a lecture.

Content:
{text_sample}

IMPORTANT: Return topic names in KOREAN language.
Return ONLY a JSON array of topic names (strings), nothing else. Example: ["주제 1", "주제 2", "주제 3"]"""

        try:
            response = self.invoke_llm(prompt, phase="content_analysis")
            content = response.content.strip()

            # Extract JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            topics = json.loads(content)

            if isinstance(topics, list):
                return topics[:10]  # Limit to 10 topics
            else:
                logger.warning(f"Unexpected topics format: {topics}")
                return []

        except Exception as e:
            logger.error(f"Error extracting topics: {e}")
            # Fallback: return main topic
            return [main_topic] if main_topic else []

    def _extract_entities(self, text: str, key_topics: List[str]) -> List[Entity]:
        """Extract entities/concepts from text."""
        entities = []

        # Create entities from key topics
        for i, topic in enumerate(key_topics):
            entities.append(
                Entity(
                    name=topic,
                    type="concept",
                    description=f"Key concept: {topic}",
                    mentions=1,
                    sources=["content_analysis"],
                    difficulty="intermediate",
                )
            )

        # Use LLM to extract additional entities for first few topics
        for topic in key_topics[:3]:  # Limit to first 3 topics for efficiency
            text_sample = text[:10000] if len(text) > 10000 else text

            prompt = f"""For the topic "{topic}", identify 3-5 important sub-concepts or related terms from this text.

Text:
{text_sample}

IMPORTANT: Return concept names in KOREAN language.
Return ONLY a JSON array of concept names (strings). Example: ["개념 1", "개념 2"]"""

            try:
                response = self.invoke_llm(prompt, phase="content_analysis")
                content = response.content.strip()

                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()

                sub_concepts = json.loads(content)

                for concept in sub_concepts[:5]:
                    if concept not in [e.name for e in entities]:
                        entities.append(
                            Entity(
                                name=concept,
                                type="sub_concept",
                                description=f"Related to {topic}",
                                mentions=1,
                                sources=[topic],
                                difficulty="intermediate",
                            )
                        )

            except Exception as e:
                logger.warning(f"Error extracting sub-concepts for {topic}: {e}")

        return entities

    def _assess_difficulty(self, topics: List[str], text: str) -> Dict[str, float]:
        """Assess difficulty level for each topic (0.0 = beginner, 1.0 = advanced)."""
        difficulty_scores = {}

        for topic in topics:
            # Simple heuristic: check for technical terms, complexity indicators
            topic_lower = topic.lower()

            # Keywords that indicate difficulty
            beginner_keywords = ["basic", "introduction", "beginner", "simple", "overview"]
            advanced_keywords = [
                "advanced",
                "complex",
                "optimization",
                "architecture",
                "implementation",
            ]

            score = 0.5  # Default to intermediate

            if any(kw in topic_lower for kw in beginner_keywords):
                score = 0.3
            elif any(kw in topic_lower for kw in advanced_keywords):
                score = 0.8

            difficulty_scores[topic] = score

        return difficulty_scores

    def _build_relationships(self, entities: List[Entity], text: str) -> List[ConceptRelation]:
        """Build relationships between concepts."""
        relations = []

        # Create prerequisite relationships (simple heuristic)
        # Basic concepts should be prerequisites for advanced ones
        beginner_entities = [e for e in entities if "basic" in e.name.lower() or "introduction" in e.name.lower()]
        advanced_entities = [e for e in entities if "advanced" in e.name.lower() or "optimization" in e.name.lower()]

        for beginner in beginner_entities:
            for advanced in advanced_entities:
                relations.append(
                    ConceptRelation(
                        source=beginner.name,
                        target=advanced.name,
                        relation_type="prerequisite",
                        strength=0.7,
                    )
                )

        # Create related_to relationships for entities in same domain
        for i, e1 in enumerate(entities):
            for e2 in entities[i + 1 :]:
                # Simple heuristic: if they share words, they're related
                words1 = set(e1.name.lower().split())
                words2 = set(e2.name.lower().split())

                if words1 & words2:  # Has common words
                    relations.append(
                        ConceptRelation(
                            source=e1.name,
                            target=e2.name,
                            relation_type="related_to",
                            strength=0.5,
                        )
                    )

        return relations

    def _create_clusters(self, entities: List[Entity], relations: List[ConceptRelation]) -> List[TopicCluster]:
        """Create topic clusters from entities and relations."""
        clusters = []

        # Group concepts by type
        main_concepts = [e for e in entities if e.type == "concept"]
        sub_concepts = [e for e in entities if e.type == "sub_concept"]

        # Create a cluster for each main concept
        for i, main in enumerate(main_concepts):
            # Find related sub-concepts
            related = []
            for sub in sub_concepts:
                if any(sub.name in source for source in sub.sources if main.name in source):
                    related.append(sub.name)

            cluster = TopicCluster(
                id=f"cluster_{i}",
                name=main.name,
                concepts=[main.name] + related[:5],  # Limit to 5 sub-concepts
                central_concept=main.name,
                difficulty=main.difficulty,
                estimated_time=10,  # Default 10 minutes per cluster
            )
            clusters.append(cluster)

        return clusters

    def _recommend_images(
        self,
        topics: List[str],
        entities: List[Entity],
        image_result: Dict = None,
    ) -> Dict[str, List[str]]:
        """Recommend image keywords for each concept."""
        recommendations = {}

        # For each topic, suggest image search keywords
        for topic in topics:
            keywords = [topic]

            # Add related terms
            topic_lower = topic.lower()
            if "machine learning" in topic_lower:
                keywords.extend(["neural network", "data science", "AI"])
            elif "deep learning" in topic_lower:
                keywords.extend(["neural network", "AI", "artificial intelligence"])
            elif "neural network" in topic_lower:
                keywords.extend(["deep learning", "AI", "neurons"])

            recommendations[topic] = list(set(keywords))[:3]  # Max 3 keywords

        return recommendations
