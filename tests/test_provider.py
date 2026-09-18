import io
import json

import pytest

from bundesliga_betting.provider import OddsApiProvider, ProviderError


class Response(io.StringIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_provider_aggregates_complete_bookmakers() -> None:
    payload = [{
        "id": "game-1", "commence_time": "2026-09-20T13:30:00Z",
        "home_team": "Home FC", "away_team": "Away FC",
        "bookmakers": [
            {"markets": [{"key": "h2h", "outcomes": [
                {"name": "Home FC", "price": 2.0}, {"name": "Draw", "price": 4.0},
                {"name": "Away FC", "price": 4.0},
            ]}]},
            {"markets": [{"key": "h2h", "outcomes": [
                {"name": "Home FC", "price": 3.0}, {"name": "Draw", "price": 3.0},
            ]}]},
        ],
    }]
    requested = []

    def opener(url, timeout):
        requested.append((url, timeout))
        return Response(json.dumps(payload))

    fixtures = OddsApiProvider("secret key", opener=opener).upcoming()

    assert len(fixtures) == 1
    assert fixtures[0].bookmaker_count == 1
    assert fixtures[0].bookmaker_markets[0].odds.home == 2.0
    assert fixtures[0].probabilities.home == pytest.approx(0.5)
    assert "apiKey=secret+key" in requested[0][0]
    assert "regions=eu" in requested[0][0]


def test_provider_wraps_network_errors() -> None:
    def opener(url, timeout):
        raise OSError("offline")

    with pytest.raises(ProviderError, match="could not retrieve odds"):
        OddsApiProvider("secret", opener=opener).upcoming()
