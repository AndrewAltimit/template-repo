#!/bin/bash

# Tmux + Lazygit Development Environment Setup
# Creates a 3-pane layout with Claude Code, Lazygit, and Terminal

# Start a new tmux session named 'dev' (detached)
# Kill existing session if it exists and create new one
if ! tmux new-session -d -s dev 2>/dev/null; then
    tmux kill-session -t dev 2>/dev/null
    tmux new-session -d -s dev
fi

# Create the layout
# Split vertically first (60% left, 40% right)
tmux split-window -h -t dev:0 -p 40

# Split the left pane horizontally (70% top, 30% bottom)
tmux select-pane -t dev:0.0
tmux split-window -v -t dev:0 -p 30

# Setup each pane
# Top-left pane (0): Claude Code / Main Editor
tmux select-pane -t dev:0.0
tmux send-keys -t dev:0.0 'clear' C-m
tmux send-keys -t dev:0.0 'echo "=== Claude Code / Editor ==="' C-m
tmux send-keys -t dev:0.0 'echo "Start with: claude-code, nvim, or your preferred editor"' C-m
# Uncomment the line below to auto-start your editor
# tmux send-keys -t dev:0.0 'nvim .' C-m

# Bottom-left pane (1): Terminal
tmux select-pane -t dev:0.1
tmux send-keys -t dev:0.1 'clear' C-m
tmux send-keys -t dev:0.1 'echo "=== Terminal ==="' C-m
tmux send-keys -t dev:0.1 'echo "General purpose terminal"' C-m

# Right pane (2): Lazygit
tmux select-pane -t dev:0.2
tmux send-keys -t dev:0.2 'clear' C-m
# Check if lazygit is installed
if command -v lazygit >/dev/null 2>&1; then
    tmux send-keys -t dev:0.2 'lazygit' C-m
else
    tmux send-keys -t dev:0.2 'echo "Lazygit not installed!"' C-m
    tmux send-keys -t dev:0.2 'echo "Install with: brew install lazygit (macOS)"' C-m
    tmux send-keys -t dev:0.2 'echo "or see: https://github.com/jesseduffield/lazygit"' C-m
    tmux send-keys -t dev:0.2 'echo ""' C-m
    tmux send-keys -t dev:0.2 'echo "Falling back to git status watch..."' C-m
    tmux send-keys -t dev:0.2 'watch -n 2 -c "git status -sb && echo && git diff --stat"' C-m
fi

# Optional: Set pane titles (requires tmux 2.3+)
tmux select-pane -t dev:0.0 -T "Editor"
tmux select-pane -t dev:0.1 -T "Terminal"
tmux select-pane -t dev:0.2 -T "Git"

# Select the main editor pane
tmux select-pane -t dev:0.0

# Attach to the session
tmux attach-session -t dev
