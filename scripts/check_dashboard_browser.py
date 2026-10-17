"""Exercise the generated dashboard in Chromium, including real CSV downloads.

Install .[browser] and run playwright install chromium (or use a system Chromium).
Run: python scripts/check_dashboard_browser.py reports/dashboard.html
The temporary loopback server is only used for internal browser validation.
"""
from __future__ import annotations

import argparse
import csv
import functools
import http.server
import json
import shutil
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dashboard", type=Path)
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    target = args.dashboard.resolve()
    html = target.read_text()
    payload = json.loads(html.split('<script type="application/json" id="dashboard-data">', 1)[1].split("</script>", 1)[0])

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_args):
            pass

    handler = functools.partial(QuietHandler, directory=str(target.parent))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright, tempfile.TemporaryDirectory() as temporary:
            executable = shutil.which("chromium") or shutil.which("google-chrome")
            browser = playwright.chromium.launch(executable_path=executable, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context(viewport={"width": 1440, "height": 1100}, accept_downloads=True)
            page = context.new_page()
            errors, remote_requests = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: remote_requests.append(request.url) if request.url.startswith("http") and not request.url.startswith("http://127.0.0.1:") else None)
            page.goto(f"http://127.0.0.1:{server.server_port}/{target.name}")
            expect(page.get_by_role("heading", name="Find the room to move.")).to_be_visible()
            for dataset in payload["datasets"]:
                page.locator(f'[data-league="{dataset["id"]}"]').click()
                for checkpoint in (40, 80):
                    page.locator(f'[data-checkpoint="{checkpoint}"]').click()
                    games = [game for game in dataset["games"] if str(checkpoint) in game["snapshots"]]
                    expect(page.locator("#result-count")).to_have_text(f"{len(games):,} games")
                    if not games:
                        continue
                    expect(page.locator("#future-path")).to_have_count(0)
                    expected = max(game["snapshots"][str(checkpoint)]["forecast"] for game in games)
                    assert abs(float(page.locator("#rankings-body .forecast").first.inner_text()) - expected) <= .051
                    page.locator('[data-sort="forecast"]').click()
                    expected = min(game["snapshots"][str(checkpoint)]["forecast"] for game in games)
                    assert abs(float(page.locator("#rankings-body .forecast").first.inner_text()) - expected) <= .051
                    page.locator('[data-sort="forecast"]').click()
                    if len(games) > 25:
                        page.get_by_role("button", name="Next page", exact=True).click()
                        expect(page.locator("#page-summary")).to_contain_text("26–")
                        page.get_by_role("button", name="Previous page", exact=True).click()
                    game = games[0]
                    page.get_by_role("searchbox").fill(game["id"])
                    expect(page.locator("#result-count")).to_have_text("1 game")
                    page.get_by_role("button", name=f'View {game["awayName"]} at {game["homeName"]}', exact=True).click()
                    expect(page.locator("#home-name")).to_have_text(game["homeName"])
                    assert page.locator("#observed-path").get_attribute("d").count("L") == checkpoint - 1
                    with page.expect_download() as download:
                        page.get_by_role("button", name="Export CSV", exact=True).click()
                    filename = Path(temporary) / "rankings.csv"
                    download.value.save_as(filename)
                    with filename.open(encoding="utf-8-sig", newline="") as handle:
                        rows = list(csv.DictReader(handle))
                    assert len(rows) == 1 and rows[0]["game_id"] == game["id"]
                    assert "observed_future_range_pp" not in rows[0]
                    page.get_by_role("checkbox", name="Reveal later observations").check()
                    expect(page.locator("#future-path")).to_have_count(1)
                    expect(page.locator("#actual-range")).to_be_visible()
                    with page.expect_download() as download:
                        page.get_by_role("button", name="Export CSV", exact=True).click()
                    download.value.save_as(filename)
                    with filename.open(encoding="utf-8-sig", newline="") as handle:
                        rows = list(csv.DictReader(handle))
                    assert abs(float(rows[0]["observed_future_range_pp"]) - game["snapshots"][str(checkpoint)]["actual"]) < 1e-6
                    page.get_by_role("checkbox", name="Reveal later observations").uncheck()
                    page.get_by_role("searchbox").fill("no-such-team-0000")
                    expect(page.locator("#empty")).to_be_visible()
                    expect(page.get_by_role("button", name="Export CSV", exact=True)).to_be_disabled()
                    page.get_by_role("searchbox").fill("")
                    print(f'{dataset["label"]}, checkpoint {checkpoint}: {len(games)} games; filters, sort, selection, chart and CSV passed')
            page.get_by_role("button", name="How to read this").click()
            expect(page.get_by_role("dialog")).to_be_visible()
            page.get_by_role("button", name="Got it").click()
            expect(page.get_by_role("dialog")).not_to_be_visible()
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.locator(f'[data-league="{payload["datasets"][0]["id"]}"]').click()
            page.locator('[data-checkpoint="40"]').click()
            page.get_by_role("button", name="View ", exact=False).first.click()
            expect(page.locator("#detail-panel")).to_be_visible()
            if args.screenshot:
                page.screenshot(path=str(args.screenshot), full_page=True)
            assert not errors, errors
            assert not remote_requests, remote_requests
            print("Mobile layout, help dialog, zero JavaScript errors and zero external requests passed")
            context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
