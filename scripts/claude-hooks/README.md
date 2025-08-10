# Claude Code Hooks

This directory contains custom hooks for Claude Code to enforce best practices and prevent common mistakes.

## Available Hooks

### gh-comment-validator.py

**Purpose**: Prevents incorrect GitHub comment formatting that would escape the `!` character in reaction images.

**Type**: PreToolUse hook for Bash tool

**What it prevents**:
- Using `--body` flag directly with reaction images
- Using heredocs (`cat <<EOF`) to create comment files
- Using echo/printf to pipe content to gh commands
- Command substitution with echo/printf containing reaction images

**Correct method enforced**:
1. Use the Write tool to create a temporary markdown file
2. Use `gh pr comment --body-file /tmp/filename.md` to post

## Configuration

The hooks are registered in `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": {
      "Bash": "python3 /home/miku/Documents/repos/template-repo/scripts/claude-hooks/gh-comment-validator.py"
    }
  }
}
```

## How Hooks Work

1. **PreToolUse hooks** run after Claude creates tool parameters but before the tool executes
2. The hook receives tool details as JSON on stdin
3. The hook can:
   - Allow the tool to run: `{"permissionDecision": "allow"}`
   - Block the tool: `{"permissionDecision": "deny", "permissionDecisionReason": "..."}`
   - Ask for user confirmation: `{"permissionDecision": "ask"}`

## Adding New Hooks

1. Create a new Python script in this directory
2. Read tool input from stdin as JSON
3. Implement validation logic
4. Return permission decision as JSON
5. Register in `.claude/settings.json`

## Testing Hooks

To test a hook manually:

```bash
echo '{"tool_name": "Bash", "tool_input": {"command": "gh pr comment 50 --body \"Test ![Reaction](url)\""}}' | \
  python3 scripts/claude-hooks/gh-comment-validator.py
```

Expected output for incorrect format:
```json
{
  "permissionDecision": "deny",
  "permissionDecisionReason": "❌ Incorrect GitHub comment formatting detected!..."
}
```

## References

- [Claude Code Hooks Documentation](https://docs.anthropic.com/en/docs/claude-code/hooks)
- Project-specific formatting rules in `CLAUDE.md`
