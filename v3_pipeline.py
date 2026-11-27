#!/usr/bin/env python3
"""Safe season-aware pipeline. No publication during offseason or unverified season.

Production writes are explicit and gated. Run on a clean repository checkout.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo
from run_v3 import execute
from collector_v30a import load_config
from archive_collector import atomic_json
from incremental_v30b import execute as detail_execute


def pipeline(day, config_path, feed_path, archive_root, details_root, write=False,
             fetch=None, details_engine=None, details_publisher=None):
    config = load_config(config_path)
    plan, feed = execute(day, config, fetch=fetch)
    report = {'date':day.isoformat(), 'plan':plan, 'feed_published':False,
              'details_published':False, 'detail_warning':None}
    if feed is None:
        return report
    if write:
        atomic_json(Path(feed_path),feed)
        report['feed_published']=True
    # Details are independent of scoreboard publication. The feed must be available
    # on disk before detail enrichment, so read-only simulations do not call it.
    if not write:
        report['game_count']=len(feed['games'])
        return report
    try:
        kw={}
        if details_engine is not None: kw['engine']=details_engine
        if details_publisher is not None: kw['publisher']=details_publisher
        detail_report=detail_execute(feed_path,config_path,archive_root,details_root,day,
                                     write=True,**kw)
        report['details_published']=True
        report['detail_report']=detail_report
    except Exception as exc:
        report['detail_warning']=str(exc)[:300]
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--date')
    p.add_argument('--config',default='config_v3.json')
    p.add_argument('--feed',default='public/nc-scores.json')
    p.add_argument('--archive-root',default='public/archive')
    p.add_argument('--details-root',default='public/game-details')
    p.add_argument('--write',action='store_true')
    a=p.parse_args()
    day=dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(ZoneInfo('America/New_York')).date()
    report=pipeline(day,a.config,a.feed,a.archive_root,a.details_root,write=a.write)
    print(json.dumps(report,indent=2))
    if report['detail_warning']:
        print('::warning::Detail enrichment needs review: '+report['detail_warning'])

if __name__=='__main__':main()
