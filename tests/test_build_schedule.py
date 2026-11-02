"""The publish schedule hits 07:00, 12:00 and 19:00 Paris time all year."""
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import schedule_gate as gate  # noqa: E402

WINTER = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)   # CET, UTC+1
SUMMER = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)    # CEST, UTC+2
SPRING_FORWARD = datetime(2026, 3, 29, 12, tzinfo=timezone.utc)
FALL_BACK = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)


def allowed(now):
    return sorted(c for c in gate.utc_crons() if gate.should_run(c, now))


class ScheduleTests(unittest.TestCase):
    def test_exactly_three_runs_publish_each_day_all_year(self):
        self.assertEqual(allowed(WINTER), ['57 10 * * *', '57 17 * * *', '57 5 * * *'])
        self.assertEqual(allowed(SUMMER), ['57 16 * * *', '57 4 * * *', '57 9 * * *'])
        for day in (SPRING_FORWARD, FALL_BACK):
            self.assertEqual(len(allowed(day)), 3, day)

    def test_manual_runs_always_publish(self):
        self.assertTrue(gate.should_run(''))
        self.assertEqual(gate.SLOTS, ('06:57', '11:57', '18:57'))

    def test_workflow_lists_every_needed_cron_and_gates_publish(self):
        workflow = (ROOT / '.github/workflows/daily-edition.yml').read_text()
        crons = re.findall(r"- cron: '([^']+)'", workflow)
        self.assertEqual(sorted(crons), gate.utc_crons())
        self.assertIn("if: needs.gate.outputs.run == 'true'", workflow)
        self.assertIn('scripts/schedule_gate.py "$CRON"', workflow)


if __name__ == '__main__':
    unittest.main()
