"""Past-only features and strictly future 40-play labels."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from football_volatility.schema import normalize

DEFAULT_CHECKPOINTS = (40, 80)
DEFAULT_HORIZON = 40
FEATURES = [
    "checkpoint", "current_wp", "uncertainty", "score_diff", "abs_score_diff",
    "total_points", "wp_change_10", "wp_change_20", "historic_range_20",
    "historic_tv_20", "historic_tv_all", "big_swings_20", "close_fraction_20",
    "score_changes_20", "lead_changes", "period", "seconds_remaining", "down", "distance",
]


def _num(value: object, fallback: float = float("nan")) -> float:
    try:
        v = float(value)
        return v if np.isfinite(v) else fallback
    except (TypeError, ValueError):
        return fallback


def _one_game(g: pd.DataFrame, checkpoint: int, horizon: int, labeled: bool) -> dict | None:
    if len(g) < checkpoint or (labeled and len(g) < checkpoint + horizon):
        return None
    past = g.iloc[:checkpoint]
    prior = past.iloc[-1]
    wp = past.home_wp.to_numpy(dtype=float)
    if len(wp) < 21 or not np.isfinite(wp).all():
        return None
    scores_home = past.home_score.to_numpy(dtype=float)
    scores_away = past.away_score.to_numpy(dtype=float)
    score_diff = scores_home - scores_away
    deltas = np.diff(wp)
    close = wp[-20:]
    score_total = scores_home + scores_away
    signs = np.sign(score_diff)
    # Lead changes only when two distinct nonzero leader states occur in order.
    leaders = signs[signs != 0]
    lead_changes = int(np.sum(np.diff(leaders) != 0)) if len(leaders) else 0
    row = {
        "league": str(prior.league), "season": int(prior.season),
        "week": _num(prior.week), "game_date": prior.game_date,
        "game_id": str(prior.game_id), "home_team": prior.home_team,
        "away_team": prior.away_team, "checkpoint": int(checkpoint), "horizon": int(horizon),
        "current_wp": float(wp[-1]), "uncertainty": float(4*wp[-1]*(1-wp[-1])),
        "score_diff": float(score_diff[-1]), "abs_score_diff": float(abs(score_diff[-1])),
        "total_points": float(score_total[-1]),
        "wp_change_10": float(wp[-1] - wp[-11]),
        "wp_change_20": float(wp[-1] - wp[-21]),
        "historic_range_20": float(np.ptp(close)),
        "historic_tv_20": float(np.sum(np.abs(np.diff(close)))),
        "historic_tv_all": float(np.sum(np.abs(deltas))),
        "big_swings_20": int(np.sum(np.abs(np.diff(close)) >= .10)),
        "close_fraction_20": float(np.mean((close >= .35) & (close <= .65))),
        "score_changes_20": int(np.count_nonzero(np.diff(score_total[-20:]))),
        "lead_changes": lead_changes,
        "period": _num(prior.period), "seconds_remaining": _num(prior.seconds_remaining),
        "down": _num(prior.down), "distance": _num(prior.distance),
    }
    if labeled:
        future = g.iloc[checkpoint:checkpoint + horizon].home_wp.to_numpy(dtype=float)
        path = np.concatenate(([wp[-1]], future))
        if not np.isfinite(path).all():
            return None
        row["future_range"] = float(np.ptp(path))
        row["future_total_variation"] = float(np.sum(np.abs(np.diff(path))))
        row["future_large_moves"] = int(np.sum(np.abs(np.diff(path)) >= .10))
        row["future_path"] = json.dumps([round(float(p), 6) for p in path])
    return row


def build_features(plays: pd.DataFrame, *, checkpoints: tuple[int, ...] = DEFAULT_CHECKPOINTS, horizon: int = DEFAULT_HORIZON, labeled: bool = True) -> pd.DataFrame:
    if horizon <= 0 or any(c < 21 for c in checkpoints):
        raise ValueError("Checkpoints must be >=21 and horizon > 0")
    normalized = normalize(plays)
    records = []
    for (_, game_id), game in normalized.groupby(["league", "game_id"], sort=False):
        # Game ID is unique within league and includes year for NFL. CFB numeric IDs also unique.
        if game.season.nunique() != 1:
            raise ValueError(f"Game ID {game_id} appears in multiple seasons")
        for checkpoint in sorted(set(checkpoints)):
            row = _one_game(game, checkpoint, horizon, labeled)
            if row:
                records.append(row)
    if not records:
        raise ValueError("No eligible game snapshots (check minimum play count and horizons)")
    return pd.DataFrame.from_records(records).sort_values(["league", "season", "game_id", "checkpoint"]).reset_index(drop=True)
