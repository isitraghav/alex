"""FastAPI wrapper — same agent, over HTTP. A web UI can call these later.

Stateless per request except an optional client-managed session id kept in
memory (fine for single-process dev; move to Redis/Postgres for multi-worker).
"""
from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from . import analysis
from .agent import run
from .config import settings
from .storage import init_postgres

app = FastAPI(title="alex", version="0.1.0")
_SESSIONS: dict[str, list[dict]] = {}  # ponytail: in-memory; swap for Redis if multi-worker


@app.on_event("startup")
def _startup() -> None:
    init_postgres()


class Ask(BaseModel):
    question: str
    session_id: str | None = None


@app.post("/ask")
def ask(body: Ask) -> dict:
    hist = _SESSIONS.get(body.session_id) if body.session_id else None
    trace: list[dict] = []
    emit = trace.append if settings.show_trace else None
    answer, hist = run(body.question, hist, emit=emit)
    if body.session_id:
        _SESSIONS[body.session_id] = hist
    return {"answer": answer, "trace": trace}


@app.get("/risk")
def risk(tickers: str, period: str = "1y") -> dict:
    return analysis.risk_metrics([t.strip().upper() for t in tickers.split(",")], period=period)


@app.get("/correlation")
def correlation(tickers: str, period: str = "1y") -> dict:
    return analysis.correlation([t.strip().upper() for t in tickers.split(",")], period=period)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def main() -> None:
    import uvicorn
    uvicorn.run("alex.api:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
