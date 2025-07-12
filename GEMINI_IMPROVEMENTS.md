# Gemini PR Review Script Improvements

## Key Enhancements

The Gemini PR review script has been significantly improved to handle large PRs better:

### 1. **Increased Diff Limits**
- **Before**: 10,000 character limit on diffs
- **After**: 75,000 character limit on diffs
- **Impact**: 7.5x more context for Gemini to analyze

### 2. **Chunked Analysis for Large PRs**
- **Before**: All PRs analyzed the same way, large diffs truncated
- **After**: Smart chunking by file groups for PRs > 50KB
- **File Groups**: workflows, python, docker, config, docs, other
- **Impact**: No more "code abruptly ending" issues

### 3. **Enhanced Context**
- **Before**: Limited to first 20 files listed
- **After**: All changed files listed
- **Workflow Files**: Full content included for workflow YAML files
- **Statistics**: Added file change statistics (+X/-Y lines)

### 4. **Better Error Handling**
- Fallback to basic Gemini model if pro model fails
- Improved error messages
- Local backup of review if posting fails

### 5. **Project Context Awareness**
- Reads PROJECT_CONTEXT.md for better understanding
- Container-first architecture considerations
- Single-maintainer project awareness

## Usage

The improved script is now the default at `scripts/gemini-pr-review.py` and is automatically used in the PR validation workflow.

## Performance

- Small PRs (< 50KB): Single comprehensive analysis
- Large PRs (> 50KB): Intelligent grouping and chunked analysis
- Workflow files: Always included in full for complete context