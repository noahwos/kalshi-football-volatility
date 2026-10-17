"""Simple research CLI: fva ingest-nfl/ingest-cfb/features/train/backtest/score/demo."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from football_volatility.backtest import backtest, save_report
from football_volatility.demo import make_demo
from football_volatility.features import build_features
from football_volatility.model import score, train
from football_volatility.schema import read_csv, save_csv


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="fva", description="NFL/CFB probability-volatility analyzer")
    sub = parser.add_subparsers(dest="command", required=True)
    nfl = sub.add_parser("ingest-nfl", help="Fetch and normalize nflverse PBP")
    nfl.add_argument("--seasons", nargs="+", type=int, required=True)
    nfl.add_argument("--format", choices=["parquet", "csv"], default="parquet")
    nfl.add_argument("--cache", default="data/raw/nfl")
    nfl.add_argument("--output", required=True)
    cfb = sub.add_parser("ingest-cfb", help="Fetch CFBD games, plays and WP with token")
    cfb.add_argument("--seasons", nargs="+", type=int, required=True)
    cfb.add_argument("--weeks", nargs="+", type=int, required=True)
    cfb.add_argument("--limit-games", type=int)
    cfb.add_argument("--season-type", choices=["regular", "postseason"], default="regular")
    cfb.add_argument("--cache", default="data/raw/cfb")
    cfb.add_argument("--output", required=True)
    feats = sub.add_parser("features", help="Create past-only features and future labels")
    feats.add_argument("--input", required=True)
    feats.add_argument("--output", required=True)
    feats.add_argument("--checkpoints", nargs="+", type=int, default=[40, 80])
    feats.add_argument("--horizon", type=int, default=40)
    training = sub.add_parser("train", help="Fit a league model and evaluate later season")
    training.add_argument("--input", required=True)
    training.add_argument("--league", choices=["nfl", "cfb"], required=True)
    training.add_argument("--test-season", type=int, required=True)
    training.add_argument("--model-dir", required=True)
    test = sub.add_parser("backtest", help="Backtest held-out predictions using model WP proxies")
    test.add_argument("--predictions", required=True)
    test.add_argument("--output", required=True)
    test.add_argument("--top-fraction", type=float, default=.25)
    test.add_argument("--target", type=float, default=.10)
    test.add_argument("--stop", type=float, default=.08)
    test.add_argument("--cost", type=float, default=.02)
    scoring = sub.add_parser("score", help="Rank observed games at a fixed play checkpoint")
    scoring.add_argument("--input", required=True)
    scoring.add_argument("--model-dir", required=True)
    scoring.add_argument("--checkpoint", type=int, choices=[40, 80], required=True)
    scoring.add_argument("--league", choices=["nfl", "cfb"], help="Optional explicit league filter; defaults to league of model")
    scoring.add_argument("--output", required=True)
    demo = sub.add_parser("demo", help="Generate synthetic games for smoke tests ONLY")
    demo.add_argument("--output", required=True)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.command == "ingest-nfl":
        from football_volatility.data.nfl import ingest
        result = ingest(args.seasons, args.cache, args.format)
        save_csv(result, args.output)
        print(f"NFL: {len(result)} plays from {result.game_id.nunique()} games -> {args.output}")
    elif args.command == "ingest-cfb":
        from football_volatility.data.cfb import ingest
        result = ingest(args.seasons, args.weeks, args.limit_games, args.cache, season_type=args.season_type)
        save_csv(result, args.output)
        print(f"CFB: {len(result)} plays from {result.game_id.nunique()} games -> {args.output}")
    elif args.command == "features":
        result = build_features(read_csv(args.input), checkpoints=tuple(args.checkpoints), horizon=args.horizon)
        save_csv(result, args.output)
        print(f"{len(result)} labeled snapshots -> {args.output}")
    elif args.command == "train":
        report = train(pd.read_csv(args.input, dtype={"game_id": str}), args.league, args.test_season, args.model_dir)
        print(json.dumps(report, indent=2))
    elif args.command == "backtest":
        report = backtest(pd.read_csv(args.predictions, dtype={"game_id": str}), top_fraction=args.top_fraction, target=args.target, stop=args.stop, cost=args.cost)
        save_report(report, args.output)
        print(json.dumps(report, indent=2))
    elif args.command == "score":
        # No future observation used: build_features(..., labeled=False) only takes the chosen prefix.
        import joblib
        artifact = joblib.load(Path(args.model_dir) / "model.joblib")
        league = args.league or artifact["league"]
        if league != artifact["league"]:
            raise ValueError("League filter must match the stored model league")
        observed = read_csv(args.input)
        observed = observed.loc[observed.league == league]
        feats = build_features(observed, checkpoints=(args.checkpoint,), labeled=False)
        result = score(feats, args.model_dir)
        save_csv(result, args.output)
        print(result.head(20).to_string(index=False))
    elif args.command == "demo":
        result = make_demo()
        save_csv(result, args.output)
        print(f"Created {len(result)} SYNTHETIC plays -> {args.output}")


if __name__ == "__main__":
    main()
