import json
import math
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from scripts import sentiment
from test_build_edition import builder, FEED, RSS


def weekdays(count, start=date(2020, 1, 1)):
    days, day = [], start
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day.isoformat())
        day += timedelta(days=1)
    return days


def series(count=700, crash_at=None):
    """Smooth synthetic markets; an optional crash makes the last days fearful."""
    days = weekdays(count)
    cac, chf, gold, usd = {}, {}, {}, {}
    level = 5000.0
    for i, day in enumerate(days):
        level *= 1 + 0.004 * math.sin(i / 7) + (0.0006 if crash_at is None or i < crash_at else -0.02 + 0.04 * (-1) ** i)
        cac[day] = level
        chf[day] = 1.05 + 0.02 * math.sin(i / 11) - (0.002 * (i - crash_at) if crash_at and i >= crash_at else 0)
        gold[day] = 1800 + 50 * math.sin(i / 13) + (15 * (i - crash_at) if crash_at and i >= crash_at else 0)
        usd[day] = 1.1
    return dict(cac=cac, eurchf=chf, gold=gold, eurusd=usd)


class SentimentTests(unittest.TestCase):
    def test_rank_is_a_percentile_with_ties_counting_half(self):
        self.assertEqual(sentiment.rank([1, 2, 3, 4], 4), 87.5)
        self.assertEqual(sentiment.rank([1, 2, 3, 4], 0), 0)
        self.assertEqual(sentiment.rank([5, 5], 5), 50)

    def test_index_needs_a_year_of_history_and_averages_the_legs(self):
        rows = sentiment.compute(series())
        self.assertTrue(rows)
        first = date.fromisoformat(rows[0]['date'])
        self.assertGreaterEqual((first - date(2020, 1, 1)).days, 360)
        row = rows[-1]
        self.assertEqual(set(row['legs']), {'momentum', 'volatility', 'haven', 'gold'})
        self.assertAlmostEqual(row['index'], sum(l['score'] for l in row['legs'].values()) / 4, delta=0.06)

    def test_a_crash_reads_as_extreme_fear_and_volatility_is_flipped(self):
        rows = sentiment.compute(series(700, crash_at=690))
        last = rows[-1]
        self.assertEqual(sentiment.band(last['index']), 'Extreme fear')
        self.assertLess(last['legs']['volatility']['score'], 5)  # wild swings rank high, then flip to fear
        self.assertGreater(last['legs']['volatility']['raw'], 30)

    def test_history_is_not_rewritten_when_new_days_arrive(self):
        full = sentiment.compute(series(700))
        cut = sentiment.compute({k: dict(list(v.items())[:650]) for k, v in series(700).items()})
        self.assertEqual(cut[-1], next(r for r in full if r['date'] == cut[-1]['date']))

    def test_missing_input_leaves_out_its_leg(self):
        data = series()
        del data['gold']
        self.assertEqual(set(sentiment.compute(data)[-1]['legs']), {'momentum', 'volatility', 'haven'})

    def test_bands(self):
        self.assertEqual([sentiment.band(v) for v in (0, 24.9, 25, 50, 55, 75, 100)],
                         ['Extreme fear', 'Extreme fear', 'Fear', 'Neutral', 'Greed', 'Extreme greed', 'Extreme greed'])

    def test_csv_and_page(self):
        rows = sentiment.compute(series())
        text = sentiment.csv_text(rows)
        self.assertTrue(text.startswith('date,index,momentum_raw,momentum_score'))
        self.assertEqual(text.count('\n'), len(rows) + 1)
        html = sentiment.page(rows, dict(tone=-20, stories=60), 'https://example.test/', '')
        for part in ('One number from 0 to 100', 'Where today sits in the record', 'The four market readings',
                     'Equity momentum', 'Volatility', 'Safe haven', 'Stocks vs gold', 'not in the index',
                     'The index through time', 'sentiment.csv', 'How the index is built', 'class="gauge"'):
            self.assertIn(part, html)
        self.assertNotIn('<script', html)
        self.assertIn('Market data is not available yet', sentiment.page([], None, 'https://example.test/', ''))


class SentimentBuildTests(unittest.TestCase):
    def test_build_publishes_sentiment_and_keeps_last_values_when_data_fails(self):
        module = builder()
        now = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        data = series()

        def yahoo(url):
            for key, symbol in sentiment.SYMBOLS.items():
                if symbol.replace('^', '%5E').replace('=', '%3D') in url and 'range=10y' in url:
                    stamps = [int(datetime.fromisoformat(d + 'T12:00:00+00:00').timestamp()) for d in data[key]]
                    return json.dumps({'chart': {'result': [{'timestamp': stamps, 'indicators': {'quote': [
                        {'close': list(data[key].values())}]}}]}}).encode()
            raise OSError('not available')

        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / 'first'
            result = module.build(first, 'https://example.test/News/', now=now, feeds=[FEED], fetcher=lambda feed: RSS,
                                  history_root=Path(temp) / 'empty', market_fetcher=yahoo)
            self.assertEqual(result['market']['sentiment']['errors'], [])
            html = (first / 'sentiment/index.html').read_text()
            self.assertIn('<h1>Sentiment</h1>', html)
            self.assertIn('aria-current="page">Sentiment</a>', html)
            self.assertIn('href="https://example.test/News/sentiment/">Sentiment</a>', (first / 'index.html').read_text())
            saved = json.loads((first / 'sentiment.json').read_text())['days']
            self.assertTrue(saved)

            def broken(url):
                raise OSError('offline')
            second = Path(temp) / 'second'
            module.build(second, 'https://example.test/News/', now=now, feeds=[FEED], fetcher=lambda feed: RSS,
                         history_root=first, market_fetcher=broken)
            self.assertEqual(json.loads((second / 'sentiment.json').read_text())['days'], saved)
            self.assertIn('showing the last saved values', (second / 'sentiment/index.html').read_text())


if __name__ == '__main__':
    unittest.main()
