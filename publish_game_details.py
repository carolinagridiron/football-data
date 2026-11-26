#!/usr/bin/env python3
"""Publish compact, immutable-by-default NCAA detail documents from a season archive."""
import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def compact(game, detail):
    if str(game['id']) != str(detail.get('id')):
        raise ValueError('Game/detail ID mismatch')
    periods = []
    for row in detail.get('period_scores') or []:
        if not isinstance(row, dict):
            continue
        periods.append({'period': str(row.get('period') or ''),
                        'away': row.get('away'), 'home': row.get('home')})
    venue = detail.get('venue') or {}
    return {'schema_version': 1, 'id': str(game['id']),
            'season': None, 'division': game.get('division'),
            'date': game.get('date'), 'status': game.get('status'),
            'away': {'name': game.get('away', {}).get('name'), 'ncaa_slug': game.get('away', {}).get('ncaa_slug')},
            'home': {'name': game.get('home', {}).get('name'), 'ncaa_slug': game.get('home', {}).get('ncaa_slug')},
            'ncaa_away': detail.get('ncaa_away') or {},
            'ncaa_home': detail.get('ncaa_home') or {},
            'venue': {k: venue.get(k) for k in ('stadium','city','state')},
            'period_scores': periods}

def encode(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')

def publish(archive, target, write=False):
    games = archive['games']; details = archive.get('details') or {}
    season = int(archive['season'])
    if not 2000 <= season <= 2100: raise ValueError('Invalid season')
    expected = {}
    for gid, game in games.items():
        if not str(gid).isdigit() or str(game.get('id')) != str(gid):
            raise ValueError('Invalid game ID')
        detail = details.get(gid)
        if not detail: continue
        payload = compact(game, detail)
        payload['season'] = season
        expected[str(gid) + '.json'] = encode(payload)
    added = updated = unchanged = 0
    conflicts = []
    for filename, content in sorted(expected.items()):
        path = target / filename
        if not path.exists():
            added += 1
            if write:
                target.mkdir(parents=True, exist_ok=True)
                atomic_write(path, content)
        elif path.read_bytes() == content:
            unchanged += 1
        else:
            # Never silently overwrite a previously published game document.
            updated += 1
            conflicts.append(filename)
    return {'season': season, 'games_in_archive': len(games),
            'details_available': len(expected), 'new_files': added,
            'unchanged_files': unchanged, 'changed_files_held': updated,
            'conflicts': conflicts, 'write_enabled': write}

def atomic_write(path, data):
    temp = path.with_name(path.name + '.tmp')
    try:
        temp.write_bytes(data)
        os.replace(temp, path)
    finally:
        if temp.exists(): temp.unlink()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--season', type=int, default=2026)
    p.add_argument('--archive-root', default='public/archive')
    p.add_argument('--output-root', default='public/game-details')
    p.add_argument('--write', action='store_true')
    a = p.parse_args()
    source = Path(a.archive_root) / str(a.season) / 'archive.json'
    archive = json.loads(source.read_text(encoding='utf-8'))
    if int(archive['season']) != a.season: raise ValueError('Archive season mismatch')
    report = publish(archive, Path(a.output_root) / str(a.season), a.write)
    print(json.dumps(report, indent=2))
    if report['conflicts']:
        raise SystemExit('Previously published detail files differ; review required')

if __name__ == '__main__': main()
