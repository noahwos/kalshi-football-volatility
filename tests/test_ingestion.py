import pandas as pd
import pytest

from football_volatility.data.cfb import wp_frame
from football_volatility.data.nfl import nfl_frame
from football_volatility.schema import normalize


def test_nfl_uses_in_game_scores_not_final_scores():
    raw = pd.DataFrame([{"season": 2024, "game_id": "2024_01_A_B", "play_id": 1, "home_wp": .4,
                         "home_score": 41, "away_score": 13, "total_home_score": 0, "total_away_score": 0},
                        {"season": 2024, "game_id": "2024_01_A_B", "play_id": 2, "home_wp": .5,
                         "home_score": 41, "away_score": 13, "total_home_score": 7, "total_away_score": 0}])
    normalized = nfl_frame(raw)
    assert normalized.home_score.tolist() == [0, 7]
    assert normalized.away_score.tolist() == [0, 0]


def test_cfb_joins_win_probabilities_and_play_time():
    games = [{"id": 9, "completed": True, "season": 2024, "week": 1, "homeTeam": "H", "awayTeam": "A"}]
    plays = [{"gameId": 9, "id": "p1", "period": 1, "clock": {"minutes": 8, "seconds": 5}}]
    wp = {9: [{"playId": "p1", "playNumber": 1, "homeWinProbability": .6, "homeScore": 3, "awayScore": 0}]}
    result = wp_frame(games, plays, wp)
    assert len(result) == 1
    assert result.seconds_remaining.iloc[0] == 3185
    assert result.home_wp.iloc[0] == .6


def test_normalization_removes_invalid_probabilities_duplicates_and_sorts():
    rows = pd.DataFrame([{"league": "NFL", "season": 2023, "game_id": "x", "play_number": 2, "home_wp": .6, "home_score": 7, "away_score": 0},
                         {"league": "NFL", "season": 2023, "game_id": "x", "play_number": 1, "home_wp": .5, "home_score": 0, "away_score": 0},
                         {"league": "NFL", "season": 2023, "game_id": "x", "play_number": 1, "home_wp": .7, "home_score": 0, "away_score": 0},
                         {"league": "NFL", "season": 2023, "game_id": "x", "play_number": 3, "home_wp": 1.2, "home_score": 7, "away_score": 0}])
    clean = normalize(rows)
    assert clean.home_wp.tolist() == [.5, .6]
    assert clean.league.tolist() == ["nfl", "nfl"]


def test_invalid_league_fails():
    with pytest.raises(ValueError):
        normalize(pd.DataFrame([{"league": "soccer", "season": 2024, "game_id": "x", "play_number": 1, "home_wp": .5, "home_score": 0, "away_score": 0}]))
