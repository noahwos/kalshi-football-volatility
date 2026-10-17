# Pull request: NFL + CFB Historical Volatility Analyzer

## Summary
- Add standalone NFL nflverse importer and college football CFBD historical games, plays, and win-probability importer; normalize data without exposing final scores at decision time.
- Construct exact 40- and 80-play in-game snapshots and next-40-play volatility labels using only data available by each checkpoint.
- Train league-specific gradient boosting pipelines, separated by season; enforce held-out game isolation.
- Generate out-of-sample ranking MAE/RMSE/baselines and toy time-ordered probability-proxy backtests with cost, stop and target.
- Provide offline synthetic CLI smoke test, unit tests, CI workflow, docs for reproducible real-data work and source attribution.
- Reject game IDs reused across seasons before deduplicating plays, and remove non-finite required values and blank game IDs during normalization.
- Validate backtest probability paths, predictions and trade parameters; report the actual future horizon and reject mixed horizons.

## Verification
- `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv/bin/pytest -q` — 27 passed on Python 3.12.14, including regression tests for data validation.
- `.venv/bin/ruff check src tests` and `.venv/bin/pip check` — passed.
- Clean up imports and redundant integer casts; report unexpected CFBD response types with `TypeError`.
- End-to-end CLI run: `demo`, `features`, `train --league nfl`, `train --league cfb`, `backtest` and `score` executed successfully on **synthetic** data.
- Real NFL ingestion succeeded for 2023–2025: 147,928 normalized plays across 855 games and 1,710 labeled snapshots. Training on 2023–2024, 2025 holdout evaluation/backtesting and scoring at both checkpoints completed.
- NFL holdout range MAE: 0.06815 versus 0.08961 for the training-mean baseline. The toy strategy lost money; this is not an exchange-profitability result. See `docs/VALIDATION.md` for commands, source hashes and limitations.
- Authenticated CFBD historical ingestion remains untested because `CFBD_API_KEY` is absent. No exchange P&L is claimed.

## Known limitations / follow-ups
- Needs source-API integration smoke tests with network + a real CFBD token.
- `home_wp` and CFBD `homeWinProbability` represent source-model probabilities, not actual Kalshi order-book prices.
- Validate Kalshi historical quotes, fees, fills, latency and market halts before drawing executable strategy conclusions.
- Pregame prediction, real-time polling, order execution and account management are intentionally not included.
