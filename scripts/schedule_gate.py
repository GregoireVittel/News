#!/usr/bin/env python3
"""Decide whether a scheduled run should publish, in Europe/Paris time.

GitHub cron schedules are UTC-only, so the workflow lists the UTC times for both
winter (CET, UTC+1) and summer (CEST, UTC+2). Each scheduled run checks the cron
line that triggered it: it publishes only when that line's UTC time is a Paris
publication slot today. Using the cron line rather than the clock keeps the
decision correct even when GitHub starts a job late.

Usage: schedule_gate.py "<cron expression>"   (empty for a manual run)
Prints run=true|false for $GITHUB_OUTPUT.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import sys

PARIS = ZoneInfo('Europe/Paris')
# Publication slots (Paris time). Runs start 3 minutes early so the site is
# rebuilt by 07:00, 12:00 and 19:00; GitHub delays jobs queued on the hour.
SLOTS = ('06:57', '11:57', '18:57')


def should_run(cron, now=None):
    """True for manual runs, or when the triggering cron time is a Paris slot today."""
    if not cron.strip():
        return True
    minute, hour = cron.split()[:2]
    now = now or datetime.now(timezone.utc)
    scheduled = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
    return scheduled.astimezone(PARIS).strftime('%H:%M') in SLOTS


def utc_crons():
    """Every UTC cron line needed to hit SLOTS in both CET and CEST."""
    times = set()
    for offset in (1, 2):
        for slot in SLOTS:
            hour, minute = map(int, slot.split(':'))
            times.add(((hour - offset) % 24, minute))
    return sorted(f'{minute} {hour} * * *' for hour, minute in times)


if __name__ == '__main__':
    print(f'run={str(should_run(sys.argv[1] if len(sys.argv) > 1 else "")).lower()}')
