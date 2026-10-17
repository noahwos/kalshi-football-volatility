# Kalshi Football Volatility Analyzer

**Historical research toolkit** to rank football games by *prospective intragame win-probability movement*, rather than by which team is more likely to win. **NFL and college football (CFB) use separate data pipelines, training sets, and fitted models.**

> **Status:** 43 tests pass. An offline browser dashboard explores historical NFL/CFB holdout rankings and probability charts. Real ingestion, training, holdout evaluation and scoring work with public archives and no API key. Authenticated CFBD ingestion remains an optional, unvalidated alternative. See [validation results](docs/VALIDATION.md). This is research software, not a trading system or an assurance of profitable trades.

## What it does

1. Downloads NFL historical play-by-play from **nflverse** and college football historical play-by-play from the public **cfbfastR / SportsDataverse** archives. An optional **CollegeFootballData** connector requires `CFBD_API_KEY`. Raw sources share a normalized schema; keep separate models by league and probability source.
2. At **exactly 40 and 80 observed plays**, calculates features known at that instant. The targets measure the **next 40 plays** of home-team win-probability movement (future range and variation). Incomplete future windows are not labeled. No final score, final game length or future observation is allowed into features.
3. Trains **two separate** gradient-boosted regressors (one per league), with chronological season holdouts. Predicts the size of the potential range of probability movement over the next 40 plays.
4. Generates out-of-sample ranking metrics, baseline comparisons, and a *toy* contrarian trading rule, with cost/slippage modeled in percentage points. **These are model-probability proxy quotes, not historical Kalshi quotes**. Actual exchange trade P&L, fill probability, spreads and liquidity remain unvalidated.
5. Scores new normalized play sequences at either checkpoint and emits predicted movement ranges, not predicted winners.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
fva --help
pytest -q
```

## Browser dashboard

Once the real-data workflow below has prepared `data/` and `models/` (already
done in the cloud workspace), generate a self-contained dashboard:

```bash
fva dashboard --output reports/dashboard.html
```

Open `reports/dashboard.html` in your browser. You can copy that one HTML file
to another computer; Python, a server, internet and API keys are not needed to
view it. Filters, charts and exports all run inside the browser.

- Choose NFL or college football, and the 40- or 80-observation checkpoint.
- Search teams or game IDs, sort rankings, and select a game to inspect its path.
- Later observations are hidden initially. Reveal them to compare the forecast
  with the historical outcome; the later path is observed data, not a forecast.
- Export the current filtered rankings to CSV. Observed future ranges are only
  included when the reveal toggle is on.

The dashboard includes only the season held out during training. It verifies
that predictions match the normalized observations before exporting. Model error
is the held-out mean absolute range error across both checkpoints. This is a
historical snapshot; rerun the CLI workflow and export to refresh it. Live feeds
and Kalshi execution are not connected. The export embeds derived historical
data; follow source licensing when sharing it.

To read prepared outputs in another checkout location, add `--workspace PATH`.

## Reproducible real-data workflow

```bash
# 1: Download three NFL seasons as normalized play-by-play (internet needed).
fva ingest-nfl --seasons 2023 2024 2025 --output data/nfl_2023_2025.csv

# 2: Public historical college football archives (no API key).
fva ingest-cfbfastr --seasons 2023 2024 2025 --output data/cfbfastr_2023_2025.csv

# 3: Construct *separate* research datasets.
fva features --input data/nfl_2023_2025.csv --output data/nfl_features.csv
fva features --input data/cfbfastr_2023_2025.csv --output data/cfbfastr_features.csv

# 4: Later-season holdout (will fail fast if training/holdout is too small).
fva train --input data/nfl_features.csv --league nfl --test-season 2025 --model-dir models/nfl
fva train --input data/cfbfastr_features.csv --league cfb --test-season 2025 --model-dir models/cfbfastr

# 5: Out-of-sample backtest (probability proxy; NOT Kalshi P&L).
fva backtest --predictions models/nfl/holdout_predictions.csv --output reports/nfl.json
fva backtest --predictions models/cfbfastr/holdout_predictions.csv --output reports/cfbfastr.json

# 6: Example scoring at the 40-play checkpoint (input must only include observed plays).
fva score --input data/nfl_2023_2025.csv --model-dir models/nfl --checkpoint 40 \
  --output reports/nfl_scores.csv
```

For the optional CFBD connector, securely set `CFBD_API_KEY` and run
`fva ingest-cfb --seasons 2023 2024 2025 --weeks 1 2 3 4 5 --output data/cfbd.csv`.
Extend weeks for a larger regular-season sample; postseason uses a separate
`--season-type postseason` download. Do not pool CFBD and cfbfastR probabilities
in one model. See the source-specific ordering and coverage caveats in
[Data sources](docs/DATA_SOURCES.md).

For an entirely offline **synthetic smoke test**, run:

```bash
fva demo --output data/demo.csv
fva features --input data/demo.csv --output data/demo_features.csv
fva train --input data/demo_features.csv --league nfl --test-season 2025 --model-dir models/demo
fva backtest --predictions models/demo/holdout_predictions.csv --output reports/demo.json
```

The synthetic `demo` dataset is only for testing plumbing. **Its scores must never be interpreted as real trading edge.** No live in-game data polling, real-time exchange order book, fees integration, bankroll or order execution is included.

## Prediction details

- `predicted_future_range` is in **probability points** from 0 to 1: a value of 0.24 means a modeled future 24-percentage-point max-minus-min range, *not* a 24% chance of winning or a 24% profit.
- `future_range` uses the current decision-point probability plus the following **40 observed plays**. Range requires perfect hindsight to capture and is **not** itself a realizable return.
- Rankings are supported at fixed 40 and 80 play checkpoints; a `score` call on a completed game intentionally ignores subsequent plays to avoid lookahead.
- Holdout by **season**, never by individual random play. One game can create up to two checkpoints; both remain on the same side of a seasonal split.
- Historical data can be revised; pin exports or snapshot raw downloads to make research fully reproducible.

See [Architecture](docs/ARCHITECTURE.md), [Backtesting caveats](docs/BACKTEST.md), [Data sources](docs/DATA_SOURCES.md), [Release/PR steps](docs/DEPLOY.md), and the [prepared PR description](docs/PR_DESCRIPTION.md).

## Browser verification for development

```bash
pip install -e '.[dev,browser]'
python -m playwright install chromium
python scripts/check_dashboard_browser.py reports/dashboard.html
```

The check script uses a temporary internal loopback server and Chromium to
exercise filtering, sorting, paging, charts, CSV downloads, mobile layout and
the help dialog. It also rejects JavaScript errors and external requests. CI
runs the same check on fabricated test fixtures; historical validation results
are documented separately.
