"""Offline tests for the dashboard panels, extra pages and stats history."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import dashboard  # noqa: E402
from story_classification import _section  # noqa: E402
from test_build_edition import builder, FEED, RSS  # noqa: E402

NOW = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
SECTIONS = ('Poland', 'France', 'World', 'Technology', 'Financial')
LABELS = dict(zip(SECTIONS, ('Polish News', 'French News', 'World News', 'Technology', 'Financial News')))


def story(title, section='World', hours=1, sources=('TEST ONLY A',), index=0):
    link = f'https://example.test/{index}'
    return dict(title=title, link=link, description='', image='', language='en', section=section,
                sourceName=sources[0], date=NOW - timedelta(hours=hours), sourceCount=len(set(sources)),
                sources=[dict(name=name, url=f'{link}/{n}') for n, name in enumerate(sources)])


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.stories = [
            story('Iran talks resume in Geneva', 'World', 1, ('TEST A', 'TEST B', 'TEST C'), 0),
            story('Iran sanctions hit oil exports', 'Financial', 2, ('TEST A', 'TEST B'), 1),
            story('Iran election turnout falls', 'World', 5, ('TEST B',), 2),
            story('Warsaw opens new metro line', 'Poland', 8, ('TEST C',), 3),
            story('Chip makers expand in Dresden', 'Technology', 30, ('TEST A',), 4),
        ]

    def test_new_badge_only_within_three_hours(self):
        self.assertTrue(dashboard.is_new(self.stories[1], NOW))
        self.assertFalse(dashboard.is_new(self.stories[2], NOW))
        self.assertIn('badge-new', dashboard.new_badge(self.stories[0], NOW))
        self.assertEqual(dashboard.new_badge(self.stories[3], NOW), '')

    def test_most_covered_lists_outlets_and_skips_single_source(self):
        html = dashboard.most_covered(self.stories, LABELS)
        self.assertIn('TEST A, TEST B, TEST C', html)
        self.assertIn('Iran sanctions hit oil exports', html)
        self.assertNotIn('Warsaw', html)
        self.assertIn('more than one outlet', dashboard.most_covered(self.stories[2:], LABELS))

    def test_trending_counts_distinct_headlines_and_ignores_stopwords(self):
        topics = dashboard.trending(self.stories)
        self.assertEqual([(label, len(items)) for label, _, items in topics], [('Iran', 3)])
        self.assertEqual(topics[0][1], 'iran')
        panel = dashboard.trending_panel(topics, 'https://example.test/')
        self.assertIn('href="https://example.test/trending/#kw-iran"', panel)
        page = dashboard.trending_page(topics, LABELS, NOW)
        self.assertIn('id="kw-iran"', page)
        self.assertEqual(page.count('<li><span class="mini-section">'), 3)

    def test_sources_page_groups_every_outlet_once_per_story(self):
        html = dashboard.sources_page(self.stories, LABELS, NOW)
        for name, count in (('TEST A', 3), ('TEST B', 3), ('TEST C', 2)):
            section = html.split(f'id="src-{dashboard.slug(name)}"', 1)[1].split('</section>', 1)[0]
            self.assertIn(f'{count} stories', section)
        self.assertLess(html.index('id="src-test-a"'), html.index('id="src-test-c"'))

    def test_archive_page_trend_and_week_links(self):
        stats = {'2026-10-25': dashboard.day_stats(self.stories[:2], SECTIONS),
                 '2026-11-01': dashboard.day_stats(self.stories, SECTIONS)}
        html = dashboard.archive_page('https://example.test/', ['2026-11-01', '2026-10-25'], stats, SECTIONS, LABELS)
        self.assertEqual(html.count('class="spark"'), 5)
        self.assertIn('class="spark-line"', html)
        self.assertIn('same day last week (2026-10-25)', html)
        self.assertIn('5 stories', html)


class FinancialTermsTests(unittest.TestCase):
    def test_deal_terms_route_to_financial_without_catching_floating(self):
        for title in ('Blue Lagoon owner plans to float as Icelandic tourism booms',
                      'Unilever agrees £3bn takeover of rival', 'Retailer prepares IPO in New York',
                      'TotalEnergies annonce le rachat de sa filiale',
                      'Orlen zapowiada debiut na giełdzie spółki zależnej'):
            self.assertEqual(_section({'title': title, 'description': ''})[0], 'Financial', title)
        self.assertEqual(_section({'title': 'Floating solar farm opens in Poland', 'description': ''})[0], 'Poland')


class BuildIntegrationTests(unittest.TestCase):
    def test_build_writes_dashboard_pages_stats_and_english_chrome(self):
        edition = builder()
        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp) / 'history'
            history.mkdir()
            (history / 'stats.json').write_text(json.dumps({'schemaVersion': 1, 'days': {
                '2026-10-31': {'total': 7, 'publishers': 2, 'sections': {'World': 7}},
                'junk': {'total': 1}}}))
            site = Path(tmp) / 'site'
            edition.build(site, 'https://example.test/News/', now=NOW, feeds=[FEED],
                          fetcher=lambda feed: RSS, history_root=history)
            front = (site / 'index.html').read_text()
            for marker in ('id="covered-title"', 'id="trending-title"', 'class="top-stories"'):
                self.assertIn(marker, front)
            for removed in ('class="numbers"', 'glance', 'pulse'):
                self.assertNotIn(removed, front)
            self.assertIn('<html lang="en">', front)
            # The language switch filters stories; the page text stays English.
            self.assertIn('<html lang="en">', (site / 'pl/index.html').read_text())
            self.assertNotIn('Wygenerowano', front)
            self.assertNotIn('Archiwum', front)
            self.assertIn('href="https://example.test/News/sources/"', front)
            self.assertEqual(front.count('<article '), 1)
            self.assertIn('TEST ONLY publisher', (site / 'sources/index.html').read_text())
            self.assertTrue((site / 'trending/index.html').is_file())
            stats = json.loads((site / 'stats.json').read_text())['days']
            self.assertEqual(sorted(stats), ['2026-10-31', '2026-11-01'])
            self.assertEqual(stats['2026-11-01']['total'], 1)
            archive = (site / 'archive/index.html').read_text()
            self.assertIn('Edition archive', archive)
            self.assertEqual(archive.count('class="spark"'), 5)
            sitemap = (site / 'sitemap.xml').read_text()
            self.assertIn('https://example.test/News/sources/', sitemap)
            self.assertIn('https://example.test/News/trending/', sitemap)


if __name__ == '__main__':
    unittest.main()
