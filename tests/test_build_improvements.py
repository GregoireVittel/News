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


if __name__ == '__main__':
    unittest.main()
