"""Season-aware collection gate. No network calls during the offseason."""
import datetime as dt
from season_policy import resolve, SeasonNotReady

def collection_plan(day, config):
    year, settings = resolve(day, config)
    anchor = dt.date.fromisoformat(settings['week_anchor_date'])
    week = int(settings['week_anchor_number']) + (day - anchor).days // 7
    max_week = int(settings['max_week'])
    if week < 1 or week > max_week + 1:
        return {'season': year, 'mode': 'offseason', 'weeks': []}
    weeks = [w for w in (week-1,week,week+1) if 1 <= w <= max_week]
    return {'season': year, 'mode': 'collect' if weeks else 'offseason', 'weeks': weeks}
