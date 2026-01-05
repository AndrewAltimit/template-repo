# Reaction Search MCP Server

Semantic search MCP server for anime reaction images. Uses sentence-transformers to find contextually appropriate reactions based on natural language queries.

## Features

- **Semantic Search**: Natural language queries like "celebrating after fixing a bug"
- **Tag Filtering**: Filter results by emotion/action tags
- **Lazy Loading**: Model and embeddings loaded on first query
- **Caching**: Config cached locally with 1-week TTL
- **60+ Reactions**: Curated collection of anime reaction images

## Installation

```bash
# Install the package
pip install -e tools/mcp/mcp_reaction_search

# Or install dependencies directly
pip install sentence-transformers pyyaml requests
```

## Usage

### STDIO Mode (for Claude Code)

```bash
python -m mcp_reaction_search.server --mode stdio
```

### HTTP Mode

```bash
python -m mcp_reaction_search.server --mode http --port 8024
```

### Via .mcp.json

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "reaction-search": {
      "command": "python",
      "args": ["-m", "mcp_reaction_search.server", "--mode", "stdio"]
    }
  }
}
```

## Tools

### search_reactions

Search for reactions using natural language.

```python
# Example queries
"celebrating after fixing a bug"     # -> felix, aqua_happy
"confused about the error message"   # -> confused, miku_confused
"annoyed at the failing tests"       # -> kagami_annoyed, nao_annoyed
"deep in thought while debugging"    # -> thinking_foxgirl, hifumi_studious
```

**Parameters:**
- `query` (required): Natural language search query
- `limit` (optional): Max results (default: 5, max: 20)
- `tags` (optional): Filter by tags (e.g., ["smug", "happy"])
- `min_similarity` (optional): Minimum similarity threshold 0-1

**Returns:**
```json
{
  "success": true,
  "query": "celebrating after fixing a bug",
  "count": 3,
  "results": [
    {
      "id": "felix",
      "url": "https://raw.githubusercontent.com/.../felix.webp",
      "markdown": "![Reaction](https://...)",
      "description": "Happy, cheerful, or excited expression",
      "similarity": 0.8712,
      "tags": ["happy", "cheerful", "excited"],
      "usage_scenarios": ["Expressing joy or excitement", ...],
      "character_appearance": "Felix Argyle with pink headphones..."
    }
  ]
}
```

### get_reaction

Get a specific reaction by ID.

**Parameters:**
- `reaction_id` (required): Reaction identifier (e.g., "felix", "miku_typing")

### list_reaction_tags

List all available tags with occurrence counts.

### refresh_reactions

Force refresh the reaction cache from GitHub.

### reaction_search_status

Get server status including initialization state and cache info.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REACTION_SEARCH_MODEL` | `sentence-transformers/all-MiniLM-L12-v2` | HuggingFace model ID |
| `REACTION_CACHE_DIR` | `~/.cache/mcp_reaction_search` | Cache directory |

## Model

Uses [sentence-transformers/all-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L12-v2):
- 33M parameters
- 384-dimensional embeddings
- Good balance of speed and quality
- Downloaded automatically on first use (~120MB)

## Testing

```bash
# Run test script
python tools/mcp/mcp_reaction_search/scripts/test_server.py
```

## Docker

```bash
# Build and run
docker-compose up -d mcp-reaction-search

# View logs
docker-compose logs -f mcp-reaction-search
```

## Architecture

```
mcp_reaction_search/
├── server.py         # MCP server implementation
├── search_engine.py  # Semantic search with sentence-transformers
├── config_loader.py  # Config fetching and caching
└── tools.py          # Tool registry for CI
```

## Reaction Sources

Reactions are sourced from:
- [AndrewAltimit/Media](https://github.com/AndrewAltimit/Media/tree/main/reaction)

Config is fetched from:
- https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/config.yaml

## License

Part of the template-repo project. See repository LICENSE file.
