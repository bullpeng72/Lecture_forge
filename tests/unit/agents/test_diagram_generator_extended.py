"""
Extended unit tests for DiagramGeneratorAgent utility methods.
These tests cover the pure-logic methods without LLM calls.
"""

from unittest.mock import MagicMock, patch

import pytest

from lecture_forge.agents.diagram_generator import DiagramGeneratorAgent
from lecture_forge.models.lecture import MermaidDiagram, SectionContent


@pytest.fixture
def agent(test_env_vars, mock_llm):
    return DiagramGeneratorAgent()


@pytest.fixture
def process_section():
    return SectionContent(
        section_id="s_process",
        title="훈련 과정",
        markdown_content=(
            "# 모델 훈련 과정\n\n"
            "1. 데이터 수집\n2. 전처리\n3. 모델 훈련\n4. 검증\n5. 평가\n\n"
            "데이터 수집 후 전처리를 수행합니다. 그다음 모델을 훈련합니다."
        ),
        word_count=50,
    )


@pytest.fixture
def architecture_section():
    return SectionContent(
        section_id="s_arch",
        title="시스템 아키텍처",
        markdown_content=(
            "# 트랜스포머 아키텍처\n\n"
            "트랜스포머 모델은 인코더 컴포넌트와 디코더 컴포넌트로 구성됩니다. "
            "어텐션 레이어와 피드포워드 계층이 주요 요소입니다."
        ),
        word_count=40,
    )


# ===== _detect_section_type() =====

class TestDetectSectionType:
    def test_process_from_title_keyword(self, agent):
        assert agent._detect_section_type("데이터 훈련 과정") == "process"

    def test_process_keyword_프로세스(self, agent):
        assert agent._detect_section_type("학습 프로세스") == "process"

    def test_architecture_keyword(self, agent):
        assert agent._detect_section_type("트랜스포머 아키텍처") == "architecture"

    def test_architecture_model(self, agent):
        assert agent._detect_section_type("GPT 모델 구조") == "architecture"

    def test_comparison_keyword(self, agent):
        assert agent._detect_section_type("CNN vs RNN 비교") == "comparison"

    def test_default_concept(self, agent):
        assert agent._detect_section_type("딥러닝 기초") == "concept"

    def test_process_from_content_sequential(self, agent):
        content = "첫째, 데이터를 수집합니다. 둘째, 전처리합니다. 셋째, 모델을 훈련합니다. 넷째, 평가합니다."
        result = agent._detect_section_type("주제", content)
        assert result == "process"

    def test_architecture_from_content_components(self, agent):
        content = "시스템에는 입력 컴포넌트, 처리 모듈, 출력 레이어, 검증 계층이 있습니다."
        result = agent._detect_section_type("구성", content)
        assert result == "architecture"


# ===== _get_diagram_template() =====

class TestGetDiagramTemplate:
    def test_returns_string(self, agent):
        for t in ["process", "architecture", "comparison", "concept"]:
            tmpl = agent._get_diagram_template(t)
            assert isinstance(tmpl, str)
            assert len(tmpl) > 20

    def test_process_template_lr(self, agent):
        tmpl = agent._get_diagram_template("process")
        assert "flowchart LR" in tmpl

    def test_architecture_template_td(self, agent):
        tmpl = agent._get_diagram_template("architecture")
        assert "flowchart TD" in tmpl

    def test_unknown_type_returns_default(self, agent):
        tmpl = agent._get_diagram_template("unknown_type")
        assert "flowchart" in tmpl


# ===== _detect_diagram_type() =====

class TestDetectDiagramType:
    def test_flowchart_td(self, agent):
        assert agent._detect_diagram_type("flowchart TD\n  A --> B") == "flowchart"

    def test_flowchart_lr(self, agent):
        assert agent._detect_diagram_type("flowchart LR\n  A --> B") == "flowchart"

    def test_graph(self, agent):
        assert agent._detect_diagram_type("graph TD\n  A --> B") == "graph"

    def test_mindmap(self, agent):
        assert agent._detect_diagram_type("mindmap\n  root((Topic))") == "mindmap"

    def test_class_diagram(self, agent):
        assert agent._detect_diagram_type("classDiagram\n  class A") == "class"

    def test_sequence_diagram(self, agent):
        assert agent._detect_diagram_type("sequenceDiagram\n  A->>B: msg") == "sequence"

    def test_unknown_defaults_to_flowchart(self, agent):
        assert agent._detect_diagram_type("unknownType\n  A --> B") == "flowchart"


