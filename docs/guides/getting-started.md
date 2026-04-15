# Getting Started with LectureForge

Complete guide to installing and using LectureForge for the first time.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Your First Lecture](#your-first-lecture)
5. [Next Steps](#next-steps)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

- **Operating System**: macOS, Linux, or Windows
- **Python**: 3.11, 3.12, or 3.13
- **Memory**: 2GB+ RAM recommended
- **Disk Space**: 500MB+ for installation + 50MB per lecture

### Required API Keys

You'll need API keys from:
1. **OpenAI** (required)
   - Get from: [platform.openai.com](https://platform.openai.com)
   - Cost: Pay-per-use (~$0.035 per 60-min lecture, actual measured)

2. **Serper** (required)
   - Get from: [serper.dev](https://serper.dev)
   - Free tier: 2,500 searches/month

### Optional API Keys

For enhanced image search:
- **Pexels** - [pexels.com/api](https://pexels.com/api) (free, unlimited)
- **Unsplash** - [unsplash.com/developers](https://unsplash.com/developers) (free tier: 50/hour)

---

## Installation

### Method 1: pipx (Recommended ⭐⭐)

**Easiest and cleanest installation method:**

```bash
# Install pipx (if not already installed)
pip install pipx
pipx ensurepath

# Install LectureForge
pipx install lecture-forge

# Install Playwright (for web scraping)
pipx inject lecture-forge playwright
pipx runpip lecture-forge install playwright
playwright install chromium

# Verify installation
lecture-forge --version
```

**Why pipx?**
- ✅ Isolated environment (no dependency conflicts)
- ✅ Global `lecture-forge` command
- ✅ No need to activate environments
- ✅ Easy to upgrade: `pipx upgrade lecture-forge`

### Method 2: PyPI + conda (Recommended for Python Developers ⭐)

```bash
# Create Python 3.11 environment (strongly recommended)
conda create -n lecture-forge python=3.11
conda activate lecture-forge

# Install from PyPI
pip install lecture-forge

# Install Playwright browsers
playwright install chromium

# Verify installation
lecture-forge --version
```

### Method 3: Development Install (For Contributors)

```bash
# Clone repository
git clone https://github.com/bullpeng72/Lecture_forge.git
cd Lecture_forge

# Create environment
conda create -n lecture-forge python=3.11
conda activate lecture-forge

# Install in editable mode
pip install -e .

# Install Playwright
playwright install chromium

# Run tests
pytest
```

### Python Version Compatibility

| Python | Status | Notes |
|--------|--------|-------|
| 3.11 | ✅ **Recommended** | Full support, tested |
| 3.12 | ✅ Supported | Works correctly |
| 3.13 | ✅ Supported | Verified compatible (v0.3.8+) |

---

## Configuration

### Step 1: Initialize Configuration

Run the init command to set up your API keys:

```bash
lecture-forge init
```

This will:
1. Create `~/Documents/LectureForge/` directory
2. Prompt for required API keys (OpenAI, Serper)
3. Prompt for optional API keys (Pexels, Unsplash)
4. Create `.env` file with your settings

**Example session:**

```
🚀 LectureForge Configuration Setup

📁 Using default directory: ~/Documents/LectureForge/

📝 Required API Keys

1. OpenAI API Key
   • Get from: https://platform.openai.com
   • Used for: LLM generation, embeddings
   • Cost: ~$0.035 per 60-min lecture (GPT-4o-mini, actual measured)

   Enter your OpenAI API Key (starts with sk-): sk-proj-xxxxx
   ✓ OpenAI key saved (51 characters)

2. Serper API Key
   • Get from: https://serper.dev
   • Used for: Web search
   • Free tier: 2,500 searches/month

   Enter your Serper API Key: xxxxx
   ✓ Serper key saved (32 characters)

📸 Optional: Image Search APIs

3. Pexels API Key (Optional)
   Pexels API Key (or press Enter to skip):
   ⊘ Skipped

4. Unsplash Access Key (Optional)
   Unsplash Access Key (or press Enter to skip):
   ⊘ Skipped

✅ Configuration completed successfully!

📄 Configuration saved to: ~/Documents/LectureForge/.env

🎉 Next Steps:
   1. Start generating lectures:
      $ lecture-forge create

   2. Or see all available commands:
      $ lecture-forge --help
```

### Step 2: Verify Configuration

Check that your .env file was created:

```bash
lecture-forge home env
```

This opens the .env file in your default text editor.

### Step 3: (Optional) Customize Settings

Edit `.env` to customize settings:

```bash
# Required
OPENAI_API_KEY=sk-proj-...
SERPER_API_KEY=...

# Optional
PEXELS_API_KEY=...
UNSPLASH_ACCESS_KEY=...

# Model Settings (optional, has defaults)
DEFAULT_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

# Quality Settings (optional)
QUALITY_THRESHOLD=80
MAX_ITERATIONS=3
```

---

## Your First Lecture

### Interactive Mode (Recommended for First Time)

Generate your first lecture using interactive mode:

```bash
lecture-forge create
```

**Example interactive session:**

```
📚 LectureForge Pro v0.5.5 - Lecture Material Generator

Starting lecture generation...

=== Lecture Parameters ===

📌 Topic (e.g., "Introduction to Python"):
> Introduction to Machine Learning

⏱️  Duration in minutes (e.g., 60):
> 60

👥 Target audience level:
   1. beginner
   2. intermediate
   3. advanced
Select (1-3):
> 1

=== Content Sources ===

📄 Add PDF files? (y/n):
> y

Select PDF files (Ctrl+C to finish):
  1. machine_learning_basics.pdf
  2. data_science_handbook.pdf
  3. ...

Selected files: 1

🌐 Add URLs? (y/n):
> n

🔍 Add search keywords? (y/n):
> y

Enter keywords (one per line, Ctrl+D when done):
> machine learning basics
> supervised learning
> neural networks
> ^D

=== Options ===

🖼️  Enable image search from web? (Y/n):
> y

📊 Quality level (lenient/balanced/strict):
> balanced

Starting multi-agent pipeline...

📚 Phase 1: Collecting content...
   ✅ Content collected: 3 docs, 245 chunks

🖼️  Phase 2: Collecting images...
   📸 Extracting PDF images with location-based matching
   ✅ Images collected: 12

🔍 Phase 3a: Analyzing content...
   ✅ Analysis complete: 8 topics, 25 entities

📋 Phase 3b: Designing curriculum...
   ✅ Curriculum designed: 5 sections

✍️  Phase 4: Writing content...
==================================================
Section 1/5: Introduction to Machine Learning
==================================================
   📷 Available images: 12
   ✅ Used 2 images in this section
   ...

📊 Phase 5: Generating diagrams...
   ✅ Generated 3 Mermaid diagrams

🎨 Phase 6: Assembling HTML...
   ✅ HTML assembled

✅ Phase 7: Quality evaluation...
   ✅ Quality score: 85.2/100

✅ Lecture generated successfully!

📄 HTML File: /Users/you/Documents/LectureForge/outputs/Introduction_to_Machine_Learning_20260215_103045.html
🗄️  Knowledge Base: /Users/you/Documents/LectureForge/data/vector_db/Introduction_to_Machine_Learning_20260215_103045

📊 Statistics:
   • Sections: 5
   • Words: 4,250
   • Diagrams: 3
   • Images: 12
   • Quality score: 85.2/100

💰 Cost Estimate:
   • Total tokens: 12,500
   • Estimated cost: $0.045

💡 Open the HTML file in a browser to view the lecture!
```

### Config File Mode (Advanced)

Create a config file for repeatable generation:

**lecture_config.yaml:**
```yaml
topic: "Introduction to Machine Learning"
duration: 60
audience_level: "beginner"
pdfs:
  - "ml_textbook.pdf"
  - "ml_handbook.pdf"
urls:
  - "https://scikit-learn.org/stable/tutorial/index.html"
keywords:
  - "machine learning basics"
  - "supervised learning"
  - "neural networks"
image_keywords:
  - "machine learning diagram"
  - "neural network visualization"
```

**Generate from config:**
```bash
lecture-forge create --config lecture_config.yaml
```

### Quick Commands

```bash
# With image search enabled
lecture-forge create --image-search

# High quality mode
lecture-forge create --quality-level strict

# Custom output name
lecture-forge create --output "ML_Introduction"

# Enable interactive Q&A mode during generation (-i)
lecture-forge create --interactive

# Web images only (faster)
lecture-forge create --no-include-pdf-images

# Async mode (70% faster content collection, v0.3.4+)
lecture-forge create --async-mode

# Reuse an existing knowledge base (read-only)
lecture-forge create --existing-kb data/vector_db/MyTopic_...

# Extend an existing knowledge base with new sources
lecture-forge create --existing-kb data/vector_db/MyTopic_... --kb-mode extend
```

---

## Next Steps

### 1. View Your Lecture

Open the generated HTML file in your browser:

```bash
# Open outputs folder
lecture-forge home outputs
```

Or open directly:
```bash
open ~/Documents/LectureForge/outputs/Introduction_to_Machine_Learning_*.html
```

### 2. Interactive Q&A

Chat with your knowledge base:

```bash
lecture-forge chat
```

**Example Q&A session:**

```
🤖 LectureForge Q&A Agent

Available knowledge bases:
  1. Introduction_to_Machine_Learning_20260215_103045
  2. Python_Programming_20260214_154520

Select knowledge base (1-2):
> 1

✅ Loaded: Introduction_to_Machine_Learning_20260215_103045
📊 Collection stats: 245 chunks

Type /help for commands, /exit to quit

You: What is supervised learning?

🔍 Searching knowledge base... (1.2s)

Answer:
Supervised learning is a type of machine learning where the model is trained on
labeled data. The training data consists of input-output pairs, and the algorithm
learns to map inputs to outputs. Common examples include:

• Classification: Predicting categories (e.g., spam vs. not spam)
• Regression: Predicting continuous values (e.g., house prices)

Key characteristics:
- Requires labeled training data
- Can make predictions on new, unseen data
- Accuracy depends on quality and quantity of training data

📚 Sources: 3 documents (pages 12, 15, 23)
🎯 Confidence: High

You: /exit

Goodbye! 👋
```

### 3. Web-Based Editor (New in v0.5.0, Optional)

Edit lecture content directly in your browser:

```bash
lecture-forge edit outputs/your_lecture.html
```

This opens a 3-panel GUI editor on port 5757:
- **Left**: Section list with add/delete/reorder controls
- **Center**: Markdown editor (EasyMDE) with live preview
- **Right**: Image gallery with RAG-based alternative search

**Options:**
```bash
lecture-forge edit outputs/lecture.html --port 8080     # Custom port
lecture-forge edit outputs/lecture.html --no-browser    # Server only
```

### 4. Edit Images (Optional)

Edit images in your generated lecture using the CLI:

```bash
lecture-forge edit-images outputs/your_lecture.html
```

### 5. Convert to Slides (Optional)

Convert your lecture to presentation slides:

```bash
# Basic conversion (per-section LLM rewrite included by default: ≤35자, no truncation)
lecture-forge improve outputs/your_lecture.html --to-slides

# Without presenter notes (notes are included by default)
lecture-forge improve outputs/your_lecture.html --to-slides --without-notes
```

This creates a Reveal.js presentation with:
- Keyboard navigation (Arrow keys, Space)
- Overview mode (Esc)
- Speaker notes (S) — press S to open speaker view (included by default; use `--without-notes` to disable)
- Full screen (F)

### 6. Translate English PDF (Optional)

Convert an English PDF directly into Korean lecture material (v0.4.1+):

```bash
# Basic translation (→ paper_ko.html)
lecture-forge translate paper.pdf

# Specify output name
lecture-forge translate paper.pdf -o my_lecture_ko

# Keep original English (structure debug, fast)
lecture-forge translate paper.pdf --no-translate

# Beginner-level Korean + slides
lecture-forge translate paper.pdf --audience-level beginner --with-slides

# Include Mermaid diagrams (opt-in; PDF images used by default)
lecture-forge translate paper.pdf --with-diagrams
```

### 7. Manage Storage

Delete old knowledge bases to free space:

```bash
# Interactive selection
lecture-forge cleanup

# Delete all (dangerous!) — also available as -a
lecture-forge cleanup --all
```

---

## Troubleshooting

### Issue: "No module named 'lecture_forge'"

**Problem**: Installation didn't complete correctly.

**Solution:**
```bash
# Verify installation
pip list | grep lecture-forge

# Reinstall
pip install --upgrade lecture-forge
```

### Issue: "OPENAI_API_KEY not found"

**Problem**: .env file not found or not loaded.

**Solution:**
```bash
# Run init again
lecture-forge init

# Or manually create .env
lecture-forge home env
# Add: OPENAI_API_KEY=sk-proj-...
```

### Issue: "playwright not found"

**Problem**: Playwright browsers not installed.

**Solution:**
```bash
playwright install chromium
```

### Issue: Generation is slow

**Causes and Solutions:**

1. **Large PDFs**: PDFs with 1000+ pages take longer
   - Solution: Split into smaller PDFs or use specific pages

2. **Many images**: Image quality analysis is slow
   - Solution: Use `--no-include-pdf-images` for faster generation

3. **High quality level**: Strict mode triggers more revisions
   - Solution: Use `balanced` or `lenient` quality level

### Issue: Low quality score

**Solutions:**

1. **Provide more sources**: Add more PDFs/URLs/keywords
2. **Increase duration**: Longer lectures have more room for quality
3. **Use strict quality**: Force higher standards
4. **Better image keywords**: More specific keywords = better images

### Getting Help

- **Documentation**: See `/docs` directory
- **Examples**: See `/examples` directory
- **Issues**: [GitHub Issues](https://github.com/bullpeng72/Lecture_forge/issues)
- **CLI Help**: `lecture-forge --help`
- **Command Help**: `lecture-forge create --help`

---

## Common Workflows

### Workflow 1: Quick Lecture from PDF

```bash
lecture-forge create
# → Select PDF
# → Set topic and duration
# → Use defaults for everything else
```

### Workflow 2: High-Quality Research Lecture

```bash
# 1. Create with strict quality
lecture-forge create --quality-level strict --image-search

# 2. Review and enhance if needed
lecture-forge improve outputs/lecture.html --to-slides

# 3. Chat with knowledge base
lecture-forge chat
```

### Workflow 3: Series of Related Lectures

```bash
# Create config files
# lecture_1.yaml, lecture_2.yaml, lecture_3.yaml

# Generate series
lecture-forge create -c lecture_1.yaml
lecture-forge create -c lecture_2.yaml
lecture-forge create -c lecture_3.yaml

# View all outputs
lecture-forge home outputs
```

---

## What's Next?

**Explore Advanced Features:**
- [CLI API Reference](../api/cli.md) - Detailed options for all commands
- [Architecture Overview](../architecture/system-overview.md) - How the system works
- [Input Limits Analysis](../INPUT_LIMITS_ANALYSIS.md) - RAG parameters and multi-source strategy

**For Developers:**
- [Agent API Reference](../api/agents.md)
- [Architecture Overview](../architecture/system-overview.md)

---

**Last Updated**: 2026-04-13
**Version**: 0.5.5

**Ready to create amazing lectures? Start with:**
```bash
lecture-forge create
```
