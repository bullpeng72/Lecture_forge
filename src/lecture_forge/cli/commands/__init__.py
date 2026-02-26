"""
CLI command modules.
"""

from lecture_forge.cli.commands.chat import chat
from lecture_forge.cli.commands.cleanup import cleanup
from lecture_forge.cli.commands.create import create
from lecture_forge.cli.commands.edit import edit
from lecture_forge.cli.commands.edit_images import edit_images
from lecture_forge.cli.commands.home import home
from lecture_forge.cli.commands.improve import improve
from lecture_forge.cli.commands.init import init
from lecture_forge.cli.commands.translate import translate

__all__ = [
    "chat",
    "cleanup",
    "create",
    "edit",
    "edit_images",
    "home",
    "improve",
    "init",
    "translate",
]
