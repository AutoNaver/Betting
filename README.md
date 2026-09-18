# Bundesliga score suggestions

This project turns publicly available Bundesliga **1X2 decimal odds** into score guesses for
a friendly prediction game. It is not intended to provide financial advice or guarantee a
betting profit.

The game awards:

- **5 points** for the exact result;
- **3 points** for the correct goal difference; and
- **2 points** for only the correct outcome (home win, draw, or away win).

Rather than simply choosing the likeliest exact score, the model evaluates every score guess
and chooses the one with the highest expected number of game points.

## Current baseline

1. Convert decimal odds to raw implied probabilities (`1 / odds`).
2. Remove the bookmaker margin by proportionally normalizing the three probabilities.
3. For provider data, average each bookmaker's margin-free probabilities with equal weight.
4. Fit independent home/away Poisson goal rates to those probabilities, with a weak expected
   total-goals prior (3.1 by default).
5. Calculate each possible guess's expected points under the fitted score distribution.

The total-goals prior is necessary because a three-way outcome market alone does not uniquely
determine the score distribution. Adding over/under or correct-score prices is an intended
next step.

## Setup

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
```

Try the baseline with manually entered odds:

```bash
bundesliga-predict --home 1.80 --draw 3.80 --away 4.50
bundesliga-predict --home 1.80 --draw 3.80 --away 4.50 --json
```

## Web dashboard

Launch the Streamlit interface locally:

```bash
streamlit run streamlit_app.py
```

The dashboard provides:

- live upcoming fixtures or a no-key manual-odds mode;
- configurable bookmaker region and total-goals prior;
- the expected-points-optimal score, market probabilities, and fitted goal rates;
- a probability chart and transparent bookmaker-by-bookmaker source table; and
- a short explanation of the model and the exclusive 5/3/2 scoring objective.

For local use, set `ODDS_API_KEY` as described below. On Streamlit Community Cloud, add a
top-level `ODDS_API_KEY = "..."` entry to the app's secrets rather than committing it here.

## Fetch upcoming games

The initial provider is [The Odds API](https://the-odds-api.com/), using its Bundesliga sport
key, European bookmaker region, decimal prices, and head-to-head (1X2) market. Create a free
account, copy its API key, and keep it outside the repository:

```bash
export ODDS_API_KEY="your-key"
bundesliga-predict --upcoming
bundesliga-predict --upcoming --json
```

The command fetches all currently available upcoming Bundesliga fixtures. For each fixture it
removes every bookmaker's margin separately, discards incomplete markets, and equally averages
the resulting probabilities. This produces a consensus rather than allowing a high-margin
bookmaker to dominate. Run it shortly before the prediction game's submission deadline so the
prices contain the latest public information; scheduling can be added once that deadline is
known. Each fetch consumes provider quota, so avoid unnecessary polling.

## Planned data flow

The odds-fetching layer will be kept separate from the prediction model:

```text
public odds provider -> normalized fixture/market records -> probability model -> suggestions
```

The provider is isolated from the prediction model, making a later API change straightforward.
Provider terms and rate limits must be respected. API keys are read from `ODDS_API_KEY` and must
never be committed or passed on the command line, where they could appear in shell history.

## Decisions made

- The Odds API is the first provider; it offers one documented integration instead of scraping.
- The model uses a European multi-bookmaker consensus rather than one bookmaker or best prices.
- The scoring categories are exclusive: an exact result earns 5 points total.
- The CLI is the first delivery format and operates on current prices when invoked.

## Roadmap

- Support totals markets to estimate expected goals more accurately.
- Persist timestamped odds and results for walk-forward backtesting.
- Compare proportional margin removal with more sophisticated methods.
- Measure average prediction-game points, not betting return, as the primary objective.
- Add the chosen delivery format and scheduling only after the questions above are resolved.
