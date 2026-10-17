"""Independent NFL/CFB fit, chronological holdout, and inference."""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.pipeline import Pipeline

from football_volatility.features import FEATURES
from football_volatility.schema import save_csv


def train(frame: pd.DataFrame, league: str, test_season: int, model_dir: str | Path) -> dict:
    league = league.lower()
    if league not in ("nfl", "cfb"):
        raise ValueError("league must be nfl or cfb")
    if any(col not in frame for col in FEATURES + ["league", "season", "future_range"]):
        raise ValueError("Feature frame missing required columns; run `fva features` first")
    data = frame.loc[frame.league == league].copy()
    train_df = data.loc[data.season < test_season]
    test_df = data.loc[data.season == test_season]
    if len(train_df) < 25 or len(test_df) < 5 or train_df.game_id.nunique() < 10:
        raise ValueError("Need >=25 training snapshots from >=10 games and >=5 holdout snapshots, in later season")
    if "horizon" in data:
        if data.horizon.nunique() != 1:
            raise ValueError("Cannot mix future horizons in one fitted model")
        horizon = int(data.horizon.iloc[0])
    else:
        horizon = 40
    # Each game appears only in one season => both of its checkpoints split together.
    if set(train_df.game_id) & set(test_df.game_id):
        raise ValueError("Leakage: training and test share game IDs")
    pipeline = Pipeline([
        ("impute", SimpleImputer(strategy="constant", fill_value=0.0)),
        ("predictor", HistGradientBoostingRegressor(max_iter=120, max_leaf_nodes=12, min_samples_leaf=6, l2_regularization=2.0, random_state=42)),
    ])
    pipeline.fit(train_df[FEATURES], train_df.future_range)
    test_predictions = np.clip(pipeline.predict(test_df[FEATURES]), 0, 1)
    train_mean = float(train_df.future_range.mean())
    predicted = test_df.copy()
    predicted["predicted_future_range"] = test_predictions
    predicted["train_mean_baseline"] = train_mean
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipeline, "league": league, "features": FEATURES, "train_seasons": sorted(map(int, train_df.season.unique())), "horizon": horizon}, model_dir / "model.joblib")
    save_csv(predicted, model_dir / "holdout_predictions.csv")
    stats = {
        "league": league, "holdout_season": int(test_season),
        "train_seasons": sorted(map(int, train_df.season.unique())),
        "training_snapshots": len(train_df), "training_games": int(train_df.game_id.nunique()),
        "holdout_snapshots": len(test_df), "holdout_games": int(test_df.game_id.nunique()),
        "mae": float(mean_absolute_error(test_df.future_range, test_predictions)),
        "rmse": float(root_mean_squared_error(test_df.future_range, test_predictions)),
        "baseline_mae": float(mean_absolute_error(test_df.future_range, np.full(len(test_df), train_mean))),
        "baseline_rmse": float(root_mean_squared_error(test_df.future_range, np.full(len(test_df), train_mean))),
        "target": f"future_range_next_{horizon}_plays", "note": "WP proxy only; no Kalshi market quotes",
    }
    (model_dir / "evaluation.json").write_text(json.dumps(stats, indent=2))
    return stats


def score(frame: pd.DataFrame, model_dir: str | Path) -> pd.DataFrame:
    artifact = joblib.load(Path(model_dir) / "model.joblib")
    if not frame.league.eq(artifact["league"]).all():
        raise ValueError("Cannot score one league using another league's model")
    frame = frame.copy()
    frame["predicted_future_range"] = np.clip(artifact["pipeline"].predict(frame[artifact["features"]]), 0, 1)
    return frame[["league", "season", "game_id", "home_team", "away_team", "checkpoint", "current_wp", "predicted_future_range"]].sort_values("predicted_future_range", ascending=False).reset_index(drop=True)
