"""
Analysis data models for Content Analyzer.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Entity(BaseModel):
    """An entity/concept extracted from content."""

    name: str
    type: str  # concept, technology, person, method, etc.
    description: str
    mentions: int = 1
    sources: List[str] = Field(default_factory=list)  # Which documents mention this
    difficulty: str = "intermediate"  # beginner, intermediate, advanced


class ConceptRelation(BaseModel):
    """Relationship between two concepts."""

    source: str  # Entity name
    target: str  # Entity name
    relation_type: str  # prerequisite, related_to, part_of, etc.
    strength: float = 1.0  # 0.0 to 1.0


class TopicCluster(BaseModel):
    """A cluster of related topics."""

    id: str
    name: str
    concepts: List[str] = Field(default_factory=list)
    central_concept: Optional[str] = None
    difficulty: str = "intermediate"
    estimated_time: int = 0  # minutes


class AnalysisResult(BaseModel):
    """Result of content analysis."""

    # Extracted entities
    entities: List[Entity] = Field(default_factory=list)

    # Key topics identified
    key_topics: List[str] = Field(default_factory=list)

    # Topic clusters
    topic_clusters: List[TopicCluster] = Field(default_factory=list)

    # Concept relationships (knowledge graph edges)
    concept_relations: List[ConceptRelation] = Field(default_factory=list)

    # Difficulty assessment per topic
    difficulty_scores: Dict[str, float] = Field(
        default_factory=dict
    )  # topic -> score (0-1)

    # Image recommendations (which concepts need visual aids)
    image_recommendations: Dict[str, List[str]] = Field(
        default_factory=dict
    )  # concept -> image_keywords

    # Overall content statistics
    metadata: Dict = Field(default_factory=dict)

    def get_entities_by_type(self, entity_type: str) -> List[Entity]:
        """Get entities of a specific type."""
        return [e for e in self.entities if e.type == entity_type]

    def get_beginner_topics(self) -> List[str]:
        """Get topics suitable for beginners."""
        return [
            topic
            for topic, score in self.difficulty_scores.items()
            if score < 0.3
        ]

    def get_advanced_topics(self) -> List[str]:
        """Get advanced topics."""
        return [
            topic
            for topic, score in self.difficulty_scores.items()
            if score > 0.7
        ]

    def get_prerequisites(self, topic: str) -> List[str]:
        """Get prerequisite topics for a given topic."""
        prerequisites = []
        for relation in self.concept_relations:
            if relation.target == topic and relation.relation_type == "prerequisite":
                prerequisites.append(relation.source)
        return prerequisites

    def get_related_topics(self, topic: str) -> List[str]:
        """Get topics related to a given topic."""
        related = []
        for relation in self.concept_relations:
            if relation.source == topic and relation.relation_type == "related_to":
                related.append(relation.target)
            elif relation.target == topic and relation.relation_type == "related_to":
                related.append(relation.source)
        return list(set(related))
