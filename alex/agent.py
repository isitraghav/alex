"""Agentic loop: NVIDIA NIM model + tool calling.

The model decides which data/analysis tools to call, we execute them locally,
feed results back, and repeat until it answers (or hits the turn cap).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from .config import settings
from .llm import client
from .routing import prefilter
from .tools import DISPATCH, SCHEMAS

# emit(event) surfaces the agent's internal steps (thinking, tool calls, results)
# so the CLI can print them live and the API can return them. No-op if None.
Emit = Callable[[dict[str, Any]], None]

log = logging.getLogger("alex.agent")

SYSTEM = """You are alex, an autonomous financial analyst terminal.
Use the provided tools to fetch real data — never invent prices, ratios, macro \
values, or filing dates. Always cite which tool/source produced a number.
For risk or correlation questions call risk_metrics / correlation on the \
relevant tickers. For macro use fred_series. Note that risk metrics are \
historical estimates, not guarantees. Be concise and quantitative."""


def run(question: str, history: list[dict] | None = None,
        emit: Emit | None = None) -> tuple[str, list[dict]]:
    """Answer one question. Returns (answer_text, full_message_history).

    If `emit` is given, it is called with an event dict at each step:
      {"type": "prefilter", ...}          intent classification result
      {"type": "thinking", "text": ...}   model reasoning / narration
      {"type": "tool_call", "name","args"}
      {"type": "tool_result", "name","result"}
      {"type": "answer", "text": ...}     final answer
    """
    def _emit(**e: Any) -> None:
        if emit:
            emit(e)

    msgs: list[dict] = history or [{"role": "system", "content": SYSTEM}]
    msgs.append({"role": "user", "content": question})

    # Laya prefilter: cheap intent check before the LLM. Short-circuit off-topic,
    # otherwise hint the category so the model reaches for the right tools.
    pf = prefilter(question)
    _emit(type="prefilter", **pf)
    if pf.get("enabled") and not pf["on_topic"] and pf["confidence"] >= settings.prefilter_threshold:
        answer = (f"That looks off-topic for a financial terminal "
                  f"(Laya: off_topic {pf['confidence']:.0%}). Ask about prices, risk, "
                  f"correlation, macro, filings, or company news.")
        _emit(type="answer", text=answer)
        return answer, msgs
    if pf.get("category") and pf["on_topic"]:
        msgs.append({"role": "system",
                     "content": f"[prefilter] likely intent: {pf['category']} "
                                f"({pf['confidence']:.0%}). Prefer the matching tools."})

    cli = client()

    for _ in range(settings.llm_max_tool_turns):
        resp = cli.chat.completions.create(
            model=settings.nvidia_model,
            messages=msgs,
            tools=SCHEMAS,
            temperature=settings.llm_temperature,
        )
        m = resp.choices[0].message
        msgs.append(m.model_dump(exclude_none=True))

        # Surface model reasoning: reasoning_content (nemotron/reasoning models) or
        # narration text emitted alongside tool calls.
        reasoning = getattr(m, "reasoning_content", None)
        if reasoning:
            _emit(type="thinking", text=reasoning.strip())
        if m.tool_calls and m.content:
            _emit(type="thinking", text=m.content.strip())

        if not m.tool_calls:
            answer = m.content or ""
            _emit(type="answer", text=answer)
            return answer, msgs

        for tc in m.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
                _emit(type="tool_call", name=name, args=args)
                result = DISPATCH[name](**args)
            except Exception as e:  # noqa: BLE001 - report tool failure to model
                result = {"error": f"{type(e).__name__}: {e}"}
                log.warning("tool %s failed: %s", name, e)
            _emit(type="tool_result", name=name, result=result)
            msgs.append({
                "role": "tool", "tool_call_id": tc.id, "name": name,
                "content": json.dumps(result, default=str),
            })

    answer = "Stopped: hit max tool turns without a final answer."
    _emit(type="answer", text=answer)
    return answer, msgs
