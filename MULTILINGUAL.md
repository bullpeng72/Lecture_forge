# 🌐 Multilingual Support Guide

> **Version**: 0.3.2+
> **Status**: ✅ Production Ready
> **Last Updated**: 2026-02-14

LectureForge now supports **multilingual knowledge bases** with automatic cross-lingual search!

---

## 🎯 Key Features

### 1. **Automatic Language Detection**
- Every chunk is automatically tagged with its language
- Supports Korean (ko), English (en), and other major languages
- Works with mixed-language PDFs (e.g., Korean text with English papers)

### 2. **Cross-Lingual Search (Dual Query)**
- Ask in Korean → Search both Korean AND English chunks
- Ask in English → Search both English AND Korean chunks
- Automatically translates queries for comprehensive results

### 3. **Intelligent Re-Ranking**
- Prioritizes same-language results (10% bonus)
- Includes cross-lingual results for comprehensive answers
- Removes duplicates and ranks by relevance

---

## 📚 Usage Examples

### Example 1: English PDF + Korean Query

```bash
$ lecture-forge create
# Add: Advanced_Python.pdf (English)

$ lecture-forge chat

You: 파이썬 데코레이터는 무엇인가요?

🌐 Detected language: Korean
🔄 Cross-lingual search enabled