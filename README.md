# agy-usage-monitor

Standalone statusline for Google Antigravity CLI (`agy`).

## Preview

```text
◆ Gemini 3.8 Flash │ agy-usage-monitor/main
▰▰▰▰▰ 95% │ ↑45.2k ↓12.3k │ Weekly: ▰▰▰▰▱ 85% (3d3h)
```

## Setup

Add the following to `~/.gemini/antigravity-cli/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python -X utf8 C:/Users/mredw/Desktop/agy-usage-monitor/statusline.py",
    "enabled": true
  }
}
```

Or run directly in an active session:

```text
/statusline python -X utf8 C:/Users/mredw/Desktop/agy-usage-monitor/statusline.py
```

## Configuration

Customise behaviour via environment variables (all prefixed with `AGY_`):

| Variable | Default | Description |
|---|---|---|
| `AGY_REMAINING` | `1` | `1` shows remaining % / gauge fill; `0` shows used % |
| `AGY_BAR` | `1` | `1` shows 5-block gauge bars; `0` hides bars |
| `AGY_TOKENS` | `1` | `1` shows `↑in ↓out` tokens; `0` hides |
| `AGY_RESET` | `1` | `1` shows quota reset countdown; `0` hides |
| `AGY_BRANCH` | `1` | `1` shows git branch; `0` hides |
| `AGY_TASKS` | `1` | `1` shows background task count; `0` hides |
| `AGY_CONTEXT_SIZE` | `0` | `1` adds total context size label (e.g. `of 1M`) |
| `AGY_MAX_WIDTH` | auto | Override terminal column width budget |
