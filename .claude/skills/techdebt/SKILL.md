---
name: techdebt
description: Analyze and report on technical debt in the LectureForge codebase. Use when reviewing code quality, identifying maintainability issues, refactoring priorities, or assessing architectural improvements needed.
argument-hint: [path-or-component]
allowed-tools: Read, Grep, Glob, Bash
---

# Technical Debt Analysis for LectureForge

Perform comprehensive technical debt analysis on the specified code area or entire project.

## Usage

```bash
# Analyze entire project
/techdebt

# Analyze specific module
/techdebt src/lecture_forge/agents/

# Analyze specific file
/techdebt src/lecture_forge/cli.py

# Analyze multiple areas (space-separated)
/techdebt src/lecture_forge/agents/ src/lecture_forge/quality/
```

## Analysis Framework

When analyzing `$ARGUMENTS` (or entire project if no arguments), examine:

### 1. Code Quality Issues ⚠️

- **Complexity Hotspots**: Functions with high cyclomatic complexity or deep nesting
- **Code Duplication**: Repeated logic that should be abstracted
- **Anti-Patterns**: Known code smells (God classes, long parameter lists, etc.)
- **Naming & Documentation**: Unclear names, missing docstrings, inadequate comments
- **Type Safety**: Missing or incorrect type hints
- **Error Handling**: Inconsistent exception handling, bare excepts, missing validations

### 2. Testing & Quality Assurance 🧪

- **Test Coverage**: Missing unit tests, integration tests, or edge case tests
- **Test Quality**: Brittle tests, lack of test data management, unclear assertions
- **Testability**: Hard-to-test code due to tight coupling or side effects
- **CI/CD**: Missing automated checks, linting, or quality gates

### 3. Architectural Debt 🏗️

- **Coupling & Cohesion**: Tight coupling between modules, low cohesion within modules
- **SOLID Violations**: Single Responsibility, Open/Closed, Liskov Substitution, etc.
- **Layering**: Violated architectural boundaries (e.g., CLI calling database directly)
- **Abstraction Issues**: Missing abstractions or over-engineering
- **Agent System**: Inefficient agent communication, unclear responsibilities
- **RAG Pipeline**: Inefficient vector operations, poor chunk management

### 4. Dependencies & Configuration 📦

- **Dependency Health**: Outdated packages, security vulnerabilities, unnecessary deps
- **Dependency Management**: Circular dependencies, version conflicts
- **Configuration**: Hard-coded values, missing environment variable validation
- **Magic Numbers**: Unexplained constants, undocumented thresholds

### 5. Performance & Scalability 🚀

- **Algorithm Efficiency**: Inefficient algorithms (O(n²) where O(n log n) possible)
- **Database/Vector DB**: Unoptimized queries, missing indexes, N+1 queries
- **Memory Management**: Memory leaks, large object copying, inefficient data structures
- **API Usage**: Inefficient LLM API calls, missing caching, rate limit issues
- **I/O Operations**: Blocking I/O, missing async patterns, redundant file reads

### 6. Security & Best Practices 🔒

- **Security Issues**: SQL injection, command injection, XSS vulnerabilities
- **Secrets Management**: Hard-coded API keys, insecure credential storage
- **Input Validation**: Missing or weak input validation
- **Error Exposure**: Stack traces or sensitive info in error messages

### 7. Documentation & Knowledge 📚

- **Code Documentation**: Missing README, outdated architecture docs
- **API Documentation**: Undocumented public APIs, unclear function signatures
- **Design Decisions**: No ADRs (Architecture Decision Records), unclear rationale
- **Onboarding**: Missing setup instructions, contributing guidelines

### 8. LectureForge-Specific Concerns 🎓

- **Agent Orchestration**: Inefficient agent sequencing, missing parallel execution
- **RAG Quality**: Poor chunking strategies, inadequate retrieval quality
- **Token Management**: Excessive token usage, missing cost optimization
- **Template System**: Hard-coded HTML/CSS, poor template reusability
- **CLI UX**: Confusing commands, missing progress indicators, poor error messages
- **Image Processing**: Inefficient image handling, missing cleanup, duplicate detection issues

## Reporting Format

For each technical debt item identified:

```markdown
### [SEVERITY] Issue Title

**Location**: `path/to/file.py:lines`
**Category**: Code Quality | Testing | Architecture | Performance | Security | Documentation
**Severity**: 🔴 High | 🟡 Medium | 🟢 Low

**Description**:
Clear explanation of what the issue is.

**Impact**:
- Maintenance cost: Why it makes code harder to maintain
- Defect risk: How it might lead to bugs
- Performance impact: If applicable
- Developer experience: How it affects productivity

**Recommendation**:
Specific, actionable steps to resolve the issue.

**Effort Estimate**:
🕐 Quick (< 1h) | 🕑 Medium (1-4h) | 🕒 Large (> 4h)

**Priority Score**: X/10
(Based on: Impact × Likelihood × Urgency / Effort)
```

