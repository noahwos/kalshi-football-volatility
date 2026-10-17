"""Public cfbfastR historical archives; no CFBD API credential is required."""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from football_volatility.schema import normalize

LOG = logging.getLogger(__name__)
BASE = (
    "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/"
    "cfbfastR_cfb_pbp/play_by_play_{year}.parquet"
)
REQUIRED = {
    "season", "game_id", "home_wp_before", "home_team", "away_team",
    "pos_team", "def_pos_team", "pos_team_score", "def_pos_team_score", "completed",
    "home_team_division", "away_team_division", "period", "clock_minutes", "clock_seconds", "play_type",
}
OPTIONAL = {"week", "start_date", "id_play", "down", "distance"}


def cfbfastr_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Map completed FBS games to chronological pre-play probability observations."""
    if missing := REQUIRED - set(raw):
        raise ValueError(f"cfbfastR missing columns: {sorted(missing)}")
    fbs = raw.home_team_division.eq("fbs") | raw.away_team_division.eq("fbs")
    home_possession = raw.pos_team.eq(raw.home_team) & raw.def_pos_team.eq(raw.away_team)
    away_possession = raw.pos_team.eq(raw.away_team) & raw.def_pos_team.eq(raw.home_team)
    valid = raw.completed.eq(True) & fbs & (home_possession | away_possession)
    data = raw.loc[valid].copy()
    for name in ("period", "clock_minutes", "clock_seconds"):
        data[name] = pd.to_numeric(data[name], errors="coerce")
    data = data.loc[data.period.ge(1) & data.clock_minutes.between(0, 15) & data.clock_seconds.between(0, 59)]
    # Some archives have broken game_play_number counters. Use the regulation
    # period/clock, preserving source order when clocks tie (including overtime).
    data = data.sort_values(["season", "game_id", "period", "clock_minutes", "clock_seconds"], ascending=[True, True, True, False, False], kind="stable")
    home_possession = data.pos_team.eq(data.home_team)
    data["home_score_after"] = data.pos_team_score.where(home_possession, data.def_pos_team_score)
    data["away_score_after"] = data.def_pos_team_score.where(home_possession, data.pos_team_score)
    grouped = data.groupby(["season", "game_id"], sort=False)
    # home_wp_before is pre-play. Shift in-game scores to that same instant;
    # post-play probability fields in upstream archives can invert at possession changes.
    data["home_score_before"] = grouped.home_score_after.shift().fillna(0)
    data["away_score_before"] = grouped.away_score_after.shift().fillna(0)
    administrative = data.play_type.str.contains(r"^(?:Timeout|Penalty|End of|End Period)", case=False, na=False)
    data = data.loc[~administrative].copy()
    data["observation_number"] = data.groupby(["season", "game_id"], sort=False).cumcount() + 1

    def col(name: str):
        return data[name] if name in data else pd.Series(float("nan"), index=data.index)

    period = pd.to_numeric(col("period"), errors="coerce")
    seconds = (4 - period) * 900 + pd.to_numeric(col("clock_minutes"), errors="coerce") * 60 + pd.to_numeric(col("clock_seconds"), errors="coerce")
    # TimeSecsRem in this archive is a HALF clock, not a game clock.
    seconds = seconds.where(period.between(1, 4)).clip(lower=0)
    frame = pd.DataFrame({
        "league": "cfb", "season": data.season, "week": col("week"),
        "game_id": data.game_id, "game_date": col("start_date"),
        "home_team": data.home_team, "away_team": data.away_team,
        "play_id": col("id_play"), "play_number": data.observation_number,
        "period": period, "seconds_remaining": seconds,
        "home_score": data.home_score_before, "away_score": data.away_score_before,
        "home_wp": data.home_wp_before, "down": col("down"), "distance": col("distance"),
    })
    result = normalize(frame)
    LOG.info("cfbfastR: %s raw rows -> %s completed FBS plays with valid WP", len(raw), len(result))
    return result


def ingest(seasons: list[int], cache: str | Path = "data/raw/cfbfastr") -> pd.DataFrame:
    years = sorted(set(seasons))
    if not years or any(not 2014 <= year <= 2100 for year in years):
        raise ValueError("Select cfbfastR seasons from 2014 onward")
    cache_path = Path(cache)
    cache_path.mkdir(parents=True, exist_ok=True)
    outputs = []
    with requests.Session() as session:
        session.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))
        for year in years:
            path = cache_path / f"play_by_play_{year}.parquet"
            if not path.exists():
                url = BASE.format(year=year)
                LOG.info("Downloading %s", url)
                partial = path.with_suffix(".parquet.partial")
                try:
                    with session.get(url, stream=True, timeout=(10, 120)) as response:
                        response.raise_for_status()
                        with partial.open("wb") as handle:
                            for chunk in response.iter_content(chunk_size=2**20):
                                if chunk:
                                    handle.write(chunk)
                    partial.replace(path)
                finally:
                    partial.unlink(missing_ok=True)
            available = set(pq.ParquetFile(path).schema_arrow.names)
            if missing := REQUIRED - available:
                raise ValueError(f"cfbfastR {year} missing columns: {sorted(missing)}")
            raw = pd.read_parquet(path, columns=sorted((REQUIRED | OPTIONAL) & available))
            frame = cfbfastr_frame(raw)
            if not frame.season.eq(year).all():
                raise ValueError(f"cfbfastR {year} archive contains unexpected seasons")
            outputs.append(frame)
    result = normalize(pd.concat(outputs, ignore_index=True))
    if result.empty:
        raise ValueError("No completed FBS games with valid WP found in the cfbfastR archives")
    return result
