# LectureForge Tests

This directory contains tests for the LectureForge project.

## Setup

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage report
```bash
pytest --cov=lecture_forge --cov-report=html
```

### Run specific test file
```bash
pytest tests/unit/agents/test_content_writer.py -v
```

### Run tests in a specific directory
```bash
pytest tests/unit/ -v
```

### Run tests with detailed output
```bash
pytest -v --tb=long
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Unit tests
│   ├── agents/             # Agent tests
│   │   ├── test_content_collector.py
│   │   ├── test_content_writer.py
│   │   └── test_curriculum_designer.py
│   ├── test_chunker.py     # Text chunking tests
│   ├── test_config.py      # Configuration tests
│   └── test_retriever.py   # RAG retriever tests
└── integration/            # Integration tests
    ├── test_knowledge_pipeline.py
    └── test_content_collection.py
```

## Writing New Tests

### Unit Tests

1. Create test file in `tests/unit/` with `test_` prefix
2. Use fixtures from `conftest.py` for common setup
3. Mock external dependencies (APIs, LLMs, databases)
4. Test one component in isolation

Example:
```python
def test_my_function(mock_llm):
    result = my_function()
    assert result is not None
```

### Integration Tests

1. Create test file in `tests/integration/`
2. Test multiple components working together
3. May use real dependencies (vector DB, file system)
4. Slower but more realistic

## Available Fixtures

- `test_env_vars`: Sets up test environment variables
- `temp_dir`: Temporary directory for test files
- `mock_llm`: Mocked LLM with sample responses
- `mock_vector_store`: Mocked ChromaDB vector store
- `sample_curriculum`: Sample curriculum data
- `sample_images`: Sample image metadata

See `conftest.py` for full list of fixtures.

## Coverage Goals

- **Unit tests**: 80%+ coverage
- **Integration tests**: Cover critical workflows
- **Smoke tests**: Basic functionality for all agents

## Continuous Integration

Tests should be run automatically on:
- Pull requests
- Commits to main branch
- Before releases

Setup CI with GitHub Actions:
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements-dev.txt
      - run: pytest --cov=lecture_forge
```

## Current Test Status

✅ **Completed** (Week 1 - Feb 2026):
- Unit tests for chunker, config, retriever
- Smoke tests for 3 critical agents (ContentCollector, ContentWriter, CurriculumDesigner)
- Integration tests for knowledge pipeline

⏳ **TODO**:
- Remaining 7 agent tests
- Tool tests (PDF parser, web scraper, image search)
- Quality assurance system tests
- Performance/benchmark tests
- End-to-end pipeline tests

**Current Coverage**: ~15% (estimated)
**Target Coverage**: 80%+
