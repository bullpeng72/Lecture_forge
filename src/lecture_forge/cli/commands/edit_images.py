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
      d <number>    - Delete image or diagram (e.g., d 3)
      u <number>    - Undo deletion (e.g., u 3)
      r <number>    - Replace image (images only; search alternatives)
      s             - Save changes
      /exit, /quit  - Exit without saving (or use: q)
      h             - Show help
    """
    from rich.console import Console
    from rich.prompt import Prompt, Confirm
    from lecture_forge.tools.image_editor import ImageEditor

    console = Console()

    # Detect Reveal.js slides file before entering the main try block
    with open(html_path, "r", encoding="utf-8", errors="replace") as _f:
        _head = _f.read(4096)
    if 'class="reveal"' in _head or "reveal.min.js" in _head or "reveal.min.css" in _head:
        console.print("\n[bold red]❌ 슬라이드 파일은 지원되지 않습니다[/bold red]")
        console.print("[yellow]💡 edit-images 명령어는 강의 HTML 파일 전용입니다.[/yellow]")
        console.print("[dim]   슬라이드 파일이 아닌 강의 HTML 파일을 지정하세요.[/dim]")
        console.print("[dim]   예: lecture-forge edit-images outputs/강의명.html[/dim]")
        return

    try:
        # Initialize editor
        console.print("\n[bold cyan]📸 강의 시각 요소 편집 모드[/bold cyan]")
        console.print("━" * 60)

        with console.status("[bold green]HTML 로딩 중..."):
            editor = ImageEditor(html_path)

        # Display summary
        console.print(f"\n[bold]HTML:[/bold] {Path(html_path).name}")
        console.print(
            f"[bold]이미지:[/bold] {len(editor.images)}개  |  "
            f"[bold]다이어그램:[/bold] {len(editor.diagrams)}개\n"
        )

        # Main loop
        while True:
            # Build unified element list (refreshes status each iteration)
            elements = editor.list_elements()
            index_map = {el["display_index"]: el for el in elements}

            # Display unified table
            _display_elements_table(console, elements)

            # Display compact command hint
            console.print("\n[bold cyan]명령어:[/bold cyan]")
            console.print("  [bold]d <번호>[/bold]     - 삭제 (이미지·다이어그램 공통, 예: d 3)")
            console.print("  [bold]u <번호>[/bold]     - 삭제 취소 (예: u 3)")
            console.print("  [bold]r <번호>[/bold]     - 이미지 교체 (이미지만 지원)")
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
                summary = editor.get_summary()
                has_changes = (
                    summary["to_delete"] > 0
                    or summary["to_replace"] > 0
                    or summary["diagrams_to_delete"] > 0
                )
                if has_changes:
                    if Confirm.ask("[yellow]변경사항이 저장되지 않았습니다. 종료하시겠습니까?[/yellow]"):
                        console.print("[red]변경사항 취소됨[/red]")
                        break
                else:
                    break

            elif cmd in ("d", "delete"):
                if not args:
                    console.print("[red]❌ 번호를 입력하세요 (예: d 3)[/red]")
                    continue
                try:
                    num = int(args[0])
                    el = index_map.get(num)
                    if el is None:
                        console.print(f"[red]❌ 잘못된 번호: {num}[/red]")
                    elif el["kind"] == "image":
                        if editor.mark_delete(el["img_index"]):
                            console.print(f"[green]✅ 이미지 {num} 삭제 표시됨[/green]")
                        else:
                            console.print(f"[red]❌ 이미지 삭제 표시 실패[/red]")
                    else:
                        if editor.mark_delete_diagram(el["dgm_index"]):
                            console.print(f"[green]✅ 다이어그램 {num} 삭제 표시됨[/green]")
                        else:
                            console.print(f"[red]❌ 다이어그램 삭제 표시 실패[/red]")
                except ValueError:
                    console.print("[red]❌ 유효한 숫자를 입력하세요[/red]")

            elif cmd in ("u", "undo", "undelete"):
                if not args:
                    console.print("[red]❌ 번호를 입력하세요 (예: u 3)[/red]")
                    continue
                try:
                    num = int(args[0])
                    el = index_map.get(num)
                    if el is None:
                        console.print(f"[red]❌ 잘못된 번호: {num}[/red]")
                    elif el["kind"] == "image":
                        if editor.unmark_delete(el["img_index"]):
                            console.print(f"[green]✅ 이미지 {num} 삭제 취소됨[/green]")
                        else:
                            console.print(f"[yellow]⚠️ {num}번 이미지는 삭제 표시되지 않았습니다[/yellow]")
                    else:
                        if editor.unmark_delete_diagram(el["dgm_index"]):
                            console.print(f"[green]✅ 다이어그램 {num} 삭제 취소됨[/green]")
                        else:
                            console.print(f"[yellow]⚠️ {num}번 다이어그램은 삭제 표시되지 않았습니다[/yellow]")
                except ValueError:
                    console.print("[red]❌ 유효한 숫자를 입력하세요[/red]")

            elif cmd in ("r", "replace"):
                if not args:
                    console.print("[red]❌ 번호를 입력하세요 (예: r 3)[/red]")
                    continue
                try:
                    num = int(args[0])
                    el = index_map.get(num)
                    if el is None:
                        console.print(f"[red]❌ 잘못된 번호: {num}[/red]")
                    elif el["kind"] == "diagram":
                        console.print("[yellow]⚠️ 다이어그램 교체는 지원되지 않습니다.[/yellow]")
                        console.print("[dim]   삭제(d) 후 improve 커맨드로 재생성하세요.[/dim]")
                    else:
                        _handle_replace_image(console, editor, el["img_index"])
                except ValueError:
                    console.print("[red]❌ 유효한 숫자를 입력하세요[/red]")

            elif cmd in ("s", "save"):
                _handle_save_changes(console, editor, output)
                break

            elif cmd in ("h", "help"):
                _display_help(console)

            else:
                console.print(f"[red]❌ 알 수 없는 명령어: {cmd}[/red]")
                console.print("[yellow]힌트: 'h' 를 입력하여 도움말 보기[/yellow]")

    except Exception as e:
        console.print(f"\n[bold red]❌ 오류 발생:[/bold red] {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise click.Abort()


def _display_elements_table(console, elements: list):
    """Display unified table of images and diagrams."""
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("번호", style="dim", width=5)
    table.add_column("종류", width=7)
    table.add_column("제목 / 설명", width=34)
    table.add_column("섹션", width=24)
    table.add_column("정보", width=10)
    table.add_column("상태", width=10)

    for el in elements:
        if el["kind"] == "image":
            kind_label = "[blue][IMG][/blue]"
        else:
            kind_label = "[magenta][DGM][/magenta]"

        status = el["status"]
        if status == "delete":
            status_text = "[red]🗑️ 삭제[/red]"
        elif status == "replace":
            status_text = "[yellow]🔄 교체[/yellow]"
        else:
            status_text = "[green]유지[/green]"

        table.add_row(
            str(el["display_index"]),
            kind_label,
            el["title"] or "[dim]설명 없음[/dim]",
            el["section"],
            el["extra"],
            status_text,
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

    if summary["to_delete"] == 0 and summary["to_replace"] == 0 and summary["diagrams_to_delete"] == 0:
        console.print("\n[yellow]⚠️ 변경사항이 없습니다[/yellow]")
        return

    # Display summary
    console.print("\n[bold cyan]💾 변경사항 요약:[/bold cyan]")
    if summary["to_delete"] > 0:
        console.print(f"  • 이미지 삭제: [red]{summary['to_delete']}개[/red]")
    if summary["to_replace"] > 0:
        console.print(f"  • 이미지 교체: [yellow]{summary['to_replace']}개[/yellow]")
    if summary["diagrams_to_delete"] > 0:
        console.print(f"  • 다이어그램 삭제: [red]{summary['diagrams_to_delete']}개[/red]")

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

        if summary["to_delete"] > 0:
            console.print(f"  • [red]이미지 삭제됨:[/red] {summary['to_delete']}개")
        if summary["to_replace"] > 0:
            console.print(f"  • [yellow]이미지 교체됨:[/yellow] {summary['to_replace']}개")
        if summary["diagrams_to_delete"] > 0:
            console.print(f"  • [red]다이어그램 삭제됨:[/red] {summary['diagrams_to_delete']}개")

    except Exception as e:
        console.print(f"\n[bold red]❌ 저장 실패:[/bold red] {e}")
        raise


def _display_help(console):
    """Display help message."""
    help_text = """