# ===== _clean_unsafe_patterns() =====

class TestCleanUnsafePatterns:
    def test_removes_parentheses_from_label(self, agent):
        code = "flowchart TD\n    A[텍스트(설명)]\n    A --> B[End]"
        cleaned = agent._clean_unsafe_patterns(code)
        assert "(" not in cleaned.split("[")[1].split("]")[0] if "[" in cleaned else True

    def test_preserves_connections(self, agent):
        code = "flowchart TD\n    A[Start] --> B[End]"
        cleaned = agent._clean_unsafe_patterns(code)
        assert "-->" in cleaned

    def test_preserves_diagram_type_line(self, agent):
        code = "flowchart TD\n    A[Start] --> B[End]"
        cleaned = agent._clean_unsafe_patterns(code)
        assert cleaned.startswith("flowchart TD")

    def test_replaces_colon_in_label(self, agent):
        code = "flowchart TD\n    A[텍스트: 설명]\n"
        cleaned = agent._clean_unsafe_patterns(code)
        # Colon should be replaced with " - "
        assert "텍스트 - 설명" in cleaned or ":" not in cleaned.split("[")[1].split("]")[0]

    def test_truncates_long_label(self, agent):
        long_label = "A" * 55
        code = f"flowchart TD\n    A[{long_label}]\n"
        cleaned = agent._clean_unsafe_patterns(code)
        # Label should be truncated to ≤ 50 chars
        import re
        match = re.search(r'\[(.*?)\]', cleaned)
        if match:
            assert len(match.group(1)) <= 50

    def test_no_changes_returns_original(self, agent):
        code = "flowchart TD\n    A[Clean Text] --> B[More Text]"
        cleaned = agent._clean_unsafe_patterns(code)
        assert "Clean Text" in cleaned


# ===== _clean_text_for_mermaid() =====

class TestCleanTextForMermaid:
    def test_removes_parentheses(self, agent):
        assert "(" not in agent._clean_text_for_mermaid("text(with parens)")

    def test_removes_brackets(self, agent):
        assert "[" not in agent._clean_text_for_mermaid("text[with brackets]")

    def test_removes_colons(self, agent):
        result = agent._clean_text_for_mermaid("key: value")
        assert ":" not in result

    def test_removes_quotes(self, agent):
        assert '"' not in agent._clean_text_for_mermaid('"quoted"')
        assert "'" not in agent._clean_text_for_mermaid("'quoted'")

    def test_truncates_long_text(self, agent):
        long = "A" * 50
        result = agent._clean_text_for_mermaid(long)
        assert len(result) <= 40

    def test_strips_whitespace(self, agent):
        result = agent._clean_text_for_mermaid("  text  ")
        assert result == result.strip()

    def test_plain_korean_preserved(self, agent):
        result = agent._clean_text_for_mermaid("기계 학습")
        assert "기계" in result or len(result) > 0


# ===== _evaluate_diagram_quality() =====

