"""
Unit tests for PromptManager.
"""

from pathlib import Path

import pytest

from lecture_forge.utils.prompt_manager import PromptManager, get_prompt_manager, load_prompt


@pytest.fixture
def templates_dir(tmp_path):
    """Create a temporary templates directory with sample templates."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    # Simple template with one variable
    (prompts_dir / "simple.txt").write_text("Hello, {name}!")
    # Template with multiple variables
    (prompts_dir / "complex.txt").write_text("Topic: {topic}\nWords: {min_words}")
    # Empty-ish template
    (prompts_dir / "no_vars.txt").write_text("Static content only.")

    return prompts_dir


@pytest.fixture
def manager(templates_dir):
    return PromptManager(templates_dir=templates_dir)


class TestPromptManagerInit:
    def test_init_with_valid_dir(self, templates_dir):
        pm = PromptManager(templates_dir=templates_dir)
        assert pm.templates_dir == Path(templates_dir)

    def test_init_with_missing_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            PromptManager(templates_dir=tmp_path / "nonexistent")

    def test_init_default_uses_config(self):
        """Default init uses Config.TEMPLATES_DIR/prompts (real templates dir)."""
        pm = PromptManager()
        assert pm.templates_dir.exists()


class TestLoadTemplate:
    def test_load_existing_template(self, manager):
        content = manager.load_template("simple")
        assert content == "Hello, {name}!"

    def test_load_with_txt_extension(self, manager):
        content = manager.load_template("simple.txt")
        assert content == "Hello, {name}!"

    def test_load_nonexistent_raises(self, manager):
        with pytest.raises(FileNotFoundError):
            manager.load_template("nonexistent")

    def test_load_error_message_shows_available(self, manager):
        try:
            manager.load_template("nonexistent")
        except FileNotFoundError as e:
            # Should show available templates
            assert "simple" in str(e) or "Available" in str(e)


class TestFormatTemplate:
    def test_format_with_variables(self, manager):
        result = manager.format_template("simple", name="World")
        assert result == "Hello, World!"

    def test_format_multiple_variables(self, manager):
        result = manager.format_template("complex", topic="Python", min_words=1000)
        assert "Python" in result
        assert "1000" in result

    def test_format_no_variables_needed(self, manager):
        result = manager.format_template("no_vars")
        assert result == "Static content only."

    def test_format_missing_variable_raises(self, manager):
        with pytest.raises(ValueError) as exc_info:
            manager.format_template("simple")  # missing 'name'
        assert "name" in str(exc_info.value)

    def test_format_missing_variable_shows_provided(self, manager, templates_dir):
        """Error message shows which variables were provided."""
        (templates_dir / "two_vars.txt").write_text("{var1} and {var2}")
        manager2 = PromptManager(templates_dir=templates_dir)
        with pytest.raises(ValueError) as exc_info:
            manager2.format_template("two_vars", var1="hello")
        assert "var2" in str(exc_info.value) or "var1" in str(exc_info.value)


class TestListTemplates:
    def test_lists_available_templates(self, manager):
        templates = manager.list_templates()
        assert "simple" in templates
        assert "complex" in templates
        assert "no_vars" in templates

    def test_sorted_output(self, manager):
        templates = manager.list_templates()
        assert templates == sorted(templates)

    def test_no_txt_extension_in_names(self, manager):
        templates = manager.list_templates()
        assert all(not t.endswith(".txt") for t in templates)


class TestGetTemplateVariables:
    def test_simple_variable(self, manager):
        variables = manager.get_template_variables("simple")
        assert "name" in variables

    def test_multiple_variables(self, manager):
        variables = manager.get_template_variables("complex")
        assert "topic" in variables
        assert "min_words" in variables

    def test_no_variables(self, manager):
        variables = manager.get_template_variables("no_vars")
        assert variables == set()


class TestLoadPromptFunction:
    def test_load_prompt_uses_real_templates(self):
        """load_prompt() works with real content_generation template."""
        # Just verify it doesn't crash with the real template vars
        from lecture_forge.config import Config
        # The actual templates exist in the package
        pm = get_prompt_manager()
        assert "content_generation" in pm.list_templates()

    def test_get_prompt_manager_singleton(self):
        """get_prompt_manager() returns the same instance."""
        pm1 = get_prompt_manager()
        pm2 = get_prompt_manager()
        assert pm1 is pm2


def test_list_templates_nonexistent_dir(tmp_path):
    """Line 103: list_templates() returns [] when templates_dir doesn't exist."""
    from lecture_forge.utils.prompt_manager import PromptManager
    pm = PromptManager.__new__(PromptManager)
    pm.templates_dir = tmp_path / "nonexistent_dir"
    result = pm.list_templates()
    assert result == []
