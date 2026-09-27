"""Tests for the Claude CLI invocation used by the AI visual analyzer."""

from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

import ai_visual_analyzer  # noqa: E402
from ai_visual_analyzer import AIVisualAnalyzer, build_claude_command  # noqa: E402


def test_command_uses_print_mode_with_read_only_tools(tmp_path):
    shot = tmp_path / "overview.png"
    cmd = build_claude_command("Check the layout.", [shot])

    assert cmd[:2] == ["claude", "-p"]
    assert cmd[3:] == ["--allowedTools", "Read"]
    # The CLI has no image flag: the prompt names the image file for the Read tool
    assert str(shot.resolve()) in cmd[2]
    assert cmd[2].endswith("Check the layout.")


def test_command_lists_every_compared_image(tmp_path):
    before, after = tmp_path / "before.png", tmp_path / "after.png"
    prompt = build_claude_command("Compare.", [before, after])[2]
    assert str(before.resolve()) in prompt and str(after.resolve()) in prompt


def test_missing_cli_is_reported_as_unavailable(tmp_path):
    with (
        patch.object(ai_visual_analyzer.shutil, "which", return_value=None),
        patch.object(ai_visual_analyzer.subprocess, "run") as run,
    ):
        result = AIVisualAnalyzer._run_claude("prompt", [tmp_path / "x.png"])

    assert result["status"] == "unavailable"
    run.assert_not_called()


def test_cli_output_and_failures_are_recorded(tmp_path):
    shot = tmp_path / "x.png"
    ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="No issues found", stderr="")
    failed = subprocess.CompletedProcess(args=[], returncode=2, stdout="", stderr="")
    with (
        patch.object(ai_visual_analyzer.shutil, "which", return_value="/usr/bin/claude"),
        patch.object(
            ai_visual_analyzer.subprocess, "run", side_effect=[ok, failed, subprocess.TimeoutExpired("claude", 1)]
        ) as run,
    ):
        success = AIVisualAnalyzer._run_claude("prompt", [shot])
        error = AIVisualAnalyzer._run_claude("prompt", [shot])
        timeout = AIVisualAnalyzer._run_claude("prompt", [shot])

    assert success == {"status": "success", "analysis": "No issues found", "timestamp": success["timestamp"]}
    assert error["status"] == "error" and "exited with 2" in error["error"]
    assert timeout["status"] == "error"
    assert run.call_args_list[0].args[0] == build_claude_command("prompt", [shot])


def test_no_other_ai_backends_are_invoked():
    source = Path(ai_visual_analyzer.__file__).read_text(encoding="utf-8").lower()
    assert "gemini" not in source
