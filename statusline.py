#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# ── Configuration (env vars) ─────────────────────────────────────
SHOW_CONTEXT_SIZE = os.environ.get("AGY_CONTEXT_SIZE", "0") == "1"
SHOW_TOKENS = os.environ.get("AGY_TOKENS", "1") == "1"
SHOW_RESET = os.environ.get("AGY_RESET", "1") == "1"
SHOW_BRANCH = os.environ.get("AGY_BRANCH", "1") == "1"
SHOW_REMAINING = os.environ.get("AGY_REMAINING", "1") == "1"
SHOW_BAR = os.environ.get("AGY_BAR", "1") == "1"
SHOW_TASKS = os.environ.get("AGY_TASKS", "1") == "1"
SHOW_ALL_QUOTAS = os.environ.get("AGY_ALL_QUOTAS", "0") == "1"

# ── Read stdin ──────────────────────────────────────────────────
raw = sys.stdin.read().strip()
if not raw:
    print("Antigravity")
    sys.exit(0)

try:
    d = json.loads(raw)
except json.JSONDecodeError:
    print("Antigravity")
    sys.exit(0)

# Terminal width budget
MAX_WIDTH = 80
for candidate in (d.get("terminal_width"), os.environ.get("AGY_MAX_WIDTH"), os.environ.get("COLUMNS")):
    try:
        width = int(candidate)
        if width > 0:
            MAX_WIDTH = width
            break
    except (TypeError, ValueError):
        continue

# ── ANSI colors ─────────────────────────────────────────────────
C = "\033[36m"   # cyan
G = "\033[32m"   # green
Y = "\033[33m"   # yellow
R = "\033[31m"   # red
D = "\033[2m"    # dim
N = "\033[0m"    # reset

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def strip_ansi(text):
    return _ANSI_RE.sub("", text)


def color_pct(used_pct):
    if used_pct >= 90:
        return R
    if used_pct >= 70:
        return Y
    return G


# ── Helpers ─────────────────────────────────────────────────────
def compact(n):
    n = float(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}m".replace(".0m", "m")
    if n >= 1_000:
        return f"{n / 1_000:.1f}k".replace(".0k", "k")
    return str(int(n))


def format_reset(minutes, compact=False):
    if minutes is None or minutes <= 0:
        return ""
    m = int(minutes)
    if m >= 1440:
        d_cnt, h_cnt = m // 1440, (m % 1440) // 60
        return f" {D}({d_cnt}d{h_cnt}h){N}" if h_cnt and not compact else f" {D}({d_cnt}d){N}"
    if m >= 60:
        h_cnt, mm = m // 60, m % 60
        return f" {D}({h_cnt}h{mm}m){N}" if mm and not compact else f" {D}({h_cnt}h){N}"
    return f" {D}({m}m){N}"


def gauge_blocks(val):
    v = min(100, max(0, val))
    return max(1, round(v / 20.0)) if v >= 10 else 0


def used_pct_str(used_pct):
    if used_pct is None or used_pct == "--":
        return "--"
    used = int(used_pct)
    c = color_pct(used)
    val = 100 - used if SHOW_REMAINING else used
    val = max(0, min(100, val))
    if SHOW_BAR:
        filled = gauge_blocks(val)
        bar = f"{c}{'\u25b0' * filled}{'\u25b1' * (5 - filled)}{N} "
    else:
        bar = ""
    return f"{bar}{c}{val}%{N}"


def select_quotas(quota_dict, model_data, show_all=False):
    if show_all or not quota_dict or len(quota_dict) <= 1:
        return quota_dict

    general = {}
    model_quotas = {}
    for k, v in quota_dict.items():
        k_low = k.lower()
        if any(w in k_low for w in ("weekly", "7d", "daily", "24h", "5h")):
            general[k] = v
        else:
            model_quotas[k] = v

    if not model_quotas:
        return general

    disp = str(model_data.get("display_name") or "") if isinstance(model_data, dict) else str(model_data)
    m_id = str(model_data.get("id") or "") if isinstance(model_data, dict) else ""
    effort = str(model_data.get("effort") or "").lower() if isinstance(model_data, dict) else ""

    candidates = []
    for raw in (disp, m_id):
        if raw:
            n = re.sub(r"[^a-z0-9.]+", "-", raw.lower()).strip("-")
            candidates.append(n)
            if not n.startswith("gemini-"):
                candidates.append(f"gemini-{n}")
            if effort and not n.endswith(effort):
                candidates.append(f"{n}-{effort}")
                candidates.append(f"gemini-{n}-{effort}")

    matched = {}
    for cand in candidates:
        if cand in model_quotas:
            matched[cand] = model_quotas[cand]
            break

    if not matched:
        for cand in candidates:
            for k, v in model_quotas.items():
                if k.startswith(cand) or cand.startswith(k):
                    matched[k] = v
                    break
            if matched:
                break

    res = dict(general)
    res.update(matched)
    return res if res else quota_dict


# ── Parse session data ──────────────────────────────────────────
model = "Gemini"
try:
    model = d.get("model", {}).get("display_name") or model
    model = re.sub(r"\s*\((?:High|Medium|Low)\)$", "", model)
except (KeyError, TypeError):
    pass

ctx_pct_used = 0
ctx_size = 0
try:
    cw = d.get("context_window", {})
    ctx_pct_used = int(round(float(cw.get("used_percentage") or 0)))
    ctx_size = int(cw.get("context_window_size") or 0)
