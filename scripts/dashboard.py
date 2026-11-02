"""Front-page dashboard panels and extra static pages (stdlib only, no JavaScript).

Every panel here links to stories rather than repeating story cards, so each
story keeps exactly one card in its own section.
"""
from collections import Counter, defaultdict
from datetime import date as Date, timedelta
from html import escape
from zoneinfo import ZoneInfo
import re
import unicodedata

PARIS = ZoneInfo("Europe/Paris")
NEW_WINDOW = timedelta(hours=3)
MOST_COVERED = 6
TRENDING = 12
TRENDING_MIN_STORIES = 3


def plural(count, one, many):
    return f'{count} {one if count == 1 else many}'


def is_new(article, now):
    return now - article['date'] <= NEW_WINDOW


def new_badge(article, now):
    return '<span class="badge-new">New</span>' if is_new(article, now) else ''


def _link(article):
    return f'<a href="{escape(article["link"], quote=True)}" rel="noopener noreferrer">{escape(article["title"])}</a>'


def publishers(articles):
    return Counter(source['name'] for article in articles for source in article['sources'])


# --- Most covered -----------------------------------------------------------

def most_covered(articles, labels):
    picks = [a for a in articles if a['sourceCount'] > 1][:MOST_COVERED]
    heading = ('<div class="section-heading"><h2 class="section-title" id="covered-title">Most covered</h2>'
               '<span>stories reported by several outlets</span></div>')
    if not picks:
        return (f'<section class="panel" aria-labelledby="covered-title">{heading}'
                '<p class="empty-mini">No story was covered by more than one outlet in this edition.</p></section>')
    rows = ''
    for a in picks:
        outlets = ', '.join(escape(name) for name in dict.fromkeys(s['name'] for s in a['sources']))
        rows += (f'<li><span class="coverage-count" aria-label="{a["sourceCount"]} outlets">{a["sourceCount"]}</span>'
                 f'<div><a class="mini-section" href="#{a["section"].lower()}">{labels.get(a["section"], a["section"])}</a>'
                 f'{_link(a)}<span class="mini-meta">{outlets}</span></div></li>')
    return f'<section class="panel" aria-labelledby="covered-title">{heading}<ol class="covered-list">{rows}</ol></section>'


# --- Trending keywords ------------------------------------------------------

STOPWORDS = set('''
a about after against ahead all also amid an and any are as at back be been before being but by can could day
days does down during each early first for from has have he her his how if in into is it its just last latest
least like live make man many may more most much new news not now of off on one only or other our out over
people plan plans report said say says she should since so some still than that the their them then there these
they this those three through to today top two under up us was way we week were what when where which while who
why will with without would year years you your get gets set sets takes take back being own amid against
au aux avec ce ces dans de des du elle en est et il ils la le les leur mais ne nous ou par pas pour qu que qui
sa se ses son sur un une vous apres avant comme contre deux entre fait plus sans selon sous tout tres ans dont
etre ete fin nouveau nouvelle ont peut premier premiere quand trois
a aby ale bez by byc co czy dla do gdy go i ich jak jako jej jest jego juz ma na nad nie niz o od oraz po pod
przed przez sie ta tak tam te to tu tylko w we wiec z za ze roku lat dzis jeszcze moze bedzie byl byla bylo
oraz ktore ktory ktora sa tez nowy nowe nowa ponad wsrod mowi dwa trzy polsce polska
january february march april june july august september october november december
monday tuesday wednesday thursday friday saturday sunday
janvier fevrier mars avril juin juillet aout septembre octobre novembre decembre
lundi mardi mercredi jeudi vendredi samedi dimanche
styczen styczna lutego marca kwietnia maja czerwca lipca sierpnia wrzesnia pazdziernika listopada grudnia
poniedzialek wtorek sroda czwartek piatek sobota niedziela
face faces video videos photo photos watch live update updates analysis opinion explainer interview review
says told amid calls call show shows looks look turns time times year week weeks month months next big
faire fait apres selon politique video direct entretien analyse lors alors encore personnes
wideo zdjecia relacja wywiad analiza opinia
'''.split())


