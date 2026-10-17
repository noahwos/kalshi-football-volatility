import pandas as pd
import pytest

from football_volatility.data.cfbfastr import cfbfastr_frame, ingest


def archive_rows():
    base = {
        "season": 2024, "game_id": 10, "home_team": "H", "away_team": "A",
        "home_team_division": "fbs", "away_team_division": "fcs", "completed": True,
        "period": 1, "clock_minutes": 8, "clock_seconds": 5, "play_type": "Rush",
        "home_wp_after": .1, "TimeSecsRem": 1385,
        # Final/drive-end information must not become snapshot scores.
        "home_points": 49, "away_points": 21, "drive_end_offense_score": 49,
    }
    return pd.DataFrame([
        {**base, "game_play_number": 1, "play_number": 1, "pos_team": "H", "def_pos_team": "A",
         "pos_team_score": 7, "def_pos_team_score": 0, "home_wp_before": .6},
        {**base, "game_play_number": 2, "play_number": 1, "pos_team": "A", "def_pos_team": "H",
         "pos_team_score": 3, "def_pos_team_score": 7, "home_wp_before": .55},
    ])


def test_public_archive_aligns_pre_play_wp_with_prior_in_game_scores():
    result = cfbfastr_frame(archive_rows())
    assert result.home_wp.tolist() == [.6, .55]
    assert result.home_score.tolist() == [0, 7]
    assert result.away_score.tolist() == [0, 0]
    assert result.play_number.tolist() == [1, 2]  # not per-drive play_number
    assert result.seconds_remaining.tolist() == [3185, 3185]


def test_public_archive_excludes_unfinished_non_fbs_and_unmatched_teams():
    rows = archive_rows().iloc[[0]].copy()
    unfinished = rows.assign(game_id=20, completed=False)
    non_fbs = rows.assign(game_id=30, home_team_division="fcs")
    unknown = rows.assign(game_id=40, pos_team="Unknown")
    result = cfbfastr_frame(pd.concat([rows, unfinished, non_fbs, unknown], ignore_index=True))
    assert result.game_id.tolist() == ["10"]


def test_public_archive_does_not_invent_regulation_clock_in_overtime():
    rows = archive_rows().assign(period=5)
    assert cfbfastr_frame(rows).seconds_remaining.isna().all()


def test_public_archive_cached_ingestion_is_offline_and_repeatable(tmp_path, monkeypatch):
    archive_rows().to_parquet(tmp_path / "play_by_play_2024.parquet", index=False)

    def no_network(*args, **kwargs):
        pytest.fail("Cached archive should not make a network request")

    monkeypatch.setattr("requests.Session.get", no_network)
    first = ingest([2024, 2024], cache=tmp_path)
    pd.testing.assert_frame_equal(first, ingest([2024], cache=tmp_path))
    assert len(first) == 2


def test_public_archive_rejects_missing_schema_and_wrong_cached_season(tmp_path):
    with pytest.raises(ValueError, match="missing columns"):
        cfbfastr_frame(archive_rows().drop(columns="home_wp_before"))
    archive_rows().assign(season=2023).to_parquet(tmp_path / "play_by_play_2024.parquet")
    with pytest.raises(ValueError, match="unexpected seasons"):
        ingest([2024], cache=tmp_path)


def test_public_archive_reconstructs_order_when_source_counters_reset():
    rows = archive_rows()
    rows.loc[0, ["game_play_number", "clock_minutes"]] = [100, 14]
    rows.loc[1, ["game_play_number", "clock_minutes"]] = [1, 13]
    result = cfbfastr_frame(rows.iloc[::-1])
    assert result.home_wp.tolist() == [.6, .55]
    assert result.play_number.tolist() == [1, 2]
    assert result.home_score.tolist() == [0, 7]


def test_public_archive_excludes_administrative_events():
    rows = archive_rows()
    rows.loc[1, "play_type"] = "Timeout"
    assert len(cfbfastr_frame(rows)) == 1
