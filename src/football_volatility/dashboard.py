"""Build an offline browser dashboard from audited historical holdout outputs."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path

import numpy as np
import pandas as pd

from football_volatility.schema import read_csv

SOURCES = (
    ("nfl", "NFL", "nflverse", "nfl", "nfl_2023_2025.csv"),
    ("cfb", "College football", "cfbfastR", "cfbfastr", "cfbfastr_2023_2025.csv"),
)
NFL_NAMES = dict(zip(
    ["ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC", "LA", "LAC", "LV", "MIA", "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS"],
    ["Arizona Cardinals", "Atlanta Falcons", "Baltimore Ravens", "Buffalo Bills",
     "Carolina Panthers", "Chicago Bears", "Cincinnati Bengals", "Cleveland Browns",
     "Dallas Cowboys", "Denver Broncos", "Detroit Lions", "Green Bay Packers",
     "Houston Texans", "Indianapolis Colts", "Jacksonville Jaguars", "Kansas City Chiefs",
     "Los Angeles Rams", "Los Angeles Chargers", "Las Vegas Raiders", "Miami Dolphins",
     "Minnesota Vikings", "New England Patriots", "New Orleans Saints", "New York Giants",
     "New York Jets", "Philadelphia Eagles", "Pittsburgh Steelers", "Seattle Seahawks",
     "San Francisco 49ers", "Tampa Bay Buccaneers", "Tennessee Titans", "Washington Commanders"],
    strict=True,
))
PREDICTION_COLUMNS = {
    "league", "season", "game_id", "home_team", "away_team", "checkpoint", "horizon",
    "current_wp", "predicted_future_range", "future_range",
}


def _text(value: object, fallback: str = "") -> str:
    return fallback if pd.isna(value) else str(value)


def _dataset(league: str, label: str, source: str, predictions: pd.DataFrame,
             plays: pd.DataFrame, evaluation: dict) -> dict:
    if missing := PREDICTION_COLUMNS - set(predictions):
        raise ValueError(f"{label} predictions missing columns: {sorted(missing)}")
    if predictions.empty or not predictions.league.eq(league).all():
        raise ValueError(f"{label} predictions must contain only that league's held-out games")
    holdout = int(evaluation["holdout_season"])
    training = list(map(int, evaluation["train_seasons"]))
    if not training or max(training) >= holdout or not predictions.season.eq(holdout).all():
        raise ValueError(f"{label} dashboard requires a chronological season holdout")
    if not predictions.checkpoint.isin([40, 80]).all() or not predictions.horizon.eq(40).all():
        raise ValueError("Dashboard supports 40/80-observation checkpoints and a 40-observation horizon")
    if predictions.duplicated(["game_id", "checkpoint"]).any():
        raise ValueError(f"{label} contains duplicate game/checkpoint predictions")
    for name in ("current_wp", "predicted_future_range", "future_range"):
        if not np.isfinite(predictions[name]).all() or not predictions[name].between(0, 1).all():
            raise ValueError(f"{label} {name} must contain finite probabilities in [0, 1]")
    for name in ("mae", "baseline_mae"):
        if not np.isfinite(evaluation[name]) or not 0 <= evaluation[name] <= 1:
            raise ValueError(f"{label} evaluation {name} must be a finite probability error")
    if (plays.loc[plays.league.eq(league) & plays.season.lt(holdout), "game_id"]
            .isin(predictions.game_id).any()):
        raise ValueError(f"{label} training and holdout games overlap")

    groups = {str(gid): game for gid, game in plays.loc[
        plays.league.eq(league) & plays.season.eq(holdout)
    ].groupby("game_id", sort=False)}
    games = []
    for gid, rows in predictions.groupby("game_id", sort=False):
        if str(gid) not in groups:
            raise ValueError(f"{label} holdout game {gid} is missing its probability observations")
        observed = groups[str(gid)]
        end = int((rows.checkpoint + rows.horizon).max())
        if len(observed) < end:
            raise ValueError(f"{label} game {gid} lacks the full observation window")
        row = rows.iloc[0]
        snapshots = {}
        for _, snapshot in rows.iterrows():
            checkpoint = int(snapshot.checkpoint)
            path = observed.home_wp.iloc[checkpoint - 1:checkpoint + 40].to_numpy(float)
            if not np.isclose(path[0], snapshot.current_wp, atol=1e-6) or not np.isclose(np.ptp(path), snapshot.future_range, atol=1e-6):
                raise ValueError(f"{label} game {gid} predictions and observations do not match")
            snapshots[str(checkpoint)] = {
                "current": round(float(snapshot.current_wp) * 100, 4),
                "forecast": round(float(snapshot.predicted_future_range) * 100, 4),
                "actual": round(float(snapshot.future_range) * 100, 4),
            }
        home, away = _text(row.home_team, str(gid)), _text(row.away_team, str(gid))
        games.append({
            "id": str(gid), "season": int(row.season),
            "date": _text(row.get("game_date"))[:10], "home": home, "away": away,
            "homeName": NFL_NAMES.get(home, home) if league == "nfl" else home,
            "awayName": NFL_NAMES.get(away, away) if league == "nfl" else away,
            "snapshots": snapshots,
            "path": [round(float(p) * 100, 4) for p in observed.home_wp.iloc[:end]],
        })
    return {
        "id": league, "label": label, "source": source, "games": games,
        "evaluation": {"season": holdout, "training": training,
                       "mae": float(evaluation["mae"]) * 100,
                       "baselineMae": float(evaluation["baseline_mae"]) * 100},
    }


def build_dashboard(workspace: str | Path = ".", output: str | Path = "reports/dashboard.html") -> Path:
    """Export a self-contained HTML file; read existing holdout files without refitting."""
    root = Path(workspace).resolve()
    datasets, unavailable = [], []
    for league, label, source, model, data in SOURCES:
        predictions = root / "models" / model / "holdout_predictions.csv"
        evaluation = predictions.parent / "evaluation.json"
        observations = root / "data" / data
        if not all(p.is_file() for p in (predictions, evaluation, observations)):
            unavailable.append(label)
            continue
        datasets.append(_dataset(
            league, label, source, pd.read_csv(predictions, dtype={"game_id": str}),
            read_csv(observations), json.loads(evaluation.read_text()),
        ))
    if not datasets:
        raise ValueError("No historical holdouts found. Run the real-data workflow in README.md first (ingest, features, train), then fva dashboard.")
    payload = {"builtAt": datetime.now(timezone.utc).isoformat(),
               "datasets": datasets, "unavailable": unavailable}
    # Keep source strings inside JSON even when they contain HTML/script delimiters.
    encoded = json.dumps(payload, separators=(",", ":"), allow_nan=False)
    for char, escaped in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026")):
        encoded = encoded.replace(char, escaped)
    template = files("football_volatility").joinpath("assets/dashboard.html").read_text()
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(template.replace("__DASHBOARD_DATA__", encoded), encoding="utf-8")
    return target.resolve()
