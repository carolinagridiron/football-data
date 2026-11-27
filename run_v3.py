#!/usr/bin/env python3
"""Opt-in candidate: verify season and collect only when NCAA weeks are active."""
import argparse,datetime as dt,json
from pathlib import Path
from zoneinfo import ZoneInfo
from season_runtime import collection_plan
from collector_v30a import collect, load_config
from archive_collector import atomic_json

def execute(day, config, fetch=None):
    plan=collection_plan(day,config)
    if plan['mode']=='offseason':return plan,None
    if fetch is None: result=collect(config,day)
    else: result=collect(config,day,fetch=fetch)
    if result['season'] != plan['season']:raise ValueError('Collector season mismatch')
    if not result['games'] and not config.get('allow_empty_game_feed',False):
        raise ValueError('Empty feed refused: existing published feed retained')
    return plan,result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--date')
    p.add_argument('--config',default='config_v3.json')
    p.add_argument('--output',default='build/v3-preview/nc-scores.json')
    p.add_argument('--write',action='store_true')
    a=p.parse_args()
    day=dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(ZoneInfo('America/New_York')).date()
    plan,result=execute(day,load_config(a.config))
    print(json.dumps({'plan':plan,'game_count':len(result['games']) if result else 0},indent=2))
    if a.write and result is not None:atomic_json(Path(a.output),result)
    else:print('NO PUBLICATION: read-only or offseason')
if __name__=='__main__':main()
