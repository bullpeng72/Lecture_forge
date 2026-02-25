"""
Chat command - Chat.
"""

import sys
from typing import Optional

import click
from rich.panel import Panel
from rich.prompt import Prompt

from lecture_forge.agents.qa_agent import QAAgent
from lecture_forge.cli.utils import console, select_knowledge_base
from lecture_forge.config import Config
from lecture_forge.utils import logger


@click.command()
@click.option(
    "--knowledge-base",
    "-kb",
    type=click.Path(exists=True),
    help="Path to knowledge base directory (e.g., data/vector_db/my_lecture)",
)
def chat(knowledge_base: Optional[str]) -> None:
    """
    Start interactive Q&A mode with knowledge base.

    Chat with AI about the content in your generated lecture using RAG
    (Retrieval Augmented Generation). The AI will answer questions based
    on the knowledge base created during lecture generation.

    \b
    Features:
      • Context-aware answers from your lecture content
      • Source citations with references
      • Multilingual support (Korean/English)
      • Cross-lingual search with automatic translation

    \b
    Examples:
      # Interactive selection from available knowledge bases
      $ lecture-forge chat

      # Direct path to knowledge base
      $ lecture-forge chat -kb data/vector_db/AI_Basics_20260207

      # Use tab completion for paths
      $ lecture-forge chat -kb data/vector_db/<TAB>

    \b
    Exit Commands:
      /exit, /quit  - Exit chat mode
      Ctrl+C        - Force quit

    \b
    Example Session:
      You: What is supervised learning?
      AI: Supervised learning is a type of machine learning where...

          Sources:
          - ml_basics.pdf (page 12)
          - https://example.com/ml-guide

    \b
    Note:
      Knowledge base is created automatically during 'lecture-forge create'
      and stored in data/vector_db/ directory.
    """
    from lecture_forge.agents.qa_agent import QAAgent

    # If no knowledge base provided, list available ones
    if not knowledge_base:
        knowledge_base = select_knowledge_base()
        if not knowledge_base:
            console.print("[yellow]No knowledge base selected. Exiting.[/yellow]\n")
            return

    # Start Q&A agent
    try:
        qa_agent = QAAgent(knowledge_base)
        qa_agent.start_chat()
    except Exception as e:
        console.print(f"[bold red]❌ Error starting Q&A mode: {e}[/bold red]")
        logger.exception("Q&A mode failed")
        sys.exit(1)


# NOTE: This 'improve' command is disabled due to name conflict with the newer improve command at line 1201
# TODO: Rename this to 'evaluate' or 'improve-quality' if this functionality is still needed
# @click.command()
# @click.argument("lecture_path", type=click.Path(exists=True))
# @click.option("--threshold", "-t", type=int, default=80, help="Quality threshold (0-100)", show_default=True)
