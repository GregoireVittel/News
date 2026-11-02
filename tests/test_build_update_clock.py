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
    def test_next_target_in_winter_and_summer(self):
        self.assertEqual(clock.next_target(paris(2026, 11, 3, 8, 0)), paris(2026, 11, 3, 11, 57))
        self.assertEqual(clock.next_target(paris(2026, 7, 1, 19, 30)), paris(2026, 7, 2, 6, 57))
        # A slot less than a minute away counts as passed.
        self.assertEqual(clock.next_target(paris(2026, 11, 3, 11, 56, 30)), paris(2026, 11, 3, 18, 57))

    def test_long_gaps_hop_without_publishing_and_never_exceed_job_limit(self):
        seconds, publish, target = clock.plan(paris(2026, 11, 3, 19, 5))
        self.assertFalse(publish)
        self.assertEqual(seconds, clock.MAX_WAIT.total_seconds())
        self.assertLess(clock.MAX_WAIT, timedelta(minutes=350))
        seconds, publish, _ = clock.plan(paris(2026, 11, 3, 7, 5))
        self.assertTrue(publish)
        self.assertAlmostEqual(seconds, timedelta(hours=4, minutes=52).total_seconds())

    def test_chain_publishes_exactly_three_times_a_day_across_clock_changes(self):
        for start, day in ((paris(2026, 11, 2, 21, 30), '11-03'), (paris(2026, 3, 28, 21, 30), '03-29'),
                           (paris(2026, 10, 24, 21, 30), '10-25'), (paris(2026, 7, 1, 21, 30), '07-02')):
            published = [p for p in simulate(start, 30) if p.startswith(day)]
            self.assertEqual(published, [f'{day} 06:57', f'{day} 11:57', f'{day} 18:57'], start)

    def test_workflow_wiring(self):
        workflow = (ROOT / '.github/workflows/update-clock.yml').read_text()
        self.assertIn('python3 scripts/update_clock.py wait', workflow)
        self.assertIn('gh workflow run daily-edition.yml', workflow)
        self.assertIn('gh workflow run update-clock.yml', workflow)
        self.assertIn('timeout-minutes: 350', workflow)
        self.assertIn('actions: write', workflow)


if __name__ == '__main__':
    unittest.main()
