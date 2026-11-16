"""alex-chat: Markdown rendering and the per-turn CLI handling (no model is called)."""
import io
import json

from rich.console import Console

from alex import chat

ANSWER = """**MSFT (quote tool):** $517.99

- Annual volatility: 34.03%
- Max drawdown: -28.09%

| Metric | Value |
|---|---|
| Beta | 1.00 |

Use `kg_path` for links."""


def _render(fn, *args, terminal=True):
    buf = io.StringIO()
    c = Console(file=buf, width=80, force_terminal=terminal, color_system="truecolor" if terminal else None)
    fn(*args, console=c)
    return buf.getvalue()


def test_markdown_is_rendered_not_printed_raw():
    out = _render(chat.show_answer, ANSWER)
    assert "**" not in out and "| Metric |" not in out and "`kg_path`" not in out
    assert "\x1b[" in out                                   # styled in a terminal
    for text in ("517.99", "34.03%", "Beta", "1.00", "kg_path"):
        assert text in out


def test_plain_output_when_not_a_terminal():
    out = _render(chat.show_answer, ANSWER, terminal=False)
    assert "\x1b[" not in out and "517.99" in out and "**" not in out


def test_tool_lines_and_errors_are_not_markup():
    assert "[x]" in _render(chat.show_tool, "kg_path", "entities=['A'], relations=[x]", terminal=False)
    assert "[error] usage limit" in _render(chat.show_answer, "[error] usage limit", terminal=False)


class FakePopen:
    last_cmd = None

    def __init__(self, cmd, **kw):
        FakePopen.last_cmd = cmd
        self.stdin = io.StringIO()
        events = [{"type": "system", "subtype": "init", "session_id": "s-123"},
                  {"type": "assistant", "message": {"content": [
                      {"type": "tool_use", "name": "mcp__alex__quote", "input": {"tickers": ["MSFT"]}}]}},
                  {"type": "result", "subtype": "success", "result": "**$517.99**", "session_id": "s-123"}]
        self.stdout = io.StringIO("\n".join(json.dumps(e) for e in events) + "\n")
        self.stderr = io.StringIO("")
        self.returncode = 0

    def wait(self):
        return 0


def test_turn_keeps_session_and_uses_saving_tool_server(monkeypatch):
    shown = []
    monkeypatch.setattr(chat.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(chat, "show_tool", lambda name, args, console=None: shown.append((name, args)))
    answer, sid = chat.ask("price of MSFT?", "claude-haiku-5-5", True, None, "medium")
    assert answer == "**$517.99**" and sid == "s-123" and shown == [("quote", "tickers=['MSFT']")]
    assert "--resume" not in FakePopen.last_cmd
    chat.ask("and NVDA?", "claude-haiku-5-5", True, sid, "medium")
    assert FakePopen.last_cmd[FakePopen.last_cmd.index("--resume") + 1] == "s-123"
    cfg = json.loads(open(FakePopen.last_cmd[FakePopen.last_cmd.index("--mcp-config") + 1]).read())
    assert "--sandbox" not in cfg["mcpServers"]["alex"]["args"]          # chat saves graph changes