## Priority Scoring

Calculate priority using:

```
Priority = (Impact × Likelihood × Urgency) / Effort
```

- **Impact**: 1-5 (how much it hurts if not fixed)
- **Likelihood**: 1-5 (probability it will cause problems)
- **Urgency**: 1-5 (how soon it needs fixing)
- **Effort**: 1-5 (complexity of the fix)

**Interpretation**:
- **10+**: Critical - Fix immediately
- **5-9**: High - Schedule soon
- **2-4**: Medium - Backlog
- **< 2**: Low - Nice-to-have

## Analysis Steps

1. **Scan Code Structure**
   - Use Glob to identify all Python files in target area
   - Categorize by module (agents, tools, knowledge, quality, CLI)

2. **Static Analysis**
   - Check for missing type hints, docstrings
   - Identify long functions (>50 lines), complex functions (>10 branches)
   - Find code duplication patterns

3. **Dependency Analysis**
   - Check import structure for circular dependencies
   - Identify tight coupling between modules
   - Review external dependency usage

4. **Test Coverage Assessment**
   - Check for presence of test files
   - Estimate coverage by comparing test files to source files
   - Identify untested critical paths

5. **Performance Review**
   - Look for inefficient patterns (nested loops, redundant I/O)
   - Check API call optimization (batching, caching)
   - Review database/vector store queries

6. **Security Scan**
   - Check for hard-coded secrets or credentials
   - Look for unsafe input handling
   - Review command execution for injection risks

7. **Documentation Audit**
   - Check for README, CONTRIBUTING, architecture docs
   - Review docstring coverage
   - Assess code comment quality

## Summary Report Format

```markdown
# Technical Debt Report: $ARGUMENTS

**Generated**: YYYY-MM-DD HH:MM
**Scope**: [Full Project | Specific Module]
**Total Issues**: XX
**Estimated Effort**: XX hours

## Executive Summary

[2-3 sentence overview of major findings]

## Issue Breakdown

| Severity | Count | Est. Effort |
|----------|-------|-------------|
| 🔴 High  | XX    | XX hours    |
| 🟡 Medium| XX    | XX hours    |
| 🟢 Low   | XX    | XX hours    |

## Top 5 Priority Issues

1. [Issue with highest priority score]
2. [Second highest]
3. ...

## Detailed Issues

[Full list of issues grouped by category]

## Recommendations Roadmap

### Immediate (This Sprint)
- Fix critical security issues
- Resolve high-priority bugs

### Short-term (Next 1-2 Sprints)
- Add missing tests
- Refactor complexity hotspots

### Long-term (Backlog)
- Architectural improvements
- Documentation enhancements

## Metrics

- **Code Quality Score**: X/10
- **Test Coverage**: ~X%
- **Documentation Coverage**: X/10
- **Dependency Health**: X/10

## Positive Highlights

[List 3-5 things that are done well in the codebase]
```

## Configuration

This skill uses read-only tools by default. To perform actual fixes, use:

```bash
# Analyze and propose fixes (read-only)
/techdebt src/module/

# After review, ask Claude to implement fixes:
"Please implement the top 3 high-priority fixes from the techdebt report"
```

## Integration with LectureForge Workflow

After generating a technical debt report:

1. **Review**: Discuss findings with the team
2. **Prioritize**: Agree on which issues to tackle
3. **Track**: Create issues in GitHub/project tracker
4. **Schedule**: Allocate time in sprint planning
5. **Measure**: Re-run `/techdebt` periodically to track improvement

## Example Output

```markdown
# Technical Debt Report: src/lecture_forge/agents/

**Generated**: 2026-02-08 14:30
**Scope**: All agent modules
**Total Issues**: 12
**Estimated Effort**: 18 hours

## Executive Summary

The agents module shows good separation of concerns but lacks comprehensive testing (only 2/10 agents have tests). Performance optimization opportunities exist in the content writer agent's RAG queries. Documentation is sparse with missing docstrings on 40% of public methods.

## Top 5 Priority Issues

1. [Priority 8.5] Missing unit tests for 8/10 agents
2. [Priority 7.2] Content Writer agent makes redundant RAG calls
3. [Priority 6.8] No error handling in Image Collector API calls
...
```

---

**Note**: This skill is designed for LectureForge specifically but can be adapted for other Python projects by modifying the "LectureForge-Specific Concerns" section.
