"""Narrow, auditable paraphrase matching, not broad topic clustering."""
import unittest
from scripts.story_events import same_event


class EventMatchingTests(unittest.TestCase):
    def test_resumed_service_paraphrases_need_same_entity_action_and_object(self):
        pairs = [
            ('Binance resumes withdrawals following $6.3 billion breach',
             'Binance Resumes Withdrawals After Suffering Biggest-Ever Crypto Hack'),
            ('La plateforme Binance annonce une reprise des retraits après un piratage',
             'Binance resumes withdrawals following a breach'),
            ('Eurostar resumes trains after strike', 'Eurostar restarts train services after walkout'),
        ]
        for left, right in pairs:
            with self.subTest(left=left):
                self.assertTrue(same_event(left, right))
                self.assertTrue(same_event(right, left))

    def test_different_entity_outcome_number_or_object_remains_separate(self):
        original = 'Binance resumes withdrawals following $6.3 billion breach'
        for other in (
            'Coinbase resumes withdrawals following $6.3 billion breach',
            'Binance suspends withdrawals following $6.3 billion breach',
            'Binance resumes deposits following $6.3 billion breach',
            'Binance resumes withdrawals following $2 billion breach',
            'Binance resumes withdrawals following scheduled maintenance',
            'Binance CEO says stolen assets have been replenished',
            'North Korea linked to massive Binance crypto heist',
        ):
            with self.subTest(other=other):
                self.assertFalse(same_event(original, other))
