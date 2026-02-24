# LectureForge Documentation

Welcome to the LectureForge documentation! This directory contains guides and API references for the LectureForge project.

## 📚 Documentation Structure

```
docs/
├── README.md                    - This file
├── INPUT_LIMITS_ANALYSIS.md     - Input source limits & RAG analysis
├── guides/
│   └── getting-started.md       - Installation and first steps
├── architecture/
│   └── system-overview.md       - High-level architecture & data flow
└── api/
    ├── agents.md                 - All agents API reference
    └── cli.md                    - CLI module reference
```

### 📖 Guides
User-facing documentation:
- **[Getting Started](guides/getting-started.md)** - Installation, configuration, and your first lecture

### 🏗️ Architecture
System architecture and design:
- **[System Overview](architecture/system-overview.md)** - Architecture, data flow, technology stack, RMC self-review

### 🔧 API Reference
Technical API documentation:
- **[Agents API](api/agents.md)** - All 11 agents (BaseAgent, 10 task agents, AsyncContentCollector)
- **[CLI API](api/cli.md)** - CLI module structure, commands, utilities

### 📊 Analysis
- **[Input Limits Analysis](INPUT_LIMITS_ANALYSIS.md)** - Input source limits, RAG parameters, multi-source strategy

---

## 🚀 Quick Links

**For Users:**
- [Installation Guide](guides/getting-started.md#installation)
- [Your First Lecture](guides/getting-started.md#your-first-lecture)
- [Troubleshooting](guides/getting-started.md#troubleshooting)

**For Developers:**
- [Architecture Overview](architecture/system-overview.md)
- [Agent API Reference](api/agents.md)
- [CLI API Reference](api/cli.md)

---

## 📊 Project Status

**Version**: 0.4.2
**Status**: Production Ready+ (RMC Self-Review)
**Test Coverage**: ~48% with 1,356+ test functions
**Python**: 3.11, 3.12, 3.13

**Recent Updates:**
- ✅ **Version bump (v0.4.2)** - Version alignment across all docs and package files
- ✅ **translate quality (v0.4.1)** - PDF artifact removal, TOC detection, empty-section filter, AI/ML glossary, `--with-diagrams` flag; meta-commentary stripping in `content_expander.py`; `constants.py` magic-number removal; refined exception types; type hints added
- ✅ **Search Coverage Fix (v0.4.0)** - Full-section search indexing (removed [:500] truncation); `--re-evaluate` HTML stats auto-update; `--to-slides` always rewrites (≤35자); `--with-notes` O(n²) hang fix
- ✅ **RMC Self-Review (v0.3.8)** - 2-layer self-review in CurriculumDesigner, ContentWriter, QAAgent; LLM refusal detection
- ✅ **UI & Slides Enhancement (v0.3.7)** - Lightbox zoom, substring search, diagram full-width, Mermaid 10 API fix
- ✅ **Code Quality & Reliability (v0.3.6)** - retry utility, base classes, config validation, RAG env-vars
- ✅ **RAG quality boost (v0.3.5)** - 400-word answers, 15+15 retrieval, confidence fix, Rich rendering
- ✅ **Async I/O support (v0.3.4)** - 70% faster content collection
- ✅ **Multilingual support (v0.3.2)** - cross-lingual RAG, language detection

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/bullpeng72/Lecture_forge/issues)
- **CLI Help**: `lecture-forge --help` or `lecture-forge <command> --help`

---

**Last Updated**: 2026-02-24 (v0.4.2)
**Maintained by**: Sungwoo Kim
