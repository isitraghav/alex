"""Offline checks for the risk/correlation math (no network): monkeypatch the
price source with a synthetic panel and assert the numbers are sane."""
import numpy as np
import pandas as pd

from alex import analysis


def _fake_prices(monkeypatch):
    idx = pd.bdate_range("2023-01-01", periods=252)
    rng = np.random.default_rng(0)
    base = rng.normal(0.0005, 0.01, 252).cumsum()
    df = pd.DataFrame({
        "AAA": 100 * np.exp(base),
        "BBB": 100 * np.exp(base + rng.normal(0, 0.003, 252)),  # ~ tracks AAA
        "CCC": 100 * np.exp(rng.normal(0.0005, 0.01, 252).cumsum()),  # independent
        "SPY": 100 * np.exp(base * 0.9),
    }, index=idx)
    monkeypatch.setattr(analysis, "price_history", lambda t, period="1y", **k: df[t])


def test_risk_metrics(monkeypatch):
    _fake_prices(monkeypatch)
    r = analysis.risk_metrics(["AAA", "BBB"], period="1y")["metrics"]
    m = r["AAA"]
    assert 0 < m["annual_volatility"] < 1
    assert -1 < m["max_drawdown"] <= 0
    assert m["var_95_1d"] < 0                     # a loss quantile is negative
    assert m["beta_vs_SPY"] is not None
    assert m["observations"] == 251


def test_correlation_ranking(monkeypatch):
    _fake_prices(monkeypatch)
    c = analysis.correlation(["AAA", "BBB", "CCC"], period="1y")
    # AAA/BBB are constructed to co-move more than either vs CCC
    top = c["most_correlated"][0]
    assert {top[0], top[1]} == {"AAA", "BBB"}
    assert top[2] > 0.5


if __name__ == "__main__":
    import sys, pytest
    sys.exit(pytest.main([__file__, "-q"]))
