"""Terminal REPL for the alex agent."""
from __future__ import annotations

import logging
import sys

import json

from .agent import run
from .config import settings
from .storage import init_postgres


def _print_event(e: dict) -> None:
    """Render one agent trace event to the terminal."""
    t = e.get("type")
    if t == "prefilter" and e.get("enabled"):
        print(f"  · intent: {e.get('category')} ({e.get('confidence', 0):.0%})")
    elif t == "thinking":
        print(f"  · thinking: {e['text']}")
    elif t == "tool_call":
        print(f"  → {e['name']}({json.dumps(e['args'])})")
    elif t == "tool_result":
        s = json.dumps(e["result"], default=str)
        print(f"  ← {e['name']}: {s[:300]}{'…' if len(s) > 300 else ''}")


def main() -> None:
    # Windows consoles default to cp1252; LLM output has unicode (–, ‑, €) -> force UTF-8.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    if not settings.nvidia_api_key:
        print("NVIDIA_API_KEY not set. Copy .env.example -> .env and fill it.", file=sys.stderr)
        sys.exit(1)
    init_postgres()

    print("alex — Financial Terminal Initialized. Ask about a ticker or macro indicator. Ctrl-C to quit.")
    history: list[dict] | None = None
    while True:
        try:
            q = input("\nalex> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q:
            continue
        emit = _print_event if settings.show_trace else None
        try:
            answer, history = run(q, history, emit=emit)
        except Exception as e:  # noqa: BLE001 - keep REPL alive on API/network errors
            print(f"\n[error] {type(e).__name__}: {e}")
            continue
        print("\n" + answer)


if __name__ == "__main__":
    main()
