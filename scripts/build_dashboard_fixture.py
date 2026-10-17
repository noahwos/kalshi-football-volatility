"""Build fabricated model outputs for browser tests in a NEW temporary directory.

This is a test fixture generator, not a source of research results.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from football_volatility.dashboard import build_dashboard
from football_volatility.demo import make_demo
from football_volatility.features import build_features
from football_volatility.model import train


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    root = args.workspace
    root.mkdir(parents=True, exist_ok=False)  # Never overwrite a real workspace.
    (root / "data").mkdir()
    plays = make_demo(games_per_season=28)
    for league, model, filename in (
        ("nfl", "nfl", "nfl_2023_2025.csv"),
        ("cfb", "cfbfastr", "cfbfastr_2023_2025.csv"),
    ):
        observed = plays.loc[plays.league.eq(league)]
        observed.to_csv(root / "data" / filename, index=False)
        train(build_features(observed), league, 2025, root / "models" / model)
    target = build_dashboard(root, root / "dashboard.html")
    print(f"SYNTHETIC browser-test fixture: {target}")


if __name__ == "__main__":
    main()
