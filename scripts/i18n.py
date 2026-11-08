"""Menu order, story-language filter options and interface text (stdlib only).

The interface is English on every page. The language switch (English /
Français / Polski) only filters stories by the language they were written in.
"""

LANGUAGES = ('en', 'fr', 'pl')
LANGUAGE_NAMES = {'en': 'English', 'fr': 'Français', 'pl': 'Polski'}
# Menu order; keys are the stored section names in articles.json.
MENU = ('World', 'Poland', 'France', 'Financial', 'Technology')

TEXT = {
    'en': {
        'sections': {'World': 'World', 'Poland': 'Poland', 'France': 'France',
                     'Financial': 'Global Markets', 'Technology': 'Tech'},
        'site_title': "What's happening in the World",
        'tagline': 'What’s happening now…',
        'topline': ('THE DAILY BRIEFING · STORIES FROM AROUND THE WORLD', 'INDEPENDENT NEWS AGGREGATOR'),
        'skip': 'Skip to content',
        'updated': 'Updated',
        'live_reader': 'Live reader',
        'front_page': 'Front Page',
        'sections_nav': 'News sections',
        'language_nav': 'Story language',
        'past_day': 'past 24 hours',
        'feeds_unavailable': '{feeds} unavailable',
        'unavailable_feeds': 'Unavailable feeds',
        'ordering': 'Ordered by distinct publisher count, then recency.',
        'top_stories': 'Top stories',
        'top_stories_note': 'most publishers, then most recent',
        'coverage_sources': 'Coverage sources',
        'google_note': 'Google News RSS aggregation; Google News links redirect to publisher coverage. Snippets are supplied RSS text, not original summaries.',
        'empty_section': 'No stories in this section for this edition.',
        'empty_bnp': 'No BNP Paribas stories in this edition.',
        'new': 'New',
        'most_covered': 'Most covered',
        'most_covered_note': 'stories reported by several outlets',
        'most_covered_empty': 'No story was covered by more than one outlet in this edition.',
        'outlets': 'outlets',
        'trending': 'Trending',
        'trending_note': 'words in the most headlines',
        'trending_empty': 'Not enough overlap between headlines yet.',
        'trending_all': 'All trending topics →',
        'by_source': 'By source',
        'archive': 'Archive',
        'footer_note': "Descriptions are snippets from the publishers' or aggregators' RSS feeds, not original summaries. Links go to publishers directly or via Google News.",
        'og_locale': 'en_GB',
        'description': 'What’s happening now… Publisher feed headlines and snippets.',
    },
}

NOUNS = {
    'en': {'story': ('story', 'stories'), 'source': ('source', 'sources'), 'feed': ('feed', 'feeds')},
}


def count(language, n, noun):
    """'1 story' / '3 stories'. The interface is English whatever the story filter."""
    forms = NOUNS['en'][noun]
    return f'{n} {forms[0] if n == 1 else forms[1]}'


def ui_language(language):
    """Interface language: always English; the language switch filters stories only."""
    return 'en'