[bold cyan]📖 시각 요소 편집 도움말[/bold cyan]

[bold]목록 구분:[/bold]
  • [blue][IMG][/blue]  - 이미지 (삭제·교체 모두 지원)
  • [magenta][DGM][/magenta]  - Mermaid 다이어그램 (삭제만 지원)

[bold]기본 명령어:[/bold]
  • [bold]d <번호>[/bold]  - 삭제 표시 (이미지·다이어그램 공통)
    예: d 3 → 3번 항목 삭제 표시

  • [bold]u <번호>[/bold]  - 삭제 취소
    예: u 3 → 3번 항목 삭제 취소

  • [bold]r <번호>[/bold]  - 이미지 교체 (이미지만 지원)
    예: r 5 → 5번 이미지를 대안으로 교체
    (Vector DB에서 관련 이미지 자동 검색)
    다이어그램에 r 적용 시: 안내 메시지 표시

  • [bold]s[/bold]         - 변경사항 저장 후 종료

  • [bold]/exit, /quit[/bold] - 취소 및 종료 (단축키: q)

[bold yellow]💡 사용 팁:[/bold yellow]
  1. 먼저 강의를 브라우저에서 열어 시각 요소를 확인하세요
  2. 불필요한 이미지·다이어그램은 'd' 명령어로 삭제 표시
  3. 교체가 필요한 이미지는 'r' 명령어 사용
  4. 다이어그램을 변경하려면 삭제 후 'improve' 커맨드로 재생성
  5. 모든 변경사항을 검토한 후 's'로 저장

[bold cyan]📋 상태 표시:[/bold cyan]
  • [green]유지[/green]      - 변경 없음
  • [red]🗑️ 삭제[/red]  - 삭제 예정
  • [yellow]🔄 교체[/yellow]  - 교체 예정 (이미지만)
"""
    console.print(Panel(help_text, border_style="cyan"))


