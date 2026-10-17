# Data sources and assumptions

## NFL (nflverse)

Release URL pattern: `https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.{parquet,csv}`. Data dictionary: https://nflreadr.nflverse.com/articles/dictionary_pbp.html . Project/source attribution: nflverse / nflfastR; follow original data licensing and attribution before republishing underlying plays.

Core fields: `game_id`, `season`, `week`, `game_date`, `home_team`, `away_team`, `play_id`, `qtr`, `home_wp`, `total_home_score`, `total_away_score`, `down`, `ydstogo`. **Do not use `home_score` / `away_score`: these can be final game scores.** We deliberately exclude final scores and outcome flags. The `home_wp` estimates are a model's contextual probabilities, not Kalshi prices.

## CollegeFootballData

- `/games?year=YYYY&classification=fbs&seasonType=regular` (or `postseason`) returns games with team identities, week, start date and completion status.
- `/plays?year=YYYY&week=W&classification=fbs&seasonType=regular` (or `postseason`) returns play-level game data including period/clock, play ID and scores.
- `/metrics/wp?gameId=ID` returns play-level win probability by play ID/number. Each game makes an additional API request. `CFBD_API_KEY` must be a Bearer token; rate/usage limits depend on your account.
- API reference: https://api.collegefootballdata.com/api/plays , https://api.collegefootballdata.com/api/metrics , https://api.collegefootballdata.com/api/games .

Normalize CFB by joining (`gameId`, `playId`) to (`gameId`, `id`) when available. Win-probability records carry `playNumber`; retain WP ordering even if not matched. The pipeline fetches historical play-by-play as requested; **it does not equate CFBD `excitementIndex` with tradeable volatility**. CFB samples can be biased if limited to FBS, completed games, specific weeks, or games with WP coverage. Missing WP games are explicitly skipped/reported.

## Reproducibility and availability

Source endpoints require an active internet connection. API fields/coverage may change; ingestion includes schema checks, retries, caching of upstream results and explicit skips. nflverse and CFBD probability models are not the same; don't pool trajectories without calibration. Retain per-source original snapshots and ingestion timestamp for audit use.
