# Backtest protocol and limitations

**Primary test: out-of-sample forecasting/ranking, not trade profitability.** Split seasons chronologically: train on all records strictly earlier than `--test-season`, hold out only that later season. Never train on games or snapshots from the holdout season, and don't tune hyperparameters using the reported holdout. For model selection, use expanding-window backtests and reserve a final untouched season.

Ranking metrics: regression MAE, RMSE vs training-mean baseline, top-quartile future-range lift against all holdout decisions and Spearman rank correlation. Sampling units are *games*: multiple checkpoints from the same game are correlated, and naive standard errors would be misleading. The toy simulation uses the same held-out rows.

Toy rule: enter on the side whose estimated win probability fell over the previous 10 plays (a purely mechanical contrarian direction). `target=+0.10`, `stop=-0.08`, `cost=0.02` in probability-point terms, with exit checked every subsequent play through next 40 plays. Hindsight is only used to determine when the already-specified exit conditions would have triggered. `pnl_proxy` is the difference in a *probability model*, not a realized trading return. It intentionally omits variable prices, transaction fees, depth, fill rates, halted markets, limit-order queue priority, revisions and execution latency. No profitable signal is proven by these outputs.

Risks: models can be overconfident and mechanically clipped at 0/1. Live feed latency, in-game Kalshi price behavior, official game stat corrections, FCS coverage, cross-source team identifiers and probability model version drift all require validation. The metric `future_range` overstates captures by assuming perfect trade timing; don't describe it as yield.

Before deployment, align tick-level Kalshi quotes by as-of timestamps (no nearest future tick), account for spread, commissions and skipped fills, and re-run a walk-forward test. Track return distribution, risk-adjusted net returns, max drawdown, exposure, and regime calibration. Don't use this tool to place orders.
