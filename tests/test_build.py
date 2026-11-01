import datetime as dt
import tempfile
import unittest
from pathlib import Path

from build import generate, parse_feed, configured_feeds

UTC = dt.timezone.utc


class EditionTests(unittest.TestCase):
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
