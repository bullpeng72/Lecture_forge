"""
Q&A Agent - Answers questions using knowledge base.
"""

from pathlib import Path
from typing import Dict

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from lecture_forge.agents.base import BaseAgent
from lecture_forge.knowledge.vector_store import VectorStore
from lecture_forge.utils import logger


class QAAgent(BaseAgent):
    """Agent for answering questions using RAG."""

    def __init__(self, knowledge_base_path: str):
        super().__init__()
        self.knowledge_base_path = Path(knowledge_base_path)

        # Load vector store
        collection_name = self.knowledge_base_path.name
        self.vector_store = VectorStore(collection_name=collection_name)

        logger.info(f"Initializing Q&A Agent with KB: {knowledge_base_path}")

    def answer(self, question: str) -> Dict:
        """
        Answer a question using the knowledge base.

        Args:
            question: User question

        Returns:
            Answer with sources
        """
        logger.info(f"Answering question: {question}")

        # 1. RAG query to get relevant context
        try:
            results = self.vector_store.query(question, n_results=5)

            if not results or not results.get("documents"):
                return {
                    "answer": "죄송합니다. 관련 정보를 찾을 수 없습니다.",
                    "sources": [],
                    "confidence": 0.0,
                }

            contexts = results["documents"][0]
            metadatas = results.get("metadatas", [[]])[0]

            # 2. Build prompt with context
            context_text = "\n\n---\n\n".join(contexts)

            prompt = f"""다음 질문에 제공된 컨텍스트를 사용하여 한국어로 답변해주세요.

질문: {question}

컨텍스트:
{context_text}

**답변 시 주의사항:**
1. 제공된 컨텍스트의 정보만 사용하세요
2. 한국어로 명확하고 간결하게 답변하세요
3. 관련 예시나 설명을 포함하세요
4. 컨텍스트에 정보가 없다면 솔직히 모른다고 답변하세요

답변:"""

            # 3. Generate answer
            response = self.invoke_llm(prompt, phase="qa")
            answer = response.content.strip()

            # 4. Extract sources
            sources = []
            for metadata in metadatas:
                if metadata:
                    source_info = metadata.get("source", "Unknown")
                    sources.append(source_info)

            return {
                "answer": answer,
                "sources": list(set(sources))[:3],  # Top 3 unique sources
                "confidence": 0.85 if contexts else 0.0,
            }

        except Exception as e:
            logger.error(f"Error answering question: {e}")
            return {
                "answer": f"답변 중 오류가 발생했습니다: {str(e)}",
                "sources": [],
                "confidence": 0.0,
            }

    def start_chat(self):
        """Start interactive chat mode."""
        logger.info("Starting Q&A chat mode")

        console = Console()

        # Display welcome banner
        welcome = Panel(
            "[bold]💬 Q&A Chat Mode[/bold]\n\n"
            f"[cyan]Knowledge Base:[/cyan] {self.knowledge_base_path.name}\n\n"
            "[dim]Available commands:[/dim]\n"
            "  • [bold]/help[/bold] - Show help\n"
            "  • [bold]/exit[/bold] or [bold]/quit[/bold] - Exit chat mode\n"
            "  • [bold]Ctrl+C[/bold] - Quick exit\n\n"
            "[dim]Just type your question to start![/dim]",
            title="🤖 LectureForge Q&A",
            border_style="blue",
        )
        console.print(welcome)

        question_count = 0

        while True:
            try:
                # Get user question
                question = Prompt.ask("\n[bold cyan]You[/bold cyan]")

                # Check for commands
                if question.lower() in ["exit", "quit", "/exit", "/quit"]:
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

                # Display answer
                console.print(f"\n[bold yellow]Assistant[/bold yellow]: {result['answer']}\n")

                # Display sources if available
                if result["sources"]:
                    console.print("[dim]📚 Sources:[/dim]")
                    for source in result["sources"]:
                        console.print(f"  • [dim]{source}[/dim]")
                    console.print()

            except KeyboardInterrupt:
                console.print("\n")
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
        help_table.add_row("exit, quit", "Exit Q&A mode (alternative)")
        help_table.add_row("Ctrl+C", "Quick exit")
        help_table.add_row("<question>", "Ask any question about the lecture content")

        console.print("\n")
        console.print(help_table)
        console.print("\n[dim]💡 Tips:[/dim]")
        console.print("  • Be specific in your questions for better answers")
        console.print("  • You can ask follow-up questions")
        console.print("  • Sources are shown below each answer")
        console.print("  • To delete knowledge bases, exit and run 'lecture-forge chat' again")
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
