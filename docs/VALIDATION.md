# Validation results

Validated on October 17, 2026 with Python 3.12.14. This records one historical
holdout, not a final model-selection study or an executable trading result.

## Automated and synthetic checks

- Full test suite: **27 passed**.
- `ruff check src tests`: passed.
- `python -m pip check`: no broken requirements.
- Synthetic CLI workflow: demo generation, feature creation, separate NFL/CFB
  training and backtesting, and scoring at both 40 and 80 plays completed.
- Regression coverage rejects cross-season game ID collisions before play
  deduplication, non-finite required data, invalid probability paths, non-finite
  trade parameters/predictions and mixed forecast horizons.

## Real NFL historical workflow

```bash
source .venv/bin/activate
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
fva ingest-nfl --seasons 2023 2024 2025 --output data/nfl_2023_2025.csv
fva features --input data/nfl_2023_2025.csv --output data/nfl_2023_2025_features.csv
fva train --input data/nfl_2023_2025_features.csv --league nfl \
  --test-season 2025 --model-dir models/nfl
fva backtest --predictions models/nfl/holdout_predictions.csv --output reports/nfl.json
for checkpoint in 40 80; do
  fva score --input data/nfl_2023_2025.csv --model-dir models/nfl \
    --checkpoint "$checkpoint" --output "reports/nfl_${checkpoint}_scores.csv"
done
```

All commands completed. Ingestion produced **147,928 normalized plays across 855
games**, yielding **1,710 labeled snapshots**. Training used 1,140 snapshots from
570 games in 2023–2024. The untouched-by-training 2025 holdout contained 570
snapshots from 285 games. Both checkpoint scoring calls completed.

| Holdout metric | Model | Training-mean baseline |
| --- | ---: | ---: |
| Future-range MAE | 0.06815 | 0.08961 |
| Future-range RMSE | 0.08974 | 0.11175 |

Spearman rank correlation was 0.5993. Top-quartile mean future-range lift was
1.2196. These values are in source win-probability units; MAE 0.06815 is about
6.8 percentage points of range error.

The toy strategy lost money at the default cost: mean probability-proxy P&L
was **-0.01647 per decision** over all 570 decisions, and **-0.01664** over the
143 selected decisions. This is not historical Kalshi P&L and is not evidence
of a profitable strategy. The forecast holdout was not used to tune model
parameters during this run; further model selection needs additional seasons
and a new untouched evaluation period.

### Source snapshots

Source: nflverse GitHub `pbp` release, files named `play_by_play_YEAR.parquet`.
Downloaded files, models and reports remain in ignored directories locally.
Upstream historical releases can change; retain these files or verify hashes
before comparing reruns.

| File | SHA-256 |
| --- | --- |
| `play_by_play_2023.parquet` | `bd3484731408def6b0ec93225bba2bd7b2c65769ca707a2b9444d891abdc6776` |
| `play_by_play_2024.parquet` | `3fd2896bc0b911b615142d2f1fabae54a4bbba5ab7b73b28187b118ef8af6a3b` |
| `play_by_play_2025.parquet` | `c6ecedd6d678cc37ed316b23ef84ee1ec6abb69c514bb11868a7ebd5a367df29` |

Installed versions: numpy 2.5.4, pandas 3.0.6, scikit-learn 1.9.1,
requests 2.34.2, pyarrow 26.0.0, pytest 9.1.1. Dependency ranges in
`pyproject.toml` are not a lockfile; future installations may resolve differently.

## Remaining external prerequisites

Authenticated CollegeFootballData ingestion was **not run**: `CFBD_API_KEY` is
absent. Supply it securely in environment settings and allow
`api.collegefootballdata.com`; then start with one season/week and
`--limit-games 1`, inspect joined play/WP coverage, and expand to enough seasons
for independent CFB training and holdout evaluation. Local fixture tests do not
establish live API compatibility, coverage or quota sufficiency.

Actual exchange research additionally requires historical Kalshi quotes aligned
to event timestamps, fees, spreads, depth, fills, latency and market-halt handling.
No Kalshi order execution is implemented.
