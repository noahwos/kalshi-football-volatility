import json

import pandas as pd
import pytest

from football_volatility.cli import main
from football_volatility.dashboard import build_dashboard
from football_volatility.demo import make_demo
from football_volatility.features import build_features


@pytest.fixture
def dashboard_workspace(tmp_path):
    plays = make_demo(games_per_season=1)
    plays = plays.loc[plays.league.eq("nfl")]
    predictions = build_features(plays)
    predictions = predictions.loc[predictions.season.eq(2025)].copy()
    predictions["predicted_future_range"] = .2
    predictions["train_mean_baseline"] = .3
    model = tmp_path / "models" / "nfl"
    model.mkdir(parents=True)
    (tmp_path / "data").mkdir()
    predictions.to_csv(model / "holdout_predictions.csv", index=False)
    plays.to_csv(tmp_path / "data" / "nfl_2023_2025.csv", index=False)
    (model / "evaluation.json").write_text(json.dumps({
        "holdout_season": 2025, "train_seasons": [2023, 2024],
        "mae": .1, "baseline_mae": .2,
    }))
    return tmp_path


def payload(path):
    html = path.read_text()
    start = '<script type="application/json" id="dashboard-data">'
    return json.loads(html.split(start, 1)[1].split("</script>", 1)[0])


def test_dashboard_contains_only_holdout_and_both_aligned_checkpoints(dashboard_workspace):
    target = build_dashboard(dashboard_workspace, dashboard_workspace / "dashboard.html")
    data = payload(target)
    assert data["unavailable"] == ["College football"]
    dataset = data["datasets"][0]
    assert dataset["evaluation"]["mae"] == 10
    assert len(dataset["games"]) == 1
    game = dataset["games"][0]
    assert game["season"] == 2025
    assert set(game["snapshots"]) == {"40", "80"}
    assert len(game["path"]) == 120
    for checkpoint in (40, 80):
        snapshot = game["snapshots"][str(checkpoint)]
        path = game["path"][checkpoint - 1:checkpoint + 40]
        assert snapshot["current"] == path[0]
        assert snapshot["actual"] == pytest.approx(max(path) - min(path), abs=1e-4)
        assert snapshot["forecast"] == 20


def test_dashboard_escapes_data_that_contains_script_delimiters(dashboard_workspace):
    path = dashboard_workspace / "models" / "nfl" / "holdout_predictions.csv"
    predictions = pd.read_csv(path)
    attack = '</script><img src=x onerror="alert(1)">'
    predictions["home_team"] = attack
    predictions.to_csv(path, index=False)
    target = build_dashboard(dashboard_workspace, dashboard_workspace / "dashboard.html")
    assert attack not in target.read_text()
    assert payload(target)["datasets"][0]["games"][0]["home"] == attack


@pytest.mark.parametrize("damage, message", [
    ("season", "chronological"), ("duplicate", "duplicate"),
    ("short", "full observation"), ("stale", "do not match"),
])
def test_dashboard_rejects_invalid_or_mismatched_artifacts(dashboard_workspace, damage, message):
    predictions_path = dashboard_workspace / "models" / "nfl" / "holdout_predictions.csv"
    plays_path = dashboard_workspace / "data" / "nfl_2023_2025.csv"
    predictions = pd.read_csv(predictions_path)
    if damage == "season":
        predictions["season"] = 2024
    elif damage == "duplicate":
        predictions = pd.concat([predictions, predictions.iloc[[0]]])
    elif damage == "stale":
        predictions["current_wp"] = 0
    else:
        plays = pd.read_csv(plays_path)
        plays = plays.loc[~(plays.season.eq(2025) & plays.play_number.ge(100))]
        plays.to_csv(plays_path, index=False)
    predictions.to_csv(predictions_path, index=False)
    with pytest.raises(ValueError, match=message):
        build_dashboard(dashboard_workspace, dashboard_workspace / "dashboard.html")


def test_dashboard_without_prepared_data_explains_setup(tmp_path):
    with pytest.raises(ValueError, match="README.md"):
        build_dashboard(tmp_path, tmp_path / "dashboard.html")


def test_dashboard_cli_writes_an_offline_artifact(dashboard_workspace, capsys):
    target = dashboard_workspace / "export" / "dashboard.html"
    main(["dashboard", "--workspace", str(dashboard_workspace), "--output", str(target)])
    assert target.is_file()
    assert "no server or API key" in capsys.readouterr().out
    html = target.read_text()
    assert '__DASHBOARD_DATA__' not in html
    assert '<script src=' not in html
    assert '<link rel="stylesheet"' not in html


def test_dashboard_cli_without_data_exits_with_actionable_message(tmp_path):
    with pytest.raises(SystemExit, match="Run the real-data workflow"):
        main(["dashboard", "--workspace", str(tmp_path)])