except (KeyError, TypeError, ValueError):
    pass

in_tok = 0
out_tok = 0
try:
    cw = d.get("context_window", {})
    in_tok = int(cw.get("total_input_tokens") or 0)
    out_tok = int(cw.get("total_output_tokens") or 0)
except (KeyError, TypeError, ValueError):
    pass

proj_dir = ""
proj_name = ""
try:
    proj_dir = (
        d.get("workspace", {}).get("project_dir")
        or d.get("workspace", {}).get("current_dir")
        or d.get("cwd")
        or ""
    )
    proj_name = os.path.basename(proj_dir) if proj_dir else ""
except (KeyError, TypeError):
    pass

branch = ""
try:
    branch = d.get("vcs", {}).get("branch") or ""
except (KeyError, TypeError):
    pass

if not branch:
    candidate_dirs = [p for p in (proj_dir, os.getcwd()) if p]
    for try_dir in candidate_dirs:
        try:
            r = subprocess.run(
                ["git", "-C", try_dir, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=2,
            )
            if r.returncode == 0:
                branch = r.stdout.strip()
                if not proj_name:
                    proj_name = os.path.basename(try_dir)
                break
        except Exception:
            pass

# ── Build output ────────────────────────────────────────────────
SEP = " \u2502 "  # │
DIAMOND = "\u25c6"  # ◆

# Line 1: model, project/branch
line1_parts = [f"{C}{DIAMOND} {model}{N}"]
if proj_name:
    loc = f"{proj_name}/{branch}" if (branch and SHOW_BRANCH) else proj_name
    if len(loc) > 40:
        loc = loc[:39] + "\u2026"
    line1_parts.append(loc)

line1 = SEP.join(line1_parts)

# Line 2: context gauge, tokens, quota, tasks
ctx_remaining = max(0, min(100, 100 - ctx_pct_used))
ctx_val = ctx_remaining if SHOW_REMAINING else ctx_pct_used
ctx_color = color_pct(ctx_pct_used)
if SHOW_BAR:
    filled = gauge_blocks(ctx_val)
    gauge = "\u25b0" * filled + "\u25b1" * (5 - filled)
    ctx_str = f"{ctx_color}{gauge}{N} {ctx_val}%"
else:
    ctx_str = f"{ctx_val}%"

if SHOW_CONTEXT_SIZE and ctx_size:
    ctx_label = f"{ctx_size // 1_000_000}M" if ctx_size >= 1_000_000 else f"{ctx_size // 1000}K"
    ctx_str += f" of {ctx_label}"

line2_segments = [(ctx_str, 2)]

# Tokens
if SHOW_TOKENS and (in_tok or out_tok):
    line2_segments.append((f"\u2191{compact(in_tok)} \u2193{compact(out_tok)}", 4))

# Quotas
quota_at = []
quota_fallbacks = []
quota_dict = select_quotas(d.get("quota") or {}, d.get("model", {}), SHOW_ALL_QUOTAS)
for bucket_name, qdata in quota_dict.items():
    b_lower = bucket_name.lower()
    if "weekly" in b_lower or "7d" in b_lower:
        label = "Weekly"
    elif "daily" in b_lower or "24h" in b_lower:
        label = "Daily"
    elif "5h" in b_lower:
        label = "5h"
    else:
        label = bucket_name.replace("gemini-", "").replace("-", " ").title()

    rem_frac = qdata.get("remaining_fraction")
    if rem_frac is not None:
        rem_pct = int(round(float(rem_frac) * 100))
        used_pct = max(0, min(100, 100 - rem_pct))
        q_str = f"{label}: {used_pct_str(used_pct)}"
    else:
        q_str = f"{label}: --"

    rem_sec = qdata.get("reset_in_seconds")
    reset_min = int(rem_sec) // 60 if rem_sec is not None else None
    reset_full = format_reset(reset_min) if SHOW_RESET else ""
    reset_compact = format_reset(reset_min, compact=True) if SHOW_RESET else ""

    quota_at.append(len(line2_segments))
    line2_segments.append((q_str + reset_full, 1))
    quota_fallbacks.append((q_str + reset_compact, q_str))

# Tasks
if SHOW_TASKS:
    task_count = int(d.get("task_count") or 0)
    if task_count > 0:
        line2_segments.append((f"{D}{task_count} task{'s' if task_count > 1 else ''}{N}", 3))


def build_line(segments):
    return SEP.join(text for text, _ in segments)


line2 = build_line(line2_segments)

# Shed countdown units if line overflows
for idx, (compact_q, plain_q) in enumerate(quota_fallbacks):
    if len(strip_ansi(line2)) <= MAX_WIDTH:
        break
    pos = quota_at[idx]
    line2_segments[pos] = (compact_q, line2_segments[pos][1])
    line2 = build_line(line2_segments)

for idx, (compact_q, plain_q) in enumerate(quota_fallbacks):
    if len(strip_ansi(line2)) <= MAX_WIDTH:
        break
    pos = quota_at[idx]
    line2_segments[pos] = (plain_q, line2_segments[pos][1])
    line2 = build_line(line2_segments)

# Drop lowest-priority segments until it fits
while len(strip_ansi(line2)) > MAX_WIDTH and line2_segments:
    worst = max(range(len(line2_segments)), key=lambda i: line2_segments[i][1])
    line2_segments.pop(worst)
    line2 = build_line(line2_segments)

print(line1)
print(line2)
