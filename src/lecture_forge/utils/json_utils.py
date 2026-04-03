"""
JSON utility helpers for LectureForge.
"""

import json


def strip_json_fence(text: str) -> str:
    """Strip markdown code fences (```json or ```) from LLM response text."""
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    return text


def parse_json_response(text: str):
    """Strip markdown fences from LLM response and parse as JSON."""
    return json.loads(strip_json_fence(text))
