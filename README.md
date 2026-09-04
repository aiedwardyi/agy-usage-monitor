# agy-usage-monitor

Statusline for Google Antigravity CLI (`agy`), mirroring the design of `claude-usage-monitor`.

## Preview

```text
◆ Gemini 3.8 Flash │ agy-usage-monitor/main
▰▰▰▰▰ 95% │ ↑45k ↓12k │ Weekly: ▰▰▰▰▱ 85% (3d3h)
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
