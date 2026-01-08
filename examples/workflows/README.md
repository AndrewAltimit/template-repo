# Example Workflows

This directory contains example/template GitHub Actions workflows that demonstrate various agent automation patterns.

## Available Examples

### scheduled-agent-work.example.yml

A complete example of scheduled autonomous agent work using GitHub Projects v2 boards.

**Features:**
- Scheduled runs during business hours (configurable)
- Manual trigger for on-demand work
- Integration with `board-agent-worker.yml` reusable workflow
- Multi-agent support (Claude, OpenCode, Gemini, Crush, Codex)
- Notification hooks (Slack, Teams, etc.)
- Weekly summary reports

**Usage:**

1. Copy to your `.github/workflows/` directory
2. Rename to `scheduled-agent-work.yml`
3. Configure your `ai-agents-board.yml` board configuration
4. Set required secrets:
   - `AGENT_TOKEN` - GitHub token with repo write access
   - `GH_PROJECTS_TOKEN` - Classic token with project scope
   - `OPENROUTER_API_KEY` - For OpenCode/Crush agents (optional)
5. Customize schedule, agents, and notifications

**Customization Points:**
- Schedule frequency (cron expressions)
- Agent selection and priorities
- Timeout and max-issues settings
- Notification integrations
- Weekly summary content

## Related Files

- `.github/workflows/board-agent-worker.yml` - Reusable workflow for agent work
- `ai-agents-board.yml` - Board configuration
- `.agents.yaml` - Agent configuration

## Notes

- The main workflow at `.github/workflows/scheduled-agent-work.yml` has schedules disabled by default
- Use the example in this directory as a reference for full functionality
- Always test with `dry-run: true` before enabling scheduled automation
