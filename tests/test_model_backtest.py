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
