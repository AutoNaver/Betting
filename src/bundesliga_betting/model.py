"""A small, transparent score-selection model."""

from dataclasses import dataclass
from math import exp, factorial

from .odds import MarketOdds, OutcomeProbabilities, remove_margin


@dataclass(frozen=True)
class Prediction:
    home_goals: int
    away_goals: int
    expected_points: float
    probabilities: OutcomeProbabilities
    expected_home_goals: float
    expected_away_goals: float


def _poisson(k: int, rate: float) -> float:
    return exp(-rate) * rate**k / factorial(k)


def _score_grid(home_rate: float, away_rate: float, max_goals: int) -> list[list[float]]:
    home = [_poisson(goals, home_rate) for goals in range(max_goals + 1)]
    away = [_poisson(goals, away_rate) for goals in range(max_goals + 1)]
    grid = [[home[h] * away[a] for a in range(max_goals + 1)] for h in range(max_goals + 1)]
    mass = sum(map(sum, grid))
    return [[probability / mass for probability in row] for row in grid]


def _outcomes(grid: list[list[float]]) -> OutcomeProbabilities:
    home = draw = away = 0.0
    for home_goals, row in enumerate(grid):
        for away_goals, probability in enumerate(row):
            if home_goals > away_goals:
                home += probability
            elif home_goals == away_goals:
                draw += probability
            else:
                away += probability
    return OutcomeProbabilities(home, draw, away)


def _fit_rates(target: OutcomeProbabilities, total_goals_prior: float) -> tuple[float, float]:
    """Fit Poisson rates to 1X2 prices, regularized by a league scoring prior."""

    best_loss = float("inf")
    best_rates = (1.5, 1.3)
    # A deterministic grid search keeps this initial model dependency-free and auditable.
    for home_step in range(2, 81):
        home_rate = home_step * 0.05
        for away_step in range(2, 81):
            away_rate = away_step * 0.05
            outcomes = _outcomes(_score_grid(home_rate, away_rate, 10))
            market_error = sum(
                (actual - expected) ** 2
                for actual, expected in zip(
                    (outcomes.home, outcomes.draw, outcomes.away),
                    (target.home, target.draw, target.away),
                    strict=True,
                )
            )
            prior_error = 0.015 * (home_rate + away_rate - total_goals_prior) ** 2
            loss = market_error + prior_error
            if loss < best_loss:
                best_loss = loss
                best_rates = (home_rate, away_rate)
    return best_rates


def _points(guess: tuple[int, int], result: tuple[int, int]) -> int:
    if guess == result:
        return 5
    guess_difference = guess[0] - guess[1]
    result_difference = result[0] - result[1]
    if guess_difference == result_difference:
        return 3
    if (guess_difference > 0) == (result_difference > 0) and (
        guess_difference == 0
    ) == (result_difference == 0):
        return 2
    return 0


def predict_score(
    odds: MarketOdds, *, total_goals_prior: float = 3.1, max_goals: int = 10
) -> Prediction:
    """Return the score guess that maximizes expected prediction-game points.

    The independent-Poisson rates are inferred from margin-free 1X2 probabilities.
    Since 1X2 odds cannot identify the expected goal total on their own, the fit uses
    ``total_goals_prior`` as a weak regularizer.
    """

    return predict_probabilities(
        remove_margin(odds), total_goals_prior=total_goals_prior, max_goals=max_goals
    )


def predict_probabilities(
    probabilities: OutcomeProbabilities, *, total_goals_prior: float = 3.1, max_goals: int = 10
) -> Prediction:
    """Return the score guess maximizing points for margin-free probabilities."""

    if total_goals_prior <= 0:
        raise ValueError("total_goals_prior must be positive")
    if max_goals < 1:
        raise ValueError("max_goals must be at least 1")
    values = (probabilities.home, probabilities.draw, probabilities.away)
    if any(value <= 0 for value in values):
        raise ValueError("outcome probabilities must be positive")
    if abs(sum(values) - 1.0) > 1e-9:
        raise ValueError("outcome probabilities must sum to 1")

    home_rate, away_rate = _fit_rates(probabilities, total_goals_prior)
    grid = _score_grid(home_rate, away_rate, max_goals)

    best_guess = (0, 0)
    best_expected_points = -1.0
    for guessed_home in range(max_goals + 1):
        for guessed_away in range(max_goals + 1):
            expected_points = sum(
                probability * _points((guessed_home, guessed_away), (actual_home, actual_away))
                for actual_home, row in enumerate(grid)
                for actual_away, probability in enumerate(row)
            )
            if expected_points > best_expected_points:
                best_guess = (guessed_home, guessed_away)
                best_expected_points = expected_points

    return Prediction(
        *best_guess,
        expected_points=best_expected_points,
        probabilities=probabilities,
        expected_home_goals=home_rate,
        expected_away_goals=away_rate,
    )
