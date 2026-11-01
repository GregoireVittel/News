"""Offline tests for fetch retries, failure listing and page accessibility."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from unittest import mock
import tempfile
import unittest

from test_build_edition import builder, FEED, RSS


class FetchRetryTests(unittest.TestCase):
    def setUp(self):
        self.edition = builder()

    def response(self):
        handle = mock.MagicMock()
        handle.__enter__.return_value.read.return_value = RSS
        return handle

    def test_transient_error_is_retried_once(self):
        with mock.patch.object(self.edition, 'urlopen', side_effect=[URLError('reset'), self.response()]) as opener, \
                mock.patch.object(self.edition.time, 'sleep') as sleep:
            self.assertEqual(self.edition.fetch_feed(FEED), RSS)
        self.assertEqual(opener.call_count, 2)
        sleep.assert_called_once()

    def test_client_errors_are_not_retried(self):
        error = HTTPError(FEED['url'], 404, 'Not Found', {}, None)
        with mock.patch.object(self.edition, 'urlopen', side_effect=error) as opener, \
                mock.patch.object(self.edition.time, 'sleep'):
            with self.assertRaises(HTTPError):
                self.edition.fetch_feed(FEED)
        self.assertEqual(opener.call_count, 1)

    def test_persistent_server_errors_give_up(self):
        error = HTTPError(FEED['url'], 503, 'Unavailable', {}, None)
        with mock.patch.object(self.edition, 'urlopen', side_effect=error) as opener, \
                mock.patch.object(self.edition.time, 'sleep'):
            with self.assertRaises(HTTPError):
                self.edition.fetch_feed(FEED)
        self.assertEqual(opener.call_count, 2)


class PageTests(unittest.TestCase):
    def test_failures_listed_counts_pluralised_and_skip_link(self):
        edition = builder()
        now = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        broken = dict(FEED, name='TEST ONLY broken <feed>', url='https://example.test/broken')

        def fetcher(feed):
            if feed is broken:
                raise ValueError('boom')
            return RSS

        with tempfile.TemporaryDirectory() as tmp:
            result = edition.build(Path(tmp) / 'site', 'https://example.test/News/', now=now,
                                   feeds=[FEED, broken], fetcher=fetcher, history_root=Path(tmp) / 'none')
            html = (Path(tmp) / 'site/index.html').read_text()
        self.assertEqual(len(result['failures']), 1)
        self.assertIn('1 story · past 24 hours · 1 feed unavailable', html)
        self.assertIn('<li>TEST ONLY broken &lt;feed&gt;</li>', html)
        self.assertNotIn('https://example.test/broken', html)
        self.assertIn('<a class="skip-link" href="#main-content">', html)
        self.assertIn('id="main-content"', html)


class TopStoriesTests(unittest.TestCase):
    def stories(self, edition, count):
        now = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        items = []
        for index in range(count):
            story = edition.parse_feed(RSS, FEED)[0]
            story.update(title=f'TEST ONLY story {index}', link=f'https://example.test/{index}',
                         section=('World', 'Technology')[index % 2], sourceCount=1,
                         sources=[{'name': 'TEST ONLY', 'url': f'https://example.test/{index}'}],
                         date=now - timedelta(minutes=index))
            items.append(story)
        return now, items

    def test_front_page_lists_top_stories_without_duplicate_cards(self):
        edition = builder()
        now, items = self.stories(edition, 9)
        html = edition.edition_page(items, 'https://example.test/', '', 'All', now, [])
        top = html.split('class="top-stories"', 1)[1].split('</section>', 1)[0]
        self.assertEqual(top.count('<li '), edition.TOP_STORIES)
        self.assertIn('TEST ONLY story 0', top)
        self.assertNotIn('TEST ONLY story 7', top)
        self.assertIn('href="#technology">Technology</a>', top)
        self.assertLess(html.index('class="top-stories"'), html.index('id="poland"'))
        self.assertEqual(html.count('<article '), 9)

    def test_language_pages_and_empty_editions_have_no_top_stories(self):
        edition = builder()
        now, items = self.stories(edition, 3)
        self.assertNotIn('top-stories', edition.edition_page(items, 'https://example.test/', '', 'pl', now, []))
        self.assertNotIn('top-stories', edition.edition_page([], 'https://example.test/', '', 'All', now, []))


if __name__ == '__main__':
    unittest.main()
