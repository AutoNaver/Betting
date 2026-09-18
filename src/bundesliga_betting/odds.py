"""Decimal odds validation and conversion."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketOdds:
    """Best available decimal odds for the three match outcomes."""

    home: float
    draw: float
    away: float

    def __post_init__(self) -> None:
        if any(value <= 1.0 for value in (self.home, self.draw, self.away)):
            raise ValueError("decimal odds must all be greater than 1.0")


@dataclass(frozen=True)
class OutcomeProbabilities:
    home: float
    draw: float
    away: float


def remove_margin(odds: MarketOdds) -> OutcomeProbabilities:
    """Convert 1X2 decimal odds to probabilities using proportional normalization."""

    raw = (1.0 / odds.home, 1.0 / odds.draw, 1.0 / odds.away)
    overround = sum(raw)
    return OutcomeProbabilities(*(value / overround for value in raw))

