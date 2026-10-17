"""Deterministic fabricated data for offline smoke tests; not real football outcomes."""
import numpy as np
import pandas as pd

from football_volatility.schema import normalize


def make_demo(games_per_season: int = 14, plays_per_game: int = 145, seed: int = 101) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for league in ("nfl", "cfb"):
        for season in (2022, 2023, 2024, 2025):
            for idx in range(games_per_season):
                p = rng.uniform(.3, .7)
                home_score = away_score = 0
                trend = rng.normal(0, .01)
                for n in range(1, plays_per_game+1):
                    if n % 12 == 0:
                        if rng.random() < .5: home_score += 7
                        else: away_score += 7
                    shock = rng.normal(0, .026 if league == "nfl" else .034)
                    p = float(np.clip(p + trend + shock, .005, .995))
                    rows.append({"league": league, "season": season, "week": idx//4+1,
                                 "game_id": f"{league}_{season}_{idx:03d}",
                                 "game_date": f"{season}-10-{idx+1:02d}",
                                 "home_team": f"Home{idx}", "away_team": f"Away{idx}",
                                 "play_id": n, "play_number": n, "period": min(4, 1+n//37),
                                 "seconds_remaining": max(0,3600-n*25), "home_score": home_score,
                                 "away_score": away_score, "home_wp": p,
                                 "down": (n % 4)+1, "distance": 10})
    return normalize(pd.DataFrame(rows))
