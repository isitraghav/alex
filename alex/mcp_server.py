"""Minimal stdio MCP server exposing alex's tools (no extra dependencies).

Used by the `claude-code` provider: `claude -p` connects to it via --mcp-config, so a
model running under the Claude Code CLI (subscription login) calls exactly the same
tools, with the same schemas and the same frozen fixtures, as the API providers.

  python -m alex.mcp_server            frozen fixtures (default)
  python -m alex.mcp_server --live     real data sources

Protocol: newline-delimited JSON-RPC 2.0 on stdin/stdout (MCP stdio transport).
Only what a tool-only server needs: initialize, ping, tools/list, tools/call.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from .tools import SCHEMAS, frozen_dispatch, live_dispatch

PROTOCOL = "2025-06-18"
SERVER_NAME = "alex"


def mcp_tools() -> list[dict]:
    return [{"name": t["name"], "description": t["description"], "inputSchema": t["input_schema"]}
            for t in SCHEMAS]


def call(dispatch: dict, name: str, args: Any) -> dict:
    if name not in dispatch:
        return {"content": [{"type": "text", "text": json.dumps({"error": f"unknown tool {name}"})}],
                "isError": True}
    try:
        result = dispatch[name](**(args if isinstance(args, dict) else {}))
    except Exception as e:  # noqa: BLE001 - bad args are the model's error; report, don't crash
        result = {"error": f"{type(e).__name__}: {e}"}
    bad = isinstance(result, dict) and "error" in result
    return {"content": [{"type": "text", "text": json.dumps(result, default=str)}], "isError": bad}


def handle(dispatch: dict, msg: dict) -> dict | None:
    """One JSON-RPC message in, one response out (None for notifications)."""
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:  # notification (e.g. notifications/initialized)
        return None
    if method == "initialize":
        ver = (msg.get("params") or {}).get("protocolVersion") or PROTOCOL
        res: Any = {"protocolVersion": ver, "capabilities": {"tools": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": "0.3"}}
    elif method == "ping":
        res = {}
    elif method == "tools/list":
        res = {"tools": mcp_tools()}
    elif method == "tools/call":
        p = msg.get("params") or {}
        res = call(dispatch, p.get("name", ""), p.get("arguments") or {})
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": res}


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    dispatch = live_dispatch() if "--live" in argv else frozen_dispatch()
    inp = sys.stdin.buffer
    out = sys.stdout.buffer
    for raw in inp:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            resp: dict | None = {"jsonrpc": "2.0", "id": None,
                                 "error": {"code": -32700, "message": "parse error"}}
        else:
            resp = handle(dispatch, msg)
        if resp is not None:
            out.write(json.dumps(resp).encode("utf-8") + b"\n")
            out.flush()


if __name__ == "__main__":
    main()
