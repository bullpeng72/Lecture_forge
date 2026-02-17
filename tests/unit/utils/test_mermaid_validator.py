"""
Unit tests for MermaidValidator.
"""

import pytest

from lecture_forge.utils.mermaid_validator import (
    MermaidValidator,
    clean_mermaid_code,
    validate_mermaid,
)


@pytest.fixture
def validator():
    return MermaidValidator()


# ===== validate() method =====

class TestValidate:
    def test_empty_code_invalid(self, validator):
        valid, msg = validator.validate("")
        assert valid is False
        assert "Empty" in msg

    def test_whitespace_only_invalid(self, validator):
        valid, msg = validator.validate("   \n  ")
        assert valid is False

    def test_unknown_type_invalid(self, validator):
        valid, msg = validator.validate("unknownDiagram\n  A --> B")
        assert valid is False
        assert "Invalid or missing diagram type" in msg

    def test_valid_flowchart(self, validator):
        code = "flowchart TD\n  A[Start] --> B[End]"
        valid, msg = validator.validate(code)
        assert valid is True
        assert msg == ""

    def test_valid_graph_lr(self, validator):
        code = "graph LR\n  A[Node] --> B[Other]"
        valid, msg = validator.validate(code)
        assert valid is True

    def test_valid_mindmap(self, validator):
        code = "mindmap\n  root((Topic))\n    SubA\n    SubB"
        valid, msg = validator.validate(code)
        assert valid is True

    def test_valid_classDiagram(self, validator):
        code = "classDiagram\n  class Animal {\n    +String name\n  }"
        valid, msg = validator.validate(code)
        assert valid is True

    def test_valid_sequenceDiagram(self, validator):
        code = "sequenceDiagram\n  A->>B: Hello\n  B-->>A: Hi"
        valid, msg = validator.validate(code)
        assert valid is True

    def test_valid_erDiagram(self, validator):
        # ER diagrams use ||--o| syntax (no brackets to mismatch)
        code = "erDiagram\n  CUSTOMER ||--o| ORDER : places"
        valid, msg = validator.validate(code)
        assert valid is True

    def test_valid_gantt(self, validator):
        code = "gantt\n  title Project\n  section Phase1\n  Task1: 2024-01-01, 30d"
        valid, msg = validator.validate(code)
        assert valid is True

    def test_flowchart_no_nodes_invalid(self, validator):
        code = "flowchart TD\n  %% just a comment"
        valid, msg = validator.validate(code)
        assert valid is False

    def test_flowchart_tb_valid(self, validator):
        code = "flowchart TB\n  A[Node A] --> B[Node B]"
        valid, msg = validator.validate(code)
        assert valid is True

    def test_mindmap_missing_root_invalid(self, validator):
        code = "mindmap\n  NoRoot\n    SubTopic"
        valid, msg = validator.validate(code)
        assert valid is False
        assert "root node" in msg.lower()

    def test_unmatched_bracket_invalid(self, validator):
        code = "flowchart TD\n  A[Start --> B[End"
        valid, msg = validator.validate(code)
        assert valid is False

    def test_empty_node_label_invalid(self, validator):
        code = "flowchart TD\n  A[] --> B[End]"
        valid, msg = validator.validate(code)
        assert valid is False
        assert "Empty node labels" in msg

    def test_very_long_line_invalid(self, validator):
        long_line = "A" * 301
        code = f"flowchart TD\n  A[Node] --> B[End]\n  %% {long_line}"
        valid, msg = validator.validate(code)
        assert valid is False
        assert "too long" in msg


class TestDetectType:
    def test_flowchart_td(self, validator):
        assert validator._detect_type("flowchart TD") == "flowchart"

    def test_flowchart_lr(self, validator):
        assert validator._detect_type("flowchart LR") == "flowchart"

    def test_graph_td(self, validator):
        assert validator._detect_type("graph TD") == "graph"

    def test_mindmap(self, validator):
        assert validator._detect_type("mindmap") == "mindmap"

    def test_class_diagram(self, validator):
        assert validator._detect_type("classDiagram") == "class"

    def test_sequence_diagram(self, validator):
        assert validator._detect_type("sequenceDiagram") == "sequence"

    def test_er_diagram(self, validator):
        assert validator._detect_type("erDiagram") == "er"

    def test_gantt(self, validator):
        assert validator._detect_type("gantt") == "gantt"

    def test_unknown_returns_none(self, validator):
        assert validator._detect_type("unknownType") is None


class TestValidateBrackets:
    def test_balanced_brackets(self, validator):
        assert validator._validate_brackets("(a) [b] {c}") == []

    def test_unmatched_close(self, validator):
        errors = validator._validate_brackets("(a))")
        assert any("Unmatched" in e for e in errors)

    def test_unclosed_bracket(self, validator):
        errors = validator._validate_brackets("(a [b")
        assert any("Unclosed" in e for e in errors)

    def test_mismatched_brackets(self, validator):
        errors = validator._validate_brackets("(a]")
        assert any("Mismatched" in e for e in errors)


class TestCleanMermaidCode:
    def test_strips_code_fence(self):
        code = "```mermaid\nflowchart TD\n  A --> B\n```"
        cleaned = clean_mermaid_code(code)
        assert "```" not in cleaned
        assert "flowchart TD" in cleaned

    def test_strips_plain_code_fence(self):
        code = "```\nflowchart TD\n  A --> B\n```"
        cleaned = clean_mermaid_code(code)
        assert "```" not in cleaned

    def test_removes_comments(self):
        code = "flowchart TD\n  A --> B %% This is a comment"
        cleaned = clean_mermaid_code(code)
        assert "%%" not in cleaned

    def test_strips_whitespace(self):
        code = "  \nflowchart TD\n  A --> B\n  "
        cleaned = clean_mermaid_code(code)
        assert cleaned.startswith("flowchart")

    def test_no_fence_unchanged(self):
        code = "flowchart TD\n  A --> B"
        cleaned = clean_mermaid_code(code)
        assert "flowchart TD" in cleaned


class TestValidateMermaidFunction:
    def test_valid_code(self):
        code = "flowchart TD\n  A[Start] --> B[End]"
        valid, msg = validate_mermaid(code)
        assert valid is True

    def test_invalid_code(self):
        valid, msg = validate_mermaid("")
        assert valid is False