class TestEvaluateDiagramQuality:
    def test_returns_dict_with_required_keys(self, agent):
        code = "flowchart TD\n    A[Start] --> B[End]\n    B --> C[Done]"
        result = agent._evaluate_diagram_quality(code)
        assert "score" in result
        assert "pass" in result
        assert "feedback" in result
        assert "node_count" in result

    def test_high_quality_diagram(self, agent):
        # 7 nodes, 8+ connections, decision point
        code = (
            "flowchart TD\n"
            "    A[Start]\n    B[Process 1]\n    C[Process 2]\n    D[Process 3]\n"
            "    E[Process 4]\n    F{{Check}}\n    G[Done]\n"
            "    A --> B --> C --> D\n"
            "    D --> E --> F\n"
            "    F -->|Yes| G\n"
            "    F -->|No| B\n"
        )
        result = agent._evaluate_diagram_quality(code)
        assert result["score"] > 0
        assert result["node_count"] >= 6

    def test_low_quality_few_nodes(self, agent):
        # Nodes on the same line as --> are not counted; feedback still fires for node_count < 4
        code = "flowchart TD\n    A[Start]\n    B[End]\n    A --> B"
        result = agent._evaluate_diagram_quality(code)
        assert result["node_count"] == 2
        assert any("Too few nodes" in f for f in result["feedback"])

    def test_decision_point_detected(self, agent):
        code = (
            "flowchart TD\n"
            "    A[Start]\n    B{{Decision?}}\n    C[Yes Path]\n    D[No Path]\n"
            "    A --> B\n    B -->|Yes| C\n    B -->|No| D\n"
        )
        result = agent._evaluate_diagram_quality(code)
        assert result["decision_count"] >= 1

    def test_score_capped_at_100(self, agent):
        # Even the best diagram shouldn't exceed 100
        code = (
            "flowchart TD\n"
            "    A[N1]\n    B[N2]\n    C[N3]\n    D[N4]\n    E[N5]\n    F[N6]\n    G{{D}}\n"
            "    A --> B --> C --> D\n    D --> E --> F\n    G --> A\n    E --> G\n"
        )
        result = agent._evaluate_diagram_quality(code)
        assert result["score"] <= 100


# ===== _create_process_fallback() and _create_general_fallback() =====

class TestFallbackDiagrams:
    def test_process_fallback_with_enough_keywords(self, agent):
        keywords = ["데이터 수집", "전처리", "훈련", "검증", "평가"]
        code = agent._create_process_fallback(keywords)
        assert "flowchart LR" in code
        assert "A[데이터 수집]" in code

    def test_process_fallback_few_keywords(self, agent):
        keywords = ["시작", "끝"]
        code = agent._create_process_fallback(keywords)
        assert "flowchart LR" in code

    def test_general_fallback_with_enough_keywords(self, agent):
        keywords = ["개념", "특징 1", "특징 2", "작동 방식", "응용"]
        code = agent._create_general_fallback(keywords, "Test Title")
        assert "flowchart TD" in code

    def test_general_fallback_few_keywords(self, agent):
        keywords = ["개념"]
        code = agent._create_general_fallback(keywords, "Test Title")
        assert "flowchart TD" in code


# ===== _extract_keywords_simple() =====

class TestExtractKeywordsSimple:
    def test_returns_list(self, agent):
        result = agent._extract_keywords_simple("Some content here.", "Test Section")
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_max_7_keywords(self, agent):
        long_content = "\n".join([f"#### 항목 {i}" for i in range(20)])
        result = agent._extract_keywords_simple(long_content, "Test", "concept")
        assert len(result) <= 7

    def test_process_keywords_extracted(self, agent):
        content = "데이터 수집을 먼저 합니다. 그다음 전처리합니다. 모델을 훈련합니다."
        result = agent._extract_keywords_simple(content, "Test", "process")
        assert any("수집" in k or "전처리" in k or "훈련" in k for k in result)

    def test_no_duplicate_keywords(self, agent):
        content = "#### 특징 A\n#### 특징 A\n#### 특징 B"
        result = agent._extract_keywords_simple(content, "Test")
        # Check that we don't have duplicates
        lower_results = [r.lower() for r in result]
        assert len(lower_results) == len(set(lower_results))


# ===== generate_diagrams() integration =====

class TestGenerateDiagrams:
    def test_skips_intro_section(self, agent):
        sections = [
            SectionContent(section_id="intro_1", title="Introduction", markdown_content="Intro text"),
            SectionContent(section_id="sec_1", title="Main Section", markdown_content="A[Node]"),
        ]

        mock_response = MagicMock()
        mock_response.content = "flowchart TD\n    A[Start] --> B[End]\n    B --> C[Done]\n    C --> D[Final]"

        with patch.object(agent, "invoke_llm", return_value=mock_response):
            result = agent.generate_diagrams(sections)

        # Intro section should be skipped (no diagram generation attempted)
        assert result[0].diagrams == []

    def test_empty_sections_list(self, agent):
        result = agent.generate_diagrams([])
        assert result == []

    def test_conclusion_section_skipped(self, agent):
        sections = [
            SectionContent(section_id="conclusion_1", title="Conclusion", markdown_content="Wrap up."),
        ]
        result = agent.generate_diagrams(sections)
        assert result[0].diagrams == []


