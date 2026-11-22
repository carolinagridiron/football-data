# Carolina Gridiron NCAA Score Collector

A **read-only prototype** that retrieves NCAA football scoreboard data for FBS, FCS, Division II, and Division III from the unofficial [henrygd/ncaa-api](https://github.com/henrygd/ncaa-api) public service. It produces `public/nc-scores.json` for later comparison against Carolina Gridiron's editorial Google Sheets. It does **not** modify Google Sheets or Blogger.

## Quick setup (no coding needed)

1. Create a new **public** GitHub repository named `football-data` under `carolinagridiron` (or another name you prefer).
2. Upload all files and folders in this package, including `.github/workflows/collect.yml`, to the root of the new repository. The `.github` directory is hidden on some computers; ensure it is uploaded.
3. In the repository's **Actions** tab, enable workflows if prompted, open **Update NCAA scores**, and click **Run workflow**.
4. Open the workflow run and check that it succeeds. It will commit `public/nc-scores.json` to the repository.
5. To make the feed accessible via GitHub Pages, go to **Settings → Pages**, choose **Deploy from a branch**, branch `main`, folder `/ (root)`, then save. The feed URL should be `https://carolinagridiron.github.io/football-data/public/nc-scores.json` if the repo is named `football-data`.
6. Do **not** connect the feed to Blogger until we compare its results to your existing scoreboard.

## What is automated?

The workflow runs every two hours Thursday through Monday (UTC), subject to GitHub Actions scheduling delays. It queries the estimated NCAA football week plus its adjacent weeks for each division. This is **periodically updated**, not guaranteed real-time. On days without football, requests are still made; adjust the schedule after testing.

## Known limitations and checks

- The football API uses `YYYY/WK`, not calendar dates. The 2026 week anchor (`2026-11-21` = week 12) was verified from a user-supplied NCAA response. **Update `config.json` for each new season**; postseason weeks must be verified separately.
- The list of NC school slugs is a **starter list** and must be audited against your complete scoreboard. Some NCAA slugs may differ; edit `nc_school_slugs` to match the NCAA `names.seo` values.
- The output includes only games involving at least one listed NC school. All-source game counts are included for diagnostics, but full national games are not published.
- A successful but incomplete response is not automatically distinguishable from a legitimate small week. Before production use, add checks for unexpectedly shrinking data, game IDs, and freshness.
- The `currentPeriod` and `contestClock` fields exist in completed-game samples; **live update quality is not yet verified**.
- The public demonstration API may be rate-limited, delayed, unavailable, or changed without notice. Verify data reuse permissions and consider self-hosting for production.
- The workflow writes a new commit even if only `generated_at_utc` changes. Reduce cadence or use a separate publishing branch if history grows excessively.
- This is **not** a live source for bowl schedules or editorial corrections. Your existing Sheets remain authoritative.

## Run locally (optional)

```bash
python collector.py --date 2026-11-21
python -m unittest discover -s tests -v
```

No third-party Python packages or API keys are required.
