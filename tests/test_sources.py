"""Live-source safety checks that need no network."""
from alex import sources


def test_errors_never_contain_api_keys(monkeypatch):
    monkeypatch.setattr(sources.settings, "fred_api_key", "FREDSECRET123")
    monkeypatch.setattr(sources.settings, "finnhub_api_key", "FINNSECRET456")
    e = RuntimeError("400 Bad Request for url: https://api.stlouisfed.org/fred/series/observations"
                     "?series_id=X&api_key=FREDSECRET123&file_type=json "
                     "and https://finnhub.io/api/v1/company-news?symbol=X&token=FINNSECRET456")
    msg = sources._err(e)["error"]
    assert "FREDSECRET123" not in msg and "FINNSECRET456" not in msg
    assert "api_key=<redacted>" in msg and "token=<redacted>" in msg
    # a secret that shows up outside a query string is removed too
    assert "FREDSECRET123" not in sources._redact("key was FREDSECRET123")


def test_unknown_ticker_quote_is_an_error(monkeypatch):
    class FastInfo(dict):
        pass

    class Ticker:
        def __init__(self, t):
            self.fast_info = FastInfo(last_price=None, previous_close=None)

    monkeypatch.setattr(sources.yf, "Ticker", Ticker)
    assert sources.quote(["ZZZZQ"]) == {"ZZZZQ": {"error": "no data for ZZZZQ"}}
