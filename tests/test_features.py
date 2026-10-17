import pandas as pd
import pytest

from football_volatility.features import build_features


def game(n=100, *, future_up=False):
    records = []
    for i in range(n):
        # First 40 plays always the same, future paths differ.
        p = .5 if i < 40 else (.9 if future_up else .1)
        records.append({"league": "nfl", "season": 2023, "game_id": "one", "play_number": i+1,
                        "home_wp": p, "home_score": 7 if i >= 40 else 0, "away_score": 0})
    return pd.DataFrame(records)


def test_snapshot_is_lookahead_safe():
    left = build_features(game(future_up=True), checkpoints=(40,), horizon=40)
    right = build_features(game(future_up=False), checkpoints=(40,), horizon=40)
    snapshot_cols = [c for c in left if c not in {"future_range", "future_total_variation", "future_large_moves", "future_path"}]
    pd.testing.assert_frame_equal(left[snapshot_cols], right[snapshot_cols])
    assert left.future_range.iloc[0] == pytest.approx(.4)
    assert right.future_range.iloc[0] == pytest.approx(.4)
    assert left.future_path.iloc[0] != right.future_path.iloc[0]


def test_incomplete_future_window_excluded():
    with pytest.raises(ValueError, match="No eligible"):
        build_features(game(79), checkpoints=(40,), horizon=40)
    assert len(build_features(game(79), checkpoints=(40,), labeled=False)) == 1


def test_checkpoint_excludes_unobserved_plays():
    left = build_features(game(40), checkpoints=(40,), labeled=False)
    right = build_features(game(110), checkpoints=(40,), labeled=False)
    pd.testing.assert_frame_equal(left, right)


def test_input_limits_checked():
    with pytest.raises(ValueError):
        build_features(game(), checkpoints=(10,))
