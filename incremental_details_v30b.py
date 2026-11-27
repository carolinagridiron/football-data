#!/usr/bin/env python3
"""Incremental NCAA detail archiving from the published scoreboard; dry run by default."""
import argparse
import datetime as dt
import json
from pathlib import Path
from archive_collector import parse_detail, merge, detail_state, atomic_json, is_final
from collector import BASE, get_json

ROOT = Path(__file__).resolve().parent

def recent(game, now, days):
    raw = str(game.get('date') or '')
    for fmt in ('%m/%d/%Y', '%Y-%m-%d'):
        try:
            day = dt.datetime.strptime(raw, fmt).date()
            return abs((now-day).days) <= days
        except ValueError:
            pass
    return False

def run(feed, archive, now, fetch=get_json, window=3, limit=30):
    if int(feed['season']) != int(archive['season']):
        raise ValueError('Season mismatch: refusing cross-season archive updates')
    games = dict(archive.get('games') or {})
    details = dict(archive.get('details') or {})
    tracking = dict(archive.get('detail_tracking') or {})
    report = {'season':feed['season'], 'feed_games':len(feed.get('games') or []), 'new_games':0,
              'game_updates':0,'detail_requests':0,'detail_errors':[], 'conflicts':[], 'skipped':0}
    candidates=[]
    for g in feed.get('games') or []:
        gid = str(g.get('id') or '')
        if not gid.isdigit(): continue
        old = games.get(gid)
        if old is None:
            games[gid] = g
            report['new_games'] += 1
        elif is_final(old):
            if (old.get('away',{}).get('score'),old.get('home',{}).get('score')) != (g.get('away',{}).get('score'),g.get('home',{}).get('score')):
                report['conflicts'].append({'id':gid,'type':'final_score_change'})
        elif old != g:
            games[gid] = g
            report['game_updates'] += 1
        if not recent(g, now, window):
            report['skipped'] += 1
            continue
        t = tracking.get(gid,{})
        # Recent final games are checked at most twice; live games on each new feed generation.
        if is_final(g) and int(t.get('attempts') or 0) >= 2:
            continue
        if is_final(g) and t.get('status') == 'COMPLETE':
            continue
        candidates.append(g)
    for g in candidates[:limit]:
        gid=str(g['id']); prior=tracking.get(gid,{})
        report['detail_requests'] += 1
        try:
            incoming=parse_detail(fetch(f'{BASE}/game/{gid}'),gid)
            # Ensure NCAA detail identifies the same two teams by slug where available.
            expected={g['away'].get('ncaa_slug'),g['home'].get('ncaa_slug')} - {None,''}
            actual={incoming['ncaa_away'].get('slug'),incoming['ncaa_home'].get('slug')} - {None,''}
            if expected and actual and not expected.issubset(actual):
                raise ValueError('Team identity mismatch')
            old_detail=details.get(gid)
            if is_final(g) or (old_detail and is_final(archive.get('games',{}).get(gid,{}))):
                merged, conflicts=merge(old_detail,incoming)
            else:
                # Live scores evolve; replace period rows, retain previously known venue fields.
                merged, conflicts=merge(old_detail,{k:v for k,v in incoming.items() if k!='period_scores'})
                if incoming.get('period_scores'):
                    merged['period_scores']=incoming['period_scores']
            details[gid]=merged
            report['conflicts'] += [dict(id=gid,type='detail',**c) for c in conflicts]
            tracking[gid]={'status':detail_state(merged),'attempts':int(prior.get('attempts') or 0)+1,
                           'last_attempt_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'last_error':None}
        except Exception as exc:
            report['detail_errors'].append({'id':gid,'error':str(exc)[:180]})
            tracking[gid]={'status':'RETRY','attempts':int(prior.get('attempts') or 0)+1,
                           'last_attempt_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'last_error':str(exc)[:180]}
    return {**archive,'games':games,'details':details,'detail_tracking':tracking},report

def publish_changed(archive, root, write=False):
    from publish_game_details import compact, encode, atomic_write
    report={'new_files':0,'updated_files':0,'unchanged_files':0,'held':[]}
    year=str(archive['season']); folder=root/year
    for gid,g in archive['games'].items():
        detail=archive.get('details',{}).get(gid)
        if not detail: continue
        doc=compact(g,detail);doc['season']=int(year)
        data=encode(doc); path=folder/(gid+'.json')
        if not path.exists():
            report['new_files']+=1
            if write: folder.mkdir(parents=True,exist_ok=True);atomic_write(path,data)
        elif path.read_bytes()==data:
            report['unchanged_files']+=1
        else:
            try: previous=json.loads(path.read_text(encoding='utf-8'))
            except Exception: report['held'].append(gid);continue
            # Final documents are immutable except additive enrichment of absent fields.
            # Do not permit changes in teams, final scores, or previously published periods.
            stable=('id','season','away','home','division','date')
            safe=all(previous.get(k)==doc.get(k) for k in stable)
            old_period=previous.get('period_scores') or []
            new_period=doc.get('period_scores') or []
            if str(previous.get('status','')).lower() in ('final','f'):
                safe=safe and (not old_period or old_period==new_period)
            else:
                safe=safe and (len(new_period)>=len(old_period) or not new_period)
            for field in ('stadium','city','state'):
                before=(previous.get('venue') or {}).get(field)
                after=(doc.get('venue') or {}).get(field)
                if before and before!=after: safe=False
            if not safe:
                report['held'].append(gid);continue
            report['updated_files']+=1
            if write:atomic_write(path,data)
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--season',type=int,default=2026)
    p.add_argument('--feed',default='public/nc-scores.json')
    p.add_argument('--archive-root',default='public/archive')
    p.add_argument('--details-root',default='public/game-details')
    p.add_argument('--window-days',type=int,default=3)
    p.add_argument('--detail-limit',type=int,default=30)
    p.add_argument('--write',action='store_true')
    a=p.parse_args()
    feed=json.loads(Path(a.feed).read_text(encoding='utf-8'))
    path=Path(a.archive_root)/str(a.season)/'archive.json'
    archive=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'schema_version':1,'season':a.season,'games':{},'details':{},'detail_tracking':{}}
    from zoneinfo import ZoneInfo
    now=dt.datetime.now(ZoneInfo('America/New_York')).date()
    result,report=run(feed,archive,now,window=a.window_days,limit=a.detail_limit)
    # Avoid writes if any upstream error or historical conflict needs review.
    if report['conflicts'] or report['detail_errors']:
        print(json.dumps(report,indent=2));raise SystemExit('Review required: archive unchanged')
    pub=publish_changed(result,Path(a.details_root),write=False)
    report['publication']=pub
    if pub['held']:
        print(json.dumps(report,indent=2));raise SystemExit('Review required: published files unchanged')
    if a.write:
        # Publication preflight passed. Save archive then publish individual documents.
        atomic_json(path,result)
        publish_changed(result,Path(a.details_root),write=True)
    print(json.dumps(report,indent=2))
    print('WRITE ENABLED' if a.write else 'READ ONLY: no files changed')
if __name__=='__main__':main()
