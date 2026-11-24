#!/usr/bin/env python3
"""Read-only 2026 season audit against a frozen editorial scoreboard export."""
import argparse
import csv
import datetime as dt
import json
import re
import time
from collections import defaultdict
from pathlib import Path
from collector import BASE, DIVISIONS, get_json, normalize, load_config

ROOT = Path(__file__).resolve().parent
ALIASES = {
    'app state':'appalachian-st','appalachian state':'appalachian-st',
    'unc':'north-carolina','north carolina':'north-carolina',
    'nc state':'north-carolina-st','north carolina state':'north-carolina-st',
    'ecu':'east-carolina','east carolina':'east-carolina',
    'nc at':'nc-at','north carolina at':'nc-at',
    'nc central':'nc-central','north carolina central':'nc-central',
    'western carolina':'western-caro','western caro':'western-caro',
    'unc pembroke':'unc-pembroke','pembroke':'unc-pembroke',
    'nc wesleyan':'nc-wesleyan','north carolina wesleyan':'nc-wesleyan',
    'winston salem state':'winston-salem-st','winston salem st':'winston-salem-st',
    'elizabeth city state':'elizabeth-city-st','elizabeth city st':'elizabeth-city-st',
    'fayetteville state':'fayetteville-st','fayetteville st':'fayetteville-st',
    'johnson c smith':'johnson-c-smith','lenoir rhyne':'lenoir-rhyne',
    'livingstone':'livingstone','shaw':'shaw','mars hill':'mars-hill',
    'florida state':'florida-st','florida st':'florida-st',
    'central state':'central-st-oh','central st':'central-st-oh',
    'south carolina state':'south-carolina-st','south carolina st':'south-carolina-st',
    'georgia tech':'georgia-tech','army':'army','army west point':'army',
    'louisburg':'louisburg','louisburg college':'louisburg',
    'ualbany':'albany-ny','albany ny':'albany-ny',
    'miami':'miami-fl','miami fl':'miami-fl',
    'emory and henry':'emory-henry','emory henry':'emory-henry',
    'fau':'fla-atlantic','florida atlantic':'fla-atlantic',
    'south alabama':'south-ala',
    'virginia state':'virginia-st','virginia st':'virginia-st',
    'louisville':'louisville','albany':'albany-ny',
    'north carolina a and t':'nc-at','n c a and t':'nc-at',
    'n c central':'nc-central','winston salem st':'winston-salem-st',
    'georgia southern':'ga-southern','georgia state':'georgia-st',
    'appalachian st':'appalachian-st','e tennessee st':'east-tennessee-st',
    'east tennessee state':'east-tennessee-st','east tennessee st':'east-tennessee-st',
    'unc charlotte':'charlotte','florida atlantic':'fla-atlantic',
    'em and henry':'emory-henry','emory and henry':'emory-henry',
}

def key(value):
    return re.sub(r'[^a-z0-9]+',' ',str(value or '').lower().replace('&',' and ')).strip()

def slug(value):
    k=key(value)
    return ALIASES.get(k, k.replace(' ','-'))

