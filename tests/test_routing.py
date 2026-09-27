"""Offline check: prefilter must read the CHOSEN label's probability, not Laya's
top-level `confidence` (which is a calibration margin ~0.03, easily below the
reject threshold and would wrongly let off-topic through)."""
from alex.routing import _confidence


def test_uses_answer_confidence_not_calibration_margin():
    ans = {  # real Laya choice-answer shape
        "choice": "off_topic",
        "probabilities": {"risk": 0.4, "off_topic": 0.6},
        "confidence": 0.03,          # calibration margin — must be ignored
        "answer_confidence": 0.6,
    }
    assert _confidence(ans) == 0.6


def test_falls_back_to_probabilities_of_choice():
    ans = {"choice": "risk", "probabilities": {"risk": 0.72, "off_topic": 0.28}}
    assert _confidence(ans) == 0.72


def test_missing_probs_defaults_open():
    assert _confidence({"choice": "prices"}) == 1.0


if __name__ == "__main__":
    import sys, pytest
    sys.exit(pytest.main([__file__, "-q"]))
