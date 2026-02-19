"""
Slide generation module for LectureForge.

This module provides functionality for converting lecture HTML into Reveal.js presentation slides.
"""

from lecture_forge.slides.converter import SlideConverter
from lecture_forge.slides.notes import SlideNotesGenerator
from lecture_forge.slides.parser import HTMLLectureParser
from lecture_forge.slides.templates import RevealJsTemplate

__all__ = ["SlideConverter", "SlideNotesGenerator", "HTMLLectureParser", "RevealJsTemplate"]
