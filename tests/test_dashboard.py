import io

import pytest
from streamlit.testing.v1 import AppTest

from bundesliga_betting.dashboard import _bookmaker_rows, _probability_rows
from bundesliga_betting.model import predict_score
from bundesliga_betting.odds import MarketOdds
from bundesliga_betting.provider import OddsApiProvider


class Response(io.StringIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_probability_rows_expose_all_outcomes() -> None:
    prediction = predict_score(MarketOdds(1.8, 3.8, 4.5))

    rows = _probability_rows(prediction)

    assert [row["Outcome"] for row in rows] == ["Home win", "Draw", "Away win"]
    assert sum(row["Probability"] for row in rows) == pytest.approx(1.0)


def test_bookmaker_rows_show_source_odds() -> None:
    payload = """[{"id":"1","commence_time":"2026-09-20T13:30:00Z",
        "home_team":"Home","away_team":"Away","bookmakers":[{"key":"book-a",
        "title":"Book A","last_update":"2026-09-18T10:00:00Z","markets":[{"key":"h2h",
        "outcomes":[{"name":"Home","price":2.0},{"name":"Draw","price":3.5},
        {"name":"Away","price":4.0}]}]}]}]"""
    market = OddsApiProvider("key", opener=lambda *args, **kwargs: Response(payload)).upcoming()[0]

    rows = _bookmaker_rows(market)

    assert rows[0]["Bookmaker"] == "Book A"
    assert rows[0]["Home odds"] == 2.0


def test_streamlit_manual_mode_renders_prediction() -> None:
    app = AppTest.from_file("../streamlit_app.py").run(timeout=15)
    app.radio[0].set_value("Manual odds").run(timeout=15)

    assert not app.exception
    assert app.metric[0].label == "Suggested score"
    assert app.metric[0].value == "2 : 1"
    assert app.metric[1].value == "1.50 / 5"
