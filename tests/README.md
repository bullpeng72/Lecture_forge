# LectureForge Tests

This directory contains the test suite for LectureForge.

## Test Structure

```
tests/
├── conftest.py              # Pytest fixtures and configuration
├── unit/                    # Unit tests for individual components
│   ├── test_config.py       # Configuration tests
│   ├── test_chunker.py      # Text chunking tests
│   └── test_retriever.py    # RAG retriever tests
├── integration/             # Integration tests for workflows
│   ├── test_knowledge_pipeline.py      # Knowledge base workflow
│   └── test_content_collection.py      # Content collection workflow
└── fixtures/                # Test data and fixtures
```

## Running Tests

### Install Test Dependencies

```bash
# Install all dependencies including dev tools
pip install -e ".[dev]"

# Or install from requirements-dev.txt
pip install -r requirements-dev.txt
```

### Run All Tests

```bash
# Run all tests with coverage
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=lecture_forge --cov-report=html
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Run tests by marker
pytest -m unit
pytest -m integration
pytest -m "not slow"
```

### Run Specific Test Files

```bash
# Single file
pytest tests/unit/test_config.py -v

# Specific test function
pytest tests/unit/test_config.py::test_config_validate_with_valid_keys -v
```

## Test Markers

Tests are marked with the following markers:

- `@pytest.mark.unit` - Fast unit tests
- `@pytest.mark.integration` - Integration tests (may be slower)
- `@pytest.mark.slow` - Slow tests (large datasets, network calls)

## Environment Variables

Tests use mock API keys set in `conftest.py`. For integration tests that make real API calls:

```bash
# Copy .env.example to .env.test
cp .env.example .env.test

# Set real API keys for integration testing
export OPENAI_API_KEY=sk-...
export SERPER_API_KEY=...
```

## Writing New Tests

### Unit Test Example

```python
# tests/unit/test_my_module.py
import pytest
from lecture_forge.my_module import MyClass

def test_my_function():
    """Test description."""
    result = MyClass().my_function()
    assert result == expected_value
```

### Integration Test Example

```python
# tests/integration/test_my_workflow.py
import pytest

@pytest.mark.integration
class TestMyWorkflow:
    """Test complete workflow."""

    def test_end_to_end(self, temp_dir, mock_llm):
        """Test end-to-end workflow."""
        # Setup
        # Execute
        # Assert
        pass
```

## Coverage Report

After running tests with coverage:

```bash
pytest --cov=lecture_forge --cov-report=html
```

Open `htmlcov/index.html` in a browser to view detailed coverage report.

## Continuous Integration

Tests automatically run on:
- Push to `main` or `develop` branches
- Pull requests
- See `.github/workflows/test.yml`

## Current Test Coverage

- **Unit Tests**: Config, Chunker, Retriever
- **Integration Tests**: Knowledge pipeline, Content collection

## TODO: Tests to Add

- [ ] Agent tests (Content Writer, Quality Evaluator, etc.)
- [ ] Tool tests (PDF parser, Web scraper, Image search)
- [ ] CLI tests
- [ ] HTML generation tests
- [ ] Quality evaluation tests
- [ ] End-to-end lecture generation test

## Troubleshooting

### Tests Fail with Import Errors

```bash
# Make sure package is installed in editable mode
pip install -e .
```

### Tests Fail with Missing Dependencies

```bash
# Install dev dependencies
pip install -r requirements-dev.txt
```

### ChromaDB Errors

```bash
# Clear test databases
rm -rf tests/temp_*
```

## Best Practices

1. **Test Isolation**: Each test should be independent
2. **Mock External APIs**: Use fixtures to mock OpenAI, Serper, etc.
3. **Use Fixtures**: Reuse common test data via conftest.py
4. **Clear Test Names**: Use descriptive test function names
5. **Fast Tests**: Keep unit tests fast (< 1s each)
6. **Mark Slow Tests**: Use `@pytest.mark.slow` for tests > 5s

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [Testing Best Practices](https://docs.python-guide.org/writing/tests/)
