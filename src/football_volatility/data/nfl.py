"""NFL nflverse release importer; never use leaked full-game final score columns."""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from football_volatility.schema import normalize

LOG = logging.getLogger(__name__)
BASE = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{year}.{fmt}"
COLUMNS = {"season", "week", "game_id", "game_date", "home_team", "away_team", "play_id", "qtr", "game_seconds_remaining", "home_wp", "total_home_score", "total_away_score", "down", "ydstogo"}


def nfl_frame(raw: pd.DataFrame) -> pd.DataFrame:
    required = {"game_id", "home_wp", "total_home_score", "total_away_score", "play_id", "season"}
    missing = required - set(raw)
    if missing:
        raise ValueError(f"nflverse missing columns: {sorted(missing)}")
    def col(key: str):
        return raw[key] if key in raw else pd.Series([pd.NA] * len(raw), index=raw.index)
    # NFL's `home_score` is often the FINAL result, not in-play score.
    frame = pd.DataFrame({
        "league": "nfl", "season": col("season"), "week": col("week"),
        "game_id": col("game_id"), "game_date": col("game_date"),
        "home_team": col("home_team"), "away_team": col("away_team"),
        "play_id": col("play_id"), "play_number": col("play_id"),
        "period": col("qtr"), "seconds_remaining": col("game_seconds_remaining"),
        "home_wp": col("home_wp"), "home_score": col("total_home_score"),
        "away_score": col("total_away_score"), "down": col("down"), "distance": col("ydstogo"),
    })
    return normalize(frame)


def _http_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def ingest(seasons: list[int], cache: str | Path = "data/raw/nfl", fmt: str = "parquet") -> pd.DataFrame:
    if fmt not in {"parquet", "csv"}:
        raise ValueError("fmt must be parquet or csv")
    cache_path = Path(cache)
    cache_path.mkdir(parents=True, exist_ok=True)
    outputs = []
    with _http_session() as session:
        for season in sorted(set(seasons)):
            if not 1999 <= season <= 2100:
                raise ValueError("NFL season year out of range")
            path = cache_path / f"play_by_play_{season}.{fmt}"
            if not path.exists():
                url = BASE.format(year=season, fmt=fmt)
                LOG.info("Downloading %s", url)
                with session.get(url, stream=True, timeout=(10, 120)) as response:
                    response.raise_for_status()
                    tmp = path.with_suffix(path.suffix + ".partial")
                    try:
                        with tmp.open("wb") as f:
                            for chunk in response.iter_content(chunk_size=2**20):
                                if chunk:
                                    f.write(chunk)
                        tmp.replace(path)
                    finally:
                        tmp.unlink(missing_ok=True)
            if fmt == "parquet":
                raw = pd.read_parquet(path, columns=sorted(COLUMNS))
            else:
                raw = pd.read_csv(path, usecols=lambda x: x in COLUMNS, low_memory=False)
            frame = nfl_frame(raw)
            if frame.empty:
                LOG.warning("No valid PBP found for NFL %s", season)
            outputs.append(frame)
    if not outputs:
        raise ValueError("No seasons selected")
    return normalize(pd.concat(outputs, ignore_index=True))
