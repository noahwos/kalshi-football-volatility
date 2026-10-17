# Pull request: NFL + CFB Historical Volatility Analyzer

## Summary
- Add public NFL nflverse and CFB cfbfastR archive importers, plus an optional authenticated CFBD connector; normalize data without exposing final scores at decision time. Historical NFL/CFB research can run without API keys.
- Reconstruct CFB archive chronology from period/clock, exclude administrative events, and align pre-play home WP with lagged in-game scores rather than unreliable archive counters or post-play probabilities.
- Construct exact 40- and 80-play in-game snapshots and next-40-play volatility labels using only data available by each checkpoint.
- Train league-specific gradient boosting pipelines, separated by season; enforce held-out game isolation.
- Generate out-of-sample ranking MAE/RMSE/baselines and toy time-ordered probability-proxy backtests with cost, stop and target.
- Provide offline synthetic CLI smoke test, unit tests, CI workflow, docs for reproducible real-data work and source attribution.
- Reject game IDs reused across seasons before deduplicating plays, and remove non-finite required values and blank game IDs during normalization.
- Validate backtest probability paths, predictions and trade parameters; report the actual future horizon and reject mixed horizons.

## Verification
- `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv/bin/pytest -q` — 34 passed on Python 3.12.14, including regression tests for data validation, CFB chronology/score alignment and repeatable cached ingestion.
- `.venv/bin/ruff check src tests` and `.venv/bin/pip check` — passed.
- Clean up imports and redundant integer casts; report unexpected CFBD response types with `TypeError`.
- End-to-end CLI run: `demo`, `features`, `train --league nfl`, `train --league cfb`, `backtest` and `score` executed successfully on **synthetic** data.
- Real NFL ingestion succeeded for 2023–2025: 147,928 normalized plays across 855 games and 1,710 labeled snapshots. Training on 2023–2024, 2025 holdout evaluation/backtesting and scoring at both checkpoints completed.
- NFL holdout range MAE: 0.06815 versus 0.08961 for the training-mean baseline. The toy strategy lost money; this is not an exchange-profitability result. See `docs/VALIDATION.md` for commands, source hashes and limitations.
- Public CFB ingestion succeeded for 2023–2025: 425,204 normalized observations across 2,762 games and 5,506 labeled snapshots. Separate CFB training on 2023–2024, holdout backtesting on 2025 and scoring at both checkpoints completed. Holdout range MAE: 0.14209 versus baseline 0.19715; archive quality caveats apply.
- Authenticated CFBD historical ingestion remains untested because `CFBD_API_KEY` is absent. No exchange P&L is claimed.

## Known limitations / follow-ups
- The optional CFBD connector needs an authenticated integration smoke test; public archive ingestion is verified without a token.
- Archive clocks, ties, coverage and model-probability revisions need source quality review before strategy conclusions; keep cfbfastR and CFBD models separate.
- GitHub Actions PR automation requires the owner's "Allow GitHub Actions to create and approve pull requests" setting. A run reached GitHub but was denied by that setting; no PR has been merged.
- `home_wp` and CFBD `homeWinProbability` represent source-model probabilities, not actual Kalshi order-book prices.
- Validate Kalshi historical quotes, fees, fills, latency and market halts before drawing executable strategy conclusions.
- Pregame prediction, real-time polling, order execution and account management are intentionally not included.
