"""Calendar-day growth plans. Saved batch plans are independent of the catalog."""
import json
from datetime import date, timedelta


def read_plan(value):
    if not value:
        return {}
    return json.loads(value) if isinstance(value, str) else dict(value)


def validate_plan(value):
    plan = read_plan(value)
    if not plan:
        return {}
    stages = plan.get('stages', [])
    if not isinstance(stages, list) or not 1 <= len(stages) <= 20:
        raise ValueError('Add between 1 and 20 growth stages.')
    names, clean = set(), []
    for stage in stages:
        name = str(stage.get('name', '')).strip()
        days = stage.get('days')
        if not name or len(name) > 60 or name.casefold() in names:
            raise ValueError('Stage names must be unique and between 1 and 60 characters.')
        if type(days) is not int or not 1 <= days <= 3650:
            raise ValueError('Each stage needs a whole-number duration of 1–3650 days.')
        names.add(name.casefold())
        clean.append({'name': name, 'days': days})
    interval = plan.get('interval_days', 0)
    lead = plan.get('reminder_days', 2)
    if type(interval) is not int or not 0 <= interval <= 3650:
        raise ValueError('Production interval must be 0 (disabled) or 1–3650 days.')
    if type(lead) is not int or not 0 <= lead <= 30:
        raise ValueError('Reminder lead time must be between 0 and 30 days.')
    if interval and lead >= interval:
        raise ValueError('Reminder lead time must be shorter than the production interval.')
    if sum(item['days'] for item in clean) > 3650:
        raise ValueError('Total maturity cannot exceed 3650 days.')
    return {'version': 1, 'stages': clean, 'interval_days': interval, 'reminder_days': lead}


def schedule(plan_value, start_value):
    plan = read_plan(plan_value)
    if not plan:
        return {}
    start = date.fromisoformat(str(start_value)[:10])
    cursor, stages = start, []
    for stage in plan['stages']:
        end = cursor + timedelta(days=stage['days'])
        stages.append({**stage, 'start_date': cursor.isoformat(), 'end_date': end.isoformat()})
        cursor = end
    interval = plan.get('interval_days', 0)
    return {'stages': stages, 'expected_harvest': cursor.isoformat(),
            'next_batch_start': (start + timedelta(days=interval)).isoformat() if interval else None}


def batch_view(batch):
    return {**batch, 'growth_schedule': schedule(batch.get('production_plan'), batch['start_date'])} if batch.get('production_plan') else batch


def reminder_events(batches, today):
    """One next-start reminder per farm/plant stream; stage reminders per active batch."""
    streams = {}
    for batch in batches:
        plan = read_plan(batch.get('production_plan'))
        if not plan:
            continue
        calendar = schedule(plan, batch['start_date'])
        lead = timedelta(days=plan.get('reminder_days', 2))
        if plan.get('interval_days'):
            key = (batch['farmID'], batch['plant_type_ID'])
            if key not in streams or batch['start_date'] > streams[key]['start_date']:
                streams[key] = batch
        if str(batch.get('production_status', '')).lower() in ('harvested', 'delivered', 'completed'):
            continue
        events = [(s['start_date'], 'stage-' + str(i), 'Growth stage: ' + s['name'])
                  for i, s in enumerate(calendar['stages']) if i > 0]
        events.append((calendar['expected_harvest'], 'harvest', 'Expected harvest'))
        for due, kind, title in events:
            due_date = date.fromisoformat(due)
            # Stage transitions expire at the next stage; harvest remains overdue until completed.
            if kind.startswith('stage-'):
                stage_end = date.fromisoformat(calendar['stages'][int(kind[6:])]['end_date'])
                if today >= stage_end:
                    continue
            if today >= due_date - lead:
                state = 'overdue' if today > due_date else 'due' if today == due_date else 'upcoming'
                yield batch, kind, due, title, state
    for batch in streams.values():
        # A newer legacy batch also fulfills a planned start; never remind from an older plan.
        if any(b['farmID'] == batch['farmID'] and b['plant_type_ID'] == batch['plant_type_ID']
               and b['start_date'] > batch['start_date'] for b in batches):
            continue
        plan = read_plan(batch['production_plan'])
        due = schedule(plan, batch['start_date'])['next_batch_start']
        due_date = date.fromisoformat(due)
        if today >= due_date - timedelta(days=plan.get('reminder_days', 2)):
            state = 'overdue' if today > due_date else 'due' if today == due_date else 'upcoming'
            yield batch, 'next-batch', due, 'Start the next batch', state
