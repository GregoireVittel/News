import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts import barometer
from test_build_edition import builder, FEED, RSS

UTC = timezone.utc


def story(title, when, section='France', link=None, description=''):
    return dict(title=title, description=description, date=when, section=section,
                link=link or 'https://example.test/' + title.replace(' ', '-'))


class ScoringTests(unittest.TestCase):
    def test_tone_counts_market_words_in_french_english_and_polish(self):
        self.assertEqual(barometer.score(story('Le CAC 40 chute, la crise menace', None))['neg'], 3)
        self.assertEqual(barometer.score(story('Stocks rally as profits jump', None))['pos'], 3)
        self.assertEqual(barometer.score(story('Spadek WIG, straty banków', None))['neg'], 2)
        self.assertEqual(barometer.tone(3, 1), 50)
        self.assertEqual(barometer.tone(0, 0), 0)

    def test_words_inside_other_words_do_not_count(self):
        # "j'ai" is not AI, "important" is not imports, "according" is not an accord, "strategy" is not a Polish loss.
        result = barometer.score(story("J'ai une strategy important according to plan", None))
        self.assertEqual((result['pos'], result['neg'], result['themes']), (0, 0, []))

    def test_themes_are_cac40_sectors_and_market_drivers(self):
        self.assertEqual(barometer.score(story('Les droits de douane menacent le luxe', None))['themes'], ['luxury', 'trade'])
        self.assertIn('rates', barometer.score(story('ECB holds interest rates', None))['themes'])
        kinds = {kind for _, _, kind, _ in barometer.THEMES}
        self.assertEqual(kinds, {'sector', 'driver'})

    def test_news_after_the_close_or_at_the_weekend_counts_for_the_next_session(self):
        paris = barometer.PARIS
        self.assertEqual(barometer.session_for(datetime(2026, 11, 4, 17, 29, tzinfo=paris)), '2026-11-04')
        self.assertEqual(barometer.session_for(datetime(2026, 11, 4, 17, 30, tzinfo=paris)), '2026-11-05')
        self.assertEqual(barometer.session_for(datetime(2026, 11, 6, 18, 0, tzinfo=paris)), '2026-11-09')
        self.assertEqual(barometer.session_for(datetime(2026, 11, 8, 12, 0, tzinfo=paris)), '2026-11-09')


class HistoryTests(unittest.TestCase):
    def test_hourly_builds_do_not_double_count_and_other_sections_are_ignored(self):
        now = datetime(2026, 11, 4, 12, tzinfo=UTC)
        items = [story('CAC 40 rally', now - timedelta(hours=1)),
                 story('Bourse en baisse', now - timedelta(hours=2), section='Financial'),
                 story('World war news', now - timedelta(hours=1), section='World')]
        first = barometer.update({}, items, now)
        second = barometer.update(json.loads(json.dumps(first)), items, now + timedelta(hours=1))
        self.assertEqual(second['sessions']['2026-11-04']['stories'], 2)
        self.assertEqual(second['sessions'], first['sessions'])

    def test_old_story_scores_fold_into_sessions_and_market_merges(self):
        now = datetime(2026, 11, 4, 12, tzinfo=UTC)
        first = barometer.update({}, [story('CAC 40 rally', now - timedelta(hours=1))], now,
                                 {'2026-11-03': 8000.0, '2026-11-04': 8080.0})
        later = barometer.update(first, [], now + timedelta(days=30), {'2026-12-04': 8100.0})
        self.assertEqual(later['pending'], {})
        self.assertEqual(later['sessions']['2026-11-04']['stories'], 1)
        self.assertEqual(sorted(later['market']), ['2026-11-03', '2026-11-04', '2026-12-04'])
        self.assertEqual(barometer.returns(later['market'])['2026-11-04'], 1.0)

    def test_correlation(self):
        self.assertEqual(barometer.pearson([(1, 2), (2, 4), (3, 6)]), 1.0)
        self.assertEqual(barometer.pearson([(1, 3), (2, 2), (3, 1)]), -1.0)
        self.assertIsNone(barometer.pearson([(1, 1), (2, 2)]))


class MarketTests(unittest.TestCase):
    def test_yahoo_then_stooq_fallback(self):
        yahoo = json.dumps({'chart': {'result': [{'timestamp': [1762156800 + i * 86400 for i in range(6)],
                                                  'indicators': {'quote': [{'close': [8000, 8010, None, 8030, 8040, 8050]}]}}]}}).encode()
        closes, source, errors = barometer.fetch_market(lambda url: yahoo if 'yahoo' in url else b'')
        self.assertEqual(source, 'Yahoo Finance')
        self.assertEqual(len(closes), 5)  # the missing close is skipped
        stooq = ('Date,Open,High,Low,Close,Volume\n' + ''.join(
            f'2026-11-0{d},1,1,1,{8000 + d},0\n' for d in range(2, 8))).encode()

        def get(url):
            if 'yahoo' in url:
                raise OSError('blocked')
            return stooq
        closes, source, errors = barometer.fetch_market(get)
        self.assertEqual((source, closes['2026-11-07']), ('Stooq', 8007.0))
        self.assertEqual(len(errors), 1)
        self.assertEqual(barometer.fetch_market(lambda url: b'nonsense')[1], None)


class PageTests(unittest.TestCase):
    def test_build_writes_barometer_page_and_history_and_survives_market_failure(self):
        module = builder()
        now = datetime(2026, 11, 1, 12, tzinfo=UTC)

        def broken(url):
            raise OSError('no network')
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'site'
            result = module.build(output, 'https://example.test/News/', now=now, feeds=[FEED],
                                  fetcher=lambda feed: RSS, history_root=Path(temp) / 'empty', market_fetcher=broken)
            self.assertIsNone(result['market']['source'])
            self.assertEqual(len(result['market']['errors']), 2)
            html = (output / 'barometer/index.html').read_text()
            for text in ('<h1>Barometer</h1>', 'class="gauge"', 'CAC 40 sectors and market drivers',
                         'could not be updated', 'How this is measured', 'aria-current="page">Barometer</a>'):
                self.assertIn(text, html)
            self.assertNotIn('<script', html)
            self.assertEqual(json.loads((output / 'barometer.json').read_text())['schemaVersion'], 1)
            self.assertIn('href="https://example.test/News/barometer/">Barometer</a>', (output / 'index.html').read_text())
            self.assertIn('https://example.test/News/barometer/', (output / 'sitemap.xml').read_text())

    def test_correlations_appear_only_with_enough_sessions(self):
        start = datetime(2026, 9, 1, 9, tzinfo=UTC)
        items, market, day = [], {}, start
        for i in range(30):
            while day.weekday() >= 5:
                day += timedelta(days=1)
            good = i % 2 == 0
            for j in range(6):
                items.append(story(('Bourse en hausse' if good else 'Bourse en baisse') + f' {i}-{j}', day + timedelta(minutes=j)))
            market[day.date().isoformat()] = 8000 + (40 if good else -40) + i
            day += timedelta(days=1)
        history = barometer.update({}, items, day)
        history['market'] = market
        html = barometer.page(history, [], day, 'https://example.test/', '')
        self.assertIn('Same session</span><span class="stat-value">r = +', html)
        few = dict(history, sessions=dict(list(history['sessions'].items())[:5]))
        self.assertIn('Correlations appear once 20', barometer.page(few, [], day, 'https://example.test/', ''))


if __name__ == '__main__':
    unittest.main()
