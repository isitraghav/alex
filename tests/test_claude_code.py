"""claude-code provider + MCP server, offline (no CLI process is started)."""
import json

from alex import claude_code, mcp_server
from alex.bench import _Trace
from alex.fixtures import DISPATCH
from alex.tools import SCHEMAS

M = "claude-haiku-5-5"


def _ev(**k):
    return json.dumps(k)


def _transcript(stop="end_turn", subtype="success", served=M, tool_error=False):
    return [
        _ev(type="system", subtype="hook_started"),
        _ev(type="system", subtype="init", model=served, tools=["mcp__alex__quote"],
            mcp_servers=[{"name": "alex", "status": "connected"}]),
        _ev(type="assistant", message={"content": [
            {"type": "thinking", "thinking": ""},
            {"type": "tool_use", "id": "t1", "name": "mcp__alex__quote", "input": {"tickers": ["MSFT"]}}]}),
        _ev(type="rate_limit_event", rate_limit_info={"utilization": 0.5}),
        _ev(type="user", message={"content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "{}", "is_error": tool_error}]}),
        "not json - ignored",
        _ev(type="result", subtype=subtype, is_error=subtype != "success", result="MSFT is $512.",
            num_turns=2, duration_ms=2100, stop_reason=stop, total_cost_usd=0.001,
            modelUsage={M: {"inputTokens": 4, "cacheReadInputTokens": 2000, "cacheCreationInputTokens": 100,
                            "outputTokens": 50, "costUSD": 0.0003}}),
    ]


def test_parse_success():
    tr = _Trace()
    meta = claude_code.parse(_transcript(), M, tr)
    assert tr.error is None and tr.answer == "MSFT is $512."
    assert tr.calls == [{"name": "quote", "args": {"tickers": ["MSFT"]}}]   # MCP prefix stripped
    assert (tr.tok_in, tr.tok_out, tr.turns, tr.billed) == (2104, 50, 2, 0.0003)
    assert meta["served_model"] == M and meta["mcp_status"] == {"alex": "connected"}
    assert meta["duration_ms"] == 2100 and meta["rate_limit"]["utilization"] == 0.5


def test_parse_failures():
    tr = _Trace()
    claude_code.parse(_transcript(stop="refusal"), M, tr)
    assert tr.error == "refusal" and tr.answer == ""
    tr = _Trace()
    claude_code.parse(_transcript(subtype="error_during_execution"), M, tr)
    assert tr.error.startswith("error_during_execution")
    tr = _Trace()
    claude_code.parse(_transcript(served="claude-sonnet-5-5"), M, tr)
    assert "served model" in tr.error                      # a silent model swap is not scored
    tr = _Trace()
    claude_code.parse(_transcript(tool_error=True), M, tr)
    assert tr.tool_errors == 1
    tr = _Trace()
    claude_code.parse([], M, tr)
    assert "no result event" in tr.error


def test_command_isolates_the_harness():
    cmd = claude_code.command(M, "SYS", "medium", live=False)
    i = cmd.index
    assert cmd[i("--tools") + 1] == ""                     # no built-in Claude Code tools
    assert cmd[i("--allowedTools") + 1] == "mcp__alex__*"
    assert cmd[i("--setting-sources") + 1] == ""           # no user hooks / plugins / settings
    assert cmd[i("--system-prompt") + 1] == "SYS" and cmd[i("--model") + 1] == M
    assert "--strict-mcp-config" in cmd and "--fallback-model" not in cmd


def test_mcp_server_protocol():
    d = dict(DISPATCH)
    init = mcp_server.handle(d, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                 "params": {"protocolVersion": "2025-06-18"}})
    assert init["result"]["capabilities"] == {"tools": {}}
    assert mcp_server.handle(d, {"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    tools = mcp_server.handle(d, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    assert [t["name"] for t in tools] == [t["name"] for t in SCHEMAS]
    assert tools[0]["inputSchema"] == SCHEMAS[0]["input_schema"]
    ok = mcp_server.handle(d, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                               "params": {"name": "quote", "arguments": {"tickers": ["MSFT"]}}})["result"]
    assert ok["isError"] is False and "MSFT" in ok["content"][0]["text"]
    bad = mcp_server.handle(d, {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                                "params": {"name": "quote", "arguments": {"wrong": 1}}})["result"]
    assert bad["isError"] is True                          # bad args -> tool error, server survives
    unk = mcp_server.handle(d, {"jsonrpc": "2.0", "id": 5, "method": "nope"})
    assert unk["error"]["code"] == -32601


def test_stalled_call_is_retried(monkeypatch):
    import subprocess
    from types import SimpleNamespace as NS
    calls = {"n": 0}

    def fake_run(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise subprocess.TimeoutExpired(cmd="claude", timeout=1)
        return NS(stdout="\n".join(_transcript()), stderr="", returncode=0)

    monkeypatch.setattr(claude_code, "available", lambda: True)
    monkeypatch.setattr(claude_code.subprocess, "run", fake_run)
    tr = _Trace()
    meta = claude_code.run(M, "q", "SYS", "medium", tr)
    assert meta["attempts"] == 2 and tr.error is None and len(tr.calls) == 1   # first try's state discarded


def test_model_errors_are_not_retried(monkeypatch):
    from types import SimpleNamespace as NS
    calls = {"n": 0}

    def fake_run(*a, **kw):
        calls["n"] += 1
        return NS(stdout="\n".join(_transcript(stop="refusal")), stderr="", returncode=0)

    monkeypatch.setattr(claude_code, "available", lambda: True)
    monkeypatch.setattr(claude_code.subprocess, "run", fake_run)
    tr = _Trace()
    assert claude_code.run(M, "q", "SYS", "medium", tr)["attempts"] == 1 and tr.error == "refusal"
