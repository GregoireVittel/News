"""Interface text for the English, French and Polish editions (stdlib only).

Only the page furniture is translated; story titles and snippets stay in the
language the publisher wrote them in (no automatic translation).
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
        'language_nav': 'Language',
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
    'fr': {
        'sections': {'World': 'Monde', 'Poland': 'Pologne', 'France': 'France',
                     'Financial': 'Marchés mondiaux', 'Technology': 'Tech'},
        'site_title': 'Ce qui se passe dans le monde',
        'tagline': 'Ce qui se passe maintenant…',
        'topline': ('LE BRIEFING QUOTIDIEN · L’ACTUALITÉ DU MONDE ENTIER', 'AGRÉGATEUR D’ACTUALITÉS INDÉPENDANT'),
        'skip': 'Aller au contenu',
        'updated': 'Mis à jour',
        'live_reader': 'Lecteur en direct',
        'front_page': 'À la une',
        'sections_nav': 'Rubriques',
        'language_nav': 'Langue',
        'past_day': 'dernières 24 heures',
        'feeds_unavailable': '{feeds} indisponible(s)',
        'unavailable_feeds': 'Flux indisponibles',
        'ordering': 'Classés par nombre de médias distincts, puis par date.',
        'top_stories': 'L’essentiel',
        'top_stories_note': 'les plus repris, puis les plus récents',
        'coverage_sources': 'Sources',
        'google_note': 'Agrégation RSS Google News ; les liens Google News redirigent vers les médias. Les extraits proviennent des flux RSS, ce ne sont pas des résumés originaux.',
        'empty_section': 'Aucun article dans cette rubrique pour cette édition.',
        'empty_bnp': 'Aucun article sur BNP Paribas dans cette édition.',
        'new': 'Nouveau',
        'most_covered': 'Les plus couverts',
        'most_covered_note': 'sujets repris par plusieurs médias',
        'most_covered_empty': 'Aucun sujet n’a été couvert par plus d’un média dans cette édition.',
        'outlets': 'médias',
        'trending': 'Tendances',
        'trending_note': 'mots présents dans le plus de titres',
        'trending_empty': 'Pas encore assez de recoupements entre les titres.',
        'trending_all': 'Toutes les tendances →',
        'by_source': 'Par source',
        'archive': 'Archives',
        'footer_note': 'Les descriptions sont des extraits des flux RSS des médias ou des agrégateurs, pas des résumés originaux. Les liens mènent aux médias directement ou via Google News.',
        'og_locale': 'fr_FR',
        'description': 'Ce qui se passe maintenant… Titres et extraits des flux des médias.',
    },
    'pl': {
        'sections': {'World': 'Świat', 'Poland': 'Polska', 'France': 'Francja',
                     'Financial': 'Rynki globalne', 'Technology': 'Technologie'},
        'site_title': 'Co dzieje się na świecie',
        'tagline': 'Co dzieje się teraz…',
        'topline': ('CODZIENNY PRZEGLĄD · WIADOMOŚCI Z CAŁEGO ŚWIATA', 'NIEZALEŻNY AGREGATOR WIADOMOŚCI'),
        'skip': 'Przejdź do treści',
        'updated': 'Aktualizacja',
        'live_reader': 'Czytnik na żywo',
        'front_page': 'Strona główna',
        'sections_nav': 'Działy',
        'language_nav': 'Język',
        'past_day': 'ostatnie 24 godziny',
        'feeds_unavailable': 'niedostępne: {feeds}',
        'unavailable_feeds': 'Niedostępne kanały',
        'ordering': 'Kolejność według liczby wydawców, potem według czasu publikacji.',
        'top_stories': 'Najważniejsze',
        'top_stories_note': 'najwięcej wydawców, potem najnowsze',
        'coverage_sources': 'Źródła',
        'google_note': 'Agregacja RSS Google News; linki Google News przekierowują do wydawców. Opisy to fragmenty z kanałów RSS, nie oryginalne streszczenia.',
        'empty_section': 'Brak artykułów w tym dziale w tym wydaniu.',
        'empty_bnp': 'Brak artykułów o BNP Paribas w tym wydaniu.',
        'new': 'Nowe',
        'most_covered': 'Najszerzej opisywane',
        'most_covered_note': 'tematy podjęte przez kilka redakcji',
        'most_covered_empty': 'W tym wydaniu żaden temat nie pojawił się u więcej niż jednego wydawcy.',
        'outlets': 'redakcje',
        'trending': 'Na czasie',
        'trending_note': 'słowa w największej liczbie nagłówków',
        'trending_empty': 'Nagłówki jeszcze się nie pokrywają.',
        'trending_all': 'Wszystkie tematy →',
        'by_source': 'Według źródła',
        'archive': 'Archiwum',
        'footer_note': 'Opisy to fragmenty kanałów RSS wydawców lub agregatorów, a nie oryginalne streszczenia. Linki prowadzą do wydawców bezpośrednio lub przez Google News.',
        'og_locale': 'pl_PL',
        'description': 'Co dzieje się teraz… Nagłówki i fragmenty z kanałów wydawców.',
    },
}

NOUNS = {
    'en': {'story': ('story', 'stories'), 'source': ('source', 'sources'), 'feed': ('feed', 'feeds')},
    'fr': {'story': ('article', 'articles'), 'source': ('source', 'sources'), 'feed': ('flux', 'flux')},
    'pl': {'story': ('artykuł', 'artykuły', 'artykułów'), 'source': ('źródło', 'źródła', 'źródeł'),
           'feed': ('kanał', 'kanały', 'kanałów')},
}


def count(language, n, noun):
    """'3 stories' / '3 articles' / '3 artykuły' with each language's plural rules."""
    forms = NOUNS[language][noun]
    if language == 'pl':
        if n == 1:
            word = forms[0]
        elif n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
            word = forms[1]
        else:
            word = forms[2]
    elif language == 'fr':
        word = forms[0] if n in (0, 1) else forms[1]
    else:
        word = forms[0] if n == 1 else forms[1]
    return f'{n} {word}'


def ui_language(language):
    """Edition language code ('All' is the English front page)."""
    return language if language in LANGUAGES else 'en'
