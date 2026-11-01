"""Deterministic, offline enrichment of RSS article dictionaries (stdlib only)."""

from datetime import timezone
from difflib import SequenceMatcher
import re
import unicodedata
from urllib.parse import unquote_plus, urlsplit, urlunsplit

if __package__:
    from .story_events import same_event
else:
    from story_events import same_event


def _canonical(url):
    """Drop known tracking parameters only; keep semantic query/path/fragment."""
    parsed = urlsplit(url)
    kept = []
    for part in parsed.query.split('&'):
        key = unquote_plus(part.split('=', 1)[0]).casefold()
        if key.startswith('utm_') or key in {'fbclid', 'gclid', 'dclid', 'msclkid', 'mc_cid', 'mc_eid'}:
            continue
        if part:
            kept.append(part)
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path,
                       '&'.join(kept), parsed.fragment))


def _text(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold().replace('ł', 'l'))
                   if not unicodedata.combining(c))


TECH = r"(?<![\w'’])(?:ai|ia|artificial intelligence|intelligence artificielle|sztuczn\w* inteligenc\w*|technolog\w*|software|robot\w*|semiconductor\w*|semi-conduct\w*|chip\w*|nauk\w*|science|scientific|quantum|cyber\w*|openai|chatgpt|researchers?|chercheur\w*|badacz\w*|exoplan\w*|planet\w*|homeview|security camera|data cent(?:er|re)\w*)\b"
POLAND = r'\b(?:poland|polish|pologne|polon\w*|polsk\w*|warsaw|warszaw\w*|varsovie|krakow\w*|gdansk\w*)\b'
FRANCE = r'\b(?:france|french|francais\w*|francj\w*|francusk\w*|paris|paryz\w*|lyon|marseille)\b'
WORLD = r'\b(?:ukrain\w*|russi\w*|russie|rosj\w*|china|chinese|chine|chin\w*|german\w*|allemagne|niem\w*|israel\w*|gaza|united states|etats-unis|usa|britain|british|london|londres|londyn\w*|india|iran\w*|frankfurt\w*|frankfur\w*|american\w*|americain\w*|amerykan\w*)\b'


def _section(article):
    text = _text(article.get('title', '') + ' ' + article.get('description', ''))
    for pattern, section in ((TECH, 'Technology'), (POLAND, 'Poland'), (FRANCE, 'France'), (WORLD, 'World')):
        if re.search(pattern, text):
            return section, 'content: ' + section + ' subject evidence (technology first; Poland wins geographic ties)'
    category = article.get('category', '')
    section = category if category in ('Poland', 'France', 'Technology') else 'World'
    if re.search(TECH, _text(category)):
        section = 'Technology'
    return section, 'feed category fallback: ' + (category or 'World')


TITLE_NOISE = set('a an the today le la les un une dzis dzisiaj'.split())


def _same_title(left, right):
    """Match substantive title tokens or a narrowly supported event signature.

    High overlap alone is unsafe (launches/delays, place names, casualties).
    The token path ignores only function words and explicit headline noise;
    the signature path requires shared entity/action/object/cause evidence.
    """
    a = [t for t in re.findall(r'\w+', _text(left['title'])) if t not in TITLE_NOISE]
    b = [t for t in re.findall(r'\w+', _text(right['title'])) if t not in TITLE_NOISE]
    # Exact four-token headlines can be specific enough (e.g. a named mission).
    # Do not apply this exception to generic two/three-word headlines.
    exact_short = (len(set(a)) >= 4 and a == b)
    return (exact_short or (len(set(a)) >= 5 and set(a) == set(b)
             and SequenceMatcher(None, a, b, autojunk=False).ratio() >= 0.94)
            or same_event(left['title'], right['title']))


def _date_key(article):
    date = article.get('date')
    if date is None:
        return float('inf')
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return -date.timestamp()


def enrich_articles(articles):
    """Return unique enriched dictionaries, preserving original representative fields.

    Representatives are newest first, then lexical URL/source/title, independent
    of feed order. Sort stories by distinct publisher count, date descending,
    then original URL. ``classification.input`` records exactly the rule inputs.
    Provenance retains each distinct (publisher name, original URL) pair.
    """
    stories = []
    by_url = {}
    for article in sorted(articles, key=lambda a: (_date_key(a), a['link'], a['sourceName'], a['title'])):
        canonical = _canonical(article['link'])
        match = by_url.get(canonical)
        if match is None:
            match = next((story for story in stories if _same_title(article, story)), None)
        if match is not None:
            story = match
            by_url[canonical] = story
            source = dict(name=article['sourceName'], url=article['link'])
            if source not in story['sources']:
                story['sources'].append(source)
            count = len({_text(s['name']).strip() for s in story['sources']})
            story['sourceCount'] = count
            story['importance'] = dict(sourceCount=count)
            continue
        story = dict(article)
        section, reason = _section(article)
        story.update(sourceCategory=article.get('category', ''), section=section,
                     sectionReason=reason,
                     classification=dict(method='rules', version=1, input=dict(
                         title=article.get('title', ''), description=article.get('description', ''),
                         sourceCategory=article.get('category', ''))),
                     sources=[dict(name=article['sourceName'], url=article['link'])],
                     sourceCount=1, importance=dict(sourceCount=1))
        stories.append(story)
        by_url[canonical] = story
    return sorted(stories, key=lambda s: (-s['sourceCount'], _date_key(s), s['link']))