def _norm(word):
    return ''.join(c for c in unicodedata.normalize('NFKD', word.casefold().replace('ł', 'l'))
                   if not unicodedata.combining(c))


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', _norm(text)).strip('-') or 'topic'


def trending(articles):
    """Return [(label, slug, [stories])] for words in the most distinct headlines."""
    stories = defaultdict(list)
    forms = defaultdict(Counter)
    for article in articles:
        seen = set()
        for word in re.findall(r"[^\W\d_][\w'’-]*", article['title']):
            word = word.strip("'’-")
            key = _norm(word)
            if len(key) < 4 or key in STOPWORDS or key in seen:
                continue
            seen.add(key)
            stories[key].append(article)
            forms[key][word] += 1
    ranked = sorted((k for k in stories if len(stories[k]) >= TRENDING_MIN_STORIES),
                    key=lambda k: (-len(stories[k]), k))
    chosen = []
    for key in ranked:
        links = {a['link'] for a in stories[key]}
        # Skip words that only ever appear alongside a stronger one ("Donald" with "Trump").
        if any(links <= {a['link'] for a in stories[other]} for other in chosen):
            continue
        chosen.append(key)
        if len(chosen) == TRENDING:
            break
    result = []
    for key in chosen:
        # Prefer a capitalised spelling (a name) when the headlines use one.
        label = max(forms[key].items(), key=lambda item: (item[0][:1].isupper(), item[1]))[0]
        label = {'paribas': 'BNP Paribas'}.get(key, label)
        result.append((label, slug(key), stories[key]))
    return result


def trending_panel(topics, base):
    heading = ('<div class="section-heading"><h2 class="section-title" id="trending-title">Trending</h2>'
               '<span>words in the most headlines</span></div>')
    if not topics:
        return (f'<section class="panel" aria-labelledby="trending-title">{heading}'
                '<p class="empty-mini">Not enough overlap between headlines yet.</p></section>')
    chips = ''.join(f'<li><a class="chip" href="{base}trending/#kw-{s}">{escape(label)} <span>{len(items)}</span></a></li>'
                    for label, s, items in topics)
    return (f'<section class="panel" aria-labelledby="trending-title">{heading}<ul class="chips">{chips}</ul>'
            f'<p class="mini-meta"><a href="{base}trending/">All trending topics →</a></p></section>')


def trending_page(topics, labels, now):
    if not topics:
        return '<p class="empty">Not enough overlap between headlines yet.</p>'
    body = '<ul class="chips">' + ''.join(f'<li><a class="chip" href="#kw-{s}">{escape(label)} <span>{len(items)}</span></a></li>'
                                        for label, s, items in topics) + '</ul>'
    for label, s, items in topics:
        body += (f'<section class="section" id="kw-{s}" aria-label="{escape(label, quote=True)}"><div class="section-heading">'
                 f'<h2 class="section-title">{escape(label)}</h2><span>{plural(len(items), "story", "stories")}</span></div>'
                 + headline_list(items, labels, now) + '</section>')
    return body


def headline_list(items, labels, now):
    rows = ''.join(f'<li><span class="mini-section">{labels.get(a["section"], a["section"])}</span>{_link(a)}'
                   f'<span class="mini-meta">{escape(a["sourceName"])} · {a["date"].astimezone(PARIS).strftime("%d.%m %H:%M")}{new_badge(a, now)}</span></li>'
                   for a in items)
    return f'<ol class="headline-list">{rows}</ol>'


# --- By source --------------------------------------------------------------

def sources_page(articles, labels, now):
    grouped = defaultdict(list)
    for article in articles:
        for name in dict.fromkeys(s['name'] for s in article['sources']):
            grouped[name].append(article)
    order = sorted(grouped, key=lambda name: (-len(grouped[name]), _norm(name)))
    if not order:
        return '<p class="empty">No stories in this edition.</p>'
    body = '<ul class="chips">' + ''.join(f'<li><a class="chip" href="#src-{slug(n)}">{escape(n)} <span>{len(grouped[n])}</span></a></li>'
                                        for n in order) + '</ul>'
    for name in order:
        body += (f'<section class="section" id="src-{slug(name)}" aria-label="{escape(name, quote=True)}"><div class="section-heading">'
                 f'<h2 class="section-title">{escape(name)}</h2><span>{plural(len(grouped[name]), "story", "stories")}</span></div>'
                 + headline_list(grouped[name], labels, now) + '</section>')
    return body