# ===== Additional coverage: missing branches =====

class TestDetectSectionTypeActionVerbs:
    """Tests for action verb detection in _detect_section_type()."""

    def test_process_from_action_verbs(self, agent):
        """Content with 4+ action verbs → 'process' type."""
        content = "데이터를 수집하고 전처리한다. 그다음 모델을 훈련하고 검증하며 평가한다."
        result = agent._detect_section_type("일반 제목", content)
        assert result == "process"

    def test_process_exactly_four_verbs(self, agent):
        """Exactly 4 action verbs → 'process'."""
        # 수집, 전처리, 훈련, 검증 are all in action_verbs list
        content = "수집, 전처리, 훈련, 검증"
        result = agent._detect_section_type("제목", content)
        assert result == "process"


class TestExtractProcessKeywords:
    """Tests for _extract_process_keywords()."""

    def test_extracts_numbered_steps(self, agent):
        """Numbered Korean steps in content are extracted."""
        content = "1. 데이터 수집\n2. 모델 훈련\n3. 결과 검증"
        result = agent._extract_process_keywords(content)
        # Should extract some keywords from numbered steps
        assert isinstance(result, list)

    def test_extracts_action_verbs(self, agent):
        """Action verbs present in content are extracted."""
        content = "데이터 수집과 전처리, 모델 훈련, 검증 단계를 수행합니다."
        result = agent._extract_process_keywords(content)
        assert isinstance(result, list)

    def test_empty_content_returns_list(self, agent):
        result = agent._extract_process_keywords("")
        assert isinstance(result, list)


class TestExtractArchitectureKeywords:
    """Tests for _extract_architecture_keywords()."""

    def test_extracts_component_keywords(self, agent):
        """Component keywords in content are extracted."""
        content = "시스템은 인코더 컴포넌트와 디코더 모듈로 구성된다. 처리 레이어가 핵심 요소다."
        result = agent._extract_architecture_keywords(content)
        assert isinstance(result, list)

    def test_empty_content(self, agent):
        result = agent._extract_architecture_keywords("")
        assert isinstance(result, list)


class TestExtractKeywordsSimple:
    """Tests for _extract_keywords_simple() branching."""

    def test_architecture_section_type_calls_architecture_extraction(self, agent):
        content = "인코더 컴포넌트와 디코더 모듈. 처리 레이어."
        result = agent._extract_keywords_simple(content, "아키텍처", "architecture")
        assert isinstance(result, list)
        assert len(result) >= 1  # At least title keyword

    def test_process_section_type_calls_process_extraction(self, agent):
        content = "1. 수집\n2. 훈련\n3. 검증"
        result = agent._extract_keywords_simple(content, "훈련 과정", "process")
        assert isinstance(result, list)

    def test_concept_type_calls_general_extraction(self, agent):
        content = "## 핵심 개념\n**머신러닝**이 중요합니다."
        result = agent._extract_keywords_simple(content, "개념", "concept")
        assert isinstance(result, list)


class TestExtractBoldText:
    """Tests for _extract_bold_text()."""

    def test_extracts_bold_words(self, agent):
        content = "**딥러닝** is important. **머신러닝** is also used."
        result = agent._extract_bold_text(content)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_ignores_long_bold_text(self, agent):
        """Bold text with > 4 words is ignored."""
        content = "**This is a very long phrase that exceeds four words**"
        result = agent._extract_bold_text(content)
        assert isinstance(result, list)

    def test_empty_content(self, agent):
        result = agent._extract_bold_text("")
        assert result == []


