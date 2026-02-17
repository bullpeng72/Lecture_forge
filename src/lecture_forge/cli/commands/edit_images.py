"""
Edit-images command - Interactive image editing for generated lectures.
"""

from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from lecture_forge.cli.utils import console
from lecture_forge.tools.image_editor import ImageEditor
from lecture_forge.utils import logger


@click.command()
@click.argument("html_path", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output file path (default: <original>_edited.html)")
def edit_images(html_path: str, output: str) -> None:
    """
    Edit images in generated HTML lecture (interactive mode).

    Provides an interactive interface to:
    - View all images in the lecture
    - Delete unwanted images
    - Replace images with alternatives from Vector DB
    - Save changes to new HTML file

    \b
    Features:
      • Real-time preview of all images in the lecture
      • Delete unwanted images (d <number>)
      • Undo deletions (u <number>)
      • Replace images with RAG-based alternatives (r <number>)
      • Save changes to new file (preserves original)

    \b
    Examples:
      # Interactive editing mode
      $ lecture-forge edit-images outputs/lecture.html

    \b
      # Specify output file
      $ lecture-forge edit-images lecture.html -o new_lecture.html

    \b
    Interactive Commands:
      d <number>    - Delete image (e.g., d 3)
      u <number>    - Undo deletion (e.g., u 3)
      r <number>    - Replace image (search alternatives)
      s             - Save changes
      /exit, /quit  - Exit without saving (or use: q)
      h             - Show help
    """
    from rich.console import Console
    from rich.prompt import Prompt, Confirm
    from lecture_forge.tools.image_editor import ImageEditor

    console = Console()

    try:
        # Initialize editor
        console.print("\n[bold cyan]📸 강의 이미지 편집 모드[/bold cyan]")
        console.print("━" * 60)

        with console.status("[bold green]HTML 로딩 중..."):
            editor = ImageEditor(html_path)

        # Display summary
        console.print(f"\n[bold]HTML:[/bold] {Path(html_path).name}")
        console.print(f"[bold]총 이미지:[/bold] {len(editor.images)}개\n")

        # Main loop
        while True:
            # Display current images
            _display_image_table(console, editor)

            # Display help
            console.print("\n[bold cyan]명령어:[/bold cyan]")
            console.print("  [bold]d <번호>[/bold]     - 이미지 삭제 (예: d 3)")
            console.print("  [bold]u <번호>[/bold]     - 삭제 취소 (예: u 3)")
            console.print("  [bold]r <번호>[/bold]     - 이미지 교체 (대안 검색)")
            console.print("  [bold]s[/bold]            - 변경사항 저장")
            console.print("  [bold]/exit, /quit[/bold] - 취소 및 종료 (단축키: q)")
            console.print("  [bold]h[/bold]            - 도움말 표시\n")

            # Get command
            command = Prompt.ask("[bold yellow]명령 입력[/bold yellow]").strip().lower()

            if not command:
                continue

            # Parse command
            parts = command.split()
            cmd = parts[0]
            args = parts[1:] if len(parts) > 1 else []

            # Handle commands
            if cmd in ["/exit", "/quit", "q"]:
                if editor.get_summary()["to_delete"] > 0 or editor.get_summary()["to_replace"] > 0:
                    if Confirm.ask("[yellow]변경사항이 저장되지 않았습니다. 종료하시겠습니까?[/yellow]"):
                        console.print("[red]변경사항 취소됨[/red]")
                        break
                else:
                    break

            elif cmd == "d" or cmd == "delete":
                if not args:
                    console.print("[red]❌ 이미지 번호를 입력하세요 (예: d 3)[/red]")
                    continue

                try:
                    img_num = int(args[0])
                    if editor.mark_delete(img_num):
                        console.print(f"[green]✅ 이미지 {img_num} 삭제 표시됨[/green]")
                    else:
                        console.print(f"[red]❌ 잘못된 이미지 번호: {img_num}[/red]")
                except ValueError:
                    console.print("[red]❌ 유효한 숫자를 입력하세요[/red]")

            elif cmd == "u" or cmd == "undo" or cmd == "undelete":
                if not args:
                    console.print("[red]❌ 이미지 번호를 입력하세요 (예: u 3)[/red]")
                    continue

                try:
                    img_num = int(args[0])
                    if editor.unmark_delete(img_num):
                        console.print(f"[green]✅ 이미지 {img_num} 삭제 취소됨[/green]")
                    else:
                        console.print(f"[yellow]⚠️ 이미지 {img_num}는 삭제 표시되지 않았습니다[/yellow]")
                except ValueError:
                    console.print("[red]❌ 유효한 숫자를 입력하세요[/red]")

            elif cmd == "r" or cmd == "replace":
                if not args:
                    console.print("[red]❌ 이미지 번호를 입력하세요 (예: r 3)[/red]")
                    continue

                try:
                    img_num = int(args[0])
                    _handle_replace_image(console, editor, img_num)
                except ValueError:
                    console.print("[red]❌ 유효한 숫자를 입력하세요[/red]")

            elif cmd == "s" or cmd == "save":
                _handle_save_changes(console, editor, output)
                break

            elif cmd == "h" or cmd == "help":
                _display_help(console)

            else:
                console.print(f"[red]❌ 알 수 없는 명령어: {cmd}[/red]")
                console.print("[yellow]힌트: 'h' 를 입력하여 도움말 보기[/yellow]")

    except Exception as e:
        console.print(f"\n[bold red]❌ 오류 발생:[/bold red] {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise click.Abort()


def _display_image_table(console, editor):
    """Display image table."""
    images = editor.list_images()

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("번호", style="dim", width=6)
    table.add_column("설명", width=35)
    table.add_column("섹션", width=25)
    table.add_column("페이지", width=8)
    table.add_column("상태", width=10)

    for img in images:
        status_style = "green"
        status_text = "유지"

        if img["status"] == "delete":
            status_style = "red"
            status_text = "🗑️ 삭제"
        elif img["status"] == "replace":
            status_style = "yellow"
            status_text = "🔄 교체"

        table.add_row(
            str(img["index"]),
            img["description"] or "[dim]설명 없음[/dim]",
            img["section"],
            str(img["page"]) if img["page"] else "-",
            f"[{status_style}]{status_text}[/{status_style}]",
        )

    console.print(table)


def _handle_replace_image(console, editor, img_num):
    """Handle image replacement."""
    console.print(f"\n[bold cyan]🔍 이미지 {img_num} 대안 검색 중...[/bold cyan]")

    alternatives = editor.find_alternative_images(img_num, max_results=5)

    if not alternatives:
        console.print("[yellow]⚠️ 대안 이미지를 찾을 수 없습니다[/yellow]")
        console.print("[dim]힌트: Vector DB가 로드되지 않았거나 관련 이미지가 없습니다[/dim]")
        return

    # Display alternatives
    console.print(f"\n[bold green]대안 이미지 ({len(alternatives)}개):[/bold green]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("번호", width=6)
    table.add_column("설명", width=50)
    table.add_column("페이지", width=8)
    table.add_column("출처", width=20)

    for alt in alternatives:
        table.add_row(str(alt["index"]), alt["description"], str(alt["page"]) if alt["page"] else "-", alt["source"])

    console.print(table)

    # Prompt for selection
    console.print("\n[dim]0: 취소[/dim]")
    choice = Prompt.ask("[bold yellow]선택[/bold yellow]", default="0")

    try:
        choice_num = int(choice)
        if choice_num == 0:
            console.print("[yellow]교체 취소됨[/yellow]")
            return

        if 1 <= choice_num <= len(alternatives):
            selected = alternatives[choice_num - 1]
            if editor.replace_image(img_num, selected["path"]):
                console.print(f"[green]✅ 이미지 {img_num} 교체 예정[/green]")
                console.print(f"[dim]   새 이미지: {selected['description'][:60]}[/dim]")
            else:
                console.print("[red]❌ 교체 실패[/red]")
        else:
            console.print("[red]❌ 잘못된 선택[/red]")

    except ValueError:
        console.print("[red]❌ 유효한 숫자를 입력하세요[/red]")


def _handle_save_changes(console, editor, output_path):
    """Handle saving changes."""
    summary = editor.get_summary()

    if summary["to_delete"] == 0 and summary["to_replace"] == 0:
        console.print("\n[yellow]⚠️ 변경사항이 없습니다[/yellow]")
        return

    # Display summary
    console.print("\n[bold cyan]💾 변경사항 요약:[/bold cyan]")
    if summary["to_delete"] > 0:
        console.print(f"  • 삭제: [red]{summary['to_delete']}개[/red]")
    if summary["to_replace"] > 0:
        console.print(f"  • 교체: [yellow]{summary['to_replace']}개[/yellow]")

    console.print()

    # Confirm
    if not Confirm.ask("[bold yellow]변경사항을 저장하시겠습니까?[/bold yellow]"):
        console.print("[yellow]저장 취소됨[/yellow]")
        return

    # Save
    try:
        with console.status("[bold green]저장 중..."):
            saved_path = editor.save_changes(output_path)

        console.print(f"\n[bold green]✅ 저장 완료![/bold green]")
        console.print(f"[bold]파일:[/bold] {saved_path}")

        # Display changes
        if summary["to_delete"] > 0:
            console.print(f"  • [red]삭제됨:[/red] {summary['to_delete']}개 이미지")
        if summary["to_replace"] > 0:
            console.print(f"  • [yellow]교체됨:[/yellow] {summary['to_replace']}개 이미지")

    except Exception as e:
        console.print(f"\n[bold red]❌ 저장 실패:[/bold red] {e}")
        raise


def _display_help(console):
    """Display help message."""
    help_text = """
[bold cyan]📖 이미지 편집 도움말[/bold cyan]

[bold]기본 명령어:[/bold]
  • [bold]d <번호>[/bold]  - 이미지 삭제 표시
    예: d 3 → 3번 이미지 삭제 표시

  • [bold]u <번호>[/bold]  - 삭제 취소
    예: u 3 → 3번 이미지 삭제 취소

  • [bold]r <번호>[/bold]  - 이미지 교체
    예: r 5 → 5번 이미지를 대안 이미지로 교체
    (Vector DB에서 관련 이미지 자동 검색)

  • [bold]s[/bold]         - 변경사항 저장 후 종료

  • [bold]/exit, /quit[/bold] - 취소 및 종료 (단축키: q)

[bold yellow]💡 사용 팁:[/bold yellow]
  1. 먼저 강의를 브라우저에서 열어 이미지를 확인하세요
  2. 불필요한 이미지는 'd' 명령어로 삭제 표시
  3. 교체가 필요한 이미지는 'r' 명령어 사용
  4. 모든 변경사항을 검토한 후 's'로 저장

[bold cyan]📋 이미지 상태:[/bold cyan]
  • [green]유지[/green]   - 변경 없음
  • [red]🗑️ 삭제[/red] - 삭제 예정
  • [yellow]🔄 교체[/yellow] - 교체 예정
"""
    console.print(Panel(help_text, border_style="cyan"))


