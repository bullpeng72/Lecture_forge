"""
Content Enhancer Agent - KB 기반 기존 강의 콘텐츠 보충 (v0.5.2).
"""

import re
from pathlib import Path
from typing import Optional

import markdown
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table

from lecture_forge.agents.content_writer import ContentWriterAgent
from lecture_forge.quality.evaluator import QualityEvaluator
from lecture_forge.utils.html_parser import parse_html_to_lecture
from lecture_forge.config import Config

console = Console()
from lecture_forge.exceptions import ConfigurationError
from lecture_forge.knowledge.vector_store import VectorStore
from lecture_forge.models.curriculum import Curriculum, Section
from lecture_forge.models.lecture import Lecture
from lecture_forge.utils import logger

_THRESHOLD_MAP = {"lenient": 70, "balanced": 80, "strict": 90}


_DIMENSION_LABELS = {
    "content_completeness": "콘텐츠 완성도",
    "logical_flow": "논리적 흐름",
    "time_alignment": "시간 구성",
    "level_appropriateness": "난이도 적합성",
    "visual_quality": "시각적 품질",
    "technical_accuracy": "기술 정확도",
}


def _display_evaluation_table(evaluation) -> None:
    """Rich 테이블로 6차원 평가 결과 출력."""
    table = Table(title="📊 품질 평가 결과", show_header=True, header_style="bold cyan")
    table.add_column("항목", style="bold")
    table.add_column("점수", justify="right")
    table.add_column("상태", justify="center")

    # 종합 점수 먼저
    score = evaluation.overall_score
    status = "✅" if score >= 80 else ("⚠️" if score >= 60 else "❌")
    table.add_row("종합 점수", f"{score:.1f}", status)

    # 6개 차원 점수
    for key, label in _DIMENSION_LABELS.items():
        score = evaluation.dimension_scores.get(key)
        if score is None:
            continue
        status = "✅" if score >= 80 else ("⚠️" if score >= 60 else "❌")
        table.add_row(label, f"{score:.1f}", status)

    console.print(table)
    console.print()


