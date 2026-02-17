"""
Reveal.js HTML template generator for lecture slides.
"""

from typing import Dict, List

from lecture_forge.config import Config


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

        for idx, block in enumerate(blocks):
            block_type = block["type"]

            if block_type == "subsection":
                # Subsection starts a new slide
                if current_slide_content:
                    slides.append(self._create_content_slide(current_slide_content))
                    current_slide_content = []
                    slide_item_count = 0

                current_title = block["content"]

                # Create dedicated title slide for subsection
                slides.append(
                    f"""
    <section data-transition="slide">
        <h2>{block['content']}</h2>
    </section>
                    """
                )

            elif block_type == "subsubsection":
                # h4 acts as slide title - start new slide
                if current_slide_content:
                    slides.append(self._create_content_slide(current_slide_content))
                    current_slide_content = []
                    slide_item_count = 0

                current_title = block["content"]

                # Add h4 as slide title
                current_slide_content.append(f"<h3>{block['content']}</h3>")
                slide_item_count += 1

            elif block_type == "paragraph":
                # Inject title if slide would otherwise have no heading
                if not current_slide_content and current_title:
                    current_slide_content.append(f"<h3>{current_title}</h3>")
                    slide_item_count += 1
                current_slide_content.append(f"<p>{block['content']}</p>")
                slide_item_count += 1

            elif block_type == "list":
                # Inject title if slide would otherwise have no heading
                if not current_slide_content and current_title:
                    current_slide_content.append(f"<h3>{current_title}</h3>")
                    slide_item_count += 1
                list_slides = self._process_list_block(block, current_slide_content, slide_item_count)
                if list_slides:
                    slides.extend(list_slides)
                    current_slide_content = []
                    slide_item_count = 0
                else:
                    # List added to current slide
                    slide_item_count += 1

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

        # Add remaining content
        if current_slide_content:
            slides.append(self._create_content_slide(current_slide_content))

        return slides

    def _process_list_block(self, block: Dict, current_slide_content: List[str], slide_item_count: int) -> List[str]:
        """Process list block, potentially splitting into multiple slides.

        Returns:
            List of slide HTML strings if list was split, empty list otherwise
        """
        list_items = block["items"]
        list_tag = "ol" if block.get("ordered", False) else "ul"

        # If list is too long, split it
        if len(list_items) > self.max_bullet_points:
            slides = []

            # If current slide has content, finish it first
            if current_slide_content:
                slides.append(self._create_content_slide(current_slide_content))

            # Split list into chunks
            for i in range(0, len(list_items), self.max_bullet_points):
                chunk = list_items[i : i + self.max_bullet_points]
                items_html = "".join(f"<li>{item}</li>" for item in chunk)
                chunk_content = [f"<{list_tag}>{items_html}</{list_tag}>"]

                # Add continuation indicator if needed
                if i + self.max_bullet_points < len(list_items):
                    chunk_content.append("<p><em>(계속...)</em></p>")

                slides.append(self._create_content_slide(chunk_content))

            return slides
        else:
            # Short list - add to current slide
            items_html = "".join(f"<li>{item}</li>" for item in list_items)
            current_slide_content.append(f"<{list_tag}>{items_html}</{list_tag}>")
            return []

    def _create_content_slide(self, content_items: List[str]) -> str:
        """Create a content slide from HTML elements.

        Args:
            content_items: List of HTML strings

        Returns:
            Complete section HTML
        """
        return f"""
    <section>
{''.join(content_items)}
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
        """Create image slide."""
        caption = block.get("caption", "")
        caption_html = f'<p><small>{caption}</small></p>' if caption else ''
        return f"""
    <section>
        <img src="{block['src']}" alt="{block['alt']}" style="max-height: 500px; max-width: 90%;">
        {caption_html}
    </section>
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
        }
        .reveal code {
            max-height: 520px;
            font-family: "Monaco", "Menlo", "Consolas", "Courier New", monospace;
            line-height: 1.5;
            padding: 1.5em;
        }
        .reveal .slides section {
            text-align: left;
            height: auto !important;
            max-height: 700px;
            overflow-y: auto;
            overflow-x: hidden;
            padding: 40px 50px;
            box-sizing: border-box;
            display: flex !important;
            flex-direction: column;
            justify-content: flex-start;
            align-items: flex-start;
        }
        /* Center-aligned slides (title, subsection) */
        .reveal .slides section[data-transition="zoom"],
        .reveal .slides section[data-transition="slide"] {
            justify-content: center;
            align-items: center;
            text-align: center;
        }
        .reveal .slides section[data-transition="zoom"] {
            text-align: center;
        }
        /* 스크롤바 스타일 (WebKit) */
        .reveal .slides section::-webkit-scrollbar {
            width: 8px;
        }
        .reveal .slides section::-webkit-scrollbar-track {
            background: rgba(0, 0, 0, 0.1);
            border-radius: 4px;
        }
        .reveal .slides section::-webkit-scrollbar-thumb {
            background: rgba(0, 0, 0, 0.3);
            border-radius: 4px;
        }
        .reveal .slides section::-webkit-scrollbar-thumb:hover {
            background: rgba(0, 0, 0, 0.5);
        }
        /* Firefox 스크롤바 */
        .reveal .slides section {
            scrollbar-width: thin;
            scrollbar-color: rgba(0, 0, 0, 0.3) rgba(0, 0, 0, 0.1);
        }
        /* Mermaid 다이어그램 */
        .reveal .mermaid {
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            max-height: 600px;
            overflow: auto;
        }
        /* 코드 블록 스크롤 */
        .reveal pre {
            max-height: 550px;
            overflow-y: auto;
        }
        .reveal pre::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        .reveal pre::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.3);
            border-radius: 3px;
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
            display: 'block',
            scrollActivationWidth: null,
        }).then(() => {
            // Mermaid 초기화
            mermaid.initialize({
                startOnLoad: true,
                theme: 'default',
                securityLevel: 'loose',
                flowchart: {
                    useMaxWidth: true,
                    htmlLabels: true,
                    curve: 'basis'
                }
            });
            mermaid.contentLoaded();

            // 스크롤 인디케이터 관리
            const updateScrollIndicator = (section) => {
                if (!section) return;

                // 기존 인디케이터 제거
                const oldIndicator = section.querySelector('.scroll-indicator');
                if (oldIndicator) {
                    oldIndicator.remove();
                }

                // 스크롤 필요 여부 확인
                const needsScroll = section.scrollHeight > (section.clientHeight + 20);

                if (needsScroll) {
                    const indicator = document.createElement('div');
                    indicator.className = 'scroll-indicator';
                    indicator.innerHTML = '↓ 아래로 스크롤하세요 ↓';
                    indicator.style.cssText = `
                        position: fixed;
                        bottom: 40px;
                        left: 50%;
                        transform: translateX(-50%);
                        background: rgba(0, 0, 0, 0.7);
                        color: white;
                        padding: 8px 16px;
                        border-radius: 20px;
                        font-size: 0.8em;
                        animation: pulse 2s infinite;
                        pointer-events: none;
                        z-index: 1000;
                        transition: opacity 0.3s;
                    `;
                    document.body.appendChild(indicator);

                    // 스크롤 시 인디케이터 처리
                    const scrollHandler = () => {
                        const scrollPercent = (section.scrollTop / (section.scrollHeight - section.clientHeight)) * 100;
                        if (scrollPercent > 5) {
                            indicator.style.opacity = '0';
                        } else {
                            indicator.style.opacity = '1';
                        }

                        if (scrollPercent > 95) {
                            indicator.remove();
                            section.removeEventListener('scroll', scrollHandler);
                        }
                    };

                    section.addEventListener('scroll', scrollHandler);

                    const cleanup = () => {
                        indicator.remove();
                        section.removeEventListener('scroll', scrollHandler);
                    };

                    section.dataset.cleanupIndicator = 'registered';
                    Reveal.on('slidechanged', cleanup);
                }
            };

            // 슬라이드 변경 시 처리
            Reveal.on('slidechanged', event => {
                event.currentSlide.scrollTop = 0;
                document.querySelectorAll('.scroll-indicator').forEach(ind => ind.remove());
                setTimeout(() => {
                    updateScrollIndicator(event.currentSlide);
                }, 100);
            });

            // 초기 슬라이드 인디케이터
            Reveal.on('ready', () => {
                setTimeout(() => {
                    const currentSlide = Reveal.getCurrentSlide();
                    updateScrollIndicator(currentSlide);
                }, 300);
            });
        });

        // 펄스 애니메이션
        const style = document.createElement('style');
        style.textContent = `
            @keyframes pulse {
                0%, 100% { opacity: 0.6; }
                50% { opacity: 1; }
            }
        `;
        document.head.appendChild(style);
    </script>"""
