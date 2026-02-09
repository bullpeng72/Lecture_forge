# Technical Debt Analysis and Resolution

Perform a comprehensive technical debt analysis of the codebase and provide actionable recommendations for improvement.

## Analysis Scope

You should analyze the following aspects of technical debt:

### 1. Code Quality Issues
- Search for TODO, FIXME, HACK, XXX, NOTE comments
- Identify overly complex functions (>50 lines, deeply nested)
- Find duplicate or near-duplicate code
- Detect code smells (long parameter lists, god classes, etc.)

### 2. Architecture & Design
- Identify tightly coupled modules
- Find circular dependencies
- Locate missing abstractions or over-engineering
- Check for violations of SOLID principles

### 3. Dependencies & Infrastructure
- Check for outdated packages in requirements.txt, package.json, etc.
- Identify unused dependencies
- Find security vulnerabilities in dependencies
- Check for deprecated APIs or libraries

### 4. Testing & Documentation
- Calculate test coverage (if tests exist)
- Find untested critical paths
- Identify missing or outdated documentation
- Locate undocumented functions/classes

### 5. Performance & Scalability
- Find potential performance bottlenecks
- Identify inefficient algorithms or data structures
- Locate resource leaks (unclosed files, connections)
- Check for missing caching opportunities

### 6. Security & Best Practices
- Look for hardcoded credentials or secrets
- Find SQL injection or XSS vulnerabilities
- Check for improper error handling
- Identify missing input validation

## Analysis Process

Follow these steps systematically:

1. **Quick Scan** (5-10 files)
   - Get a sense of the codebase structure
   - Identify the main programming language(s)
   - Note the project type (web app, library, CLI, etc.)

2. **Pattern Search**
   - Use Grep to find technical debt markers (TODO, FIXME, etc.)
   - Search for common anti-patterns
   - Look for configuration files to check dependencies

3. **Deep Analysis** (largest/most critical files)
   - Read core files to assess complexity
   - Check for code duplication
   - Evaluate error handling and logging

4. **Dependency Check**
   - Read package manifests (requirements.txt, package.json, etc.)
   - Note versions and check for known outdated packages

5. **Generate Report**
   - Categorize findings by severity (Critical, High, Medium, Low)
   - Prioritize based on impact and effort
   - Provide specific file paths and line numbers
   - Include code snippets where relevant

## Output Format

Present your findings in this structured format:

```markdown
# 🔍 Technical Debt Analysis Report

**Project:** [Project Name]
**Date:** [Current Date]
**Files Analyzed:** [Number]

---

## 📊 Executive Summary

- **Critical Issues:** [Count]
- **High Priority:** [Count]
- **Medium Priority:** [Count]
- **Low Priority:** [Count]

**Overall Health Score:** [X/100]

---

## 🚨 Critical Issues

### 1. [Issue Title]
- **Category:** [Code Quality | Architecture | Security | Performance]
- **Severity:** Critical
- **Location:** `path/to/file.py:line_number`
- **Impact:** [Description of impact]
- **Recommendation:** [Specific action to take]

```python
# Example code snippet showing the issue
```

---

## ⚠️ High Priority Issues

[Same format as Critical]

---

## 📝 Medium Priority Issues

[Grouped and summarized]

---

## 💡 Low Priority Issues

[Brief list with file references]

---

## 🎯 Recommended Action Plan

### Phase 1: Immediate Fixes (This Week)
1. [Action item with file reference]
2. [Action item]

### Phase 2: Short-term Improvements (This Month)
1. [Action item]
2. [Action item]

### Phase 3: Long-term Refactoring (This Quarter)
1. [Action item]
2. [Action item]

---

## 📈 Metrics & Statistics

- **Total Lines of Code:** [Count]
- **Technical Debt Ratio:** [Percentage]
- **Average Function Complexity:** [Score]
- **Test Coverage:** [Percentage] (if available)
- **Outdated Dependencies:** [Count]

---

## 🔧 Quick Wins

These can be fixed with minimal effort but provide significant value:

1. [Quick fix with location]
2. [Quick fix]

---

## 📚 Resources

- [Link to best practices documentation]
- [Link to migration guides for outdated dependencies]
```

## Special Instructions

- **Be Specific:** Always include file paths and line numbers
- **Be Practical:** Focus on actionable items, not just theory
- **Prioritize:** Not all debt is equal - help the team focus on what matters
- **Provide Context:** Explain WHY something is technical debt, not just WHAT
- **Suggest Solutions:** For each issue, provide at least one concrete fix
- **Be Constructive:** Frame findings as opportunities for improvement

## Usage Examples

```bash
# Full codebase analysis
/techdebt

# Analyze specific directory
/techdebt src/agents/

# Focus on specific aspect
/techdebt --focus security

# Quick scan mode
/techdebt --quick
```

## Notes

- If the codebase is large (>100 files), focus on the most critical areas first
- Ask the user if they want to focus on a specific area if the scope is unclear
- Use the Explore agent for very large codebases
- Provide estimates for fixing high-priority items when possible
- Consider the project context (startup MVP vs enterprise system) when prioritizing
