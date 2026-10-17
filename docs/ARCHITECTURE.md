# Architecture and methodology

`ingest-nfl`, `ingest-cfbfastr` or optional authenticated `ingest-cfb` -> normalized per-play CSV -> `features` -> independent models by league and probability source -> holdout rankings -> proxy trading backtest.

Each normalized row: `league`, `season`, `week`, `game_id`, `game_date`, `home_team`, `away_team`, `play_id`, `play_number`, `period`, `seconds_remaining`, `home_score`, `away_score`, `home_wp`, `down`, `distance`.

Normalized time series are sorted by play number. The cfbfastR importer first
reconstructs chronological observation numbers from period and clock because
some archived game counters reset; source order breaks ties. Administrative
events and invalid probabilities are removed. Normalization deduplicates play
numbers. See `DATA_SOURCES.md` for timing and coverage limitations. Game-end
outcomes, future total play counts and future scores are excluded from features.

At checkpoints 40 and 80, features are computed on the first N known plays. Training targets use the subsequent 40 plays: `max(WP) - min(WP)` for the current+future path, future realized total absolute WP variation, and number of moves >= 10 percentage points. The label is a **future path target**; max-min assumes hindsight and is not executable. Features capture historical range/total variation, trend/absolute swing, close-game fraction, game state and score changes. There is no ungrounded pregame prediction and no exchange quote history in this version.

The default regressor is `HistGradientBoostingRegressor`, fit independently for each league; imputation and feature selection are pinned in the serialized pipeline. The user chooses a chronologically later holdout season. Missing values are handled by a `SimpleImputer` with constant fill. Predictions are clipped to [0,1].

The backtest sorts **out-of-sample** held-out decisions by predicted future range and examines the top quartile. Returns are toy price-proxy returns (not market fills). The entry direction is deterministic, based only on the preceding 10 play movement; first target or stop to touch exits the position, otherwise close at the horizon. Return is computed as exit quote minus entry quote, minus a fixed roundtrip cost. NFL and college have distinct data sources, priors and fitted parameters.

Future extension: ingest Kalshi historical order-book or trades with aligned official event timestamps; estimate fill probabilities, taker/maker fees, spread, delay, market halts and resolution discrepancies; build scheduled-game pregame forecasts from lagged team efficiency metrics; monitor regime drift and calibration by league, season and checkpoint.
