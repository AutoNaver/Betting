"""Streamlit dashboard for interactive Bundesliga score suggestions."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

import streamlit as st

from .model import Prediction, predict_probabilities, predict_score
from .odds import MarketOdds
from .provider import FixtureMarket, OddsApiProvider, ProviderError


@dataclass(frozen=True)
class PresentedFixture:
    home_team: str
    away_team: str
    kickoff: datetime | None
    prediction: Prediction
    market: FixtureMarket | None = None


@st.cache_data(ttl=900, show_spinner=False)
def _load_upcoming(api_key: str, region: str) -> list[FixtureMarket]:
    """Cache live odds briefly to protect the free provider quota."""

    return OddsApiProvider(api_key, region=region).upcoming()


def _probability_rows(prediction: Prediction) -> list[dict[str, object]]:
    return [
        {"Outcome": "Home win", "Probability": prediction.probabilities.home},
        {"Outcome": "Draw", "Probability": prediction.probabilities.draw},
        {"Outcome": "Away win", "Probability": prediction.probabilities.away},
    ]


def _bookmaker_rows(market: FixtureMarket) -> list[dict[str, object]]:
    return [
        {
            "Bookmaker": source.title,
            "Home odds": source.odds.home,
            "Draw odds": source.odds.draw,
            "Away odds": source.odds.away,
            "Fair home": source.probabilities.home,
            "Fair draw": source.probabilities.draw,
            "Fair away": source.probabilities.away,
            "Updated": source.last_update,
        }
        for source in market.bookmaker_markets
    ]


def _render_fixture(fixture: PresentedFixture) -> None:
    prediction = fixture.prediction
    title = f"{fixture.home_team} · {fixture.away_team}"
    if fixture.kickoff:
        title += f" — {fixture.kickoff.astimezone(UTC):%d %b, %H:%M} UTC"
    st.subheader(title)

    score, expected_points, market_size = st.columns(3)
    score.metric("Suggested score", f"{prediction.home_goals} : {prediction.away_goals}")
    expected_points.metric("Expected game points", f"{prediction.expected_points:.2f} / 5")
    market_size.metric(
        "Bookmakers used", str(fixture.market.bookmaker_count if fixture.market else 1)
    )

    chart, details = st.columns([3, 2])
    with chart:
        st.caption("Margin-free market consensus")
        st.bar_chart(_probability_rows(prediction), x="Outcome", y="Probability", horizontal=True)
    with details:
        st.caption("Model inputs and fit")
        st.metric("Home win", f"{prediction.probabilities.home:.1%}")
        st.metric("Draw", f"{prediction.probabilities.draw:.1%}")
        st.metric("Away win", f"{prediction.probabilities.away:.1%}")
        st.write(
            f"Fitted goals: **{prediction.expected_home_goals:.2f} – "
            f"{prediction.expected_away_goals:.2f}**"
        )

    if fixture.market:
        with st.expander("Bookmaker odds used", expanded=False):
            st.dataframe(
                _bookmaker_rows(fixture.market),
                column_config={
                    "Fair home": st.column_config.NumberColumn(format="%.1%%"),
                    "Fair draw": st.column_config.NumberColumn(format="%.1%%"),
                    "Fair away": st.column_config.NumberColumn(format="%.1%%"),
                },
                hide_index=True,
                use_container_width=True,
            )
            st.caption(
                "Each bookmaker is de-margined first. The displayed consensus gives every "
                "complete bookmaker market equal weight."
            )


def _sidebar() -> tuple[str, float, str, str]:
    st.sidebar.header("Prediction settings")
    source = st.sidebar.radio("Data source", ["Live market", "Manual odds"])
    total_goals = st.sidebar.slider(
        "Expected total-goals prior", 1.5, 5.0, 3.1, 0.1,
        help="A weak assumption needed because 1X2 prices do not identify total goals.",
    )
    region = st.sidebar.selectbox("Bookmaker region", ["eu", "uk", "us", "au"], index=0)
    env_key = os.environ.get("ODDS_API_KEY", "")
    try:
        configured_key = env_key or str(st.secrets.get("ODDS_API_KEY", ""))
    except FileNotFoundError:
        configured_key = env_key
    api_key = ""
    if source == "Live market":
        if configured_key:
            st.sidebar.success("Using the configured ODDS_API_KEY")
            api_key = configured_key
        else:
            api_key = st.sidebar.text_input("The Odds API key", type="password")
            st.sidebar.caption("Used for this session only; it is not stored by the app.")
    return source, total_goals, region, api_key


def main() -> None:
    st.set_page_config(page_title="Bundesliga Predictor", page_icon="⚽", layout="wide")
    st.title("⚽ Bundesliga Predictor")
    st.write(
        "Market-informed score suggestions optimized for your **5 / 3 / 2 point** prediction "
        "game. An exact result earns five points total."
    )
    source, total_goals, region, api_key = _sidebar()

    fixtures: list[PresentedFixture] = []
    if source == "Live market":
        if not api_key:
            st.info("Add a free The Odds API key in the sidebar to load upcoming fixtures.")
        elif st.button("Load upcoming fixtures", type="primary", use_container_width=True):
            try:
                with st.spinner("Collecting bookmaker markets…"):
                    markets = _load_upcoming(api_key, region)
                fixtures = [
                    PresentedFixture(
                        market.home_team,
                        market.away_team,
                        market.kickoff,
                        predict_probabilities(
                            market.probabilities, total_goals_prior=total_goals
                        ),
                        market,
                    )
                    for market in markets
                ]
                st.session_state["fixtures"] = fixtures
            except ProviderError as error:
                st.error(str(error))
        else:
            fixtures = st.session_state.get("fixtures", [])
    else:
        st.subheader("Enter a single market")
        names = st.columns(2)
        home_team = names[0].text_input("Home team", "Home")
        away_team = names[1].text_input("Away team", "Away")
        columns = st.columns(3)
        home = columns[0].number_input("Home win odds", 1.01, 100.0, 1.80, 0.05)
        draw = columns[1].number_input("Draw odds", 1.01, 100.0, 3.80, 0.05)
        away = columns[2].number_input("Away win odds", 1.01, 100.0, 4.50, 0.05)
        fixtures = [
            PresentedFixture(
                home_team,
                away_team,
                None,
                predict_score(
                    MarketOdds(home=home, draw=draw, away=away),
                    total_goals_prior=total_goals,
                ),
            )
        ]

    if fixtures:
        st.divider()
        st.caption(f"Showing {len(fixtures)} fixture{'s' if len(fixtures) != 1 else ''}")
        for fixture in fixtures:
            with st.container(border=True):
                _render_fixture(fixture)

    with st.expander("How the suggestion is calculated"):
        st.markdown(
            "1. Convert each bookmaker's decimal odds to implied probabilities.\n"
            "2. Remove each bookmaker's margin, then average those fair probabilities.\n"
            "3. Fit independent home and away Poisson goal rates.\n"
            "4. Score every possible guess under the exclusive 5/3/2 rules and choose the "
            "highest expected-points result."
        )
        st.warning("For a friendly prediction game only—not financial or betting advice.")


if __name__ == "__main__":
    main()
