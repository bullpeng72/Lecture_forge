"""
Content Writer Agent - Backward compatibility wrapper.

This file now imports from the refactored content_writer module.
The original 1,611-line file has been split into modular components.

For the actual implementation, see:
- content_writer/agent.py: ContentWriterAgent class
- content_writer/image_selector.py: Image selection logic
- content_writer/code_generator.py: Code generation
- content_writer/content_expander.py: Content expansion
"""

# Import for backward compatibility
from lecture_forge.agents.content_writer.agent import ContentWriterAgent

__all__ = ["ContentWriterAgent"]
