"""
Curriculum data model.
"""

from typing import Dict, List

from pydantic import BaseModel, Field


class Section(BaseModel):
    """Section in curriculum plan."""

    id: str
    title: str
    topics: List[str] = Field(default_factory=list)
    estimated_time: int  # minutes
    difficulty_level: str  # beginner, intermediate, advanced
    learning_outcomes: List[str] = Field(default_factory=list)


class Curriculum(BaseModel):
    """Curriculum plan for lecture."""

    topic: str
    duration: int  # minutes
    audience_level: str
    learning_objectives: List[str] = Field(default_factory=list)
    sections: List[Section] = Field(default_factory=list)
    total_estimated_time: int = 0
    prerequisite_map: Dict[str, List[str]] = Field(default_factory=dict)  # section_id -> prerequisite section_ids