class ContentEnhancer:
    """v0.5.2: KB 기반 기존 강의 콘텐츠 보충 에이전트."""

    def enhance(
        self,
        html_path: Path,
        quality_level: str = "balanced",
        kb_path: Optional[str] = None,
    ) -> Optional[str]:
        """
        메인 진입점.

        Args:
            html_path: 기존 강의 HTML 경로
            quality_level: 품질 기준 (lenient/balanced/strict)
            kb_path: KB 경로 (HTML 메타데이터 없을 때 fallback)

        Returns:
            *_enhanced.html 경로 (실패 시 None)
        """
        try:
            # ① 메타데이터 추출
            meta = self._extract_html_metadata(html_path)
            vdb_path = meta.get("vector_db_path") or kb_path

            if not vdb_path:
                console.print(
                    "[red]❌ KB 경로를 찾을 수 없습니다.[/red]\n"
                    "   HTML에 메타데이터가 없으면 --kb 옵션으로 경로를 지정하세요.\n"
                    "   예: --kb ~/Documents/LectureForge/data/vector_db/MyTopic_..."
                )
                return None

            console.print(f"[dim]📂 KB 경로: {vdb_path}[/dim]")

            # ② VectorStore 로드 (qa_agent.py 패턴 동일: 디렉터리 이름만 collection_name으로 전달)
            try:
                collection_name = Path(vdb_path).name
                vector_store = VectorStore(collection_name=collection_name)
            except Exception as e:
                console.print(f"[red]❌ VectorStore 로드 실패: {e}[/red]")
                return None

            # ③ Lecture 재구성 + 메타데이터 보정
            with console.status("[bold green]HTML 파싱 중..."):
                lecture = parse_html_to_lecture(str(html_path))

            if not lecture:
                console.print("[red]❌ HTML 파싱 실패[/red]")
                return None

            lecture.topic = meta.get("topic") or lecture.topic
            if meta.get("duration"):
                try:
                    lecture.duration = int(meta["duration"])
                except ValueError:
                    pass
            lecture.audience_level = meta.get("audience_level") or lecture.audience_level
            lecture.vector_db_path = vdb_path

            console.print(f"[dim]📖 강의: {lecture.topic} ({lecture.duration}분, {lecture.audience_level})[/dim]")

            # ④ 품질 평가
            threshold = _THRESHOLD_MAP.get(quality_level, 80)
            with console.status("[bold green]품질 평가 중..."):
                evaluation = QualityEvaluator().evaluate(lecture, threshold=threshold)

            _display_evaluation_table(evaluation)

            if evaluation.overall_score >= threshold:
                console.print(f"[green]✅ 품질 기준 충족 ({evaluation.overall_score:.1f} ≥ {threshold})[/green]")
                console.print("   보강이 필요하지 않지만 KB sweep을 계속 진행합니다.")
                console.print()

            # ⑤ Curriculum 재구성
            curriculum = self._lecture_to_curriculum(lecture)

            # ⑥ ContentWriterAgent 초기화 + 청크 pre-assign
            writer = ContentWriterAgent(vector_store=vector_store)
            original_lengths = {
                sc.section_id: len(sc.markdown_content)
                for sc in lecture.sections
            }

            with console.status("[bold green]KB 청크 배분 중..."):
                writer._pre_assign_chunks_to_sections(curriculum)

            # ⑦ 최대 2라운드 coverage sweep
            try:
                total_chunks = int(vector_store.get_total_chunk_count())
            except (TypeError, ValueError):
                total_chunks = 0

            if total_chunks > 0:
                for _round in range(2):
                    ratio = len(writer.used_chunk_ids) / max(1, total_chunks)
                    if ratio >= Config.RAG_COVERAGE_MIN_RATIO:
                        break
                    with console.status(f"[bold green]Coverage sweep 라운드 {_round + 1}/2..."):
                        writer._expand_sections_for_coverage(lecture.sections, curriculum)

            # ⑧ 보충 diff 추출
            enhancements = {
                sc.section_id: sc.markdown_content[original_lengths[sc.section_id]:].strip()
                for sc in lecture.sections
                if len(sc.markdown_content) > original_lengths[sc.section_id]
            }

            if not enhancements:
                console.print("[yellow]ℹ️  추가할 보충 내용이 없습니다 (KB가 이미 충분히 반영됨)[/yellow]")
                return None

            enhanced_count = sum(1 for v in enhancements.values() if v)
            console.print(f"[dim]💡 {enhanced_count}개 섹션에 보충 내용 추가[/dim]")

            # ⑨⑩ HTML 직접 수정 + 저장
            output_path = html_path.parent / f"{html_path.stem}_enhanced.html"
            self._inject_enhancements_to_html(html_path, enhancements, output_path)

            return str(output_path)

        except ConfigurationError as e:
            console.print(f"[red]❌ 설정 오류: {e}[/red]")
            return None
        except Exception as e:
            logger.error(f"ContentEnhancer.enhance() failed: {e}", exc_info=True)
            console.print(f"[red]❌ 보강 중 오류: {e}[/red]")
            return None

    def _extract_html_metadata(self, html_path: Path) -> dict:
        """<!-- lf:xxx: yyy --> 주석 파싱."""
        meta = {
            "vector_db_path": "",
            "topic": "",
            "duration": "",
            "audience_level": "",
        }
        try:
            content = html_path.read_text(encoding="utf-8")
            pattern = re.compile(r"<!--\s*lf:(\w+):\s*(.*?)\s*-->")
            for match in pattern.finditer(content):
                key, value = match.group(1), match.group(2).strip()
                if key in meta:
                    meta[key] = value
        except Exception as e:
            logger.debug(f"HTML metadata extraction failed: {e}")
        return meta

    def _lecture_to_curriculum(self, lecture: Lecture) -> Curriculum:
        """Lecture.sections → Curriculum + Section 리스트 재구성."""
        sections = []
        per_section = max(10, lecture.duration // max(1, len(lecture.sections))) if lecture.sections else 20

        for sc in lecture.sections:
            sections.append(
                Section(
                    id=sc.section_id,
                    title=sc.title,
                    topics=[sc.title],
                    estimated_time=sc.estimated_time or per_section,
                    difficulty_level=sc.difficulty_level or "intermediate",
                    learning_outcomes=[],
                )
            )

        return Curriculum(
            topic=lecture.topic,
            duration=lecture.duration,
            audience_level=lecture.audience_level,
            learning_objectives=lecture.learning_objectives,
            sections=sections,
            total_estimated_time=lecture.duration,
        )

    def _inject_enhancements_to_html(
        self,
        html_path: Path,
        enhancements: dict,
        output_path: Path,
    ) -> None:
        """BeautifulSoup으로 section별 보충 markdown → HTML 변환 후 말미 삽입."""
        html_content = html_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html_content, "html.parser")

        _md_extensions = ["extra", "fenced_code", "tables", "nl2br", "sane_lists"]

        injected = 0
        for section_id, supplement_md in enhancements.items():
            if not supplement_md:
                continue

            section_elem = soup.find("section", id=section_id)
            if not section_elem:
                # Try sanitized ID (strip non-ASCII)
                safe_id = re.sub(r"[^\x00-\x7F]", "", section_id)
                safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", safe_id)
                safe_id = re.sub(r"_+", "_", safe_id).strip("_") or "section"
                section_elem = soup.find("section", id=safe_id)

            if not section_elem:
                logger.debug(f"Section element not found for id={section_id!r}")
                continue

            # Convert supplement markdown to HTML
            supp_html = markdown.markdown(supplement_md, extensions=_md_extensions)

            enhancement_div = soup.new_tag("div", **{"class": "lf-enhanced-content"})
            enhancement_div["style"] = (
                "border-top: 2px dashed #a3bffa; margin-top: 2rem; padding-top: 1.5rem;"
            )
            # Header label
            label = soup.new_tag("p")
            label["style"] = "font-size:0.8rem; color:#6b7280; margin-bottom:0.5rem;"
            label.string = "📎 KB 보충 내용 (v0.5.2)"
            enhancement_div.append(label)

            inner = BeautifulSoup(supp_html, "html.parser")
            enhancement_div.append(inner)

            section_elem.append(enhancement_div)
            injected += 1

        stats = self._compute_updated_stats(soup)
        self._update_stats_in_html(soup, stats)

        output_path.write_text(str(soup), encoding="utf-8")
        logger.info(
            f"✅ Enhanced HTML saved: {output_path} "
            f"({injected} sections | {stats['total_words']:,}단어)"
        )

    def _compute_updated_stats(self, soup) -> dict:
        """보강 완료 soup에서 통계 재계산."""
        from datetime import datetime as _dt

        total_words = sum(
            len(sec.get_text(" ", strip=True).split())
            for sec in soup.find_all("section", id=True)
        )
        total_images = len(soup.find_all("img"))
        total_diagrams = len(soup.find_all("div", class_="mermaid"))
        return {
            "total_words": total_words,
            "total_images": total_images,
            "total_diagrams": total_diagrams,
            "updated_at": _dt.now().strftime("%Y-%m-%d %H:%M"),
        }

    def _update_stats_in_html(self, soup, stats: dict) -> None:
        """사이드바·헤더 배지·푸터의 통계 수치를 재계산값으로 교체."""
        from bs4 import NavigableString

        words = stats["total_words"]
        images = stats["total_images"]
        diagrams = stats["total_diagrams"]
        updated_at = stats["updated_at"]

        # ① 사이드바
        sidebar = soup.find("aside", id="sidebar")
        if sidebar:
            stat_div = sidebar.find("div", class_=lambda c: c and "space-y-1" in c)
            if stat_div:
                for div in stat_div.find_all("div", recursive=False):
                    t = div.get_text()
                    if "📝" in t:
                        div.string = f"📝 {words:,}단어"
                    elif "🖼" in t:
                        div.string = f"🖼 이미지 {images}개"
                    elif "📊" in t:
                        div.string = f"📊 다이어그램 {diagrams}개"
                    elif "🕐" in t:
                        div.string = f"🕐 {updated_at}"

        # ② 헤더 배지
        header = soup.find("header")
        if header:
            for span in header.find_all("span"):
                cls = " ".join(span.get("class", []))
                t = span.get_text()
                if "bg-green-100" in cls and "📝" in t:
                    span.string = f"📝 {words:,}단어"
                elif "bg-yellow-100" in cls and "🖼" in t:
                    span.string = f"🖼 이미지 {images}개"
                elif "bg-red-100" in cls and "📊" in t:
                    span.string = f"📊 다이어그램 {diagrams}개"

        # ③ 푸터
        footer = soup.find("footer")
        if footer:
            for p in footer.find_all("p"):
                if "LectureForge" in p.get_text():
                    for child in list(p.children):
                        if isinstance(child, NavigableString) and "·" in child:
                            child.replace_with(f" · {updated_at}")
                    break
