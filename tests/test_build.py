import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from build import clean, generate, parse_feed, configured_feeds

UTC = dt.timezone.utc


class EditionTests(unittest.TestCase):
    def test_legacy_generation_persists_current_classification(self):
        now = dt.datetime(2026, 11, 1, 12, tzinfo=UTC)
        entry = dict(title='NASA launches Artemis mission', link='https://example.test/nasa',
                     source='TEST ONLY publisher', language='en', category='Technology',
                     summary='Space mission launch', published=now)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'live.html').write_text('<style></style>')
            generate(root, [entry], now)
            data = json.loads((root / 'articles.json').read_text())
            self.assertEqual(data['schemaVersion'], 2)
            self.assertEqual(data['sections'], ['Poland', 'France', 'World', 'Technology', 'Financial'])
            self.assertEqual(data['generatedAt'], now.isoformat())
            self.assertEqual(data['articles'][0]['date'], now.isoformat())
            self.assertEqual(data['articles'][0]['section'], 'Technology')
            self.assertEqual(data['articles'][0]['sourceCount'], 1)

            entry.update(title='Updated NASA mission report')
            generate(root, [entry], now)
            self.assertEqual(json.loads((root / 'articles.json').read_text())['articles'][0]['title'],
                             entry['title'])

    def test_shared_catalog_loads_only_enabled_sources_with_requested_categories(self):
        catalog = '''const sourceCatalog = [
          {"name":"Reuters","url":null,"language":"en","category":"Poland","status":"No public RSS; licensed feed required"},
          {"name":"BBC News","url":"https://feeds.bbci.co.uk/news/rss.xml","language":"en","category":"Global news and geopolitics","status":"Public RSS"}
        ];
        if (typeof module !== 'undefined') module.exports = sourceCatalog;
        '''
        self.assertEqual(configured_feeds(catalog), [dict(source='BBC News', url='https://feeds.bbci.co.uk/news/rss.xml', language='en', category='Global news and geopolitics')])

    def test_feed_items_parse_rss_and_atom_and_ignore_undated(self):
        rss = b'''<rss><channel><item><title>First &amp; last</title><link>https://example.com/a</link><pubDate>Sat, 31 Oct 2026 08:00:00 GMT</pubDate><description>&lt;p&gt;News&lt;/p&gt;</description></item></channel></rss>'''
        atom = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom</title><link href="https://example.com/b"/><updated>2026-10-31T09:00:00Z</updated></entry></feed>'''
        self.assertEqual(parse_feed(rss, 'Example', 'en')[0]['title'], 'First & last')
        self.assertEqual(parse_feed(atom, 'Example', 'en')[0]['link'], 'https://example.com/b')
        self.assertEqual(parse_feed(rss.replace(b'<pubDate>Sat, 31 Oct 2026 08:00:00 GMT</pubDate>', b''), 'Example', 'en'), [])

    def test_legacy_pages_use_shared_sections_coverage_and_portal_styles(self):
        now = dt.datetime(2026, 11, 1, 12, tzinfo=UTC)
        entry = dict(title='France unveils artificial intelligence technology',
                     link='https://example.test/ai', source='TEST ONLY publisher',
                     language='fr', category='France', summary='New software research',
                     published=now - dt.timedelta(hours=1))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'live.html').write_text('<style>.legacy{color:red}</style>')
            self.assertEqual(generate(root, [entry], now, 'https://example.test/News/'), 1)
            for relative in ('index.html', 'lang/fr.html', 'archive/2026-11-01.html'):
                page = (root / relative).read_text()
                self.assertIn('What’s happening now…', page)

                self.assertIn('Coverage sources', page)
                self.assertEqual(page.count('<article '), 1)
                for section in ('Poland', 'France', 'World', 'Technology', 'Financial'):
                    self.assertIn(f'aria-label="{section}"', page)
                self.assertIn('<div class="eyebrow">Technology</div>', page)
                self.assertIn('https://example.test/News/assets/portal.css', page)
                self.assertIn('href="https://example.test/News/lang/fr.html"', page)
                self.assertNotIn('<script', page)
            self.assertTrue((root / 'assets/portal.css').is_file())
            self.assertIn('<html lang="fr">', (root / 'lang/fr.html').read_text())
            self.assertIn('href="https://example.test/News/archive/2026-11-01.html"',
                          (root / 'archive/2026-11-01.html').read_text())

    def test_clean_preserves_distinct_publishers_for_shared_story_ranking(self):
        now = dt.datetime(2026, 11, 1, 12, tzinfo=UTC)
        entry = dict(title='TEST ONLY shared story', link='https://example.test/shared',
                     source='TEST ONLY A', language='en', category='World', summary='', published=now)
        entries = [entry, dict(entry), dict(entry, source='TEST ONLY B'),
                   dict(entry, link='https://example.test/old', published=now - dt.timedelta(days=2)),
                   dict(entry, link='https://example.test/future', published=now + dt.timedelta(seconds=1))]
        result = clean(entries, now)
        self.assertEqual([a['source'] for a in result], ['TEST ONLY A', 'TEST ONLY B'])
        self.assertEqual(entries[0], entry)

    def test_generate_counts_clustered_stories_and_ranks_by_publisher_coverage(self):
        now = dt.datetime(2026, 11, 1, 12, tzinfo=UTC)
        shared = dict(title='TEST ONLY rescue workers save stranded hikers',
                      link='https://example.test/rescue', source='TEST ONLY A', language='en',
                      category='World', summary='', published=now - dt.timedelta(hours=2))
        recent = dict(shared, title='TEST ONLY council discusses road repairs',
                      link='https://example.test/roads', published=now)
        entries = [recent, shared, dict(shared, source='TEST ONLY B')]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'live.html').write_text('<style></style>')
            count = generate(root, entries, now)
            page = (root / 'index.html').read_text()
            self.assertEqual(page.count('<article '), 2)
            self.assertIn('2 sources', page)
            self.assertLess(page.index(shared['title']), page.index(recent['title']))
            self.assertEqual(count, 2)
            self.assertEqual((root / 'feed.xml').read_text().count('<item>'), 2)

    def test_existing_dated_archive_is_immutable_on_same_day_rebuild(self):
        now = dt.datetime(2026, 11, 1, 23, 30, tzinfo=UTC)
        entry = dict(title='TEST ONLY original', link='https://example.test/original',
                     source='TEST ONLY', language='en', category='World', summary='', published=now)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'live.html').write_text('<style></style>')
            generate(root, [entry], now)
            archive = root / 'archive/2026-11-01.html'
            original = archive.read_bytes()
            generate(root, [dict(entry, title='TEST ONLY replacement')], now)
            self.assertEqual(archive.read_bytes(), original)
            self.assertIn('TEST ONLY replacement', (root / 'index.html').read_text())
            self.assertFalse((root / 'archive/2026-11-02.html').exists())

    def test_generated_front_page_archive_and_discovery_work_without_scripts(self):
        now = dt.datetime(2026, 10, 31, 10, tzinfo=UTC)
        entries = [
            dict(title='Title <one>', link='https://example.com/one?q=1&x=2', source='BBC', language='en', category='World', summary='A <test> story', published=now - dt.timedelta(hours=1)),
            dict(title='Deux', link='https://example.com/two', source='France 24', language='fr', category='Business', summary='', published=now - dt.timedelta(hours=2)),
            dict(title='Old', link='https://example.com/old', source='BBC', language='en', category='World', summary='', published=now - dt.timedelta(days=2)),
        ]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'live.html').write_text('<style>.brand{color:red}</style>', encoding='utf-8')
            generate(root, entries, now, 'https://example.com/News/')
            front = (root / 'index.html').read_text()
            archive = root / 'archive' / '2026-10-31.html'
            self.assertTrue(archive.is_file())
            self.assertIn('Title &lt;one&gt;', front)
            self.assertIn('A &lt;test&gt; story', front)
            self.assertIn('https://example.com/one?q=1&amp;x=2', front)
            self.assertNotIn('Old', front)
            self.assertNotIn('<script', front)
            self.assertIn('<html lang="pl">', front)
            self.assertIn('rel="alternate" type="application/rss+xml"', front)
            self.assertIn('property="og:title"', front)
            self.assertIn('2026-10-31T10:00:00+00:00', front)
            self.assertIn('.brand{color:red}', front)
            self.assertIn('live.html', front)
            self.assertIn('2026-10-31.html', (root / 'archive' / 'index.html').read_text())
            self.assertIn('Title &lt;one&gt;', archive.read_text())
            self.assertIn('.brand{color:red}', (root / 'archive' / 'index.html').read_text())
            self.assertIn('Title &lt;one&gt;', (root / 'feed.xml').read_text())
            self.assertIn('https://example.com/News/archive/2026-10-31.html', (root / 'sitemap.xml').read_text())
            # Rebuild on another day must not remove yesterday's edition.
            generate(root, [dict(entries[1], published=now + dt.timedelta(hours=23))], now + dt.timedelta(days=1), 'https://example.com/News/')
            self.assertTrue(archive.is_file())
            self.assertIn('2026-10-31.html', (root / 'archive' / 'index.html').read_text())


if __name__ == '__main__':
    unittest.main()
