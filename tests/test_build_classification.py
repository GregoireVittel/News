"""Offline contract tests for story enrichment; run with unittest discovery."""
import copy
from datetime import datetime, timezone
import unittest

from scripts.story_classification import enrich_articles


def article(title='A routine update', **changes):
    value = dict(title=title, link='https://example.com/story', description='',
                 date=datetime(2026, 11, 1, 12, tzinfo=timezone.utc), image='',
                 sourceName='Example', language='en', category='World')
    value.update(changes)
    return value


class EnrichmentTests(unittest.TestCase):
    def test_preserves_article_and_adds_auditable_metadata(self):
        original = article()
        snapshot = copy.deepcopy(original)
        result = enrich_articles([original])[0]
        self.assertEqual(original, snapshot)
        for key, value in original.items():
            self.assertEqual(result[key], value)
        self.assertEqual(result['sourceCategory'], 'World')
        self.assertEqual(result['section'], 'World')
        self.assertTrue(result['sectionReason'])
        self.assertEqual(set(result), set(original) | {
            'sourceCategory', 'section', 'sectionReason', 'classification',
            'sources', 'sourceCount', 'importance'})
        self.assertEqual(result['classification'], dict(method='rules', version=1,
                         input=dict(title=original['title'], description='', sourceCategory='World')))
        self.assertEqual(result['sources'], [dict(name='Example', url=original['link'])])
        self.assertEqual(result['sourceCount'], 1)
        self.assertEqual(result['importance'], dict(sourceCount=1))
        self.assertEqual(enrich_articles([]), [])

    def test_multilingual_subject_sections_override_feed_and_language(self):
        cases = [
            ('Poland launches artificial intelligence research', '', 'Poland', 'Technology'),
            ('La France investit dans les semi-conducteurs', '', 'France', 'Technology'),
            ('Polska rozwija sztuczną inteligencję', '', 'Poland', 'Technology'),
            ('French parliament debates budget', '', 'World', 'France'),
            ('W Warszawie otwarto nowy most', '', 'World', 'Poland'),
            ('Varsovie accueille le sommet', '', 'France', 'Poland'),
            ('New agreement announced', 'The Polish government signed the treaty.', 'France', 'Poland'),
            ('Ukraine holds elections', '', 'France', 'World'),
            ('A routine update', '', 'Technology', 'Technology'),
            ('A routine update', '', 'France', 'France'),
            ('France and Poland hold talks', '', 'World', 'Poland'),
            ('Poland and France hold talks', '', 'World', 'Poland'),
            ('A routine update', '', 'World', 'World'),
        ]
        for title, description, category, expected in cases:
            with self.subTest(title=title):
                result = enrich_articles([article(title, description=description,
                                         category=category, language='pl')])[0]
                self.assertEqual(result['section'], expected)
                self.assertTrue(result['sectionReason'])


    def test_canonical_url_dedup_keeps_provenance_and_counts_publisher_once(self):
        items = [article('Original title', link='https://EXAMPLE.com/story?id=7&utm_source=rss'),
                 article('An updated title', link='https://example.com/story?id=7&fbclid=abc'),
                 article('Syndicated title', link='https://example.com/story?id=7', sourceName='Second')]
        stories = enrich_articles(items)
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0]['sourceCount'], 2)
        self.assertEqual(stories[0]['importance'], dict(sourceCount=2))
        self.assertEqual({(s['name'], s['url']) for s in stories[0]['sources']},
                         {(a['sourceName'], a['link']) for a in items})
        self.assertEqual(len(enrich_articles([items[0], items[0]] )[0]['sources']), 1)

    def test_semantic_query_parameters_are_not_discarded(self):
        items = [article('Report ' + str(i), link='https://example.com/story?id=' + str(i))
                 for i in range(3)]
        self.assertEqual(len(enrich_articles(items)), 3)

    def test_near_identical_cross_source_titles_merge_but_not_shared_topics(self):
        title = 'NASA Artemis rocket launches historic lunar mission from Florida'
        items = [article(title, sourceName='One', link='https://one.test/a'),
                 article('NASA Artemis rocket launches historic lunar mission from Florida today',
                         sourceName='Two', link='https://two.test/a'),
                 article(title, sourceName='One', link='https://one.test/b')]
        stories = enrich_articles(items)
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0]['sourceCount'], 2)
        self.assertEqual(len(stories[0]['sources']), 3)
        distinct = [
            'NASA Artemis rocket delays historic lunar mission from Florida',
            'NASA Artemis rocket launches historic lunar mission from Texas',
            'NASA Artemis rocket launches historic lunar mission 2 from Florida',
            'La fusée Artemis de la NASA décolle de Floride pour la Lune',
            'NASA announces lunar mission',
            'NASA announces Mars mission',
        ]
        for i, other in enumerate(distinct):
            with self.subTest(title=other):
                pair = [items[0], article(other, sourceName='Other', link=f'https://other.test/{i}')]
                self.assertEqual(len(enrich_articles(pair)), 2)

    def test_importance_then_date_then_link_sorting_is_input_order_independent(self):
        older = datetime(2026, 11, 1, 10, tzinfo=timezone.utc)
        items = [article('Newest single', link='https://z.test/new'),
                 article('Older shared', date=older, sourceName='B', link='https://shared.test/x?utm_source=b'),
                 article('Older shared', date=older, sourceName='A', link='https://shared.test/x'),
                 article('Tied single', link='https://a.test/new')]
        result = enrich_articles(items)
        self.assertEqual([s['link'] for s in result],
                         ['https://shared.test/x', 'https://a.test/new', 'https://z.test/new'])
        self.assertEqual(result, enrich_articles(reversed(items)))

    def test_science_sections_are_multilingual(self):
        for title in ('Researchers discover new planet', 'Des chercheurs découvrent une exoplanète',
                      'Badacze odkryli nową planetę'):
            with self.subTest(title=title):
                self.assertEqual(enrich_articles([article(title, category='France')])[0]['section'], 'Technology')
    def test_real_headline_sections_do_not_confuse_contractions_or_language(self):
        cases = [
            ("Le secret de famille : j’ai commencé à avoir des angoisses", 'France', 'France'),
            ('Deux hommes écroués après un incendie ayant tué quatre personnes', 'France', 'France'),
            ('Un sapeur-pompier blessé par balle près de Marseille', 'France', 'France'),
            ('Szokujące akty przemocy na proteście we Frankfurcie', 'Poland', 'World'),
            ('Midterms : l’économie américaine avant le scrutin', 'France', 'World'),
            ('Atak w Niemczech. Nie żyją cztery osoby', 'Poland', 'World'),
            ('Apple’s HomeView could add security camera features', 'World', 'Technology'),
            ('Le plus grand data center au monde au Texas', 'France', 'Technology'),
            ('A routine update', 'Technology, AI and science', 'Technology'),
        ]
        for title, category, section in cases:
            with self.subTest(title=title):
                result = enrich_articles([article(title, category=category)])[0]
                self.assertEqual(result['section'], section)



if __name__ == '__main__':
    unittest.main()
