"""OpenRouter provider path (offline, scripted OpenAI-style client)."""
import json
from types import SimpleNamespace as NS

from alex import fixtures, llm
from alex.bench import key, run_case
from alex.prompts import CASES
from alex.tools import OPENAI_SCHEMAS, SCHEMAS

BY_ID = {c.id: c for c in CASES}


class FakeOpenRouter:
    """chat.completions: a tool call first, then a text answer; reports a billed cost."""
    def __init__(self, answer="MSFT trades at $512.40", finish="stop"):
        self.n, self.answer, self.finish, self.seen = 0, answer, finish, []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kw):
        self.n += 1
        self.seen.append(kw)
        usage = NS(prompt_tokens=900, completion_tokens=100, cost=0.0021)
        if self.n == 1:
            tc = NS(id="c1", function=NS(name="quote", arguments=json.dumps({"tickers": ["MSFT"]})))
            msg = NS(content=None, tool_calls=[tc], model_dump=lambda exclude_none=True: {
                "role": "assistant",
                "tool_calls": [{"id": "c1", "type": "function",
                                "function": {"name": "quote", "arguments": tc.function.arguments}}]})
            return NS(choices=[NS(message=msg, finish_reason="tool_calls")], usage=usage)
        msg = NS(content=self.answer, tool_calls=None,
                 model_dump=lambda exclude_none=True: {"role": "assistant", "content": self.answer})
        return NS(choices=[NS(message=msg, finish_reason=self.finish)], usage=usage)


def test_openrouter_loop_scores_and_costs():
    cli = FakeOpenRouter()
    r = run_case(cli, "anthropic/claude-sonnet-5.5", BY_ID["quote_single"], fixtures.DISPATCH, prov="openrouter")
    assert r["passed"] and r["provider"] == "openrouter" and r["tool_calls"] == 1
    assert r["model"] == "claude-sonnet-5-5" and r["model_slug"] == "anthropic/claude-sonnet-5.5"
    assert abs(r["billed_usd"] - 0.0042) < 1e-9                      # what OpenRouter reported
    assert abs(r["cost_usd"] - (1800 * 2 + 200 * 10) / 1e6) < 1e-12  # list price, comparable across providers
    first = cli.seen[0]
    assert first["messages"][0]["role"] == "system" and "temperature" not in first
    assert first["extra_body"] == {"reasoning": {"effort": "medium"}}
    # (the list is shared and later grows by the final answer, so the tool result is second-to-last)
    tool_msg = cli.seen[1]["messages"][-2]
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "c1"
    assert json.loads(tool_msg["content"])["MSFT"]["last"] == 512.40


def test_openrouter_truncation_is_an_error():
    r = run_case(FakeOpenRouter(finish="length"), "anthropic/claude-haiku-5.5", BY_ID["quote_single"],
                 fixtures.DISPATCH, prov="openrouter")
    assert r["error"] == "max_tokens reached" and not r["passed"]


def test_canonical_ids_make_providers_comparable():
    assert llm.canonical("anthropic/claude-opus-5.5") == "claude-opus-5-5" == llm.canonical("claude-opus-5-5")
    assert key("anthropic/claude-haiku-5.5", "default") == key("claude-haiku-5-5", "default")
    assert llm.cost_usd("anthropic/claude-haiku-5.5", 1_000_000, 0) == 0.10


def test_openai_schema_mirrors_claude_schema():
    assert [t["function"]["name"] for t in OPENAI_SCHEMAS] == [t["name"] for t in SCHEMAS]
    assert all(t["function"]["parameters"] == s["input_schema"] for t, s in zip(OPENAI_SCHEMAS, SCHEMAS))


def test_provider_auto_selection(monkeypatch):
    s = llm.settings
    monkeypatch.setattr(s, "llm_provider", "auto")
    monkeypatch.setattr(s, "anthropic_api_key", "")
    monkeypatch.setattr(s, "openrouter_api_key", "or-key")
    assert llm.provider() == "openrouter" and llm.default_models("openrouter") == s.openrouter_models
    monkeypatch.setattr(s, "anthropic_api_key", "sk-ant")
    assert llm.provider() == "anthropic"                       # Claude API key wins under auto
    monkeypatch.setattr(s, "llm_provider", "openrouter")
    assert llm.provider() == "openrouter"                      # explicit setting wins
