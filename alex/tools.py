"""The tool set the benched model can call: Claude tool definitions plus
two interchangeable backends:

  * frozen (default) — deterministic fixtures, identical for every model/run
  * live             — real yfinance / FRED / SEC EDGAR / Finnhub data
"""
from __future__ import annotations

from typing import Any, Callable

Dispatch = dict[str, Callable[..., Any]]


def _kg_tools(g: Any) -> Dispatch:
    from . import kg
    return {
        "kg_neighbors": lambda entity, relation=None, direction="both", limit=25:
            g.neighbors(entity, relation, direction, limit),
        "kg_path": lambda entities, max_hops=4, relations=None: g.path(entities, max_hops, relations),
        "kg_add_entity": lambda entity, label=None, name=None, properties=None:
            kg.upsert_entity(g, entity, label, name, properties),
        "kg_add_relation": lambda source, relation, target, properties=None:
            kg.upsert_relation(g, source, relation, target, properties),
        "kg_delete_relation": lambda source, relation, target: kg.delete_relation(g, source, relation, target),
        "kg_delete_entity": lambda entity: kg.delete_entity(g, entity),
    }


def live_dispatch(persist: bool = True) -> Dispatch:
    """Live data. persist=True: graph changes are saved (chat, alex-kg); persist=False: graph
    changes stay in a private sandbox copy (live benchmark runs)."""
    from . import analysis, kg, sources  # lazy: frozen mode needs no network libs
    return {
        **_kg_tools(kg.graph(live=True, persist=persist)),
        "quote": lambda tickers: sources.quote(tickers),
        "fundamentals": lambda ticker: sources.fundamentals(ticker),
        "risk_metrics": lambda tickers, period="1y": analysis.risk_metrics(tickers, period=period),
        "correlation": lambda tickers, period="1y": analysis.correlation(tickers, period=period),
        "fred_series": lambda series_id, limit=24: sources.fred_series(series_id, limit),
        "sec_filings": lambda ticker, form="10-K", count=5: sources.sec_filings(ticker, form, count),
        "company_news": lambda ticker, days=7: sources.company_news(ticker, days),
    }


def frozen_dispatch() -> Dispatch:
    """Fixed data and a FRESH seed graph: call once per run, so knowledge-graph writes made in
    one run can never reach another run or another model."""
    from . import fixtures, kg
    return {**fixtures.DISPATCH, **_kg_tools(kg.graph(live=False))}


_STR = {"type": "string"}
_TICKERS = {"type": "array", "items": {"type": "string"},
            "description": "Ticker symbols, e.g. ['AAPL','MSFT']"}


def _tool(name: str, desc: str, props: dict, required: list[str]) -> dict:
    """Claude Messages API tool definition (name / description / input_schema)."""
    return {
        "name": name, "description": desc,
        "input_schema": {"type": "object", "properties": props, "required": required},
    }


def openai_format(schemas: list[dict]) -> list[dict]:
    """Same tools in OpenAI function-calling format (for OpenRouter)."""
    return [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                              "parameters": t["input_schema"]}} for t in schemas]


SCHEMAS = [
    _tool("quote", "Latest price, day range, market cap for tickers.",
          {"tickers": _TICKERS}, ["tickers"]),
    _tool("fundamentals", "Key ratios & profile (sector, PE, beta, margins, ROE) for one ticker.",
          {"ticker": _STR}, ["ticker"]),
    _tool("risk_metrics",
          "Volatility, annual return, Sharpe, max drawdown, 1-day VaR/CVaR(95%), beta vs SPY from price history.",
          {"tickers": _TICKERS, "period": {**_STR, "description": "yfinance period e.g. 6mo,1y,2y,5y"}},
          ["tickers"]),
    _tool("correlation",
          "Return-correlation matrix across tickers + most/least correlated pairs. Needs >=2 tickers.",
          {"tickers": _TICKERS, "period": _STR}, ["tickers"]),
    _tool("fred_series",
          "Latest observations of a FRED macro series id (CPIAUCSL, GDP, INDPRO, DGS10, UNRATE, ...).",
          {"series_id": _STR, "limit": {"type": "integer"}}, ["series_id"]),
    _tool("sec_filings",
          "Recent SEC EDGAR filings (10-K/10-Q/8-K) links for a US ticker.",
          {"ticker": _STR, "form": _STR, "count": {"type": "integer"}}, ["ticker"]),
    _tool("company_news", "Recent company news headlines.",
          {"ticker": _STR, "days": {"type": "integer"}}, ["ticker"]),
    _tool("kg_neighbors",
          "Financial knowledge graph: entities directly related to one entity (a ticker, sector, "
          "industry, country or FRED series id). Relations: IN_INDUSTRY, PART_OF, DOMICILED_IN, "
          "SUPPLIES (supplier -> customer, with product), COMPETES_WITH, CORRELATED (1y return "
          "correlation), SENSITIVE_TO (company -> macro series, with direction and channel).",
          {"entity": {**_STR, "description": "e.g. NVDA, DGS10, Semiconductors"},
           "relation": {**_STR, "description": "optional relation filter, e.g. SUPPLIES"},
           "direction": {**_STR, "enum": ["in", "out", "both"],
                         "description": "out = entity is the source (e.g. what it supplies)"},
           "limit": {"type": "integer"}}, ["entity"]),
    _tool("kg_path",
          "Financial knowledge graph: shortest chain of relations connecting entities (multi-hop), "
          "e.g. how two companies are linked through suppliers, competitors or industries.",
          {"entities": {"type": "array", "items": {"type": "string"},
                        "description": "two or more entities; paths go from the first to each other one"},
           "max_hops": {"type": "integer", "description": "1-6, default 4"},
           "relations": {"type": "array", "items": {"type": "string"},
                         "description": "optional: only traverse these relation types, e.g. ['SUPPLIES']"}},
          ["entities"]),
    # --- knowledge-graph writes (create / update / delete) ---
    _tool("kg_add_entity",
          "Knowledge graph: create an entity, or update the name / properties of an existing one. "
          "A new entity needs a label (Company, Industry, Sector, Country, MacroSeries, ...).",
          {"entity": {**_STR, "description": "id, e.g. a ticker such as SMCI"},
           "label": {**_STR, "description": "type of a NEW entity, e.g. Company"},
           "name": {**_STR, "description": "display name, e.g. Super Micro Computer"},
           "properties": {"type": "object", "description": "optional extra facts: name -> text/number"}},
          ["entity"]),
    _tool("kg_add_relation",
          "Knowledge graph: create a relation between two existing entities, or update its properties "
          "(e.g. ASML SUPPLIES INTC with product). Relation names are one upper-case word.",
          {"source": _STR, "relation": {**_STR, "description": "e.g. SUPPLIES, COMPETES_WITH, PARTNERS_WITH"},
           "target": _STR, "properties": {"type": "object", "description": "optional, e.g. {product: ...}"}},
          ["source", "relation", "target"]),
    _tool("kg_delete_relation",
          "Knowledge graph: delete one relation between two entities.",
          {"source": _STR, "relation": _STR, "target": _STR}, ["source", "relation", "target"]),
    _tool("kg_delete_entity",
          "Knowledge graph: delete an entity and every relation that touches it.",
          {"entity": _STR}, ["entity"]),
]
WRITE_TOOLS = {"kg_add_entity", "kg_add_relation", "kg_delete_relation", "kg_delete_entity"}

OPENAI_SCHEMAS = openai_format(SCHEMAS)
