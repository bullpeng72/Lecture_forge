"""
Edit command - Web-based lecture editor.
"""

from pathlib import Path
from typing import Optional

import click

from lecture_forge.utils import logger


@click.command()
@click.argument("html_path", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output file path (default: <original>_edited.html)")
@click.option("--port", "-p", default=5757, show_default=True, help="Port for the local web server")
@click.option("--no-browser", is_flag=True, default=False, help="Do not open browser automatically")
def edit(html_path: str, output: Optional[str], port: int, no_browser: bool) -> None:
    """
    Launch a web-based editor for a generated lecture HTML file.

    Opens a local server (default: http://localhost:5757) with a 3-panel UI:
    - Left: Section list with status indicators
    - Center: Markdown editor (EasyMDE) with preview tab
    - Right: Image / diagram panel with gallery modal

    \b
    Features:
      • Edit section content with a rich Markdown editor
      • Delete or restore sections (staged until save)
      • Delete / replace images and diagrams
      • Browse full image gallery or upload new images
      • Save all changes to a new HTML file

    \b
    Examples:
      # Launch editor (auto-opens browser)
      $ lecture-forge edit outputs/my_lecture.html

    \b
      # Specify output file
      $ lecture-forge edit outputs/my_lecture.html -o my_lecture_v2.html

    \b
      # Run without browser (for manual access)
      $ lecture-forge edit outputs/my_lecture.html --no-browser
    """
    from rich.console import Console

    console = Console()

    # Detect Reveal.js slides file
    with open(html_path, "r", encoding="utf-8", errors="replace") as _f:
        _head = _f.read(4096)
    if 'class="reveal"' in _head or "reveal.min.js" in _head or "reveal.min.css" in _head:
        console.print("\n[bold red]❌ 슬라이드 파일은 지원되지 않습니다[/bold red]")
        console.print("[yellow]💡 edit 명령어는 강의 HTML 파일 전용입니다.[/yellow]")
        return

    # Check Flask is available
    try:
        import flask  # noqa: F401
    except ImportError:
        console.print("\n[bold red]❌ Flask가 설치되어 있지 않습니다[/bold red]")
        console.print("[yellow]설치: pip install flask markdownify[/yellow]")
        raise click.Abort()

    # Check markdownify is available
    try:
        import markdownify  # noqa: F401
    except ImportError:
        console.print("\n[bold red]❌ markdownify가 설치되어 있지 않습니다[/bold red]")
        console.print("[yellow]설치: pip install markdownify[/yellow]")
        raise click.Abort()

    try:
        from lecture_forge.editor.server import run_editor
        run_editor(
            html_path=html_path,
            output_path=output,
            port=port,
            open_browser=not no_browser,
        )
    except OSError as e:
        if "Address already in use" in str(e):
            console.print(f"\n[bold red]❌ 포트 {port}가 이미 사용 중입니다[/bold red]")
            console.print(f"[yellow]다른 포트를 지정하세요: --port <포트번호>[/yellow]")
        else:
            console.print(f"\n[bold red]❌ 서버 오류:[/bold red] {e}")
            logger.error(str(e))
        raise click.Abort()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]편집기가 종료되었습니다.[/yellow]")
