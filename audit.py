#!/usr/bin/env python3
"""Read-only 2026 season audit against a frozen editorial scoreboard export."""
import argparse
import csv
import datetime as dt
import json
import re
import time
from collections import defaultdict
import collections
from pathlib import Path
from collector import BASE, DIVISIONS, get_json, normalize, load_config

ROOT = Path(__file__).resolve().parent
from team_directory.lookup import load_lookup, resolve_name

DIRECTORY = load_lookup(ROOT / 'team_directory' / 'ncaa_teams.csv', ROOT / 'team_directory' / 'editorial_names.csv', ROOT / 'team_directory' / 'external_opponents.csv')

def slug(value):
    return resolve_name(value, DIRECTORY)


def read_reference(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        rows=list(csv.DictReader(f))
    required={'date','division','visitor','home','visitor_score','home_score','status'}
    if not rows or not required.issubset(rows[0]):
        raise ValueError('Reference CSV missing expected columns')
    return rows

def fetch_season(config, season, last_week, fetch=get_json, pause=0.4):
    # Include week 0: early-season football can begin before the week 1 anchor.
    games={}; failures=[]; endpoints=[]; warnings=[]; endpoint_coverage=[]
    for division in DIVISIONS:
        for week in range(0,last_week+1):
            endpoint=f'{division}/{week:02d}'
            try:
                payload=fetch(f'{BASE}/scoreboard/football/{division}/{season}/{week:02d}')
                if not isinstance(payload,dict) or not isinstance(payload.get('games'),list):
                    raise ValueError('Missing games array')
                endpoints.append(endpoint)
                dates=sorted({str(x.get('game',{}).get('startDate','')) for x in payload['games'] if isinstance(x,dict) and isinstance(x.get('game'),dict) and x['game'].get('startDate')})
                endpoint_coverage.append({'endpoint':endpoint,'games_returned':len(payload['games']),'first_game_date':dates[0] if dates else '', 'last_game_date':dates[-1] if dates else ''})
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
    return list(games.values()),endpoints,warnings,endpoint_coverage

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

def read_exceptions(path):
    if not path.exists():
        raise FileNotFoundError('Missing required editorial exception register: ' + str(path))
    with path.open(newline='', encoding='utf-8-sig') as f:
        rows=list(csv.DictReader(f))
    required={'date','ncaa_game_id','visitor','home','editorial_visitor_score',
              'editorial_home_score','ncaa_visitor_score','ncaa_home_score','review_status'}
    if not rows or not required.issubset(rows[0]):
        raise ValueError('Editorial exceptions register missing required fields')
    by_id={}
    for row in rows:
        gid=row['ncaa_game_id'].strip()
        if not gid or gid in by_id: raise ValueError('Blank or duplicate exception game ID')
        if row['review_status'] != 'approved_editorial_exception':
            raise ValueError('Unapproved exception cannot suppress discrepancy: '+gid)
        by_id[gid]=row
    return by_id


def approved_exception(row, game, editorial, ncaa, exceptions):
    entry=exceptions.get(str(game['id']))
    if not entry: return False
    return (entry['date']==row['date'] and
            slug(entry['visitor'])==slug(row['visitor']) and
            slug(entry['home'])==slug(row['home']) and
            score(entry['editorial_visitor_score'])==score(row['visitor_score']) and
            score(entry['editorial_home_score'])==score(row['home_score']) and
            score(entry['ncaa_visitor_score'])==ncaa[0] and
            score(entry['ncaa_home_score'])==ncaa[1])


def compare(reference,games,active,exceptions=None):
    """Conservative matching: both teams + date (within two days only if unique).

    Never match solely on score, school, or a fuzzy name. Preserve ambiguous cases.
    """
    exceptions = exceptions or {}
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
              'ncaa_status':'','finding':'','notes':'','date_offset_days':'','match_method':'','external_opponent':'','editorial_exception':''}
        if 'louisburg' in pair or str(r['division']).lower()=='juco':
            base['finding']='MANUAL_ONLY';reports.append(base);continue
        base['external_opponent']='yes' if any(v.startswith('external:') for v in pair) else 'no'
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
            if score(r['visitor_score'])==vs and score(r['home_score'])==hs:
                base['finding']='MATCH'
            elif approved_exception(r,g,(score(r['visitor_score']),score(r['home_score'])),(vs,hs),exceptions):
                base['finding']='ACCEPTED_EXCEPTION'
                base['editorial_exception']='yes'
                base['notes']='Approved editorial result differs from NCAA; editorial score retained'
            else:
                base['finding']='SCORE_DISCREPANCY'
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
    p.add_argument('--exceptions',default=str(ROOT/'audit/editorial_exceptions.csv'))
    args=p.parse_args()
    config=load_config(ROOT/'config.json')
    if args.season!=2026:raise SystemExit('This audited reference is for 2026 only')
    if not 0<=args.through_week<=config['max_week']:raise SystemExit('Invalid through-week')
    reference=read_reference(args.reference)
    games,endpoints,warnings,endpoint_coverage=fetch_season(config,args.season,args.through_week)
    exceptions=read_exceptions(Path(args.exceptions))
    report,extra=compare(reference,games,set(config['nc_school_slugs']),exceptions)
    # Diagnostics: never interpret a missing match as an incorrect score.
    all_games, conflicts = collapse_duplicates(games)
    by_team=defaultdict(list)
    for g in all_games:
        for side in ('away','home'):
            by_team[slug(g[side]['ncaa_slug'])].append(g)
    diagnostic=[]
    for r, finding in zip(reference, report):
        if finding['finding'] not in ('UNMATCHED','SCHEDULED_NOT_IN_NCAA','AMBIGUOUS'):
            continue
        team_a,team_b=slug(r['visitor']),slug(r['home'])
        date=parse_day(r['date'])
        candidates_a=by_team.get(team_a,[]);candidates_b=by_team.get(team_b,[])
        both=[g for g in candidates_a if g in candidates_b]
        nearby_a=[g for g in candidates_a if date and parse_day(g['date']) and abs((parse_day(g['date'])-date).days)<=2]
        nearby_b=[g for g in candidates_b if date and parse_day(g['date']) and abs((parse_day(g['date'])-date).days)<=2]
        if both:reason='SAME_TEAMS_OTHER_DATE_OR_DUPLICATE'
        elif nearby_a or nearby_b:reason='ONE_TEAM_PRESENT_NEAR_DATE_CHECK_OPPONENT_ALIAS'
        elif candidates_a or candidates_b:reason='TEAM_PRESENT_ELSEWHERE_CHECK_DATE_OR_COVERAGE'
        else:reason='NEITHER_TEAM_IN_FETCHED_NCAA_DATA'
        diagnostic.append({'date':r['date'],'visitor':r['visitor'],'home':r['home'],
          'visitor_slug':team_a,'home_slug':team_b,'finding':finding['finding'],
          'diagnostic_reason':reason,'visitor_games_in_api':len(candidates_a),
          'home_games_in_api':len(candidates_b),'same_pair_any_date':len(both),
          'visitor_games_near_date':len(nearby_a),'home_games_near_date':len(nearby_b)})
    out=Path(args.outdir)
    write_csv(out/'game_comparison.csv',report,list(report[0]))
    write_csv(out/'unmatched_diagnostics.csv',diagnostic,list(diagnostic[0]) if diagnostic else ['date','visitor','home','diagnostic_reason'])
    write_csv(out/'endpoint_coverage.csv',endpoint_coverage,['endpoint','games_returned','first_game_date','last_game_date'])
    write_csv(out/'ncaa_only_games.csv',extra,['date','division','ncaa_id','away','home','away_score','home_score','status'])
    counts={k:sum(r['finding']==k for r in report) for k in sorted(set(r['finding'] for r in report))}
    summary={'audit_version':'1.5.3','season':args.season,'weeks_checked':list(range(args.through_week+1)),
             'endpoints_successful':len(endpoints),'optional_week_zero_warnings':warnings,'ncaa_games_retrieved':len(games),
             'editorial_records':len(reference),'diagnostic_reason_counts':dict(collections.Counter(d['diagnostic_reason'] for d in diagnostic)),'findings':counts,'ncaa_only_games':len(extra),
             'editorial_precedence':'Google Sheets; report is read-only',
             'approved_exception_count':counts.get('ACCEPTED_EXCEPTION',0),
             'external_opponent_matched_count':sum(r['external_opponent']=='yes' and r['finding'] in ('MATCH','MATCH_NONFINAL','ACCEPTED_EXCEPTION') for r in report),
             'pending_scheduled_count':counts.get('SCHEDULED_NOT_IN_NCAA',0),
             'duplicate_conflicting_game_ids':conflicts,
             'limitations':['Two-team matching with at most 2-day date tolerance; ambiguous cases never auto-resolved','Aliases are explicit; unmatched records require review',
                            'NCAA may not cover non-NCAA opponents','2026 reference is a frozen snapshot, not live Google Sheets'],
             'date_tolerance_matches':sum(r['match_method']=='DATE_TOLERANCE' for r in report),
             'manual_review_required':sum(r['finding'] in ('SCORE_DISCREPANCY','STATUS_DISCREPANCY','AMBIGUOUS','UNMATCHED') for r in report)}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
