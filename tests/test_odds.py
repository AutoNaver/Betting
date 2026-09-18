import pytest

from bundesliga_betting.odds import MarketOdds, remove_margin


def test_remove_margin_returns_probabilities_summing_to_one() -> None:
    probabilities = remove_margin(MarketOdds(home=2.0, draw=3.5, away=4.0))

    assert probabilities.home + probabilities.draw + probabilities.away == pytest.approx(1.0)
    assert probabilities.home > probabilities.draw > probabilities.away


@pytest.mark.parametrize("odds", [(1.0, 3.0, 4.0), (2.0, 0.0, 4.0), (2.0, 3.0, -1.0)])
def test_rejects_invalid_decimal_odds(odds: tuple[float, float, float]) -> None:
    with pytest.raises(ValueError, match="greater than 1.0"):
        MarketOdds(*odds)

