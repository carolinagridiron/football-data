#!/usr/bin/env python3
"""Read-only NCAA scoreboard collector; publishes normalized JSON without modifying Sheets."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import urllib.request

BASE = os.environ.get('NCAA_API_BASE', 'https://ncaa-api.henrygd.me').rstrip('/')
DIVISIONS = ('fbs', 'fcs', 'd2', 'd3')
ROOT = Path(__file__).resolve().parent


def load_config(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def get_json(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'CarolinaGridironScoreCollector/0.1 (+https://github.com/carolinagridiron)', 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def weeks_for_day(day, config):
    # NCAA football uses year/week; the week number is not the calendar ISO week.
    # Anchor was empirically verified: 2026-11-21 belongs to NCAA week 12.
    anchor = dt.date.fromisoformat(config['week_anchor_date'])
    week = int(config['week_anchor_number']) + (day - anchor).days // 7
    return [w for w in (week - 1, week, week + 1) if 1 <= w <= int(config['max_week'])]


def normalize(item, division):
    g = item.get('game', {})
    away, home = g.get('away') or {}, g.get('home') or {}
    def team(t):
        names = t.get('names') or {}
        return {'name': names.get('short') or names.get('full') or '', 'ncaa_slug': names.get('seo') or '',
                'score': int(t['score']) if str(t.get('score', '')).isdigit() else None,
                'winner': bool(t.get('winner'))}
    return {'id': str(g.get('gameID') or ''), 'division': division, 'date': g.get('startDate') or '',
            'start_time_et': g.get('startTime') or '', 'start_time_epoch': g.get('startTimeEpoch') or '',
            'away': team(away), 'home': team(home), 'status': g.get('gameState') or '',
            'period': g.get('currentPeriod') or '', 'clock': g.get('contestClock') or '',
            'final_message': g.get('finalMessage') or '', 'network': g.get('network') or ''}


def collect(config, today, fetch=get_json):
    nc_slugs = set(config['nc_school_slugs'])
    all_games = {}
    errors = []
    successful = []
    weeks = weeks_for_day(today, config)
    for division in DIVISIONS:
        for week in weeks:
            url = f'{BASE}/scoreboard/football/{division}/{today.year}/{week}'
            try:
                response = fetch(url)
                if not isinstance(response.get('games'), list):
                    raise ValueError('Missing games list')
                successful.append(f'{division}/{week}')
                for item in response['games']:
                    game = normalize(item, division)
                    if game['id']:
                        all_games[(division, game['id'])] = game
            except Exception as exc:
                errors.append({'endpoint': f'{division}/{week}', 'error': str(exc)[:180]})
    if not successful:
        raise RuntimeError('No successful NCAA responses; refusing to replace prior feed')
    games = sorted(all_games.values(), key=lambda g: (g['date'], str(g['start_time_epoch']), g['division'], g['id']))
    nc_games = [g for g in games if g['away']['ncaa_slug'] in nc_slugs or g['home']['ncaa_slug'] in nc_slugs]
    return {'schema_version': 1, 'source': 'Unofficial NCAA API (henrygd/ncaa-api)',
            'generated_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
            'season': today.year, 'requested_weeks': weeks, 'successful_endpoints': successful,
            'errors': errors, 'games': nc_games, 'game_count': len(nc_games), 'all_games_count': len(games)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', help='YYYY-MM-DD, default today in America/New_York')
    parser.add_argument('--config', default=str(ROOT / 'config.json'))
    parser.add_argument('--output', default=str(ROOT / 'public' / 'nc-scores.json'))
    args = parser.parse_args()
    from zoneinfo import ZoneInfo
    today = dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(ZoneInfo('America/New_York')).date()
    config = load_config(args.config)
    result = collect(config, today)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temp.replace(path)
    print(f"Saved {result['game_count']} NC games; {len(result['successful_endpoints'])} endpoints succeeded, {len(result['errors'])} failed")


if __name__ == '__main__':
    main()
