"""TEST ONLY static portal acceptance fixtures; no production output."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from test_build_edition import builder, FEED, RSS


class PortalTests(unittest.TestCase):
    def test_directional_headlines_remain_distinct(self):
        from scripts.story_classification import enrich_articles
        articles = []
        for i, direction in enumerate(('to', 'from')):
            a = builder().parse_feed(RSS, FEED)[0]
            a.update(title=f'France exports natural gas {direction} Poland after agreement',
                     description='', sourceName=f'TEST ONLY {i}', link=f'https://example.test/{i}')
            articles.append(a)
        self.assertEqual(len(enrich_articles(articles)), 2)

    def test_identical_specific_short_headlines_merge(self):
        from scripts.story_classification import enrich_articles
        a = builder().parse_feed(RSS, FEED)[0]
        a.update(title='NASA launches Artemis mission', description='')
        b = dict(a, link='https://second.test/launch', sourceName='TEST ONLY second publisher')
        result = enrich_articles([a, b])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['sourceCount'], 2)
        a.update(title='Breaking news')
        b.update(title='Breaking news')
        self.assertEqual(len(enrich_articles([a, b])), 2)


    def test_real_cross_publisher_paraphrase_is_one_story(self):
        from scripts.story_classification import enrich_articles
        titles = ['Binance resumes withdrawals following $6.3 billion breach',
                  'Binance Resumes Withdrawals After Suffering Biggest-Ever Crypto Hack']
        articles = []
        for i, title in enumerate(titles):
            a = builder().parse_feed(RSS, FEED)[0]
            a.update(title=title, description='', link=f'https://source{i}.test/story',
                     sourceName=f'TEST ONLY publisher {i}')
            articles.append(a)
        result = enrich_articles(articles)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['sourceCount'], 2)
        different = dict(articles[1], title='Binance suspends withdrawals after another breach')
        self.assertEqual(len(enrich_articles([articles[0], different])), 2)

    def test_real_feed_language_traps_and_sections(self):
        from scripts.story_classification import enrich_articles
        cases = [
            ("Le secret de famille : j’ai commencé à avoir des angoisses", 'France', 'fr', 'France'),
            ('Deux hommes écroués après un incendie ayant tué quatre personnes', 'France', 'fr', 'France'),
            ('Un sapeur-pompier blessé par balle près de Marseille', 'France', 'fr', 'France'),
            ('Szokujące akty przemocy na proteście we Frankfurcie', 'Poland', 'pl', 'World'),
            ("Midterms : l’économie américaine avant le scrutin", 'France', 'fr', 'World'),
            ('Atak w Niemczech. Nie żyją cztery osoby', 'Poland', 'pl', 'World'),
            ('Apple’s HomeView could add security camera features', 'Technology, AI and science', 'en', 'Technology'),
            ('Le plus grand data center au monde au Texas', 'France', 'fr', 'Technology'),
        ]
        for title, category, language, section in cases:
            with self.subTest(title=title):
                a = builder().parse_feed(RSS, FEED)[0]
                a.update(title=title, description='', category=category, language=language)
                result = enrich_articles([a])[0]
                self.assertEqual(result['section'], section)


    def test_sections_coverage_and_unique_story_markup(self):
        module = builder()
        now = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        articles = []
        for index in range(5):
            article = module.parse_feed(RSS, FEED)[0]
            article.update(link=f'https://example.test/{index}', section='Technology',
                           sourceCount=2, sources=[{'name': 'TEST ONLY A', 'url': 'https://example.test/a'},
                                                  {'name': 'TEST ONLY B', 'url': 'https://example.test/b'}])
            articles.append(article)
        html = module.edition_page(articles, 'https://example.test/News/', '', 'All', now, [])
        self.assertIn('What’s happening now…', html)
        from html import unescape
        self.assertIn("<title>What's happening in the World</title>", unescape(html))
        self.assertNotIn('brand-mark', html)
        self.assertEqual(html.count('<article '), 5)
        for section in ('Poland', 'France', 'World', 'Technology'):
            self.assertIn(f'aria-label="{section}"', html)
            self.assertIn(f'href="#{section.lower()}"', html)

        self.assertIn('2 sources', html)
        self.assertNotIn('<script', html)
        self.assertIn('portal-grid', html)

    def test_primary_navigation_is_front_page_plus_four_topics(self):
        import re
        from html import unescape
        module = builder()
        now = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        for prefix in ('', '2026-11-01/'):
            for language in ('All', 'pl', 'fr', 'en'):
                html = module.edition_page([], 'https://example.test/News/', prefix, language, now, [])
                links = re.findall(r'<a class="nav-button[^"]*" href="([^"]+)"[^>]*>([^<]+)</a>', html)
                self.assertEqual(links, [
                    ('https://example.test/News/' + prefix, 'Front Page'),
                    ('#poland', 'Polish News'), ('#france', 'French News'),
                    ('#world', 'World News'), ('#technology', 'Technology'),
                ])
                self.assertNotIn('Przegląd', unescape(html))
                for anchor in ('poland', 'france', 'world', 'technology'):
                    self.assertIn(f'id="{anchor}"', html)

    def test_build_persists_enrichment_and_legacy_aliases(self):
        module = builder()
        now = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'site'
            module.build(output, 'https://example.test/News/', now=now, feeds=[FEED],
                         fetcher=lambda feed: RSS, history_root=Path(temp) / 'empty')
            data = json.loads((output / 'articles.json').read_text())
            self.assertEqual(data['schemaVersion'], 2)
            self.assertEqual(data['sections'], ['Poland', 'France', 'World', 'Technology'])
            self.assertEqual(len(data['articles']), 1)
            article = data['articles'][0]
            self.assertIn(article['section'], data['sections'])

            self.assertEqual(article['sourceCount'], 1)
            self.assertEqual(article['importance']['sourceCount'], 1)
            self.assertEqual(article['sourceCategory'], 'Business')
            self.assertEqual(article['date'], '2026-11-01T11:00:00+00:00')
            self.assertEqual((output / 'articles.json').read_bytes(), (output / '2026-11-01/articles.json').read_bytes())
            self.assertEqual((output / 'rss.xml').read_bytes(), (output / 'feed.xml').read_bytes())
            self.assertEqual((output / 'pl/index.html').read_bytes(), (output / 'lang/pl.html').read_bytes())


    def test_url_duplicates_preserve_distinct_publisher_evidence(self):
        module = builder()
        now = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        feeds = [FEED, dict(FEED, name='TEST ONLY second publisher')]
        # collect must not discard a second publisher before clustering can count it.
        articles, _ = module.collect(feeds, lambda feed: RSS, now)
        self.assertEqual(len({a['sourceName'] for a in articles}), 2)

    def test_dated_data_remains_immutable_on_same_day_rebuild(self):
        module = builder()
        now = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp:
            first, second = Path(temp) / 'first', Path(temp) / 'second'
            module.build(first, 'https://example.test/News/', now=now, feeds=[FEED],
                         fetcher=lambda feed: RSS, history_root=Path(temp) / 'empty')
            updated = RSS.replace(b'TEST ONLY &amp; title', b'TEST ONLY updated headline')
            module.build(second, 'https://example.test/News/', now=now, feeds=[FEED],
                         fetcher=lambda feed: updated, history_root=first)
            self.assertEqual((first / '2026-11-01/articles.json').read_bytes(),
                             (second / '2026-11-01/articles.json').read_bytes())
            self.assertNotEqual((first / 'articles.json').read_bytes(), (second / 'articles.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
