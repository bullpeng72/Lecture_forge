"""
Slide converter for transforming lecture HTML to Reveal.js presentations.
"""

from pathlib import Path
from typing import Optional

from rich.console import Console

from lecture_forge.slides.notes import SlideNotesGenerator
from lecture_forge.slides.parser import HTMLLectureParser
from lecture_forge.slides.templates import RevealJsTemplate
from lecture_forge.utils import logger


class SlideConverter:
    """Converter for transforming lecture HTML into Reveal.js slides."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize slide converter.

        Args:
            console: Rich console for progress display (optional)
        """
        self.parser = HTMLLectureParser()
        self.template = RevealJsTemplate()
        self.console = console or Console()

    def convert(
        self,
        lecture_html_path: Path,
        output_path: Path,
        with_notes: bool = False,
        slide_rewrite: bool = False,
    ) -> bool:
        """Convert lecture HTML to Reveal.js presentation slides.

        Args:
            lecture_html_path: Path to the lecture HTML file
            output_path: Path for the output slides HTML
            with_notes: If True, auto-generate LLM presenter notes for each slide
            slide_rewrite: If True, run per-section LLM rewrite to produce
                           concise, complete bullets (Plan D).

        Returns:
            True if successful, False otherwise
        """
        try:
            self.console.print("\n[cyan]📊 슬라이드 변환 중...[/cyan]")
            self.console.print("   • 서술식 텍스트를 개조식으로 변환합니다...")

            # Parse lecture HTML
            parsed_data = self.parser.parse(lecture_html_path)

            title = parsed_data["title"]
            subtitle = parsed_data["subtitle"]
            sections = parsed_data["sections"]
            converted_paragraphs = parsed_data["converted_paragraphs"]

            # Show progress
            total_sections = len(sections)
            self.console.print(f"   ✅ {total_sections}개 섹션, {converted_paragraphs}개 단락을 개조식으로 변환했습니다.")

            # Optional: per-section slide rewrite (Plan D)
            if slide_rewrite:
                self.console.print(
                    f"   • 섹션별 슬라이드 최적화 중... ({total_sections}개 섹션, LLM 사용)"
                )
                from lecture_forge.slides.section_rewriter import rewrite_sections_for_slides
                sections = rewrite_sections_for_slides(sections)
                self.console.print("   ✅ 슬라이드 최적화 완료")

            # Generate Reveal.js HTML
            self.console.print("   • 슬라이드 HTML 생성 중...")
            slides_html = self.template.generate(title, subtitle, sections)

            # Optionally inject auto-generated presenter notes
            if with_notes:
                self.console.print("   • 발표자 노트 자동 생성 중... (LLM 사용)")
                notes_gen = SlideNotesGenerator()
                slides_html = notes_gen.generate(slides_html)
                self.console.print("   ✅ 발표자 노트 생성 완료 (브라우저에서 S키로 확인)")

            # Write to output file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(slides_html)

            self.console.print(f"   ✅ 슬라이드 생성 완료: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Error converting to slides: {e}")
            self.console.print(f"[red]❌ 슬라이드 변환 실패: {e}[/red]")
            return False
