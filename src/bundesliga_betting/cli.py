"""Command-line interface for manual and current provider odds."""

import argparse
import json
import os
from typing import Any

from .model import Prediction, predict_probabilities, predict_score
from .odds import MarketOdds
from .provider import OddsApiProvider, ProviderError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create Bundesliga score suggestions")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--upcoming", action="store_true", help="fetch upcoming Bundesliga games")
    source.add_argument("--home", type=float, help="home-win decimal odds for manual mode")
    parser.add_argument("--draw", type=float, help="draw decimal odds for manual mode")
    parser.add_argument("--away", type=float, help="away-win decimal odds for manual mode")
    parser.add_argument("--total-goals", type=float, default=3.1, help="expected-goals prior")
    parser.add_argument("--region", default="eu", help="The Odds API bookmaker region")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    return parser


def _prediction_output(prediction: Prediction) -> dict[str, Any]:
    return {
        "suggested_score": f"{prediction.home_goals}:{prediction.away_goals}",
        "expected_points": round(prediction.expected_points, 3),
        "fair_probabilities": {
            "home": round(prediction.probabilities.home, 4),
            "draw": round(prediction.probabilities.draw, 4),
            "away": round(prediction.probabilities.away, 4),
        },
        "fitted_expected_goals": {
            "home": round(prediction.expected_home_goals, 2),
            "away": round(prediction.expected_away_goals, 2),
        },
    }


def _print_human(output: dict[str, Any]) -> None:
    fixture = output.get("fixture")
    if fixture:
        print(f"{fixture['home_team']} - {fixture['away_team']} ({fixture['kickoff']})")
        print(f"Bookmakers in consensus: {fixture['bookmakers']}")
    probabilities = output["fair_probabilities"]
    print(f"Suggestion: {output['suggested_score']}")
    print(
        "Fair 1X2 probabilities: "
        f"home {probabilities['home']:.1%}, draw {probabilities['draw']:.1%}, "
        f"away {probabilities['away']:.1%}"
    )
    print(f"Expected game points: {output['expected_points']:.3f}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.upcoming:
        api_key = os.environ.get("ODDS_API_KEY", "")
        if not api_key:
            parser.error("--upcoming requires the ODDS_API_KEY environment variable")
        try:
            fixtures = OddsApiProvider(api_key, region=args.region).upcoming()
        except ProviderError as error:
            parser.error(str(error))
        outputs = []
        for fixture in fixtures:
            output = _prediction_output(
                predict_probabilities(fixture.probabilities, total_goals_prior=args.total_goals)
            )
            output["fixture"] = {
                "id": fixture.event_id,
                "home_team": fixture.home_team,
                "away_team": fixture.away_team,
                "kickoff": fixture.kickoff.isoformat(),
                "bookmakers": fixture.bookmaker_count,
            }
            outputs.append(output)
    else:
        if args.draw is None or args.away is None:
            parser.error("manual mode requires --home, --draw, and --away")
        outputs = [
            _prediction_output(
                predict_score(
                    MarketOdds(home=args.home, draw=args.draw, away=args.away),
                    total_goals_prior=args.total_goals,
                )
            )
        ]

    if args.json:
        print(json.dumps(outputs if args.upcoming else outputs[0], indent=2))
    else:
        for index, output in enumerate(outputs):
            if index:
                print()
            _print_human(output)


if __name__ == "__main__":
    main()
