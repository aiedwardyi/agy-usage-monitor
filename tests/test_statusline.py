#!/usr/bin/env python3
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATUSLINE_PY = ROOT / "statusline.py"


def run_statusline(payload_dict=None, raw_input=None, env_vars=None):
    env = os.environ.copy()
    # Strip any inherited AGY_ or CQB_ configs
    for k in list(env.keys()):
        if k.startswith("AGY_") or k.startswith("CQB_"):
            del env[k]
    env["PYTHONIOENCODING"] = "utf-8"
    if env_vars:
        env.update(env_vars)

    if raw_input is None:
        raw_input = json.dumps(payload_dict) if payload_dict is not None else ""

    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(STATUSLINE_PY)],
        input=raw_input,
        text=True,
        capture_output=True,
        cwd=ROOT,
        env=env,
        encoding="utf-8",
    )
    return proc


def test_basic_render():
    payload = {
        "product": "antigravity",
        "model": {"display_name": "Gemini 3.8 Flash (High)"},
        "workspace": {"project_dir": str(ROOT)},
        "vcs": {"branch": "main"},
        "context_window": {
            "used_percentage": 5.0,
            "total_input_tokens": 45200,
            "total_output_tokens": 12300,
            "context_window_size": 1048576,
        },
        "quota": {
            "gemini-weekly": {
                "remaining_fraction": 0.85,
                "reset_in_seconds": 270000,
            }
        },
        "task_count": 0,
        "terminal_width": 100,
    }
    proc = run_statusline(payload)
    assert proc.returncode == 0
    lines = proc.stdout.strip().split("\n")
    assert len(lines) == 2
    # Model cleaned up
    assert "Gemini 3.8 Flash" in lines[0]
    assert "(High)" not in lines[0]
    # Branch
    assert "agy-usage-monitor/main" in lines[0]
    # Context %
    assert "95%" in lines[1]
    # Tokens
    assert "↑45.2k" in lines[1]
    # Quota
    assert "Weekly:" in lines[1]
    assert "85%" in lines[1]
    assert "(3d3h)" in lines[1]


def test_empty_and_invalid_input():
    proc = run_statusline(raw_input="")
    assert proc.returncode == 0
    assert "Antigravity" in proc.stdout

    proc_bad = run_statusline(raw_input="not-json")
    assert proc_bad.returncode == 0
    assert "Antigravity" in proc_bad.stdout


def test_agy_env_isolation():
    payload = {
        "product": "antigravity",
        "model": {"display_name": "Gemini 3.8 Pro"},
        "context_window": {"used_percentage": 10},
        "quota": {"gemini-weekly": {"remaining_fraction": 0.9}},
    }
    # Test AGY_BAR=0 disables bar
    proc = run_statusline(payload, env_vars={"AGY_BAR": "0"})
    assert proc.returncode == 0
    assert "\u25b0" not in proc.stdout

    # CQB_ should NOT affect AGY
    proc_cqb = run_statusline(payload, env_vars={"CQB_BAR": "0"})
    assert proc_cqb.returncode == 0
    assert "\u25b0" in proc_cqb.stdout


def test_tasks_and_context_size():
    payload = {
        "product": "antigravity",
        "model": {"display_name": "Gemini 3.8 Flash"},
        "context_window": {
            "used_percentage": 20,
            "context_window_size": 1048576,
        },
        "task_count": 2,
    }
    proc = run_statusline(payload, env_vars={"AGY_CONTEXT_SIZE": "1"})
    assert proc.returncode == 0
    assert "2 tasks" in proc.stdout
    assert "of 1M" in proc.stdout


def test_narrow_terminal_truncation():
    payload = {
        "product": "antigravity",
        "model": {"display_name": "Gemini 3.8 Flash"},
        "context_window": {
            "used_percentage": 15,
            "total_input_tokens": 50000,
            "total_output_tokens": 12000,
        },
        "quota": {
            "gemini-weekly": {
                "remaining_fraction": 0.85,
                "reset_in_seconds": 270000,
            }
        },
        "terminal_width": 35,
    }
    proc = run_statusline(payload)
    assert proc.returncode == 0
    lines = proc.stdout.strip().split("\n")
    # Visible width of line 2 must not exceed 35
    import re
    clean_line2 = re.sub(r"\x1b\[[0-9;]*m", "", lines[1])
    assert len(clean_line2) <= 35


def test_model_effort_quota_filtering():
    payload = {
        "product": "antigravity",
        "model": {
            "id": "Gemini 3.8 Flash (High)",
            "display_name": "Gemini 3.8 Flash (High)",
            "effort": "high",
        },
        "context_window": {
            "used_percentage": 10.0,
            "total_input_tokens": 1000,
            "total_output_tokens": 500,
        },
        "quota": {
            "gemini-3.7-flash-medium": {"remaining_fraction": 1.0, "reset_in_seconds": 0},
            "gemini-3.8-flash-high": {"remaining_fraction": 0.8, "reset_in_seconds": 120},
            "gemini-3.8-flash-low": {"remaining_fraction": 1.0, "reset_in_seconds": 0},
            "gemini-3.8-flash-medium": {"remaining_fraction": 1.0, "reset_in_seconds": 0},
        },
        "terminal_width": 80,
    }
    proc = run_statusline(payload)
    assert proc.returncode == 0
    lines = proc.stdout.strip().split("\n")
    assert len(lines) == 2
    assert "3.8 Flash High:" in lines[1]
    assert "3.7 Flash Medium" not in lines[1]
    assert "3.8 Flash Low" not in lines[1]
    assert "3.8 Flash Medium" not in lines[1]
    assert "90%" in lines[1]


def test_all_quotas_flag():
    payload = {
        "product": "antigravity",
        "model": {"display_name": "Gemini 3.8 Flash (High)"},
        "context_window": {"used_percentage": 5.0},
        "quota": {
            "gemini-3.8-flash-high": {"remaining_fraction": 1.0},
            "gemini-3.8-flash-low": {"remaining_fraction": 1.0},
        },
        "terminal_width": 200,
    }
    proc = run_statusline(payload, env_vars={"AGY_ALL_QUOTAS": "1"})
    assert proc.returncode == 0
    assert "3.8 Flash High" in proc.stdout
    assert "3.8 Flash Low" in proc.stdout

