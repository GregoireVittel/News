#!/usr/bin/env python3
"""Self-running update clock for the news site (used by update-clock.yml).

GitHub's cron schedule proved unreliable for this repository (runs hours late
or not at all), but workflows started with workflow_dispatch run immediately.
So the clock workflow waits inside a job until just before the next Paris
publication slot, starts the publish workflow, then starts itself again.
A job may run for at most 6 hours, so longer gaps are covered by several hops.

Usage in the workflow:  update_clock.py wait
  Prints the plan, sleeps, then writes publish=true|false to $GITHUB_OUTPUT.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import os
import sys
import time

PARIS = ZoneInfo('Europe/Paris')
# Start publishing 3 minutes early so the site is rebuilt by 07:00, 12:00, 19:00.
TARGETS = ((6, 57), (11, 57), (18, 57))
MAX_WAIT = timedelta(hours=5, minutes=30)   # stays under the 6-hour job limit
MIN_LEAD = timedelta(minutes=1)             # a slot this close is treated as passed


def next_target(now):
    """The next publication start time (aware, UTC) at least MIN_LEAD after now."""
    local = now.astimezone(PARIS)
    for day in range(3):
        date = (local + timedelta(days=day)).date()
        for hour, minute in TARGETS:
            target = datetime(date.year, date.month, date.day, hour, minute, tzinfo=PARIS)
            if target - now >= MIN_LEAD:
                return target.astimezone(timezone.utc)
    raise RuntimeError('no target found')  # unreachable: there are slots every day


def plan(now):
    """Return (seconds_to_wait, publish_after_waiting, target)."""
    target = next_target(now)
    wait = target - now
    if wait <= MAX_WAIT:
        return wait.total_seconds(), True, target
    return MAX_WAIT.total_seconds(), False, target


def main():
    if sys.argv[1:] != ['wait']:
        print(__doc__)
        return 2
    now = datetime.now(timezone.utc)
    seconds, publish, target = plan(now)
    print(f'Now {now.astimezone(PARIS):%Y-%m-%d %H:%M} Paris; next slot {target.astimezone(PARIS):%Y-%m-%d %H:%M} Paris.')
    print(f'Waiting {seconds / 3600:.2f} h, then ' + ('publishing.' if publish else 'handing over to the next clock run.'), flush=True)
    time.sleep(seconds)
    with open(os.environ.get('GITHUB_OUTPUT', os.devnull), 'a', encoding='utf-8') as out:
        out.write(f'publish={str(publish).lower()}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
