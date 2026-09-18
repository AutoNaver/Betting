import pytest

from bundesliga_betting.model import _points, predict_probabilities, predict_score
from bundesliga_betting.odds import MarketOdds, OutcomeProbabilities


@pytest.mark.parametrize(
    ("guess", "result", "points"),
    [((2, 1), (2, 1), 5), ((2, 1), (3, 2), 3), ((1, 0), (3, 1), 2), ((1, 1), (0, 0), 3), ((1, 0), (0, 1), 0)],
)
def test_points(guess: tuple[int, int], result: tuple[int, int], points: int) -> None:
    assert _points(guess, result) == points


def test_strong_home_favourite_produces_home_win_suggestion() -> None:
    prediction = predict_score(MarketOdds(home=1.35, draw=5.5, away=9.0))

    assert prediction.home_goals > prediction.away_goals
    assert prediction.probabilities.home > 0.7


def test_even_market_produces_symmetric_fit() -> None:
    prediction = predict_score(MarketOdds(home=3.0, draw=3.0, away=3.0))

    assert prediction.expected_home_goals == prediction.expected_away_goals


def test_consensus_probabilities_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="sum to 1"):
        predict_probabilities(OutcomeProbabilities(home=0.5, draw=0.3, away=0.3))
