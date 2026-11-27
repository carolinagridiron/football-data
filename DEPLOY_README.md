# Carolina Gridiron V3 — ONE production deployment

## What this package is
The minimal production file set. It does NOT change Google Sheets, Blogger, or any archive files. The historical ID lookup remains deferred.

## Before uploading
1. In GitHub main, save the current `.github/workflows/collect.yml` as a local backup, or record its last good commit SHA.
2. Verify that `main` already contains `archive_collector.py`, `collector.py`, `publish_game_details.py`, `incremental_details.py`, and the 2026 archive. Do not replace them.
3. Keep the production Google Sheet `LIVE / YES` for 2026. Do not perform spreadsheet rollover now.

## Upload ONCE to main
Upload the files in this ZIP preserving their relative paths. Replace ONLY `.github/workflows/collect.yml`; add or update the eight root files and two test files listed in the ZIP. Commit as one commit: `Deploy Carolina Gridiron V3 season-aware collection`.

Do NOT add a second scheduled workflow, and do NOT merge the entire test branch.

## One verification
From GitHub Actions, manually run **Update NCAA scores**. Verify: score stage collects 2026 games; scoreboard commit succeeds or has no diff; season-aware detail step completes or emits a visible warning; GitHub Pages `public/nc-scores.json` retains `schema_version: 1`, `season: 2026`, nonempty `games`; Blogger still loads; the Google Sheets queue refresh has no season mismatch. Then check one scheduled run.

## Important behavior
- Eastern-time schedule retained. January 2027 belongs to the 2026 season.
- Offseason or unverified 2027: no replacement score feed and no detail writes.
- If the score stage fails, it does not commit a new feed. If detail enrichment fails, scores can still publish.
- 2027 NCAA week anchor and 2027 school inventory must be verified before activation.
- Google Sheets remains 2026 until the separate, already-tested annual archive/rollover operation is explicitly approved.

## Rollback
If the workflow fails or public feed becomes invalid, restore the previous `.github/workflows/collect.yml` and the previously working code from Git history (revert the single deployment commit), then run `Update NCAA scores` manually. Never delete `public/archive/` or Google Sheets data. Inspect failure logs before retrying.

## Known limitations
This is not a guarantee of future NCAA API availability. It has passed offline tests; production live execution is verified only after the one manual run. The current 2026 Google Sheets script is still season-specific; its 2027 activation is a separate annual editorial decision.
