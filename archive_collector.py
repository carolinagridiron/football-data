#!/usr/bin/env python3
"""Opt-in historical NCAA details archive. Dry-run by default; never edits live feed."""
import argparse
import datetime as dt
import json
import os
import time
from pathlib import Path
from collector import BASE, DIVISIONS, get_json, load_config, normalize

ROOT=Path(__file__).resolve().parent

def is_final(g):
    return str(g.get('status','')).lower() in ('f','final') or 'final' in str(g.get('final_message','')).lower()

def period_scores(contest):
    rows=contest.get('linescores') or []
    return [{'period':str(r.get('period','')), 'home':r.get('home'), 'away':r.get('visit')} for r in rows]

def parse_detail(payload, game_id):
    contests=payload.get('contests') or []
    match=next((x for x in contests if str(x.get('id'))==str(game_id)),None)
    if not match: raise ValueError('Detail response lacks requested contest')
    location=match.get('location') or {}
    teams=match.get('teams') or []
    home=next((t for t in teams if t.get('isHome') is True),{})
    away=next((t for t in teams if t.get('isHome') is False),{})
    return {'id':str(game_id),'venue':{'stadium':location.get('venue') or None,'city':location.get('city') or None,'state':location.get('stateUsps') or None},'period_scores':period_scores(match),'ncaa_home':{'id':str(home.get('teamId') or ''),'slug':home.get('seoname') or '', 'name':home.get('nameShort') or ''},'ncaa_away':{'id':str(away.get('teamId') or ''),'slug':away.get('seoname') or '', 'name':away.get('nameShort') or ''},'source':'NCAA game endpoint'}

def nonempty(v): return v not in (None,'',[],{})

def merge(existing, incoming):
    result=dict(existing or {}); conflicts=[]
    for field in ('venue','period_scores','ncaa_home','ncaa_away'):
        old=result.get(field); new=incoming.get(field)
        if not nonempty(old):
            if nonempty(new): result[field]=new
        elif isinstance(old,dict) and isinstance(new,dict):
            merged=dict(old)
            for k,v in new.items():
                if not nonempty(merged.get(k)) and nonempty(v): merged[k]=v
                elif nonempty(v) and nonempty(merged.get(k)) and merged[k]!=v: conflicts.append({'field':field+'.'+k,'old':merged[k],'new':v})
            result[field]=merged
        elif nonempty(new) and old!=new: conflicts.append({'field':field,'old':old,'new':new})
    result['id']=incoming['id'];return result,conflicts

def detail_state(detail, final=False):
    """Classify a successfully fetched detail payload, not just its completeness."""
    periods = detail.get('period_scores') or []
    venue = detail.get('venue') or {}
    has_venue = any(venue.get(k) for k in ('stadium', 'city', 'state'))
    if periods and has_venue:
        return 'COMPLETE'
    if periods or has_venue:
        return 'PARTIAL'
    return 'NO_DATA'


