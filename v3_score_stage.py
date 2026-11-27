#!/usr/bin/env python3
"""Production-safe V3 score stage: never publishes an offseason/empty/unverified feed."""
import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo
from run_v3 import execute
from collector_v30a import load_config
from archive_collector import atomic_json
from season_policy import SeasonNotReady


def stage(day, config, feed_path, diagnostics_path, fetch=None, write=False):
    try:
        plan, feed = execute(day, config, fetch=fetch)
    except SeasonNotReady as exc:
        return {'mode': 'skip', 'reason': str(exc), 'season': None}
    if feed is None:
        return {'mode': 'skip', 'reason': plan['mode'], 'season': plan['season']}
    if feed.get('schema_version') != 1 or not isinstance(feed.get('games'), list):
        raise ValueError('Invalid normalized score feed')
    required = ('generated_at_utc', 'season', 'requested_weeks', 'successful_endpoints', 'games', 'game_count')
    if any(k not in feed for k in required):
        raise ValueError('Missing score feed fields')
    slugs = set(config['seasons'][str(plan['season'])]['nc_school_slugs']) if config.get('schema_version') == 2 else set(config['nc_school_slugs'])
    observed = {side.get('ncaa_slug') for g in feed['games'] for side in (g['away'], g['home'])}
    diag = {'generated_at_utc': feed['generated_at_utc'], 'season': feed['season'],
            'requested_weeks': feed['requested_weeks'], 'configured_school_count': len(slugs),
            'schools_seen_in_requested_weeks': sorted(observed & slugs),
            'schools_not_seen_in_requested_weeks': sorted(slugs - observed),
            'note': 'Not seen does not imply missing coverage: a school may have no game in the requested weeks.',
            'games_collected': feed['game_count'], 'successful_endpoints': feed['successful_endpoints'],
            'errors': feed.get('errors', [])}
    if write:
        atomic_json(Path(feed_path), feed)
        atomic_json(Path(diagnostics_path), diag)
    return {'mode': 'collect', 'season': plan['season'], 'game_count': len(feed['games']), 'write': write}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--date')
    p.add_argument('--config', default='config_v3.json')
    p.add_argument('--feed', default='public/nc-scores.json')
    p.add_argument('--diagnostics', default='public/diagnostics.json')
    p.add_argument('--write', action='store_true')
    p.add_argument('--output-status', default='build/v3-score-stage-status.json')
    a = p.parse_args()
    day = dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(ZoneInfo('America/New_York')).date()
    report = stage(day, load_config(a.config), a.feed, a.diagnostics, write=a.write)
    atomic_json(Path(a.output_status), report)
    print(json.dumps(report, indent=2))

if __name__ == '__main__': main()
