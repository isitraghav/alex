"""`claude-code` provider: run a case through the Claude Code CLI in headless mode.

Uses the machine's Claude Code login (e.g. a Pro/Max subscription) instead of an API key.
Each case is one `claude -p` process:

  * our tools come from alex's own MCP server (alex/mcp_server.py) - same schemas, same
    frozen fixtures as the API providers;
  * every built-in Claude Code tool is removed (`--tools ""`), only `mcp__alex__*` is allowed,
    and no other MCP server, setting source, hook or project file is loaded;
  * `--system-prompt` replaces Claude Code's default prompt with the variant under test;
  * no `--fallback-model`, so each score still belongs to exactly one model.

The stream-json transcript gives the served model, every tool call + arguments, tool
errors, the final answer, token usage and an API-equivalent cost estimate.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import settings

PREFIX = "mcp__alex__"
ROOT = Path(__file__).resolve().parent.parent


def available() -> bool:
    return shutil.which("claude") is not None


@lru_cache(maxsize=2)
def mcp_config(live: bool) -> str:
    """Write the MCP config once per process; returns its path."""
    args = ["-m", "alex.mcp_server"] + (["--live"] if live else [])
    cfg = {"mcpServers": {"alex": {"type": "stdio", "command": sys.executable, "args": args,
                                   "cwd": str(ROOT)}}}
    f = Path(tempfile.gettempdir()) / f"alex-mcp-{'live' if live else 'frozen'}.json"
    f.write_text(json.dumps(cfg), encoding="utf-8")
    return str(f)


@lru_cache(maxsize=1)
def workdir() -> str:
    """Empty working directory, so no CLAUDE.md / project settings leak into the run."""
    return tempfile.mkdtemp(prefix="alex-cc-")


def command(model: str, system: str, effort: str, live: bool) -> list[str]:
    return [shutil.which("claude") or "claude", "-p",
            "--model", model,
            "--system-prompt", system,
            "--tools", "",
            "--strict-mcp-config", "--mcp-config", mcp_config(live),
            "--allowedTools", f"{PREFIX}*",
            "--setting-sources", "",
            "--effort", effort,
            "--output-format", "stream-json", "--verbose",
            "--no-session-persistence"]


def parse(lines: list[str], model: str, tr: Any) -> dict[str, Any]:
    """Fill the _Trace from a stream-json transcript; returns extra metadata."""
    meta: dict[str, Any] = {"served_model": None, "tools_exposed": None, "mcp_status": None,
                            "duration_ms": None, "rate_limit": None}
    result = None
    for line in lines:
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = e.get("type")
        if t == "system" and e.get("subtype") == "init":
            meta["served_model"] = e.get("model")
            meta["tools_exposed"] = e.get("tools")
            meta["mcp_status"] = {s.get("name"): s.get("status") for s in e.get("mcp_servers") or []}
        elif t == "rate_limit_event":
            meta["rate_limit"] = e.get("rate_limit_info")
        elif t in ("assistant", "user"):
            content = (e.get("message") or {}).get("content")
            for b in content if isinstance(content, list) else []:
                if b.get("type") == "tool_use":
                    name = b.get("name", "")
                    tr.calls.append({"name": name[len(PREFIX):] if name.startswith(PREFIX) else name,
                                     "args": b.get("input") if isinstance(b.get("input"), dict) else {}})
                elif b.get("type") == "tool_result" and b.get("is_error"):
                    tr.tool_errors += 1
        elif t == "result":
            result = e

    if result is None:
        tr.error = "claude -p produced no result event"
        return meta
    meta["duration_ms"] = result.get("duration_ms")
    tr.turns = result.get("num_turns") or 0
    mu = (result.get("modelUsage") or {}).get(model)
    if mu:  # the benched model only (Claude Code may bill a helper model separately)
        tr.tok_in = (mu.get("inputTokens", 0) + mu.get("cacheReadInputTokens", 0)
                     + mu.get("cacheCreationInputTokens", 0))
        tr.tok_out = mu.get("outputTokens", 0)
        tr.billed = mu.get("costUSD")
    else:
        u = result.get("usage") or {}
        tr.tok_in = (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                     + u.get("cache_creation_input_tokens", 0))
        tr.tok_out = u.get("output_tokens", 0)
        tr.billed = result.get("total_cost_usd")
    if result.get("is_error") or result.get("subtype") != "success":
        tr.error = f"{result.get('subtype')}: {str(result.get('result') or '')[:200]}"
    elif result.get("stop_reason") == "refusal":
        tr.error = "refusal"
    elif result.get("stop_reason") == "max_tokens":
        tr.error = "max_tokens reached"
    else:
        tr.answer = (result.get("result") or "").strip()
    served = meta["served_model"]
    if served and served != model and not tr.error:
        tr.error = f"served model {served} != requested {model}"
    return meta


def run(model: str, prompt: str, system: str, effort: str, tr: Any, live: bool = False) -> dict[str, Any]:
    if not available():
        raise RuntimeError("`claude` CLI not found on PATH - install Claude Code and log in")
    p = subprocess.run(command(model, system, effort, live), input=prompt, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", cwd=workdir(),
                       timeout=settings.llm_timeout_s * settings.llm_max_tool_turns)
    meta = parse(p.stdout.splitlines(), model, tr)
    if p.returncode and not tr.error:
        tr.error = f"claude exited {p.returncode}: {p.stderr.strip()[:200]}"
    elif tr.error and "no result event" in tr.error and p.stderr.strip():
        tr.error += f" ({p.stderr.strip()[:200]})"
    if len(tr.calls) > settings.llm_max_tool_turns * 4 and not tr.error:
        tr.error = "runaway tool calls"
    return meta