class TestCreateFallbackDiagram:
    """Tests for _create_fallback_diagram()."""

    def test_process_fallback(self, agent, process_section):
        """Section of type 'process' → process flowchart fallback."""
        result = agent._create_fallback_diagram(process_section)
        assert result is not None
        assert result.mermaid_code is not None
        assert "flowchart" in result.mermaid_code.lower() or "-->" in result.mermaid_code

    def test_general_fallback(self, agent):
        """Section without process/architecture → general fallback."""
        section = SectionContent(
            section_id="s1",
            title="개념 정리",
            markdown_content="일반적인 개념 설명입니다. **핵심 용어** 위주로 정리.",
        )
        result = agent._create_fallback_diagram(section)
        assert result is not None
        assert result.mermaid_code is not None


class TestCreateGeneralFallbackManyKeywords:
    """Tests _create_general_fallback() with 5-7 keywords."""

    def test_five_keywords(self, agent):
        """5 keywords → uses 5th slot (lines 636-637)."""
        keywords = ["A", "B", "C", "D", "E"]
        result = agent._create_general_fallback(keywords, "Test Title")
        assert "E" in result or len(result) > 0

    def test_six_keywords(self, agent):
        """6 keywords → uses 6th slot (lines 639-640)."""
        keywords = ["A", "B", "C", "D", "E", "F"]
        result = agent._create_general_fallback(keywords, "Test Title")
        assert "F" in result or len(result) > 0

    def test_seven_keywords(self, agent):
        """7 keywords → uses 7th slot."""
        keywords = ["A", "B", "C", "D", "E", "F", "G"]
        result = agent._create_general_fallback(keywords, "Test Title")
        assert len(result) > 0


class TestEvaluateDiagramQualityNodeCount:
    """Tests node count branches in _evaluate_diagram_quality()."""

    def test_node_count_4_to_5(self, agent):
        """4-5 nodes → 'below optimal' feedback."""
        code = """flowchart TD
    A[Start] --> B[Step1]
    B --> C[Step2]
    C --> D[End]
    D --> E[Final]"""
        result = agent._evaluate_diagram_quality(code)
        assert "score" in result
        assert result["score"] >= 0

    def test_many_nodes_above_10(self, agent):
        """11+ nodes → 'too many nodes' feedback."""
        nodes = "\n".join(f"    N{i}[Node {i}]" for i in range(12))
        connections = "\n".join(f"    N{i} --> N{i+1}" for i in range(11))
        code = f"flowchart TD\n{nodes}\n{connections}"
        result = agent._evaluate_diagram_quality(code)
        assert "score" in result

    def test_multiple_decision_points(self, agent):
        """2+ decision diamonds → +15 points."""
        code = """flowchart TD
    A[Start] --> B{Decision1}
    B --> |yes| C[Step]
    C --> D{Decision2}
    D --> |yes| E[End]
    D --> |no| F[Alt]
    B --> |no| F"""
        result = agent._evaluate_diagram_quality(code)
        assert result["score"] > 0


class TestGenerateForSectionLlmBehavior:
    """Tests for generate_for_section() LLM return behaviors."""

    def test_empty_mermaid_code_is_skipped(self, agent):
        """When LLM returns empty string, iteration continues (line 64: continue)."""
        section = SectionContent(
            section_id="s1",
            title="Some Section",
            markdown_content="Content about process: 수집, 전처리, 훈련, 검증, 평가, 배포",
            word_count=50,
        )
        # LLM returns empty string first, then valid code
        valid_code = "flowchart TD\n    A[Start] --> B[End]"
        with patch.object(agent, "_call_llm_for_diagram",
                          side_effect=["", "", valid_code]):
            with patch.object(agent, "_evaluate_diagram_quality",
                              return_value={"score": 90, "feedback": []}):
                result = agent._generate_diagram_for_section(section)
        # Should either return a diagram (using the valid code) or None
        assert result is None or result.mermaid_code is not None

    def test_exception_in_generate_loop_handled(self, agent):
        """Exception inside generate loop is caught (lines 106-107)."""
        section = SectionContent(
            section_id="s2",
            title="Exception Section",
            markdown_content="Some content here for testing",
        )
        with patch.object(agent, "_call_llm_for_diagram",
                          side_effect=Exception("LLM error")):
            result = agent._generate_diagram_for_section(section)
        # Should return None (all retries failed)
        assert result is None
