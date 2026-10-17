"""Canonical play schema, cleaning and safe I/O."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED = ["league", "season", "game_id", "play_number", "home_wp", "home_score", "away_score"]
OPTIONAL = ["week", "game_date", "home_team", "away_team", "play_id", "period", "seconds_remaining", "down", "distance"]


def normalize(plays: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(set(REQUIRED) - set(plays.columns))
    if missing:
        raise ValueError(f"Missing required play columns: {missing}")
    df = plays.copy()
    for field in OPTIONAL:
        if field not in df:
            df[field] = pd.NA
    for field in ["season", "play_number", "home_wp", "home_score", "away_score", "week", "period", "seconds_remaining", "down", "distance"]:
        df[field] = pd.to_numeric(df[field], errors="coerce").replace([np.inf, -np.inf], np.nan)
    df["game_id"] = df["game_id"].astype("string").str.strip().replace("", pd.NA)
    df["league"] = df["league"].astype("string").str.lower().str.strip()
    df = df.dropna(subset=REQUIRED)
    if not df["league"].isin(["nfl", "cfb"]).all():
        raise ValueError("Only nfl and cfb leagues are supported")
    df = df.loc[df["home_wp"].between(0, 1) & (df["play_number"] >= 0)].copy()
    # Check before deduplication: otherwise identical play numbers can hide a reused game ID.
    seasons_per_game = df.groupby(["league", "game_id"])["season"].nunique()
    if (seasons_per_game > 1).any():
        raise ValueError("Game IDs must be unique within each league across seasons")
    df = df.sort_values(["league", "season", "game_id", "play_number"], kind="stable")
    df = df.drop_duplicates(["league", "game_id", "play_number"], keep="first")
    return df[REQUIRED + OPTIONAL].reset_index(drop=True)


def save_csv(df: pd.DataFrame, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(target, index=False)


def read_csv(path: str | Path) -> pd.DataFrame:
    return normalize(pd.read_csv(path, dtype={"game_id": "str"}, low_memory=False))
