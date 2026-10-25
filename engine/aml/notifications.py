"""Stable CPU monitor attention detection; ordinary progress never wakes a model."""
from __future__ import annotations
import json
import time

ACTIVE = frozenset(('queued', 'starting', 'running', 'unreachable', 'cancelling'))
FAILURES = frozenset(('failed', 'cancelled', 'lost', 'blocked'))


def changed(cursor, cases, transport, now=None):
    now = time.time() if now is None else now
    old = json.loads(cursor.read_text()) if cursor.exists() else {}
    initialized = old.get('version') == 2
    activity = old.get('activity', {}) if initialized else {}
    events, current = [], {}
    for run, status, summary, positive, marker in cases:
        # JSON roundtrip normalizes tuples, so unchanged markers do not reset
        # the stall clock every time a persisted cursor is read.
        marker = json.loads(json.dumps(marker))
        previous = activity.get(run, {})
        since = previous.get('since', now) if marker == previous.get('marker') else now
        stalled = status in ('starting', 'running') and transport == 0 and now - since >= 1800
        current[run] = dict(status=status, summary=bool(summary), marker=marker, since=since, stalled=stalled)
        if not initialized:
            continue  # First scan/migration is a baseline, not a history replay.
        if status in FAILURES and status != previous.get('status'):
            events.append(['run_failed', run, status])
        if status == 'succeeded' and previous.get('status') != status:
            events.append(['result_ready', run])
        if stalled and not previous.get('stalled'):
            events.append(['run_stalled', run])
    active = any(item['status'] in ACTIVE for item in current.values())
    failures = old.get('transport_failures', 0) + 1 if transport else 0
    outage_started = old.get('outage_started', now) if transport and old.get('transport_failures') else now
    if initialized and active and transport and failures == 3:
        events.append(['transport_persistently_unavailable', outage_started])
    temporary = cursor.with_suffix('.tmp')
    temporary.write_text(json.dumps(dict(version=2, activity=current, transport_failures=failures, outage_started=outage_started)))
    temporary.replace(cursor)
    return bool(events), events
