"""
Mermaid Diagram Syntax Validator.

Validates Mermaid diagram syntax to prevent rendering errors.
"""

import re
from typing import Optional, Tuple

from lecture_forge.utils import logger


class MermaidValidator:
    """Validator for Mermaid diagram syntax."""

    VALID_DIAGRAM_TYPES = {
        "flowchart": ["flowchart TD", "flowchart LR", "flowchart TB", "flowchart RL", "flowchart BT"],
        "graph": ["graph TD", "graph LR", "graph TB", "graph RL", "graph BT"],
        "mindmap": ["mindmap"],
        "class": ["classDiagram"],
        "sequence": ["sequenceDiagram"],
        "er": ["erDiagram"],
        "gantt": ["gantt"],
    }

    def validate(self, mermaid_code: str, expected_type: Optional[str] = None) -> Tuple[bool, str]:
        """
        Validate Mermaid diagram syntax.

        Args:
            mermaid_code: The Mermaid code to validate
            expected_type: Expected diagram type (flowchart, mindmap, etc.)

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not mermaid_code or not mermaid_code.strip():
            return False, "Empty Mermaid code"

        errors = []

        # Check diagram type declaration
        first_line = mermaid_code.strip().split("\n")[0].strip()
        detected_type = self._detect_type(first_line)

        if not detected_type:
            errors.append(f"Invalid or missing diagram type declaration: '{first_line}'")
            return False, "; ".join(errors)

        # Type-specific validation
        if detected_type == "mindmap":
            mindmap_errors = self._validate_mindmap(mermaid_code)
            errors.extend(mindmap_errors)

        elif detected_type in ["flowchart", "graph"]:
            flowchart_errors = self._validate_flowchart(mermaid_code)
            errors.extend(flowchart_errors)

        elif detected_type == "sequence":
            sequence_errors = self._validate_sequence(mermaid_code)
            errors.extend(sequence_errors)

        # Common validations
        bracket_errors = self._validate_brackets(mermaid_code)
        errors.extend(bracket_errors)

        # Check for problematic patterns
        pattern_errors = self._check_problematic_patterns(mermaid_code)
        errors.extend(pattern_errors)

        if errors:
            return False, "; ".join(errors)

        return True, ""

    def _detect_type(self, first_line: str) -> Optional[str]:
        """Detect diagram type from first line."""
        for diagram_type, valid_starts in self.VALID_DIAGRAM_TYPES.items():
            if any(first_line.startswith(start) for start in valid_starts):
                return diagram_type
        return None

    def _validate_mindmap(self, code: str) -> list:
        """Validate mindmap-specific syntax."""
        errors = []
        lines = code.split("\n")

        # Check for root node
        has_root = False
        for line in lines:
            if "root(" in line or "root((" in line:
                has_root = True
                # Check for proper root syntax
                if not (line.strip().startswith("root((") or line.strip().startswith("  root((")):
                    errors.append("Mindmap root should use double parentheses: root((text))")
                break

        if not has_root:
            errors.append("Mindmap must have a root node")

        # Check for special characters in nodes
        for i, line in enumerate(lines[1:], start=2):
            if line.strip() and not line.strip().startswith("root"):
                # Check for problematic characters
                if any(char in line for char in ["[", "]", "{", "}", "()", "-->"]):
                    errors.append(f"Line {i}: Mindmap nodes should not contain brackets or arrows")

        # Check indentation (should be consistent)
        indents = []
        for line in lines[1:]:
            if line.strip() and not line.strip().startswith("root"):
                indent = len(line) - len(line.lstrip())
                if indent > 0:
                    indents.append(indent)

        if indents:
            # Check if all indents are multiples of the smallest indent
            min_indent = min(indents)
            if min_indent > 0:
                if not all(indent % min_indent == 0 for indent in indents):
                    errors.append("Inconsistent indentation in mindmap")

        return errors

    def _validate_flowchart(self, code: str) -> list:
        """Validate flowchart/graph-specific syntax (relaxed for Korean text)."""
        errors = []
        lines = code.split("\n")

        # Check for nodes (connections are optional)
        has_nodes = False
        has_connections = False
        node_pattern = re.compile(r"^\s*([A-Z0-9_]+)\[")
        arrow_pattern = re.compile(r"-->|-.->|===>|~~~")

        for i, line in enumerate(lines[1:], start=2):
            line = line.strip()
            if not line or line.startswith("%%"):  # Comment
                continue

            # Check for node definitions
            if node_pattern.match(line):
                has_nodes = True

                # Check for unmatched brackets in node labels (relaxed)
                label_match = re.search(r"\[(.*?)\]", line)
                if label_match:
                    label = label_match.group(1)
                    # Only error on truly nested brackets (not just Korean text with parens)
                    if label.count("[") > 0 or label.count("]") > 0:
                        errors.append(f"Line {i}: Nested brackets in node label")

            # Check for arrow syntax
            if arrow_pattern.search(line):
                has_connections = True
                # Check if arrow is properly formatted
                if not re.search(r"[A-Z0-9_]+\s*-->", line):
                    # Could be okay if it's edge label or alternative arrow format
                    logger.debug(f"Non-standard arrow format on line {i}: {line}")

        if not has_nodes:
            errors.append("Flowchart has no node definitions")

        # Warning only if no connections (not an error)
        if has_nodes and not has_connections:
            logger.warning("Flowchart has nodes but no connections (acceptable)")

        return errors

    def _validate_sequence(self, code: str) -> list:
        """Validate sequence diagram syntax."""
        errors = []

        # Note: Sequence diagrams should have participants, but this is not strictly required
        # Participant validation is currently not enforced

        return errors

    def _validate_brackets(self, code: str) -> list:
        """Check for unmatched brackets."""
        errors = []

        brackets = {
            "(": ")",
            "[": "]",
            "{": "}",
        }

        stack = []
        for i, char in enumerate(code):
            if char in brackets.keys():
                stack.append((char, i))
            elif char in brackets.values():
                if not stack:
                    errors.append(f"Unmatched closing bracket '{char}' at position {i}")
                    continue
                opening, pos = stack.pop()
                if brackets[opening] != char:
                    errors.append(f"Mismatched brackets: '{opening}' at {pos} closed with '{char}' at {i}")

        if stack:
            for bracket, pos in stack:
                errors.append(f"Unclosed bracket '{bracket}' at position {pos}")

        return errors

    def _check_problematic_patterns(self, code: str) -> list:
        """Check for patterns known to cause issues (relaxed validation)."""
        errors = []

        # Check for empty nodes
        if re.search(r"\[\s*\]", code):
            errors.append("Empty node labels found")

        # Check for very long lines (>300 chars, increased from 200)
        for i, line in enumerate(code.split("\n"), start=1):
            if len(line) > 300:
                errors.append(f"Line {i} is too long ({len(line)} chars). Consider breaking it up.")

        # Warning only: Korean text with special characters
        # (Changed from error to warning - logged but not blocking)
        korean_with_special = re.findall(r"[가-힣]+[()[\]{}]+", code)
        if korean_with_special:
            logger.warning(f"Korean text with special characters detected (may cause issues): {korean_with_special[:3]}")
            # Don't add to errors - just warn

        return errors


def validate_mermaid(mermaid_code: str, diagram_type: Optional[str] = None) -> Tuple[bool, str]:
    """
    Convenience function to validate Mermaid code.

    Args:
        mermaid_code: Mermaid diagram code
        diagram_type: Expected diagram type

    Returns:
        (is_valid, error_message)
    """
    validator = MermaidValidator()
    return validator.validate(mermaid_code, diagram_type)


def clean_mermaid_code(mermaid_code: str) -> str:
    """
    Clean and normalize Mermaid code.

    Args:
        mermaid_code: Raw Mermaid code

    Returns:
        Cleaned Mermaid code
    """
    # Remove markdown code fences
    if "```mermaid" in mermaid_code:
        mermaid_code = mermaid_code.split("```mermaid")[1].split("```")[0].strip()
    elif "```" in mermaid_code:
        # Try to extract first code block
        parts = mermaid_code.split("```")
        if len(parts) >= 3:
            mermaid_code = parts[1].strip()

    # Remove leading/trailing whitespace
    mermaid_code = mermaid_code.strip()

    # Remove comments
    lines = []
    for line in mermaid_code.split("\n"):
        # Remove inline comments
        if "%%" in line:
            line = line.split("%%")[0]
        if line.strip():
            lines.append(line)

    mermaid_code = "\n".join(lines)

    return mermaid_code
