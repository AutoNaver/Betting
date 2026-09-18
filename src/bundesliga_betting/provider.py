"""The Odds API adapter and multi-bookmaker market aggregation."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from .odds import MarketOdds, OutcomeProbabilities, remove_margin

SPORT_KEY = "soccer_germany_bundesliga"
API_BASE_URL = "https://api.the-odds-api.com/v4"


class ProviderError(RuntimeError):
    """Raised when the provider response cannot be retrieved or interpreted."""


@dataclass(frozen=True)
class FixtureMarket:
    event_id: str
    home_team: str
    away_team: str
    kickoff: datetime
    probabilities: OutcomeProbabilities
    bookmaker_count: int
    bookmaker_markets: tuple[BookmakerMarket, ...]


@dataclass(frozen=True)
class BookmakerMarket:
    """The source prices and derived fair probabilities used in a consensus."""

    key: str
    title: str
    last_update: str
    odds: MarketOdds
    probabilities: OutcomeProbabilities


def _consensus(event: dict[str, Any]) -> tuple[OutcomeProbabilities, tuple[BookmakerMarket, ...]]:
    """Average each bookmaker's margin-free probabilities with equal weight."""

    markets: list[BookmakerMarket] = []
    home_team = event.get("home_team")
    away_team = event.get("away_team")
    for bookmaker in event.get("bookmakers", []):
        h2h = next(
            (market for market in bookmaker.get("markets", []) if market.get("key") == "h2h"),
            None,
        )
        if not h2h:
            continue
        prices = {
            outcome.get("name"): outcome.get("price") for outcome in h2h.get("outcomes", [])
        }
        try:
            odds = MarketOdds(
                home=float(prices[home_team]),
                draw=float(prices["Draw"]),
                away=float(prices[away_team]),
            )
        except (KeyError, TypeError, ValueError):
            continue
        probabilities = remove_margin(odds)
        markets.append(
            BookmakerMarket(
                key=str(bookmaker.get("key", "unknown")),
                title=str(bookmaker.get("title", bookmaker.get("key", "Unknown"))),
                last_update=str(h2h.get("last_update", bookmaker.get("last_update", ""))),
                odds=odds,
                probabilities=probabilities,
            )
        )

    if not markets:
        raise ProviderError("fixture has no complete, valid head-to-head bookmaker markets")
    count = len(markets)
    return (
        OutcomeProbabilities(
            home=sum(market.probabilities.home for market in markets) / count,
            draw=sum(market.probabilities.draw for market in markets) / count,
            away=sum(market.probabilities.away for market in markets) / count,
        ),
        tuple(markets),
    )


class OddsApiProvider:
    """Retrieve current Bundesliga head-to-head markets from The Odds API v4."""

    def __init__(
        self, api_key: str, *, region: str = "eu", opener: Callable[..., Any] = urlopen
    ) -> None:
        if not api_key.strip():
            raise ValueError("an API key is required")
        self.api_key = api_key
        self.region = region
        self.opener = opener

    def upcoming(self) -> list[FixtureMarket]:
        query = urlencode(
            {
                "apiKey": self.api_key,
                "regions": self.region,
                "markets": "h2h",
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            }
        )
        url = f"{API_BASE_URL}/sports/{SPORT_KEY}/odds/?{query}"
        try:
            with self.opener(url, timeout=20) as response:
                payload = json.load(response)
        except Exception as error:
            # Provider exceptions can contain the requested URL, including its API key.
            raise ProviderError(f"could not retrieve odds ({type(error).__name__})") from error
        if not isinstance(payload, list):
            raise ProviderError("provider returned an unexpected response")

        fixtures: list[FixtureMarket] = []
        for event in payload:
            try:
                probabilities, bookmaker_markets = _consensus(event)
                kickoff = datetime.fromisoformat(event["commence_time"])
                fixtures.append(
                    FixtureMarket(
                        event_id=event["id"],
                        home_team=event["home_team"],
                        away_team=event["away_team"],
                        kickoff=kickoff,
                        probabilities=probabilities,
                        bookmaker_count=len(bookmaker_markets),
                        bookmaker_markets=bookmaker_markets,
                    )
                )
            except (KeyError, TypeError, ValueError, ProviderError):
                continue
        return sorted(fixtures, key=lambda fixture: fixture.kickoff)