# --- Archive trend (inline SVG sparklines with native <title> tooltips) -------

def day_stats(articles, sections):
    return {'total': len(articles), 'publishers': len(publishers(articles)),
            'sections': {s: sum(1 for a in articles if a['section'] == s) for s in sections}}


def sparkline(points, label):
    """One section's daily counts as a 2px line with point markers and tooltips."""
    width, height, pad = 220, 48, 5
    peak = max(v for _, v in points) or 1
    step = (width - 2 * pad) / max(1, len(points) - 1)
    coords = [(pad + i * step if len(points) > 1 else width / 2, height - pad - (height - 2 * pad) * v / peak)
              for i, (_, v) in enumerate(points)]
    line = (f'<polyline class="spark-line" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in coords)}"/>'
            if len(coords) > 1 else '')
    dots = ''.join(f'<g><title>{day} · {plural(v, "story", "stories")}</title><circle class="hit" cx="{x:.1f}" cy="{y:.1f}" r="9"/>'
                   f'<circle class="spark-dot" cx="{x:.1f}" cy="{y:.1f}" r="3"/></g>'
                   for (day, v), (x, y) in zip(points, coords))
    return (f'<svg class="spark" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(label, quote=True)}: daily story counts">'
            f'{line}{dots}</svg>')


def archive_page(base, editions, stats, sections, labels):
    days = sorted(stats)[-30:]
    trend = '<section class="panel" aria-labelledby="trend-title"><div class="section-heading"><h2 class="section-title" id="trend-title">Daily trend</h2>'
    trend += f'<span>stories per section, last {plural(len(days), "day", "days")}</span></div>'
    if days:
        trend += '<div class="spark-grid">'
        for section in sections:
            points = [(d, stats[d]['sections'].get(section, 0)) for d in days]
            trend += (f'<div class="spark-card"><h3>{labels[section]}</h3>{sparkline(points, labels[section])}'
                      f'<span class="mini-meta">latest {points[-1][1]} · high {max(v for _, v in points)}</span></div>')
        trend += '</div>'
        if len(days) < 2:
            trend += '<p class="mini-meta">The trend lines fill in as more daily editions are published.</p>'
        table = ''.join(f'<tr><th scope="row">{d}</th><td>{stats[d]["total"]}</td>'
                        + ''.join(f'<td>{stats[d]["sections"].get(s, 0)}</td>' for s in sections) + '</tr>' for d in reversed(days))
        trend += ('<details class="data-table"><summary>Show as table</summary><div class="table-scroll"><table><thead><tr><th scope="col">Day</th><th scope="col">All</th>'
                  + ''.join(f'<th scope="col">{labels[s]}</th>' for s in sections) + f'</tr></thead><tbody>{table}</tbody></table></div></details>')
    else:
        trend += '<p class="empty-mini">No daily statistics recorded yet.</p>'
    trend += '</section>'
    available = set(editions)
    rows = ''
    for day in editions:
        week = (Date.fromisoformat(day) - timedelta(days=7)).isoformat()
        info = stats.get(day)
        rows += (f'<li><a href="{base}{day}/">{day}</a>'
                 + (f'<span class="mini-meta">{plural(info["total"], "story", "stories")}</span>' if info else '')
                 + (f' <a class="mini-meta" href="{base}{week}/">same day last week ({week})</a>' if week in available else '')
                 + '</li>')
    return (f'<main class="shell" id="main-content"><div class="edition-label"><h1>Edition archive</h1></div>{trend}'
            f'<section class="panel" aria-labelledby="editions-title"><div class="section-heading"><h2 class="section-title" id="editions-title">Editions</h2>'
            f'<span>{plural(len(editions), "edition", "editions")}</span></div><ul class="archive-list">{rows}</ul></section></main>')
