"""CollegeFootballData historical games+plays+win-probability join."""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from football_volatility.schema import normalize

LOG = logging.getLogger(__name__)
API = "https://api.collegefootballdata.com"


def wp_frame(games: list[dict], plays: list[dict], wp_by_game: dict[int, list[dict]]) -> pd.DataFrame:
    """Merge provider WP and PBP on play ID; preserve WP-provided playNumber ordering."""
    games_map = {int(g["id"]): g for g in games if g.get("id") is not None}
    play_map = {(int(p["gameId"]), str(p["id"])): p for p in plays if p.get("gameId") is not None and p.get("id") is not None}
    rows = []
    for gid, wp_rows in wp_by_game.items():
        game = games_map.get(int(gid))
        if game is None or not game.get("completed"):
            continue
        for w in wp_rows:
            prob = w.get("homeWinProbability")
            if prob is None:
                continue
            play = play_map.get((int(gid), str(w.get("playId"))), {})
            clock = play.get("clock") or {}
            seconds = None
            if isinstance(clock, dict) and play.get("period") is not None:
                # Four-quarter regulation, explicit period; not used as model feature if unavailable.
                period = int(play["period"])
                if period <= 4:
                    seconds = max(0, (4-period)*900 + 60*int(clock.get("minutes") or 0) + int(clock.get("seconds") or 0))
            rows.append({
                "league": "cfb", "season": game.get("season"), "week": game.get("week"),
                "game_id": str(gid), "game_date": game.get("startDate"),
                "home_team": game.get("homeTeam", w.get("home")), "away_team": game.get("awayTeam", w.get("away")),
                "play_id": w.get("playId"), "play_number": w.get("playNumber"),
                "period": play.get("period"), "seconds_remaining": seconds,
                "home_score": w.get("homeScore"), "away_score": w.get("awayScore"),
                "home_wp": prob, "down": w.get("down"), "distance": w.get("distance"),
            })
    if not rows:
        return normalize(pd.DataFrame(columns=["league", "season", "game_id", "play_number", "home_wp", "home_score", "away_score"]))
    return normalize(pd.DataFrame(rows))


class CFBDClient:
    def __init__(self, api_key: str, cache: str | Path = "data/raw/cfb"):
        if not api_key:
            raise ValueError("CFBD_API_KEY environment variable required")
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_key}", "Accept": "application/json"})
        self.session.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))

    def get(self, endpoint: str, params: dict, cache_id: str) -> list[dict]:
        filename = self.cache / f"{cache_id}.json"
        if filename.exists():
            return json.loads(filename.read_text())
        response = self.session.get(f"{API}/{endpoint}", params=params, timeout=(10, 90))
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise TypeError(f"Expected a list from CFBD {endpoint}")
        tmp = filename.with_suffix(".json.partial")
        tmp.write_text(json.dumps(payload))
        tmp.replace(filename)
        time.sleep(0.12)
        return payload

    def close(self):
        self.session.close()


def ingest(seasons: list[int], weeks: list[int], limit_games: int | None = None, cache: str | Path = "data/raw/cfb", api_key: str | None = None, season_type: str = "regular") -> pd.DataFrame:
    if season_type not in ("regular", "postseason"):
        raise ValueError("season_type must be regular or postseason")
    key = api_key or os.environ.get("CFBD_API_KEY")
    client = CFBDClient(key or "", cache)
    results = []
    encountered = 0
    try:
        for year in sorted(set(seasons)):
            for week in sorted(set(weeks)):
                if week < 0 or week > 25:
                    raise ValueError("CFB week must be 0-25")
                params = {"year": year, "week": week, "classification": "fbs", "seasonType": season_type}
                games = client.get("games", params, f"games_{season_type}_{year}_{week}")
                selected = sorted((g for g in games if g.get("completed") and g.get("id") is not None), key=lambda g: g["id"])
                if limit_games is not None:
                    selected = selected[:max(0, limit_games - encountered)]
                if not selected:
                    continue
                # CFBD requires year+week for historical plays, not gameId.
                plays = client.get("plays", params, f"plays_{season_type}_{year}_{week}")
                wps = {}
                for game in selected:
                    gid = int(game["id"])
                    arr = client.get("metrics/wp", {"gameId": gid}, f"wp_{gid}")
                    if not arr:
                        LOG.warning("CFBD WP not available for game %s", gid)
                        continue
                    wps[gid] = arr
                frame = wp_frame(selected, plays, wps)
                if not frame.empty:
                    results.append(frame)
                encountered += len(selected)
                LOG.info("CFB %s week %s: %s completed games, %s valid plays", year, week, len(selected), len(frame))
                if limit_games is not None and encountered >= limit_games:
                    break
            if limit_games is not None and encountered >= limit_games:
                break
    finally:
        client.close()
    if not results:
        raise ValueError("No CFB games with play-level WP found; check API coverage, weeks, and token")
    return normalize(pd.concat(results, ignore_index=True))
