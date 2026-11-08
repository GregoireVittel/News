"""TEST ONLY offline Financial/BNP contracts; no production generation."""
import unittest
import json
from unittest.mock import patch
from pathlib import Path
import tempfile
from datetime import datetime, timezone
import build as legacy
from scripts import build_edition as static
from test_build_classification import article
from scripts.story_classification import enrich_articles


class FinancialTests(unittest.TestCase):
    def test_shared_renderer_nests_subgroup_counts_without_duplicate_cards(self):
        stories = enrich_articles([
            article('BNP Paribas invests in AI software', link='https://news.google.com/rss/articles/bnp', aggregator=True),
            article('French banks report higher profits', link='https://example.test/banks')])
        now = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        rendered = static.edition_page(stories, 'https://example.test/', '', 'All', now, [])
        self.assertEqual(static.SECTIONS, ('Poland', 'France', 'World', 'Technology', 'Financial'))
        self.assertIn('href="#financial">Global Markets</a>', rendered)
        self.assertIn('href="#bnp-paribas">BNP Paribas</a>', rendered)
        self.assertIn('id="bnp-paribas"', rendered)
        financial = rendered.split('id="financial"', 1)[1].split('id="technology"', 1)[0]
        self.assertIn('2 stories', financial)
        self.assertIn('1 story', financial.split('id="bnp-paribas"', 1)[1])
        self.assertEqual(rendered.count('<article '), 2)
        self.assertLess(financial.index('French banks'), financial.index('id="bnp-paribas"'))
        self.assertIn('BNP Paribas invests', financial.split('id="bnp-paribas"', 1)[1])
        self.assertIn('Google News', rendered)
        self.assertIn('redirect', rendered.lower())
        empty = static.edition_page([], 'https://example.test/', '', 'All', now, [])
        self.assertIn('No BNP Paribas stories in this edition.', empty)

    def test_legacy_generation_preserves_subgroup_and_aggregation(self):
        now = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        entry = dict(title='BNP Paribas invests in AI software', source='TEST ONLY Publisher',
                     link='https://news.google.com/rss/articles/bnp', language='en',
                     category='Financial markets and economics', summary='TEST ONLY RSS text',
                     published=now, subgroup='BNP Paribas', aggregator=True)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'live.html').write_text('<style></style>')
            legacy.generate(root, [entry], now)
            data = json.loads((root / 'articles.json').read_text())
            self.assertEqual(data['sections'], ['Poland', 'France', 'World', 'Technology', 'Financial'])
            self.assertEqual(data['articles'][0]['subgroup'], 'BNP Paribas')
            self.assertTrue(data['articles'][0]['aggregator'])
            self.assertIn('id="bnp-paribas"', (root / 'index.html').read_text())

    def test_bnp_only_financial_section_is_not_reported_empty(self):
        stories = enrich_articles([article('BNP Paribas announces partnership')])
        rendered = static.edition_page(stories, 'https://example.test/', '', 'All',
                                       datetime(2026, 11, 1, tzinfo=timezone.utc), [])
        financial = rendered.split('id="financial"', 1)[1].split('id="technology"', 1)[0]
        self.assertNotIn('No stories in this section', financial)

    def test_legacy_keeps_explicit_evidence_beyond_snippet_length(self):
        description = 'TEST ONLY supplied RSS text ' * 12 + 'BNP Paribas expands in Poland'
        data = ('<rss><channel><item><title>New partnership announced</title>'
                '<link>https://example.test/long</link><pubDate>Sun, 01 Nov 2026 11:00:00 GMT</pubDate>'
                '<description>' + description + '</description></item></channel></rss>').encode()
        parsed = legacy.parse_feed(data, 'TEST ONLY Publisher', 'en',
                                   'Financial markets and economics', subgroup='BNP Paribas')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'live.html').write_text('<style></style>')
            legacy.generate(root, parsed, datetime(2026, 11, 1, 12, tzinfo=timezone.utc))
            story = json.loads((root / 'articles.json').read_text())['articles'][0]
            self.assertEqual(story.get('subgroup'), 'BNP Paribas')

    def test_cluster_keeps_bnp_membership_from_nonrepresentative_coverage(self):
        items = [article('Bank partnership update', description='', link='https://a.test/story'),
                 article('Bank partnership update', description='BNP Paribas invests in software',
                         link='https://b.test/story', sourceName='TEST ONLY second')]
        result = enrich_articles(items)
        self.assertEqual(len(result), 2)  # Short generic titles alone are not identity evidence.
        items[1]['link'] = items[0]['link']
        result = enrich_articles(items)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['subgroup'], 'BNP Paribas')
        self.assertEqual(result[0]['section'], 'Financial')
        self.assertEqual(result[0]['sourceCount'], 2)
        self.assertEqual({s['name'] for s in result[0]['sources']}, {'Example', 'TEST ONLY second'})

    def test_google_parser_paths_keep_real_publisher_and_filter_only_subgroup_feed(self):
        feed = dict(name='Google News — BNP Paribas (FR)', url='https://news.google.com/rss/search?q=bnp',
                    language='fr', category='Financial markets and economics', subgroup='BNP Paribas', aggregator=True)
        data = b'''<rss><channel><item><title>BNP Paribas expands in Poland</title><link>https://news.google.com/rss/articles/test</link><pubDate>Sun, 01 Nov 2026 11:00:00 GMT</pubDate><source url="https://publisher.test">TEST ONLY Publisher</source><description>TEST ONLY supplied RSS text</description></item></channel></rss>'''
        parsed = static.parse_feed(data, feed)[0]
        old = legacy.parse_feed(data, feed['name'], 'fr', feed['category'], subgroup='BNP Paribas', aggregator=True)[0]
        self.assertEqual(parsed['sourceName'], 'TEST ONLY Publisher')
        self.assertEqual(old['source'], 'TEST ONLY Publisher')
        for item in (parsed, old):
            self.assertEqual(item['subgroup'], 'BNP Paribas')
            self.assertTrue(item['aggregator'])
            self.assertEqual(item['link'], 'https://news.google.com/rss/articles/test')
        self.assertEqual(parsed['description'], 'TEST ONLY supplied RSS text')
        self.assertEqual(old['summary'], parsed['description'])
        for title in (b'Unrelated bank profits rise', b'BNP Paribas Open tennis final at Indian Wells'):
            other = data.replace(b'BNP Paribas expands in Poland', title)
            self.assertEqual(static.parse_feed(other, feed), [])
            self.assertEqual(legacy.parse_feed(other, feed['name'], 'fr', feed['category'], subgroup='BNP Paribas', aggregator=True), [])
            self.assertEqual(len(static.parse_feed(other, dict(feed, subgroup=None, aggregator=False, name='Regular bank feed'))), 1)
        # Missing source must be honestly labelled, never inferred from a title suffix.
        missing = data.replace(b'<source url="https://publisher.test">TEST ONLY Publisher</source>', b'')
        self.assertIn('unknown', static.parse_feed(missing, feed)[0]['sourceName'].lower())

    def test_both_catalog_adapters_carry_optional_metadata(self):
        feed = dict(name='Google News — BNP Paribas (EN)', url='https://news.google.com/rss/search?q=bnp',
                    language='en', category='Financial markets and economics', subgroup='BNP Paribas', aggregator=True)
        catalog = 'const sourceCatalog = ' + json.dumps([feed]) + ';'
        with patch.object(Path, 'read_text', return_value=catalog):
            self.assertEqual(static.default_feeds(), [feed])
        self.assertEqual(legacy.configured_feeds(catalog), [dict(source=feed['name'], **{k:v for k,v in feed.items() if k != 'name'})])

    def test_financial_lexicon_does_not_match_nonfinancial_shares_or_stockpiles(self):
        for title, expected in [('French actor shares family photos', 'France'),
                                ('Ukraine destroys Russian stockpiles', 'World'),
                                ('French director credits cast for success', 'France'),
                                ('BNP Paribas shares rise in Paris', 'Financial'),
                                ('French bank shares rise on earnings', 'Financial')]:
            with self.subTest(title=title):
                self.assertEqual(enrich_articles([article(title)])[0]['section'], expected)

    def test_financial_subject_precedes_geography_but_not_technology(self):
        cases = [
            ('French banks report higher profits', 'World', 'Financial'),
            ('Poland stock market rises after interest rate cut', 'Poland', 'Financial'),
            ('Les marchés financiers et la banque en France', 'France', 'Financial'),
            ('Polskie banki zwiększają zyski', 'Poland', 'Financial'),
            ('Midterms : l’économie américaine avant le scrutin', 'France', 'Financial'),
            ('Routine update', 'Financial markets and economics', 'Financial'),
            ('AI software boosts bank earnings in France', 'France', 'Technology'),
        ]
        for title, category, section in cases:
            with self.subTest(title=title):
                self.assertEqual(enrich_articles([article(title, category=category)])[0]['section'], section)

    def test_bnp_requires_explicit_bank_mention_and_excludes_pure_tennis(self):
        cases = [
            ('BNP Paribas invests in AI software', '', 'Financial', 'BNP Paribas'),
            ('New partnership announced', 'BNP Paribas expands in Poland', 'Financial', 'BNP Paribas'),
            ('BNP Paribas Open: tennis final at Indian Wells', '', 'World', None),
            ('BNP Paribas bank profits fund tennis sponsorship', '', 'Financial', 'BNP Paribas'),
            ('Other bank reports profits', '', 'Financial', None),
        ]
        for title, description, section, subgroup in cases:
            with self.subTest(title=title):
                result = enrich_articles([article(title, description=description, subgroup='BNP Paribas')])[0]
                self.assertEqual(result['section'], section)
                self.assertEqual(result.get('subgroup'), subgroup)


if __name__ == '__main__':
    unittest.main()
