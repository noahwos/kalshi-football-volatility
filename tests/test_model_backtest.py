import json

import pandas as pd
import pytest

from football_volatility.backtest import backtest, toy_trade
from football_volatility.demo import make_demo
from football_volatility.features import build_features
from football_volatility.model import score, train


def test_train_and_backtest_separate_models(tmp_path):
    frame = build_features(make_demo(games_per_season=12), horizon=40)
    for league in ("nfl", "cfb"):
        model_dir = tmp_path / league
        report = train(frame, league, 2025, model_dir)
        assert report["league"] == league
        assert report["training_games"] == 36
        assert (model_dir / "model.joblib").exists()
        predictions = pd.read_csv(model_dir / "holdout_predictions.csv")
        assert all(predictions.league == league)
        assert predictions.predicted_future_range.between(0, 1).all()
        bt = backtest(predictions)
        assert bt["selected_decisions"]["decisions"] == 6
        assert bt["all_decisions"]["decisions"] == 24
        scores = score(frame.loc[(frame.league == league) & (frame.season == 2025)], model_dir)
        assert scores.predicted_future_range.between(0, 1).all()
    with pytest.raises(ValueError, match="Cannot score"):
        score(frame.loc[frame.league == "cfb"], tmp_path / "nfl")


def test_future_trade_exits_first_target():
    row = pd.Series({"future_path": json.dumps([.50, .55, .61, .10]), "wp_change_10": -.05})
    result = toy_trade(row, cost=.02)
    assert result["side"] == "home"
    assert result["trade_status"] == "target"
    assert result["exit_play"] == 2
    assert result["pnl_proxy"] == pytest.approx(.09)


def test_future_trade_cannot_pick_side_with_future():
    row = pd.Series({"future_path": json.dumps([.50, .45, .42, .60]), "wp_change_10": .02})
    result = toy_trade(row, target=.1, stop=.08, cost=.02)
    assert result["side"] == "away"
    assert result["trade_status"] == "stop"
    assert result["pnl_proxy"] == pytest.approx(-.12)


def test_backtest_rejects_mixed_leagues():
    x = pd.DataFrame([{"league": "nfl", "season": 2025}, {"league": "cfb", "season": 2025}])
    with pytest.raises(ValueError):
        backtest(x)


@pytest.mark.parametrize("path", [
    [.5, float("nan")], [.5, float("inf")], [.5, 1.1], [[.5, .6]], [.5],
])
def test_trade_rejects_invalid_probability_paths(path):
    with pytest.raises(ValueError, match="path"):
        toy_trade(pd.Series({"future_path": json.dumps(path), "wp_change_10": -.05}))


@pytest.mark.parametrize("parameter", ["target", "stop", "cost"])
def test_trade_rejects_nonfinite_parameters(parameter):
    row = pd.Series({"future_path": "[0.5, 0.6]", "wp_change_10": -.05})
    with pytest.raises(ValueError, match="finite"):
        toy_trade(row, **{parameter: float("nan")})


def predictions_fixture():
    return pd.DataFrame([{
        "league": "nfl", "game_id": "one", "season": 2025, "checkpoint": 40,
        "predicted_future_range": .1, "future_range": .1, "future_path": "[0.5, 0.6]",
        "wp_change_10": -.05, "train_mean_baseline": .1, "horizon": 1,
    }, {
        "league": "nfl", "game_id": "two", "season": 2025, "checkpoint": 40,
        "predicted_future_range": .2, "future_range": .2, "future_path": "[0.5, 0.7]",
        "wp_change_10": .05, "train_mean_baseline": .1, "horizon": 1,
    }])


@pytest.mark.parametrize("column", ["predicted_future_range", "future_range", "wp_change_10", "train_mean_baseline"])
def test_backtest_rejects_nonfinite_predictions(column):
    predictions = predictions_fixture()
    predictions.loc[0, column] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        backtest(predictions)


def test_backtest_reports_actual_horizon_and_rejects_mixed_paths():
    predictions = predictions_fixture()
    assert backtest(predictions)["selection"]["basis"] == "predicted next-1-play WP range"
    predictions.loc[0, "future_path"] = "[0.5, 0.6, 0.7]"
    with pytest.raises(ValueError, match="horizon"):
        backtest(predictions)
