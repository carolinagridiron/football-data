#!/usr/bin/env python3
"""V3.0B opt-in season-aware wrapper for the existing incremental detail engine.

This candidate does not alter the production collector, feed or workflow.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from season_policy import resolve, SeasonNotReady
from incremental_details_v30b import run, publish_changed
from archive_collector import atomic_json


def plan(feed, config, day, archive):
    season, settings = resolve(day, config)
    if int(feed.get('season', -1)) != season:
        raise SeasonNotReady(f'Feed season {feed.get("season")} does not match verified operating season {season}')
    if archive and int(archive.get('season', -1)) != season:
        raise SeasonNotReady('Archive season mismatch')
    return season, settings


def execute(feed_path, config_path, archive_root, details_root, day, write=False,
            window=3, limit=30, engine=run, publisher=publish_changed):
    feed = json.loads(Path(feed_path).read_text(encoding='utf-8'))
    config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    season, _ = resolve(day, config)
    archive_path = Path(archive_root) / str(season) / 'archive.json'
    archive = json.loads(archive_path.read_text(encoding='utf-8')) if archive_path.exists() else {
        'schema_version': 1, 'season': season, 'games': {}, 'details': {}, 'detail_tracking': {}}
    plan(feed, config, day, archive)
    result, report = engine(feed, archive, day, window=window, limit=limit)
    if report.get('conflicts') or report.get('detail_errors'):
        raise RuntimeError('Review required: detail errors or archive conflicts; no files written')
    publication = publisher(result, Path(details_root), write=False)
    report['publication'] = publication
    if publication.get('held'):
        raise RuntimeError('Review required: unsafe published detail changes; no files written')
    if write:
        # All validations are complete before any disk writes.
        atomic_json(archive_path, result)
        publisher(result, Path(details_root), write=True)
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--date', help='YYYY-MM-DD in America/New_York (for testing)')
    p.add_argument('--config', default='config_v3.json')
    p.add_argument('--feed', default='public/nc-scores.json')
    p.add_argument('--archive-root', default='public/archive')
    p.add_argument('--details-root', default='public/game-details')
    p.add_argument('--window-days', type=int, default=3)
    p.add_argument('--detail-limit', type=int, default=30)
    p.add_argument('--write', action='store_true')
    a = p.parse_args()
    day = dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(ZoneInfo('America/New_York')).date()
    report = execute(a.feed, a.config, a.archive_root, a.details_root, day, a.write,
                     a.window_days, a.detail_limit)
    print(json.dumps(report, indent=2))
    print('WRITE ENABLED' if a.write else 'READ ONLY: no files changed')

if __name__ == '__main__':
    main()
