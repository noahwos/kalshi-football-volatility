"""Held-out ranking evaluation and deliberately simplified WP-quote trading proxy."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


def toy_trade(row: pd.Series, target: float = .10, stop: float = .08, cost: float = .02) -> dict:
    """Trade side is chosen at checkpoint using past 10-play trend only."""
    path = json.loads(row["future_path"]) if isinstance(row["future_path"], str) else row["future_path"]
    if len(path) < 2:
        raise ValueError("Trading proxy needs at least one future quote")
    past_change = float(row["wp_change_10"])
    if past_change == 0:
        return {"pnl_proxy": 0., "trade_status": "no_signal", "exit_play": 0, "side": "none"}
    # Buy whichever outcome lost probability in the last 10 plays.
    side = "home" if past_change < 0 else "away"
    prices = path if side == "home" else [1-p for p in path]
    entry = float(prices[0])
    exit_price = float(prices[-1])
    status = "time_exit"
    exit_play = len(prices) - 1
    for i, price in enumerate(prices[1:], 1):
        if price - entry >= target:
            exit_price, status, exit_play = float(price), "target", i
            break
        if price - entry <= -stop:
            exit_price, status, exit_play = float(price), "stop", i
            break
    return {"pnl_proxy": float(exit_price - entry - cost), "trade_status": status, "exit_play": exit_play, "side": side}


def summarize(rows: pd.DataFrame) -> dict:
    if rows.empty:
        return {"decisions": 0, "games": 0}
    pnl = rows.pnl_proxy.to_numpy(dtype=float)
    gross = float(np.sum(pnl))
    cumulative = np.cumsum(pnl)
    highwater = np.maximum.accumulate(np.r_[0, cumulative])
    max_drawdown = float(np.max(highwater - np.r_[0, cumulative]))
    return {
        "decisions": len(rows), "games": int(rows.game_id.nunique()),
        "mean_actual_future_range": float(rows.future_range.mean()),
        "mean_predicted_future_range": float(rows.predicted_future_range.mean()),
        "mean_pnl_proxy_per_decision": float(pnl.mean()),
        "sum_pnl_proxy_unit_stake_each": gross,
        "positive_proxy_rate": float(np.mean(pnl > 0)),
        "max_drawdown_proxy_unit_stake": max_drawdown,
        "target_exits": int((rows.trade_status == "target").sum()),
        "stop_exits": int((rows.trade_status == "stop").sum()),
        "time_exits": int((rows.trade_status == "time_exit").sum()),
        "no_signal": int((rows.trade_status == "no_signal").sum()),
    }


def backtest(predictions: pd.DataFrame, *, top_fraction: float = .25, target: float = .10, stop: float = .08, cost: float = .02) -> dict:
    required = {"league", "game_id", "season", "checkpoint", "predicted_future_range", "future_range", "future_path", "wp_change_10", "train_mean_baseline"}
    if missing := required - set(predictions):
        raise ValueError(f"Missing predictions columns: {sorted(missing)}")
    if not 0 < top_fraction <= 1 or min(target, stop) <= 0 or cost < 0:
        raise ValueError("Invalid backtest trade parameters")
    if predictions.league.nunique() != 1 or predictions.season.nunique() != 1:
        raise ValueError("Backtest accepts one held-out league and season only")
    table = predictions.copy()
    for name in ["predicted_future_range", "future_range", "wp_change_10", "train_mean_baseline"]:
        table[name] = pd.to_numeric(table[name], errors="raise")
    table = table.sort_values(["game_date", "game_id", "checkpoint"], na_position="last").reset_index(drop=True) if "game_date" in table else table.sort_values(["game_id", "checkpoint"]).reset_index(drop=True)
    trades = table.apply(lambda r: pd.Series(toy_trade(r, target, stop, cost)), axis=1)
    table = pd.concat([table, trades], axis=1)
    n = max(1, math.ceil(len(table)*top_fraction))
    top = table.sort_values("predicted_future_range", ascending=False, kind="stable").head(n)
    # Keep trade P&L aggregation in timestamp order to report a meaningful (still toy) drawdown.
    top = top.sort_values(["game_date", "game_id", "checkpoint"] if "game_date" in top else ["game_id", "checkpoint"], na_position="last")
    corr = table.predicted_future_range.corr(table.future_range, method="spearman")
    result = {
        "league": table.league.iloc[0], "holdout_season": int(table.season.iloc[0]),
        "selection": {"fraction": top_fraction, "basis": "predicted next-40-play WP range"},
        "ranking": {
            "spearman": float(corr) if pd.notna(corr) else None,
            "top_mean_future_range": float(top.future_range.mean()),
            "all_mean_future_range": float(table.future_range.mean()),
            "top_quartile_range_lift": float(top.future_range.mean()/table.future_range.mean()) if table.future_range.mean() > 0 else None,
            "holdout_mae": float(np.mean(np.abs(table.future_range - table.predicted_future_range))),
            "baseline_mae": float(np.mean(np.abs(table.future_range - table.train_mean_baseline))),
        },
        "trade_parameters": {"target": target, "stop": stop, "roundtrip_cost": cost},
        "all_decisions": summarize(table), "selected_decisions": summarize(top),
        "disclaimer": "WP model trajectory proxy, not executable Kalshi prices/fills/P&L. Selection and labeling use holdout future paths only for evaluation.",
    }
    return result


def save_report(report: dict, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2))
