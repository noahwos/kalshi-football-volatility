# Data sources and assumptions

## NFL (nflverse)

Release URL pattern: `https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.{parquet,csv}`. Data dictionary: https://nflreadr.nflverse.com/articles/dictionary_pbp.html . Project/source attribution: nflverse / nflfastR; follow original data licensing and attribution before republishing underlying plays.

Core fields: `game_id`, `season`, `week`, `game_date`, `home_team`, `away_team`, `play_id`, `qtr`, `home_wp`, `total_home_score`, `total_away_score`, `down`, `ydstogo`. **Do not use `home_score` / `away_score`: these can be final game scores.** We deliberately exclude final scores and outcome flags. The `home_wp` estimates are a model's contextual probabilities, not Kalshi prices.

## Public college football archives (cfbfastR / SportsDataverse)

`fva ingest-cfbfastr` downloads Parquet archives from
`https://github.com/sportsdataverse/sportsdataverse-data/releases/download/cfbfastR_cfb_pbp/play_by_play_YEAR.parquet`.
This is the public archive used by the official cfbfastR loader:
https://github.com/sportsdataverse/cfbfastR/blob/master/R/load_cfb_pbp.R .
No CFBD API key is needed to download these published historical snapshots.
Attribute cfbfastR, SportsDataverse and their underlying data providers, and
review source licensing before redistributing raw plays.

The importer selects completed games with at least one FBS team. It uses
`home_wp_before`, never possession-team WP or archive post-play WP. In sampled
archives, post-play probabilities could invert unexpectedly and
`game_play_number` sometimes reset within a game. The importer reconstructs
order by period and descending clock, preserving archive order for ties. It
excludes standalone timeout, penalty and end-of-period/game rows and assigns
fresh observation numbers. These are accepted probability observations, not
an independent official snap count. Missing WP rows are removed, so horizons
count the retained observations. Raw archives are retained for auditing.

Home and away **in-game** scores are derived from possession-team scores and
shifted one row to align with pre-play WP; first recorded pre-play scores start
at zero. Final scores and drive-end scores are excluded. `TimeSecsRem` is a
half clock in this archive; regulation game time is reconstructed from period,
minutes and seconds, with overtime time remaining left missing. Clock ties,
corrections, incomplete opening coverage and source-model revisions still
require quality review for each new dataset. Model-probability artifacts do
not represent exchange price movement. Keep cfbfastR models separate from
CFBD models because their probability definitions and versions differ.

## CollegeFootballData (optional authenticated alternative)

- `/games?year=YYYY&classification=fbs&seasonType=regular` (or `postseason`) returns games with team identities, week, start date and completion status.
- `/plays?year=YYYY&week=W&classification=fbs&seasonType=regular` (or `postseason`) returns play-level game data including period/clock, play ID and scores.
- `/metrics/wp?gameId=ID` returns play-level win probability by play ID/number. Each game makes an additional API request. `CFBD_API_KEY` must be a Bearer token; rate/usage limits depend on your account.
- API reference: https://api.collegefootballdata.com/api/plays , https://api.collegefootballdata.com/api/metrics , https://api.collegefootballdata.com/api/games .

Normalize CFB by joining (`gameId`, `playId`) to (`gameId`, `id`) when available. Win-probability records carry `playNumber`; retain WP ordering even if not matched. The pipeline fetches historical play-by-play as requested; **it does not equate CFBD `excitementIndex` with tradeable volatility**. CFB samples can be biased if limited to FBS, completed games, specific weeks, or games with WP coverage. Missing WP games are explicitly skipped/reported.

## Reproducibility and availability

Source endpoints require an active internet connection. API fields/coverage may change; ingestion includes schema checks, retries, caching of upstream results and explicit skips. nflverse and CFBD probability models are not the same; don't pool trajectories without calibration. Retain per-source original snapshots and ingestion timestamp for audit use.
