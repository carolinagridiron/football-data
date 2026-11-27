#!/usr/bin/env python3
"""Additive national FBS scoreboard archive and conservative postseason candidate feed.
Does not modify nc-scores.json or the editorial Bowl Master.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo
from collector import BASE, get_json, normalize
from collector_v30a import load_config
from season_runtime import collection_plan
from season_policy import SeasonNotReady
from archive_collector import atomic_json


def postseason_candidate(game):
    # Candidate window only: date does not prove that a game is a bowl.
    raw = str(game.get('date') or '').strip()
    date = None
    for fmt in ('%Y-%m-%d', '%m/%d/%Y'):
        try:
            date = dt.datetime.strptime(raw[:10], fmt).date()
            break
        except ValueError:
            pass
    if date is None:
        return False
    year = int(game.get('_season', 0))
    return (date.year == year and date.month == 12) or (date.year == year + 1 and date.month in (1, 2))


def collect_fbs(season, weeks, fetch=get_json):
    found = {}
    for week in weeks:
        url = f'{BASE}/scoreboard/football/fbs/{season}/{week:02d}'
        response = fetch(url)
        if not isinstance(response, dict) or not isinstance(response.get('games'), list):
            raise ValueError(f'Invalid NCAA FBS scoreboard response: week {week}')
        for item in response['games']:
            g = normalize(item, 'fbs')
            if g['id'].isdigit():
                g['_season'] = season
                found[g['id']] = g
    return found


def merge_preserving_finals(old, incoming):
    merged = dict(old)
    for gid, game in incoming.items():
        previous = merged.get(gid)
        if previous and str(previous.get('status', '')).lower() == 'final':
            # Final scores and identities are editorially sensitive; retain old final.
            old_key = (previous['away']['ncaa_slug'], previous['home']['ncaa_slug'], previous['away']['score'], previous['home']['score'])
            new_key = (game['away']['ncaa_slug'], game['home']['ncaa_slug'], game['away']['score'], game['home']['score'])
            if old_key != new_key and str(game.get('status','')).lower() == 'final':
                raise ValueError(f'Historical final conflict for NCAA game {gid}; no files written')
            continue
        merged[gid] = game
    return merged


def build_outputs(season, existing, incoming):
    if existing and int(existing.get('season', -1)) != int(season):
        raise ValueError('Season mismatch; refusing cross-season merge')
    merged = merge_preserving_finals({str(g['id']):g for g in existing.get('games', [])}, incoming)
    games = sorted(merged.values(), key=lambda g:(str(g['date']),str(g['id'])))
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    common = {'schema_version':1, 'source':'Unofficial NCAA API (henrygd/ncaa-api)', 'season':season, 'generated_at_utc':stamp}
    national = {**common, 'games':games, 'game_count':len(games)}
    candidates = [g for g in games if postseason_candidate(g)]
    bowl = {**common, 'classification':'DATE_WINDOW_CANDIDATES_NOT_VERIFIED_BOWLS', 'games':candidates, 'game_count':len(candidates)}
    return national,bowl


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--config',default='config_v3.json')
    p.add_argument('--date',help='YYYY-MM-DD')
    p.add_argument('--national',default='public/national-fbs.json')
    p.add_argument('--bowl',default='public/bowl-candidates.json')
    p.add_argument('--write',action='store_true')
    a=p.parse_args()
    day=dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(ZoneInfo('America/New_York')).date()
    try:
        plan=collection_plan(day,load_config(a.config))
    except SeasonNotReady as exc:
        print(f'No publication: unverified season: {exc}')
        return
    if plan['mode']!='collect' or not plan['weeks']:
        print('No publication: offseason')
        return
    path=Path(a.national)
    previous=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    # Season change must not silently erase the previous season's national data.
    if previous and int(previous.get('season',-1)) != plan['season']:
        archive=path.parent/'national-fbs-archive'/f"{previous['season']}.json"
        if not archive.exists():
            if a.write:
                atomic_json(archive,previous)
            else:
                print(f'Would archive prior national season to {archive}')
        previous={}
    incoming=collect_fbs(plan['season'],plan['weeks'])
    national,bowl=build_outputs(plan['season'],previous,incoming)
    print(json.dumps({'season':plan['season'],'weeks':plan['weeks'],'new_or_refreshed':len(incoming),'national_games':national['game_count'],'postseason_candidates':bowl['game_count'],'write':a.write}))
    if a.write:
        atomic_json(path,national)
        atomic_json(Path(a.bowl),bowl)

if __name__=='__main__':main()
