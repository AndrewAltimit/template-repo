# Gaea2 MCP Server Documentation

The Gaea2 MCP server is implemented in Rust. The authoritative, up-to-date reference for
its tools, parameters, configuration, deployment and limitations is the crate README:

**[tools/mcp/mcp_gaea2/README.md](../README.md)**

Quick facts:

- Production server: Windows host at `192.168.0.152:8007` with Gaea2 installed
  (`.mcp.json`: `{"type": "http", "url": "http://192.168.0.152:8007/messages"}`).
- Start on Windows: `automation/launchers/windows/start-gaea2-mcp.bat`
  (or `mcp-gaea2 --mode standalone --port 8007 --gaea-path <Gaea.Swarm.exe> --output-dir <dir>`).
- Docker (`docker compose --profile services up -d mcp-gaea2`) provides every tool except
  the Gaea.Swarm build tools.
- Workflows are validated before a file is written; invalid workflows are rejected with
  the list of errors instead of producing a broken `.terrain` file.

See [INDEX.md](INDEX.md) for the remaining background documents and
[GAEA2_QUICK_REFERENCE.md](GAEA2_QUICK_REFERENCE.md) for a one-page cheat sheet.