def read_reference(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        rows=list(csv.DictReader(f))
    required={'date','division','visitor','home','visitor_score','home_score','status'}
    if not rows or not required.issubset(rows[0]):
        raise ValueError('Reference CSV missing expected columns')
    return rows

def fetch_season(config, season, last_week, fetch=get_json, pause=0.4):
    # Include week 0: early-season football can begin before the week 1 anchor.
    games={}; failures=[]; endpoints=[]; warnings=[]
    for division in DIVISIONS:
        for week in range(0,last_week+1):
            endpoint=f'{division}/{week}'
            try:
                payload=fetch(f'{BASE}/scoreboard/football/{division}/{season}/{week}')
                if not isinstance(payload,dict) or not isinstance(payload.get('games'),list):
                    raise ValueError('Missing games array')
                endpoints.append(endpoint)
                for item in payload['games']:
                    g=normalize(item,division)
                    if g['id']:
                        games[(division,g['id'])]=g
            except Exception as exc:
                issue={'endpoint':endpoint,'error':str(exc)[:180]}
                if week==0: warnings.append(issue)
                else: failures.append(issue)
            if pause: time.sleep(pause)
    if failures:
        raise RuntimeError('Full-season audit incomplete; no audit files published: '+json.dumps(failures))
    return list(games.values()),endpoints,warnings

def score(value):
    try: return int(float(value)) if str(value).strip() else None
    except (ValueError,TypeError): return None

def parse_day(value):
    for fmt in ('%Y-%m-%d', '%m/%d/%Y'):
        try: return dt.datetime.strptime(str(value), fmt).date()
        except ValueError: pass
    return None

def game_pair(game):
    return tuple(sorted((slug(game['away']['ncaa_slug']),slug(game['home']['ncaa_slug']))))

def collapse_duplicates(games):
    """Collapse identical cross-division listings of the same NCAA game ID.

    Conflicting data for one ID is preserved for review, never silently chosen.
    """
    by_id=defaultdict(list)
    for g in games: by_id[str(g['id'])].append(g)
    collapsed=[]; conflicts=[]
    for gid,records in by_id.items():
        signatures={(game_pair(g),str(g['date']),str(g['away']['score']),str(g['home']['score']),g['status']) for g in records}
        if len(signatures)==1:
            collapsed.append(records[0])
        else:
            conflicts.append(gid)
            collapsed.extend(records)
    return collapsed,conflicts

def compare(reference,games,active):
    """Conservative matching: both teams + date (within two days only if unique).

    Never match solely on score, school, or a fuzzy name. Preserve ambiguous cases.
    """
    games,duplicate_conflicts=collapse_duplicates(games)
    by_pair=defaultdict(list)
    for g in games:
        if parse_day(g['date']): by_pair[game_pair(g)].append(g)
    reports=[];matched_ids=set()
    for r in reference:
        pair=tuple(sorted((slug(r['visitor']),slug(r['home']))))
        base={'date':r['date'],'division':r['division'],'visitor':r['visitor'],'home':r['home'],
              'sheet_visitor_score':r['visitor_score'],'sheet_home_score':r['home_score'],
              'sheet_status':r['status'],'ncaa_id':'','ncaa_visitor_score':'','ncaa_home_score':'',
              'ncaa_status':'','finding':'','notes':'','date_offset_days':'','match_method':''}
        if 'louisburg' in pair or str(r['division']).lower()=='juco':
            base['finding']='MANUAL_ONLY';reports.append(base);continue
        day=parse_day(r['date'])
        options=[g for g in by_pair.get(pair,[]) if day and parse_day(g['date'])]
        exact=[g for g in options if parse_day(g['date'])==day]
        near=[g for g in options if abs((parse_day(g['date'])-day).days)<=2]
        if len(exact)==1:
            candidates=exact; method='EXACT'
        elif len(exact)>1:
            candidates=exact;method='AMBIGUOUS_EXACT'
        elif len(near)==1:
            candidates=near;method='DATE_TOLERANCE'
        else:
            candidates=near;method='AMBIGUOUS_NEAR' if near else 'NO_MATCH'
        if len(candidates)!=1:
            base['finding']=('AMBIGUOUS' if candidates else
                'SCHEDULED_NOT_IN_NCAA' if str(r['status']).lower().strip() in ('scheduled','pre') else 'UNMATCHED')
            base['notes']=('Multiple NCAA records share the same two-team/date window' if candidates
                else 'No two-team match within 2 days; could be a coverage gap, alias, or schedule difference')
            base['match_method']=method;reports.append(base);continue
        g=candidates[0];matched_ids.add(str(g['id']))
        base['ncaa_id']=g['id'];base['ncaa_status']=g['status'];base['match_method']=method
        offset=(parse_day(g['date'])-day).days
        base['date_offset_days']=offset
        if offset:base['notes']=f'NCAA date differs by {offset:+d} day(s); verify schedule date'
        va=slug(r['visitor'])==slug(g['away']['ncaa_slug'])
        vs=g['away']['score'] if va else g['home']['score']
        hs=g['home']['score'] if va else g['away']['score']
        base['ncaa_visitor_score']=vs if vs is not None else ''
        base['ncaa_home_score']=hs if hs is not None else ''
        sheet_final=str(r['status']).lower().strip()=='final';ncaa_final=g['status'].lower()=='final'
        if sheet_final and ncaa_final:
            base['finding']='MATCH' if score(r['visitor_score'])==vs and score(r['home_score'])==hs else 'SCORE_DISCREPANCY'
        elif sheet_final!=ncaa_final:
            base['finding']='STATUS_DISCREPANCY'
        else:
            base['finding']='MATCH_NONFINAL'
        reports.append(base)
    extra=[]
    for g in games:
        if str(g['id']) in matched_ids:continue
        if g['away']['ncaa_slug'] not in active and g['home']['ncaa_slug'] not in active:continue
        extra.append({'date':g['date'],'division':g['division'],'ncaa_id':g['id'],
                      'away':g['away']['name'],'home':g['home']['name'],'away_score':g['away']['score'],
                      'home_score':g['home']['score'],'status':g['status']})
    return reports,extra

def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--season',type=int,default=2026)
    p.add_argument('--through-week',type=int,default=13)
    p.add_argument('--reference',default=str(ROOT/'audit/reference_2026.csv'))
    p.add_argument('--outdir',default=str(ROOT/'audit-results'))
    args=p.parse_args()
    config=load_config(ROOT/'config.json')
    if args.season!=2026:raise SystemExit('This audited reference is for 2026 only')
    if not 0<=args.through_week<=config['max_week']:raise SystemExit('Invalid through-week')
    reference=read_reference(args.reference)
    games,endpoints,warnings=fetch_season(config,args.season,args.through_week)
    report,extra=compare(reference,games,set(config['nc_school_slugs']))
    out=Path(args.outdir)
    write_csv(out/'game_comparison.csv',report,list(report[0]))
    write_csv(out/'ncaa_only_games.csv',extra,['date','division','ncaa_id','away','home','away_score','home_score','status'])
    counts={k:sum(r['finding']==k for r in report) for k in sorted(set(r['finding'] for r in report))}
    summary={'season':args.season,'weeks_checked':list(range(args.through_week+1)),
             'endpoints_successful':len(endpoints),'optional_week_zero_warnings':warnings,'ncaa_games_retrieved':len(games),
             'editorial_records':len(reference),'findings':counts,'ncaa_only_games':len(extra),
             'editorial_precedence':'Google Sheets; report is read-only',
             'limitations':['Two-team matching with at most 2-day date tolerance; ambiguous cases never auto-resolved','Aliases are explicit; unmatched records require review',
                            'NCAA may not cover non-NCAA opponents','2026 reference is a frozen snapshot, not live Google Sheets'],
             'date_tolerance_matches':sum(r['match_method']=='DATE_TOLERANCE' for r in report),
             'manual_review_required':sum(r['finding'] in ('SCORE_DISCREPANCY','STATUS_DISCREPANCY','AMBIGUOUS','UNMATCHED') for r in report)}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
