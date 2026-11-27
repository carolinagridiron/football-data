#!/usr/bin/env python3
"""Unified NCAA collection: fetch each NCAA division/week once, publish three compatible feeds.

This is an additive source for the existing season-aware score stage. Historical
finals and season transitions are guarded; no external account credentials needed.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo
from collector_v30a import BASE, DIVISIONS, get_json, load_config, normalize
from season_runtime import collection_plan
from season_policy import SeasonNotReady
from archive_collector import atomic_json


def is_final(g):
    return str(g.get('status','')).lower() in ('final','f')


def postseason(g, season):
    raw = str(g.get('date') or '')[:10]
    day = None
    for fmt in ('%m/%d/%Y','%Y-%m-%d'):
        try:
            day=dt.datetime.strptime(raw,fmt).date()
            break
        except ValueError:
            pass
    return bool(day and ((day.year==season and day.month==12) or
                         (day.year==season+1 and day.month in (1,2))))


def fetch_all(season, weeks, fetch=get_json):
    all_games={}; endpoints=[]
    for division in DIVISIONS:
        for week in weeks:
            endpoint=f'{division}/{week}'
            response=fetch(f'{BASE}/scoreboard/football/{division}/{season}/{week:02d}')
            if not isinstance(response,dict) or not isinstance(response.get('games'),list):
                raise ValueError('Incomplete NCAA response: '+endpoint)
            endpoints.append(endpoint)
            for item in response['games']:
                g=normalize(item,division)
                if str(g.get('id','')).isdigit():
                    all_games[(division,g['id'])]=g
    return sorted(all_games.values(),key=lambda g:(str(g.get('date','')),str(g.get('start_time_epoch','')),g['division'],g['id'])),endpoints


def preserve_finals(old_games, new_games):
    old={str(g['id']):g for g in old_games if str(g.get('id','')).isdigit()}
    result=dict(old)
    for g in new_games:
        gid=str(g['id']); prior=old.get(gid)
        if prior and is_final(prior):
            if (prior.get('away',{}).get('ncaa_slug'),prior.get('home',{}).get('ncaa_slug')) != (g.get('away',{}).get('ncaa_slug'),g.get('home',{}).get('ncaa_slug')):
                raise ValueError('Final team identity conflict: '+gid)
            if is_final(g) and (prior['away'].get('score'),prior['home'].get('score')) != (g['away'].get('score'),g['home'].get('score')):
                raise ValueError('Final score conflict: '+gid)
            continue
        result[gid]=g
    return sorted(result.values(),key=lambda g:(str(g.get('date','')),str(g.get('start_time_epoch','')),g['id']))


def build(day,config,fetch=get_json,existing_national=None):
    plan=collection_plan(day,config)
    if plan['mode']!='collect' or not plan['weeks']:
        return None
    season=int(plan['season'])
    games,endpoints=fetch_all(season,plan['weeks'],fetch)
    if not games: raise ValueError('Empty NCAA response; existing feeds retained')
    slugs=set(config['seasons'][str(season)]['nc_school_slugs'])
    nc=[g for g in games if g['away']['ncaa_slug'] in slugs or g['home']['ncaa_slug'] in slugs]
    # An active bowl week may contain no NC teams; national coverage still proceeds.
    stamp=dt.datetime.now(dt.timezone.utc).isoformat()
    base={'schema_version':1,'source':'Unofficial NCAA API (henrygd/ncaa-api)','generated_at_utc':stamp,'season':season}
    nc_feed={**base,'requested_weeks':plan['weeks'],'successful_endpoints':endpoints,'errors':[],
             'games':nc,'game_count':len(nc),'all_games_count':len(games)}
    prev=existing_national or {}
    if prev and int(prev.get('season',-1))==season:
        national_games=preserve_finals(prev.get('games',[]),[g for g in games if g['division']=='fbs'])
    else:
        national_games=[g for g in games if g['division']=='fbs']
    national={**base,'games':national_games,'game_count':len(national_games)}
    candidates=[g for g in national_games if postseason(g,season)]
    bowl={**base,'classification':'DATE_WINDOW_CANDIDATES_NOT_VERIFIED_BOWLS',
          'games':candidates,'game_count':len(candidates)}
    observed={t['ncaa_slug'] for g in nc for t in (g['away'],g['home'])}
    diag={'generated_at_utc':stamp,'season':season,'requested_weeks':plan['weeks'],
          'configured_school_count':len(slugs),'schools_seen_in_requested_weeks':sorted(slugs&observed),
          'schools_not_seen_in_requested_weeks':sorted(slugs-observed),
          'note':'Not seen does not imply missing coverage: a school may have no game in the requested weeks.',
          'games_collected':len(nc),'successful_endpoints':endpoints,'errors':[]}
    return {'season':season,'nc':nc_feed,'diagnostics':diag,'national':national,'bowl':bowl,'endpoints':len(endpoints)}


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',default='config_v3.json')
    p.add_argument('--date');p.add_argument('--write',action='store_true')
    p.add_argument('--status',default='build/unified-status.json')
    a=p.parse_args();day=dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(ZoneInfo('America/New_York')).date()
    status={'mode':'skip','reason':'offseason or unverified season'}
    try:
        config=load_config(a.config)
        national_path=Path('public/national-fbs.json')
        previous=json.loads(national_path.read_text(encoding='utf-8')) if national_path.exists() else {}
        result=build(day,config,existing_national=previous)
        if result is not None:
            season=result['season']
            # New seasons must have a verified configuration, and old national feeds
            # must be archived before any replacement.
            archive=None
            if previous and int(previous.get('season',-1))!=season:
                archive=Path('public/national-fbs-archive')/(str(previous['season'])+'.json')
                if archive.exists():
                    archived=json.loads(archive.read_text(encoding='utf-8'))
                    if archived!=previous:raise ValueError('Existing national archive differs from prior feed')
            if a.write:
                if archive and not archive.exists():atomic_json(archive,previous)
                # Only write after all divisions succeeded and every feed was built.
                # Do not blank the NC scoreboard when active national weeks contain no NC games.
                if result['nc']['games']:
                    atomic_json(Path('public/nc-scores.json'),result['nc'])
                    atomic_json(Path('public/diagnostics.json'),result['diagnostics'])
                atomic_json(national_path,result['national'])
                atomic_json(Path('public/bowl-candidates.json'),result['bowl'])
            status={'mode':'collect','season':season,'nc_games':result['nc']['game_count'],
                    'national_games':result['national']['game_count'],'postseason_candidates':result['bowl']['game_count'],
                    'endpoints':result['endpoints'],'write':a.write}
    except SeasonNotReady as exc:
        status={'mode':'skip','reason':'unverified season: '+str(exc)}
    atomic_json(Path(a.status),status)
    print(json.dumps(status,indent=2))

if __name__=='__main__':main()
