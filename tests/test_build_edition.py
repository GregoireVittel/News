"""Offline TEST-ONLY fixtures; never used by the production CLI."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def builder():
    path = ROOT / 'scripts/build_edition.py'
    assert path.exists(), 'Static edition builder is not implemented'
    spec = importlib.util.spec_from_file_location('edition', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FEED = {'url': 'https://example.test/rss', 'name': 'TEST ONLY publisher', 'language': 'pl', 'category': 'Business'}
RSS = b'''<rss><channel><item><title>TEST ONLY &amp; title</title><link>https://example.test/a?x=1&amp;y=2</link><pubDate>Sun, 01 Nov 2026 11:00:00 GMT</pubDate><description>&lt;p&gt;TEST ONLY snippet&lt;/p&gt;</description></item></channel></rss>'''


class ParsingTests(unittest.TestCase):
    def test_python_fetches_the_feed_url_directly(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from threading import Thread
        requests = []

        class FeedHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                self.send_response(200)
                self.send_header('Content-Type', 'application/rss+xml')
                self.end_headers()
                self.wfile.write(RSS)

            def log_message(self, format, *args):
                pass

        with ThreadingHTTPServer(('127.0.0.1', 0), FeedHandler) as server:
            worker = Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                feed = dict(FEED, url=f'http://127.0.0.1:{server.server_port}/publisher/rss?topic=news')
                self.assertEqual(builder().fetch_feed(feed), RSS)
                self.assertEqual(requests, ['/publisher/rss?topic=news'])
            finally:
                server.shutdown()
                worker.join()

    def test_atom_sanitization(self):
        data = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>TEST ONLY Atom</title><link href="https://example.test/atom"/><updated>2026-11-01T11:00:00Z</updated><summary>&lt;script&gt;evil&lt;/script&gt;TEST ONLY</summary></entry><entry><title>TEST ONLY unsafe</title><link href="javascript:alert(1)"/></entry></feed>'''
        articles = builder().parse_feed(data, FEED)
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]['description'], 'TEST ONLY')

    def test_defaults_still_inline_and_live_refresh_preserved(self):
        feeds = builder().default_feeds()
        self.assertEqual(len(feeds), 34)
        self.assertEqual(feeds[0]['name'], 'PAP Biznes')
        self.assertIn('3 * 60 * 1000', (ROOT / 'live.html').read_text())
        self.assertFalse((ROOT / 'sources.yaml').exists())

    def test_static_page_retains_original_fonts_and_link_colours(self):
        from datetime import datetime, timezone
        module = builder()
        html = module.page('https://example.test/', 'https://example.test/', 'Test', '', datetime.now(timezone.utc))
        self.assertIn('family=DM+Sans', html)
        self.assertIn('family=Playfair+Display', html)
        self.assertIn('a { color:inherit; }', (ROOT / 'assets/portal.css').read_text())

    def test_rss_description_and_metadata(self):
        articles = builder().parse_feed(RSS, FEED)
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]['title'], 'TEST ONLY & title')
        self.assertEqual(articles[0]['description'], 'TEST ONLY snippet')
        self.assertEqual(articles[0]['category'], 'Business')


class BuildTests(unittest.TestCase):
    def test_history_immutable_and_partial_feed_failures(self):
        import tempfile
        from datetime import datetime, timezone
        module = builder()
        now = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        bad_feed = dict(FEED, name='TEST ONLY failed')
        def fetch(feed):
            if feed['name'] == bad_feed['name']:
                raise OSError('TEST ONLY network failure')
            return RSS
        with tempfile.TemporaryDirectory() as temp:
            history = Path(temp) / 'history'
            (history / '2026-10-31').mkdir(parents=True)
            (history / '2026-10-31/index.html').write_text('TEST ONLY immutable history')
            (history / '2026-10-30').mkdir()
            with self.assertLogs('edition', level='WARNING') as logs:
                result = module.build(Path(temp) / 'site', 'https://example.test/News/', now=now, feeds=[FEED, bad_feed], fetcher=fetch, history_root=history)
            self.assertEqual(len(result['failures']), 1)
            self.assertIn('TEST ONLY network failure', logs.output[0])
            output = Path(result['output'])
            self.assertEqual((output / '2026-10-31/index.html').read_text(), 'TEST ONLY immutable history')
            self.assertNotIn('2026-10-30', (output / 'archive/index.html').read_text())
            second = Path(temp) / 'second'
            module.build(second, 'https://example.test/News/', now=now, feeds=[FEED], fetcher=fetch, history_root=output)
            self.assertEqual((second / '2026-11-01/index.html').read_bytes(), (output / '2026-11-01/index.html').read_bytes())

    def test_safe_url_validation_and_deduplication(self):
        from datetime import datetime, timezone
        module = builder()
        for url in ('javascript:alert(1)', 'data:text/html,x', '//example.test/x', 'https://user:pass@example.test/x', 'https://example.test/\nfoo'):
            self.assertEqual(module.safe_url(url), '')
        now = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        articles, failures = module.collect([FEED, FEED], lambda feed: RSS, now)
        self.assertEqual(len(articles), 1)
        self.assertEqual(failures, [])

    def test_static_output_and_paris_date(self):
        import tempfile
        from datetime import datetime, timezone
        import xml.etree.ElementTree as ET
        module = builder()
        now = datetime(2026, 11, 1, 23, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'site'
            result = module.build(output, 'https://example.test/News/', now=now, feeds=[FEED], fetcher=lambda feed: RSS)
            self.assertEqual(result['edition'], '2026-11-02')
            html = (output / 'index.html').read_text()
            for text in ['TEST ONLY &amp; title', 'lang="pl"', 'property="og:title"', 'Europe/Paris', 'portal-grid', 'https://example.test/News/assets/portal.css']:
                self.assertIn(text, html)
            self.assertNotIn('<script', html)
            self.assertTrue((output / '2026-11-02/index.html').exists())
            self.assertTrue((output / '2026-11-02/pl/index.html').exists())
            self.assertNotIn('TEST ONLY &amp; title', (output / 'en/index.html').read_text())
            archive = (output / 'archive/index.html').read_text()
            self.assertIn('/News/2026-11-02/', archive)
            self.assertNotIn('/News/2026-11-01/', archive)
            ET.parse(output / 'rss.xml')
            ET.parse(output / 'sitemap.xml')

    def test_empty_edition_leaves_output_untouched(self):
        import tempfile
        module = builder()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'site'
            with self.assertRaises(ValueError):
                module.build(output, 'https://example.test/News/', feeds=[FEED], fetcher=lambda feed: b'<rss/>')
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