def sweep(year, config, max_week, fetch=get_json, detail_fetch=get_json, existing=None, detail_limit=0, pause=0):
    existing = existing or {}
    games = dict(existing.get('games') or {})
    details = dict(existing.get('details') or {})
    tracking = dict(existing.get('detail_tracking') or {})
    report = {'season':year,'successful_weeks':[],'failed_weeks':[],
              'detail_requests':0,'detail_errors':[],'conflicts':[],'new_games':0}
    nc = set(config['nc_school_slugs'])
    discovered = {}
    for div in DIVISIONS:
        for week in range(1, max_week+1):
            try:
                data = fetch(f'{BASE}/scoreboard/football/{div}/{year}/{week:02d}')
                if not isinstance(data.get('games'), list):
                    raise ValueError('Missing games list')
                report['successful_weeks'].append(f'{div}/{week}')
                for item in data['games']:
                    g = normalize(item, div)
                    if g['id'] and (g['away']['ncaa_slug'] in nc or g['home']['ncaa_slug'] in nc):
                        discovered[g['id']] = g
            except Exception as exc:
                report['failed_weeks'].append({'endpoint':f'{div}/{week}', 'error':str(exc)[:180]})
    if report['failed_weeks']:
        report['blocked'] = 'Incomplete scoreboard coverage: no archive write permitted'
        return existing, report
    for gid, g in discovered.items():
        if gid not in games:
            games[gid] = g
            report['new_games'] += 1
        elif games[gid] != g:
            if is_final(games[gid]) and (games[gid]['away']['score'], games[gid]['home']['score']) != (g['away']['score'], g['home']['score']):
                report['conflicts'].append({'game_id':gid,'type':'final_score',
                    'old':[games[gid]['away']['score'],games[gid]['home']['score']],
                    'new':[g['away']['score'],g['home']['score']]})
            else:
                games[gid] = g

    # Migration: previously fetched detail records should not be requested again
    # merely because the NCAA omitted a stadium or scoring breakdown.
    for gid, detail in details.items():
        if gid not in tracking:
            tracking[gid] = {'status':detail_state(detail), 'attempts':1,
                             'last_attempt_utc':None, 'last_error':None}

    def eligible(g):
        gid = g['id']
        t = tracking.get(gid, {})
        status = t.get('status', 'PENDING')
        attempts = int(t.get('attempts') or 0)
        if status in ('COMPLETE', 'NO_DATA'):
            return False
        if status == 'PARTIAL' and attempts >= 2 and is_final(g):
            return False
        if status == 'RETRY' and attempts >= 3:
            return False
        return True

    candidates = sorted((g for g in discovered.values() if eligible(g)),
                        key=lambda g:(is_final(g),g.get('date',''),g['id']))
    for g in candidates[:max(0,detail_limit)]:
        gid = g['id']
        prior = tracking.get(gid, {})
        attempts = int(prior.get('attempts') or 0)+1
        timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
        report['detail_requests'] += 1
        try:
            detail = parse_detail(detail_fetch(f'{BASE}/game/{gid}'),gid)
            merged, conflicts = merge(details.get(gid),detail)
            details[gid] = merged
            report['conflicts'] += [dict(game_id=gid,type='detail',**c) for c in conflicts]
            tracking[gid] = {'status':detail_state(merged),'attempts':attempts,
                             'last_attempt_utc':timestamp,'last_error':None}
        except Exception as exc:
            message = str(exc)[:180]
            report['detail_errors'].append({'game_id':gid,'error':message})
            tracking[gid] = {'status':'RETRY','attempts':attempts,
                             'last_attempt_utc':timestamp,'last_error':message}
        if pause:
            time.sleep(pause)
    counts = {s:0 for s in ('COMPLETE','PARTIAL','NO_DATA','RETRY','PENDING')}
    for gid in games:
        state = tracking.get(gid,{}).get('status','PENDING')
        counts[state] = counts.get(state,0)+1
    report['detail_status_counts'] = counts
    report['details_total'] = len(details)
    report['games_total'] = len(games)
    report['details_pending'] = sum(eligible(g) for g in discovered.values())
    report['details_attempted_unique'] = sum(1 for gid in games if gid in tracking)
    return {'schema_version':1,'season':year,'games':games,'details':details,
            'detail_tracking':tracking}, report

def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(obj,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
    os.replace(temp,path)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--season',type=int,default=2026);p.add_argument('--max-week',type=int,default=None)
    p.add_argument('--config',default=str(ROOT/'config.json'))
    p.add_argument('--archive-root',default=str(ROOT/'public'/'archive'))
    p.add_argument('--detail-limit',type=int,default=15)
    p.add_argument('--pause',type=float,default=0.2)
    p.add_argument('--write',action='store_true',help='Explicitly authorize archive writes')
    a=p.parse_args();config=load_config(a.config)
    max_week=a.max_week if a.max_week is not None else int(config['max_week'])
    path=Path(a.archive_root)/str(a.season)/'archive.json'
    existing=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    result,report=sweep(a.season,config,max_week,existing=existing,detail_limit=a.detail_limit,pause=a.pause)
    print(json.dumps(report,indent=2))
    if a.write and not report.get('blocked'):
        atomic_json(path,result)
        atomic_json(path.parent/'last-run-report.json',report)
        print('Archive updated:',path)
    else:print('READ ONLY: no archive files changed')
    if report.get('blocked'):raise SystemExit(2)

if __name__=='__main__':main()
