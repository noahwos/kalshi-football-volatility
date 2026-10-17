# Football volatility analyzer with an offline browser dashboard

## Summary

Add a historical NFL/college football research toolkit and a self-contained
browser dashboard. Rank games by predicted home win-probability range over the
next 40 observations, using checkpoints at 40 and 80 observations. The dashboard
opens as one HTML file, with no server, account, API key or external assets.

- Import public nflverse and cfbfastR archives; retain an optional authenticated
  CFBD connector. Normalize in-game data and keep league/source models separate.
- Build past-only features and complete future labels, train gradient-boosted
  regressors on earlier seasons, and evaluate an isolated later-season holdout.
- Explore held-out rankings with league/checkpoint filters, team search, sorting,
  pagination and selected-game probability charts. Historical future paths are
  hidden until explicitly revealed. Export filtered rankings to CSV.
- Validate chronology, finite data, probability paths, source/label alignment,
  complete windows and cross-season game identities. Escape embedded data and
  render team names as text in the dashboard.
- Include CLI commands, an offline synthetic workflow, tests, CI, source hashes
  and reproducible real-data validation documentation.

## Use the dashboard

After the documented historical workflow has generated data and holdout models:

```bash
fva dashboard --output reports/dashboard.html
```

Open the generated HTML file in a browser. Downloaded data, models and exports
remain ignored; the application code and dashboard template are packaged.

## Validation

- Python suite: 43 passed; Ruff and dependency consistency checks passed.
- Chromium: both leagues/checkpoints, search, sorting, pagination, game selection,
  charts, outcome reveal, CSV contents, help and mobile layout passed on the real
  export and a synthetic fixture. No JavaScript errors or external requests.
  CI runs the Python matrix and a Chromium fixture check on Python 3.12.
- Built wheel includes the browser template.
- Real NFL: 147,928 observations, 855 games and 1,710 snapshots for 2023–2025;
  training on 2023–2024, holdout evaluation/backtesting on 2025 and both scoring
  checkpoints completed. Holdout range MAE 0.06815 versus mean baseline 0.08961.
- Real CFB: 425,204 observations, 2,762 games and 5,506 snapshots for 2023–2025;
  independent training, holdout evaluation/backtesting and scoring completed.
  Holdout range MAE 0.14209 versus baseline 0.19715.

See `docs/VALIDATION.md` for commands, source hashes, sample counts and limitations.

## Limits

Historical model probabilities are not Kalshi prices. The NFL toy proxy lost
money; no exchange profitability is established. cfbfastR source ordering and
post-play WP artifacts required reconstruction from period/clock and pre-play WP;
source coverage, timing ties and model revisions still need independent audit.
The optional CFBD connector remains untested against an authenticated live API.
Live polling, exchange quotes, fees/fills integration, order execution and account
management are not implemented. Leave this PR open for review; do not merge it
as part of this task.
