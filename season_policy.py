"""Safe football season selection. July 1 starts the next operating season."""
import datetime as dt

class SeasonNotReady(ValueError):
    pass

def football_season(day, start_month=7, start_day=1):
    return day.year if (day.month, day.day) >= (start_month, start_day) else day.year - 1

def resolve(day, config):
    if config.get('schema_version') == 2:
        op = config.get('operating_year', {})
        year = football_season(day, int(op.get('start_month', 7)), int(op.get('start_day', 1)))
        season = config.get('seasons', {}).get(str(year))
        if not season or season.get('verified') is not True:
            raise SeasonNotReady(f'Season {year} is not verified; existing published feed must remain unchanged')
        for field in ('week_anchor_date','week_anchor_number','max_week','nc_school_slugs'):
            if season.get(field) is None:
                raise SeasonNotReady(f'Season {year} missing {field}')
        anchor = dt.date.fromisoformat(season['week_anchor_date'])
        if anchor.year != year or int(season['max_week']) < 1 or not season['nc_school_slugs']:
            raise SeasonNotReady(f'Season {year} has invalid configuration')
        return year, season
    # Backward-compatible legacy configuration: verified only for its anchor year.
    year = dt.date.fromisoformat(config['week_anchor_date']).year
    if football_season(day) != year:
        raise SeasonNotReady('Legacy configuration is not verified for this season')
    return year, config
