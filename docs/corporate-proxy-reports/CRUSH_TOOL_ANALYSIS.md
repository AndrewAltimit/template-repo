# Crush Tool Analysis Report

## Executive Summary
Deep dive analysis of Crush source code reveals **12 primary tools** available. Our corporate proxy implementation currently supports **6 of these tools** (50% coverage).

---

## Complete Tool Inventory from Crush Source

### 1. ✅ **bash** (`/internal/llm/tools/bash.go`)
- **Status**: Implemented in our proxy
- **Purpose**: Execute shell commands
- **Parameters**: `command`, `timeout`

### 2. ❌ **diagnostics** (`/internal/llm/tools/diagnostics.go`)
- **Status**: NOT implemented
- **Purpose**: Get diagnostic information about the system
- **Parameters**: Various diagnostic queries

### 3. ❌ **download** (`/internal/llm/tools/download.go`)
- **Status**: NOT implemented
- **Purpose**: Download files from URLs
- **Parameters**: `url`, `file_path`, `timeout`

### 4. ✅ **edit** (`/internal/llm/tools/edit.go`)
- **Status**: Partially implemented (basic version)
- **Purpose**: Edit files by replacing content
- **Parameters**: `file_path`, `old_string`, `new_string`, `replace_all`

### 5. ❌ **fetch** (`/internal/llm/tools/fetch.go`)
- **Status**: NOT implemented
- **Purpose**: Fetch content from URLs and convert to markdown
- **Parameters**: `url`, `format`, `timeout`

### 6. ❌ **glob** (`/internal/llm/tools/glob.go`)
- **Status**: NOT implemented
- **Purpose**: Find files matching patterns
- **Parameters**: `pattern`, `path`

### 7. ✅ **grep** (`/internal/llm/tools/grep.go`)
- **Status**: Basic implementation
- **Purpose**: Search for patterns in files
- **Parameters**: `pattern`, `path`, `type`, `glob`, `output_mode`

### 8. ✅ **ls** (`/internal/llm/tools/ls.go`)
- **Status**: Basic implementation as "list"
- **Purpose**: List directory contents
- **Parameters**: `path`, `ignore`

### 9. ❌ **multiedit** (`/internal/llm/tools/multiedit.go`)
- **Status**: NOT implemented
- **Purpose**: Make multiple edits to a file in one operation
- **Parameters**: `file_path`, `edits[]` (array of edit operations)

### 10. ❌ **sourcegraph** (`/internal/llm/tools/sourcegraph.go`)
- **Status**: NOT implemented
- **Purpose**: Search code using Sourcegraph API
- **Parameters**: `query`, `repo`, `file`, `lang`

### 11. ✅ **view** (`/internal/llm/tools/view.go`)
- **Status**: Implemented as "read"
- **Purpose**: View file contents with offset/limit
- **Parameters**: `file_path`, `offset`, `limit`

### 12. ✅ **write** (`/internal/llm/tools/write.go`)
- **Status**: Fully implemented
- **Purpose**: Create or overwrite files
- **Parameters**: `file_path`, `content`

---

## Implementation Coverage Analysis

### Currently Implemented (6/12 = 50%)
1. ✅ **write** - Full support
2. ✅ **view/read** - Full support
3. ✅ **bash** - Full support
4. ✅ **edit** - Basic support
5. ✅ **ls/list** - Basic support
6. ✅ **grep** - Basic support

### Missing Tools (6/12 = 50%)
1. ❌ **diagnostics** - System diagnostics
2. ❌ **download** - File downloading
3. ❌ **fetch** - URL content fetching
4. ❌ **glob** - Pattern-based file finding
5. ❌ **multiedit** - Batch editing
6. ❌ **sourcegraph** - Code search integration

---

## Critical Missing Tools for Corporate Use

### High Priority
1. **fetch** - Essential for retrieving documentation, API responses
2. **download** - Needed for downloading dependencies, assets
3. **glob** - Important for finding files by pattern

### Medium Priority
4. **multiedit** - Useful for refactoring multiple parts of a file
5. **diagnostics** - Helpful for debugging issues

### Low Priority
6. **sourcegraph** - Specialized code search (requires API key)

---

## Tool Parameter Details

### Write Tool
```go
type WriteParams struct {
    FilePath string `json:"file_path"`
    Content  string `json:"content"`
}
```

### View Tool
```go
type ViewParams struct {
    FilePath string `json:"file_path"`
    Offset   int    `json:"offset"`
    Limit    int    `json:"limit"`
}
```

### Edit Tool
```go
type EditParams struct {
    FilePath    string `json:"file_path"`
    OldString   string `json:"old_string"`
    NewString   string `json:"new_string"`
    ReplaceAll  bool   `json:"replace_all"`
}
```

### Bash Tool
```go
type BashParams struct {
    Command string `json:"command"`
    Timeout int    `json:"timeout,omitempty"`
}
```

### Grep Tool
```go
type GrepParams struct {
    Pattern    string `json:"pattern"`
    Path       string `json:"path"`
    Type       string `json:"type,omitempty"`
    Glob       string `json:"glob,omitempty"`
    OutputMode string `json:"output_mode,omitempty"`
}
```

### Fetch Tool (Missing)
```go
type FetchParams struct {
    URL     string `json:"url"`
    Format  string `json:"format"`
    Timeout int    `json:"timeout,omitempty"`
}
```

### Download Tool (Missing)
```go
type DownloadParams struct {
    URL      string `json:"url"`
    FilePath string `json:"file_path"`
    Timeout  int    `json:"timeout,omitempty"`
}
```

### MultiEdit Tool (Missing)
```go
type MultiEditParams struct {
    FilePath string      `json:"file_path"`
    Edits    []EditEntry `json:"edits"`
}
```

---

## Recommendations

### Immediate Actions
1. **Add fetch tool** - Most commonly needed missing tool
2. **Add download tool** - Essential for retrieving files
3. **Add glob tool** - Important for file discovery

### Implementation Strategy
1. Update `structured_tool_api_v2.py` to include new tool definitions
2. Add pattern matching for natural language detection
3. Create mock implementations for testing
4. Update test suites to validate new tools

### Sample Implementation for Fetch Tool
```python
"fetch": Tool(
    name="fetch",
    description="Fetch content from a URL",
    parameters=[
        ToolParameter("url", "string", "URL to fetch"),
        ToolParameter("format", "string", "Output format (markdown/text)"),
        ToolParameter("timeout", "integer", "Timeout in seconds", required=False)
    ]
)
```

---

## Conclusion

Our current implementation covers the **core essential tools** (write, read, bash) that handle basic file operations. However, we're missing **50% of Crush's capabilities**, particularly around:
- Web content fetching (fetch, download)
- Advanced file operations (glob, multiedit)
- System diagnostics

To achieve full Crush compatibility, we should prioritize implementing the fetch, download, and glob tools as they are most likely to be used in typical AI-assisted development workflows.
