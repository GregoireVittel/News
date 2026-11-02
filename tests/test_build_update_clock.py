"""The self-running update clock hits 06:57, 11:57 and 18:57 Paris time."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import update_clock as clock  # noqa: E402

PARIS = clock.PARIS


def paris(*args):
    return datetime(*args, tzinfo=PARIS).astimezone(timezone.utc)


def simulate(start, hours):
    """Follow the chain like the workflow does; return Paris times it publishes."""
    now, end, published = start, start + timedelta(hours=hours), []
    while now < end:
        seconds, publish, _ = clock.plan(now)
        now += timedelta(seconds=seconds + 40)   # job start-up / dispatch overhead
        if publish:
            published.append((now - timedelta(seconds=40)).astimezone(PARIS).strftime('%m-%d %H:%M'))
    return published


class UpdateClockTests(unittest.TestCase):
    def test_next_target_is_the_coming_hour_at_57(self):
        self.assertEqual(clock.next_target(paris(2026, 11, 3, 8, 0)), paris(2026, 11, 3, 8, 57))
        self.assertEqual(clock.next_target(paris(2026, 7, 1, 23, 58)), paris(2026, 7, 2, 0, 57))
        # A slot less than a minute away counts as passed.
        self.assertEqual(clock.next_target(paris(2026, 11, 3, 11, 56, 30)), paris(2026, 11, 3, 12, 57))

    def test_every_wait_publishes_and_stays_under_an_hour(self):
        for minute in range(0, 60, 7):
            seconds, publish, _ = clock.plan(paris(2026, 11, 3, 14, minute))
            self.assertTrue(publish)
            self.assertLessEqual(seconds, 3600)
        self.assertLess(clock.MAX_WAIT, timedelta(minutes=350))

    def test_chain_publishes_every_hour_including_clock_change_days(self):
        def hours(day):
            return [f'{day} {h:02d}:57' for h in range(24)]
        for start, day in ((paris(2026, 11, 2, 23, 30), '11-03'), (paris(2026, 7, 1, 23, 30), '07-02')):
            self.assertEqual([p for p in simulate(start, 26) if p.startswith(day)], hours(day))
        # Spring forward: 02:57 does not exist, so 23 updates that day.
        spring = [p for p in simulate(paris(2026, 3, 28, 23, 30), 26) if p.startswith('03-29')]
        self.assertEqual(spring, [h for h in hours('03-29') if h != '03-29 02:57'])
        # Fall back: still one update per wall-clock hour, never two at once.
        fall = [p for p in simulate(paris(2026, 10, 24, 23, 30), 27) if p.startswith('10-25')]
        self.assertEqual(sorted(set(fall)), hours('10-25'))
        self.assertLessEqual(len(fall), 25)

    def test_workflow_wiring(self):
        workflow = (ROOT / '.github/workflows/update-clock.yml').read_text()
        self.assertIn('python3 scripts/update_clock.py wait', workflow)
        self.assertIn('gh workflow run daily-edition.yml', workflow)
        self.assertIn('gh workflow run update-clock.yml', workflow)
        self.assertIn('timeout-minutes: 350', workflow)
        self.assertIn('actions: write', workflow)


if __name__ == '__main__':
    unittest.main()
