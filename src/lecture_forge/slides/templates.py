"""
Reveal.js HTML template generator for lecture slides.
"""

import re
from typing import Dict, List

from lecture_forge.config import Config

_MAX_ITEM_CHARS = 80  # hard limit for a rendered list item (plain-text length)


def _render_slide_item(item: str, max_chars: int = _MAX_ITEM_CHARS) -> str:
    """Clean and truncate a list item for on-slide display.

    P1 (template-side): original HTML list items from the lecture source are
    not processed by the LLM bullet-converter, so they may be very long or
    multi-line.  This helper:
      1. Strips embedded newlines (sub-list noise) — take first line only.
      2. Truncates long plain text at a natural boundary (colon, comma, space).
    Inline HTML formatting (<strong>, <em>, <code>) is preserved when the item
    is already within the limit.

    Truncation uses plain-text coordinates but cuts first_html at the
    corresponding HTML position, then closes any unclosed inline tags to
    ensure the output is always valid HTML.
    """
    plain = re.sub(r"<[^>]+>", "", item)
    # For multi-line items keep only the first meaningful line
    first_plain = plain.split("\n")[0].strip()
    first_html = item.split("\n")[0].strip()

    if len(first_plain) <= max_chars:
        return first_html

    # Find cut position in plain-text coordinates
    window = first_plain[:max_chars]
    cut_plain = -1
    sentence_cut = False  # True when cut is at a complete sentence boundary (no "…" needed)

    # Priority 0) Complete sentence boundary: find the last ". " within the window
    #             and return WITHOUT ellipsis — cleaner than a truncated fragment
    last_period = window.rfind(". ")
    if last_period >= max(10, max_chars // 3):
        cut_plain = last_period + 1  # include the period
        sentence_cut = True
    else:
        for sep in (":", "：", ",", "，", " —", " -"):
            pos = window.find(sep)
            if 10 <= pos < max_chars:
                cut_plain = pos + 1
                break

        if cut_plain == -1:
            last_space = window.rfind(" ")
            cut_plain = last_space if last_space > max_chars // 2 else max_chars

    # Translate cut_plain (plain-text chars) → position in first_html
    # by scanning first_html and skipping over HTML tags.
    plain_count = 0
    cut_html = len(first_html)  # fallback: include full string
    i = 0
    while i < len(first_html):
        if first_html[i] == "<":
            end = first_html.find(">", i)
            i = (end + 1) if end != -1 else len(first_html)
        else:
            plain_count += 1
            if plain_count >= cut_plain:
                cut_html = i + 1
                break
            i += 1

    truncated = first_html[:cut_html].rstrip()

    # Close any unclosed inline tags to ensure valid HTML output
    open_tags: List[str] = []
    for m in re.finditer(r"<(/?)([a-z][a-z0-9]*)(?:\s[^>]*)?>", truncated, re.IGNORECASE):
        is_close, name = bool(m.group(1)), m.group(2).lower()
        if name in ("strong", "em", "code", "b", "i", "s", "u"):
            if is_close:
                if open_tags and open_tags[-1] == name:
                    open_tags.pop()
            else:
                open_tags.append(name)

    closing = "".join(f"</{t}>" for t in reversed(open_tags))
    if sentence_cut:
        return truncated + closing  # Complete sentence — no "…"
    return truncated + closing + "…"


class RevealJsTemplate:
    """Generator for Reveal.js presentation HTML."""

    def __init__(self):
        """Initialize Reveal.js template generator."""
        self.max_items_per_slide = Config.MAX_ITEMS_PER_SLIDE or 3
        self.max_bullet_points = 5

    def generate(self, title: str, subtitle: str, sections: List[Dict]) -> str:
        """Generate complete Reveal.js HTML from lecture content.

        Args:
            title: Lecture title
            subtitle: Lecture subtitle
            sections: List of section dictionaries

        Returns:
            Complete HTML string for Reveal.js presentation
        """
        slides_content = []

        # Title slide
        slides_content.append(self._create_title_slide(title, subtitle))

        # Section slides
        for section in sections:
            section_title = section["title"]
            blocks = section["blocks"]

            # Section title slide
            slides_content.append(self._create_section_title_slide(section_title))

            # Content slides
            content_slides = self._create_content_slides(blocks, section_title=section_title)
            slides_content.extend(content_slides)

        # End slide
        slides_content.append(self._create_end_slide())

        # Generate complete HTML
        return self._generate_html_document(title, slides_content)

    def _create_title_slide(self, title: str, subtitle: str) -> str:
        """Create title slide."""
        subtitle_html = f'<p class="subtitle">{subtitle}</p>' if subtitle else ''
        return f"""
    <section data-transition="zoom">
        <h1>{title}</h1>
        {subtitle_html}
        <p><small>LectureForge로 생성됨</small></p>
    </section>
    """

    def _create_section_title_slide(self, section_title: str) -> str:
        """Create section title slide."""
        return f"""
    <section data-transition="convex">
        <h2>{section_title}</h2>
    </section>
        """

    def _create_end_slide(self) -> str:
        """Create end slide."""
        return """
    <section data-transition="zoom">
        <h2>감사합니다!</h2>
        <p>질문이 있으신가요?</p>
        <p><small>LectureForge로 생성됨</small></p>
    </section>
    """

    def _create_content_slides(self, blocks: List[Dict], section_title: str = "") -> List[str]:
        """Create content slides from blocks.

        Args:
            blocks: List of content block dictionaries
            section_title: Title of the enclosing section (used as fallback heading)

        Returns:
            List of slide HTML strings
        """
        slides = []
        current_slide_content = []
        slide_item_count = 0
        current_title = section_title  # tracks the most recent section/subsection title
        _continuation = False  # True after a slide break within a subsection

        for idx, block in enumerate(blocks):
            block_type = block["type"]

            if block_type == "subsection":
                # P1: Save current slide only if it has real content beyond a lone heading
                if current_slide_content:
                    if any(not item.startswith("<h") for item in current_slide_content):
                        slides.append(self._create_content_slide(current_slide_content))
                    current_slide_content = []
                    slide_item_count = 0

                current_title = block["content"]
                _continuation = False  # new subsection resets continuation marker

                # P1: No standalone title slide — pre-inject h3 heading (NOT counted)
                current_slide_content.append(f"<h3>{block['content']}</h3>")

            elif block_type == "subsubsection":
                # h4 acts as slide title - start new slide
                if current_slide_content:
                    if any(not item.startswith("<h") for item in current_slide_content):
                        slides.append(self._create_content_slide(current_slide_content))
                    current_slide_content = []
                    slide_item_count = 0

                current_title = block["content"]
                _continuation = False

                # P3: heading pre-injected, NOT counted toward slide_item_count
                current_slide_content.append(f"<h3>{block['content']}</h3>")

            elif block_type == "paragraph":
                # Inject title if slide would otherwise have no heading
                if not current_slide_content and current_title:
                    # P2: show "(계속)" on continuation slides
                    heading = (
                        f"<h3>{current_title} <span class='slide-cont'>(계속)</span></h3>"
                        if _continuation
                        else f"<h3>{current_title}</h3>"
                    )
                    current_slide_content.append(heading)
                    # P3: heading NOT counted
                current_slide_content.append(f"<p>{block['content']}</p>")
                slide_item_count += 1

            elif block_type == "list":
                # Inject title if slide would otherwise have no heading
                if not current_slide_content and current_title:
                    heading = (
                        f"<h3>{current_title} <span class='slide-cont'>(계속)</span></h3>"
                        if _continuation
                        else f"<h3>{current_title}</h3>"
                    )
                    current_slide_content.append(heading)
                    # P3: heading NOT counted
                list_slides = self._process_list_block(block, current_slide_content, slide_item_count, current_title)
                if list_slides:
                    slides.extend(list_slides)
                    current_slide_content = []
                    slide_item_count = 0
                    _continuation = True
                else:
                    # List added to current slide; count actual items to detect overflow
                    slide_item_count += len(block["items"])

            elif block_type == "code":
                # Code blocks take a full slide
                if current_slide_content:
                    slides.append(self._create_content_slide(current_slide_content))
                    current_slide_content = []
                    slide_item_count = 0

                slides.append(self._create_code_slide(block))

            elif block_type == "image":
                # Images take a full slide
                if current_slide_content:
                    slides.append(self._create_content_slide(current_slide_content))
                    current_slide_content = []
                    slide_item_count = 0

                # P3: fall back to section heading if parser didn't capture a title
                if not block.get("title") and current_title:
                    block = dict(block)
                    block["title"] = current_title
                slides.append(self._create_image_slide(block))

            elif block_type == "diagram":
                # Diagrams take a full slide
                if current_slide_content:
                    slides.append(self._create_content_slide(current_slide_content))
                    current_slide_content = []
                    slide_item_count = 0

                slides.append(self._create_diagram_slide(block))

            # Check if we should start a new slide
            should_break = slide_item_count >= self.max_items_per_slide

            # Don't break if next item is closely related
            if should_break and idx + 1 < len(blocks):
                next_block = blocks[idx + 1]
                if next_block["type"] in ["subsection", "subsubsection", "code", "image", "diagram"]:
                    should_break = False

            if should_break and current_slide_content:
                slides.append(self._create_content_slide(current_slide_content))
                current_slide_content = []
                slide_item_count = 0
                _continuation = True  # P2: next slide is a continuation

        # Add remaining content
        if current_slide_content:
            slides.append(self._create_content_slide(current_slide_content))

        return slides

    def _process_list_block(
        self,
        block: Dict,
        current_slide_content: List[str],
        slide_item_count: int,
        current_title: str = "",
    ) -> List[str]:
        """Process list block, potentially splitting into multiple slides.

        P2 fix: pre-check remaining capacity BEFORE adding items, so slides
        never exceed max_items_per_slide regardless of list length.

        Returns:
            List of slide HTML strings if list was split, empty list otherwise.
            When empty, items have already been appended to current_slide_content.
        """
        list_items = block["items"]
        list_tag = "ol" if block.get("ordered", False) else "ul"
        max_items = self.max_items_per_slide

        # Remaining capacity on the current slide
        remaining_capacity = max(0, max_items - slide_item_count)

        # Fits entirely on the current slide — add in-place, no new slide needed
        if len(list_items) <= remaining_capacity:
            items_html = "".join(f"<li>{_render_slide_item(item)}</li>" for item in list_items)
            current_slide_content.append(f"<{list_tag}>{items_html}</{list_tag}>")
            return []

        # Needs split — gather any real (non-heading) content first
        slides = []
        has_non_heading = any(not item.startswith("<h") for item in current_slide_content)
        if current_slide_content and has_non_heading:
            # Commit the existing slide with whatever it has
            slides.append(self._create_content_slide(current_slide_content))
            prefix_headings: List[str] = []
        else:
            # Only headings in current_slide_content — reuse them as the
            # first chunk's heading instead of creating a heading-only slide
            prefix_headings = list(current_slide_content)

        # Pre-compute all chunks of max_items each
        all_chunks: List[List[str]] = [
            list_items[i : i + max_items]
            for i in range(0, len(list_items), max_items)
        ]

        # Merge last wimpy chunk into the previous one to avoid sparse "(계속)" slides.
        # e.g. with max=6: [6, 1] → [7], [6, 6, 2] → [6, 8]
        _MIN_LAST_CHUNK = 3
        if len(all_chunks) >= 2 and len(all_chunks[-1]) < _MIN_LAST_CHUNK:
            all_chunks[-2] = all_chunks[-2] + all_chunks[-1]
            all_chunks.pop()

        for chunk_idx, chunk in enumerate(all_chunks):
            items_html = "".join(f"<li>{_render_slide_item(item)}</li>" for item in chunk)

            chunk_content: List[str] = []
            if chunk_idx == 0 and prefix_headings:
                # Use the pre-injected heading(s) for the first chunk
                chunk_content.extend(prefix_headings)
            elif current_title:
                # Continuation chunk — add (계속) marker
                chunk_content.append(
                    f"<h3>{current_title} <span class='slide-cont'>(계속)</span></h3>"
                )
            chunk_content.append(f"<{list_tag}>{items_html}</{list_tag}>")
            slides.append(self._create_content_slide(chunk_content))

        return slides

    def _create_content_slide(self, content_items: List[str]) -> str:
        """Create a content slide from HTML elements.

        P5: Automatically adds a density CSS class based on bullet count.
        - slide-dense  (4+ items) → smaller font / tighter line-height
        - slide-sparse (0 items)  → larger font
        """
        combined = "".join(content_items)
        li_count = combined.count("<li>")
        if li_count >= 4:
            density_class = ' class="slide-dense"'
        elif li_count == 0 and "<ul>" not in combined and "<ol>" not in combined:
            density_class = ' class="slide-sparse"'
        else:
            density_class = ""
        return f"""
    <section{density_class}>
{combined}
    </section>
    """

    def _create_code_slide(self, block: Dict) -> str:
        """Create code slide."""
        language = block.get("language", "python")
        code_title = "코드 예제" if language == "python" else f"{language.upper()} 코드"
        return f"""
    <section>
        <h3>{code_title}</h3>
        <pre><code class="language-{language}" data-trim data-noescape>
{block['content']}
        </code></pre>
    </section>
                """

    def _create_image_slide(self, block: Dict) -> str:
        """Create image slide.

        P3: Renders the block's 'title' field (preceding heading from parser)
        above the image so the audience sees context.
        Image is center-aligned via .slide-img-wrap flex container.
        """
        title = block.get("title", "")
        caption = block.get("caption", "")
        title_html = f"        <h3>{title}</h3>\n" if title else ""
        caption_html = f"        <p><small>{caption}</small></p>\n" if caption else ""
        return f"""
    <section>
{title_html}        <div class="slide-img-wrap">
            <img src="{block['src']}" alt="{block['alt']}" style="max-height: 420px; max-width: 90%; object-fit: contain;">
        </div>
{caption_html}    </section>
                """

    def _create_diagram_slide(self, block: Dict) -> str:
        """Create diagram slide."""
        mermaid_code = block["content"].strip()
        return f"""
    <section>
        <div class="mermaid">
{mermaid_code}
        </div>
    </section>
                """

    def _generate_html_document(self, title: str, slides_content: List[str]) -> str:
        """Generate complete HTML document with slides.

        Args:
            title: Lecture title
            slides_content: List of slide HTML strings

        Returns:
            Complete HTML document string
        """
        return f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - 슬라이드</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.5.0/reveal.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.5.0/theme/white.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.5.0/plugin/highlight/monokai.min.css">
    <style>
{self._get_css_styles()}
    </style>
</head>
<body>
    <div class="reveal">
        <div class="slides">
{''.join(slides_content)}
        </div>
    </div>

    <!-- 라이트박스 모달 -->
    <div id="slide-lightbox" role="dialog" aria-modal="true" aria-label="이미지 확대 보기">
        <button id="slide-lightbox-close" aria-label="닫기">✕</button>
        <div id="slide-lightbox-inner"></div>
        <p id="slide-lightbox-caption"></p>
    </div>

{self._get_javascript()}
</body>
</html>
    """

    def _get_css_styles(self) -> str:
        """Get CSS styles for presentation."""
        return """        /* 한국어 폰트 및 스타일 */
        .reveal {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Malgun Gothic", "맑은 고딕", "Apple SD Gothic Neo", sans-serif;
        }
        .reveal h1, .reveal h2, .reveal h3, .reveal h4 {
            text-transform: none;
            font-weight: bold;
            margin-bottom: 0.8em;
        }
        .reveal h1 {
            font-size: 2.5em;
        }
        .reveal h2 {
            font-size: 2em;
            color: #2c3e50;
        }
        .reveal h3 {
            font-size: 1.6em;
            color: #34495e;
            margin-top: 0.5em;
        }
        .reveal h4 {
            font-size: 1.3em;
            color: #7f8c8d;
        }
        .reveal p {
            text-align: left;
            line-height: 1.8;
            font-size: 0.9em;
            margin: 0.6em 0;
        }
        .reveal ul, .reveal ol {
            text-align: left;
            line-height: 2.2;
            font-size: 0.85em;
            margin: 1em 0;
        }
        .reveal li {
            margin: 0.8em 0;
        }
        .reveal ul li::marker {
            color: #3498db;
            font-size: 1.2em;
        }
        .reveal em {
            color: #95a5a6;
            font-style: italic;
        }
        .reveal pre {
            width: 100%;
            font-size: 0.5em;
            margin: 1.5em 0;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            max-height: 550px;
            overflow-y: auto;
        }
        .reveal code {
            max-height: 520px;
            font-family: "Monaco", "Menlo", "Consolas", "Courier New", monospace;
            line-height: 1.5;
            padding: 1.5em;
        }
        .reveal .slides section {
            text-align: left;
            padding: 40px 50px;
            box-sizing: border-box;
        }
        /* Center-aligned slides: title (zoom) and section headers (convex) */
        .reveal .slides section[data-transition="zoom"],
        .reveal .slides section[data-transition="convex"] {
            text-align: center;
        }
        /* 계속 슬라이드 표시 (P4: 눈에 띄는 스타일) */
        .reveal .slide-cont {
            font-size: 0.7em;
            color: #e74c3c;
            font-weight: bold;
            font-style: normal;
            margin-left: 0.5em;
            background: rgba(231, 76, 60, 0.1);
            padding: 0.15em 0.45em;
            border-radius: 4px;
            vertical-align: middle;
        }
        /* 슬라이드 밀도 조정 (P5) */
        .reveal .slides section.slide-dense {
            font-size: 0.85em;
        }
        .reveal .slides section.slide-dense ul,
        .reveal .slides section.slide-dense ol {
            line-height: 2.0;
            margin: 0.5em 0;
        }
        .reveal .slides section.slide-dense li {
            margin: 0.4em 0;
        }
        .reveal .slides section.slide-sparse p {
            font-size: 1.0em;
            line-height: 2.0;
        }
        /* Mermaid 다이어그램 */
        .reveal .mermaid {
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            overflow: auto;
            /* align-items: flex-start 때문에 수축하는 것을 막고 슬라이드 전체 폭 사용 */
            width: 100%;
            box-sizing: border-box;
            /* 높이는 viewBox 비율로 자동 결정되도록 max-height 제거 */
        }
        /* 코드 블록 스크롤바 */
        .reveal pre::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        .reveal pre::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.3);
            border-radius: 3px;
        }
        /* 이미지 슬라이드 중앙 정렬 wrapper */
        .reveal .slide-img-wrap {
            display: flex;
            justify-content: center;
            align-items: center;
            width: 100%;
            margin: auto 0;
        }
        /* 클릭 가능한 이미지·다이어그램 커서 */
        .reveal .slides img.zoomable,
        .reveal .mermaid.zoomable {
            cursor: zoom-in;
        }
        /* 라이트박스 모달 */
        #slide-lightbox {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.88);
            z-index: 9999;
            align-items: center;
            justify-content: center;
            flex-direction: column;
        }
        #slide-lightbox.open {
            display: flex;
        }
        #slide-lightbox-close {
            position: fixed;
            top: 18px;
            right: 24px;
            background: none;
            border: none;
            color: #fff;
            font-size: 2rem;
            cursor: pointer;
            line-height: 1;
            z-index: 10000;
        }
        #slide-lightbox-inner {
            max-width: min(92vw, 1400px);
            max-height: 88vh;
            overflow: auto;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        #slide-lightbox-inner img {
            max-width: 100%;
            max-height: 85vh;
            object-fit: contain;
            border-radius: 4px;
            cursor: default;
        }
        #slide-lightbox-inner .lightbox-svg {
            background: #ffffff;
            padding: 28px 32px;
            border-radius: 10px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            max-width: min(88vw, 1300px);
            display: flex;
            align-items: center;
            justify-content: center;
        }
        #slide-lightbox-inner .lightbox-svg svg {
            width: min(82vw, 1240px) !important;
            height: auto !important;
        }
        #slide-lightbox-caption {
            color: #ccc;
            font-size: 0.85rem;
            margin-top: 10px;
            max-width: 80vw;
            text-align: center;
        }"""

    def _get_javascript(self) -> str:
        """Get JavaScript for Reveal.js initialization."""
        return """    <script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.5.0/reveal.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.5.0/plugin/highlight/highlight.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.5.0/plugin/markdown/markdown.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.5.0/plugin/notes/notes.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script>
        // Reveal.js 초기화
        Reveal.initialize({
            hash: true,
            transition: 'slide',
            plugins: [ RevealHighlight, RevealMarkdown, RevealNotes ],
            slideNumber: 'c/t',
            controls: true,
            progress: true,
            center: false,
            mouseWheel: false,
            width: 1280,
            height: 720,
            margin: 0.04,
            minScale: 0.2,
            maxScale: 2.0,
        }).then(() => {
            // Mermaid 초기화 (Mermaid 10 API)
            mermaid.initialize({
                startOnLoad: false,  // Reveal.js와 충돌 방지; 슬라이드 표시 시 수동 실행
                theme: 'default',
                securityLevel: 'loose',
                // useMaxWidth: true → SVG가 컨테이너 폭을 꽉 채우도록 허용
                flowchart:    { useMaxWidth: true, htmlLabels: true, curve: 'basis' },
                sequence:     { useMaxWidth: true },
                gantt:        { useMaxWidth: true },
                classDiagram: { useMaxWidth: true },
                stateDiagram: { useMaxWidth: true },
            });

            // 현재 슬라이드의 Mermaid 다이어그램만 렌더링 (display:none 문제 방지)
            function renderCurrentSlideMermaid() {
                const currentSlide = Reveal.getCurrentSlide();
                if (!currentSlide) return;

                const mermaidDivs = currentSlide.querySelectorAll('.mermaid:not([data-processed="true"])');
                if (mermaidDivs.length > 0) {
                    mermaid.run({ nodes: mermaidDivs });
                }
            }

            // 초기 슬라이드 렌더링
            renderCurrentSlideMermaid();

            // 슬라이드 전환 시 새 슬라이드의 Mermaid 렌더링
            Reveal.on('slidechanged', function() {
                renderCurrentSlideMermaid();
            });

            // ── 라이트박스 ────────────────────────────────────────────
            const lb        = document.getElementById('slide-lightbox');
            const lbInner   = document.getElementById('slide-lightbox-inner');
            const lbCaption = document.getElementById('slide-lightbox-caption');
            const lbClose   = document.getElementById('slide-lightbox-close');

            function openSlideLightbox(innerHtml, caption) {
                lbInner.innerHTML = '';
                lbInner.insertAdjacentHTML('beforeend', innerHtml);
                lbCaption.textContent = caption || '';
                lb.classList.add('open');
                document.body.style.overflow = 'hidden';
                // Reveal.js 키보드 탐색 일시 중지
                Reveal.configure({ keyboard: false });
            }

            function closeSlideLightbox() {
                lb.classList.remove('open');
                lbInner.innerHTML = '';
                document.body.style.overflow = '';
                // Reveal.js 키보드 탐색 복원
                Reveal.configure({ keyboard: true });
            }

            lbClose.addEventListener('click', closeSlideLightbox);
            lb.addEventListener('click', function(e) { if (e.target === lb) closeSlideLightbox(); });
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape' && lb.classList.contains('open')) {
                    e.stopImmediatePropagation();
                    closeSlideLightbox();
                }
            }, true); // capture phase - ESC 먼저 가로채서 Reveal.js 슬라이드 전환 방지

            // 이미지 클릭 핸들러 (section > img - figure 없음)
            document.querySelectorAll('.reveal .slides img').forEach(function(img) {
                img.classList.add('zoomable');
                img.addEventListener('click', function() {
                    var caption = img.alt || img.closest('section')?.querySelector('p small')?.innerText || '';
                    openSlideLightbox('<img src="' + img.src + '" alt="' + (img.alt || '') + '">', caption);
                });
            });

            // Mermaid 다이어그램 클릭 핸들러 (비동기 렌더링 대응)
            function attachDiagramClicks() {
                document.querySelectorAll('.reveal .mermaid').forEach(function(div) {
                    var svgEl = div.querySelector('svg');
                    if (svgEl && !div.dataset.lightboxReady) {
                        div.dataset.lightboxReady = '1';
                        div.classList.add('zoomable');
                        div.addEventListener('click', function() {
                            var svg = div.querySelector('svg');
                            if (!svg) return;
                            var cloned = svg.cloneNode(true);
                            cloned.style.maxWidth = '';
                            cloned.setAttribute('width', '100%');
                            cloned.removeAttribute('height');
                            var wrapper = document.createElement('div');
                            wrapper.className = 'lightbox-svg';
                            wrapper.appendChild(cloned);
                            lbInner.innerHTML = '';
                            lbInner.appendChild(wrapper);
                            lbCaption.textContent = '';
                            lb.classList.add('open');
                            document.body.style.overflow = 'hidden';
                            Reveal.configure({ keyboard: false });
                        });
                    }
                });
            }
            attachDiagramClicks();
            [500, 1200, 2500].forEach(function(ms) { setTimeout(attachDiagramClicks, ms); });

            // 슬라이드 전환 시 다이어그램 클릭 핸들러 재부착 (지연 렌더링 대응)
            Reveal.on('slidechanged', function() { setTimeout(attachDiagramClicks, 400); });
            // ─────────────────────────────────────────────────────────
        });
    </script>"""
