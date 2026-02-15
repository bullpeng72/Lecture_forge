"""
Content Writer module - Modular content generation components.

Refactored from a single 1,611-line file into:
- agent.py: Core ContentWriterAgent (~500 lines)
- image_selector.py: ImageSelector (~900 lines)
- code_generator.py: CodeGenerator (~150 lines)
- content_expander.py: ContentExpander (~150 lines)
"""

from lecture_forge.agents.content_writer.agent import ContentWriterAgent
from lecture_forge.agents.content_writer.code_generator import CodeGenerator
from lecture_forge.agents.content_writer.content_expander import ContentExpander
from lecture_forge.agents.content_writer.image_selector import ImageSelector

__all__ = [
    "ContentWriterAgent",
    "ImageSelector",
    "CodeGenerator",
    "ContentExpander",
]
