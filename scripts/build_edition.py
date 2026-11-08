#!/usr/bin/env python3
"""Direct-feed static editions. Standard library only; see README for build API."""
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime, parsedate_to_datetime
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET


class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        if tag in ('p', 'br', 'div'):
            self.parts.append(' ')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain(value):
    parser = Text()
    parser.feed(value or '')
    return ' '.join(''.join(parser.parts).split())


def safe_url(value):
    value = (value or '').strip()
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme in ('https', 'http') and parsed.hostname and not parsed.username and not any(ord(c) < 33 for c in value) else ''
    except ValueError:
        return ''


def parse_date(value):
    if not value:
        return None
    try:
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        try:
            date = parsedate_to_datetime(value)
        except (ValueError, TypeError):
            return None
    return date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date


def category(feed):
    if feed.get('category'):
        return feed['category']
    text = feed['name'] + feed['url']
    for pattern, result in [('biznes|money|bankier|financial|ft\\.com', 'Business'), ('nauka|technolog', 'Technology'), ('sport', 'Sports'), ('zdrowie', 'Lifestyle')]:
        if re.search(pattern, text, re.I):
            return result
    return 'World'


def parse_feed(data, feed):
    root = ET.fromstring(data)
    articles = []
    for node in root.iter():
        if node.tag.split('}')[-1] not in ('item', 'entry'):
            continue
        fields = {}
        link = image = ''
        for child in node:
            tag = child.tag.split('}')[-1]
            fields.setdefault(tag, ''.join(child.itertext()).strip())
            if tag == 'link' and child.get('rel', 'alternate') == 'alternate':
                link = child.get('href') or (child.text or '').strip()
            if tag in ('thumbnail', 'enclosure', 'content') and child.get('url'):
                if tag != 'enclosure' or child.get('type', '').startswith('image/'):
                    image = child.get('url')
        link = safe_url(link)
        title = plain(fields.get('title', ''))
        if not link or not title:
            continue
        article = {'title': title, 'link': link, 'description': plain(fields.get('description') or fields.get('summary') or fields.get('encoded') or fields.get('content', '')), 'date': parse_date(fields.get('pubDate') or fields.get('published') or fields.get('updated') or fields.get('date')), 'image': safe_url(image), 'sourceName': feed['name'], 'language': feed['language'], 'category': category(feed)}
        google = urlsplit(feed.get('url', '')).hostname == 'news.google.com' or feed['name'].startswith('Google News')
        if feed.get('aggregator') or google:
            article['aggregator'] = True
            article['sourceName'] = plain(fields.get('source', '')) or 'Publisher unknown (aggregated feed)'
        if feed.get('subgroup') == 'BNP Paribas':
            if not bnp_bank_article(article):
                continue
            article['subgroup'] = 'BNP Paribas'
        articles.append(article)
    return articles


from concurrent.futures import ThreadPoolExecutor
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
import argparse
import json
import logging
import os
import shutil
import tempfile
import time
import sys
from urllib.error import HTTPError, URLError

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from story_classification import enrich_articles, bnp_bank_article
    import dashboard
    import i18n
else:
    from .story_classification import enrich_articles, bnp_bank_article
    from . import dashboard, i18n

ROOT = Path(__file__).resolve().parents[1]
PARIS = ZoneInfo('Europe/Paris')
LOG = logging.getLogger('edition')
SECTIONS = ('Poland', 'France', 'World', 'Technology', 'Financial')
SITE_TITLE = "What's happening in the World"
MENU = i18n.MENU  # display order: World / Poland / France / Global Markets / Tech
SECTION_LABELS = dict(i18n.TEXT['en']['sections'])


def default_feeds():
    """Use the same approved publisher catalog as the live reader."""
    text = (ROOT / 'sources.js').read_text()
    catalog, _ = json.JSONDecoder().raw_decode(text.split('const sourceCatalog = ', 1)[1].lstrip())
    return [{key: feed[key] for key in ('url', 'name', 'language', 'category', 'subgroup', 'aggregator') if key in feed}
            for feed in catalog if feed.get('url')]


def _transient(error):
    """Network hiccups, timeouts, rate limits and server errors are worth one retry."""
    if isinstance(error, HTTPError):
        return error.code == 429 or error.code >= 500
    return isinstance(error, (URLError, TimeoutError, ConnectionError))


def fetch_feed(feed, attempts=2, backoff=2.0):
    request = Request(feed['url'], headers={'User-Agent': 'WorldNewsStatic/1.0 (RSS reader)', 'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml'})
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=15) as response:
                data = response.read(4 * 1024 * 1024 + 1)
            break
        except Exception as error:
            if attempt == attempts or not _transient(error):
                raise
            LOG.info('Retrying %s after %s', feed['name'], type(error).__name__)
            time.sleep(backoff * attempt)
    if len(data) > 4 * 1024 * 1024:
        raise ValueError('Feed exceeds 4 MiB limit')
    return data


def collect(feeds, fetcher, now):
    def one(feed):
        try:
            articles = parse_feed(fetcher(feed), feed)
            if not articles:
                raise ValueError('No usable RSS/Atom entries')
            return articles, None
        except Exception as error:
            failure = f"{feed['name']} ({feed['url']}): {type(error).__name__}: {error}"
            LOG.warning('Feed failed: %s', failure)
            return [], failure
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(one, feeds))
    articles = [a for items, _ in results for a in items if a['date'] is not None and now - timedelta(hours=24) <= a['date'] <= now]
    articles.sort(key=lambda a: a['date'], reverse=True)
    seen = set()
    unique = []
    for article in articles:
        key = (article['link'], article['sourceName'].casefold())
        if key not in seen:
            seen.add(key)
            unique.append(article)
    if not unique:
        raise ValueError('Empty edition: no valid articles from the past 24 hours; publication refused')
    return unique, [failure for _, failure in results if failure]


def plural(count, one, many):
    return f'{count} {one if count == 1 else many}'


def snippet(article, length):
    value = article['description']
    return escape(value[:length].rstrip() + ('…' if len(value) > length else ''))


def story(article, kind='story', now=None, lang='en'):
    a = article
    t = i18n.TEXT[lang]
    badge = dashboard.new_badge(a, now, t['new']) if now else ''
    heading = 'h2' if kind == 'lead' else 'h3'
    image = ''
    if kind != 'rail-item':
        if a['image']:
            image = f'<img class="{"lead-image" if kind == "lead" else "story-image"}" src="{escape(a["image"], quote=True)}" alt="" loading="lazy">'
        elif kind == 'lead':
            image = '<div class="lead-placeholder" aria-hidden="true">W.</div>'
    return (f'<article class="{kind}" lang="{escape(a["language"], quote=True)}">{image}'
            f'<div class="eyebrow">{escape(t["sections"].get(a["section"], a["section"]))}</div><{heading}><a href="{escape(a["link"], quote=True)}" rel="noopener noreferrer">{escape(a["title"])}</a></{heading}>'
            f'<div class="meta"><span class="source">{escape(a["sourceName"])}</span> · <time datetime="{a["date"].isoformat()}">{a["date"].astimezone(PARIS).strftime("%d.%m %H:%M")}</time>{badge}</div>'
            + f'<div class="meta">{i18n.count(lang, a["sourceCount"], "source")}</div>'
            + f'<details class="source-list"><summary>{t["coverage_sources"]}</summary><ul>'
            + ''.join(f'<li><a href="{escape(s["url"], quote=True)}" rel="noopener noreferrer">{escape(s["name"])}</a></li>' for s in a['sources']) + '</ul></details>'
            + (f'<p class="meta">{t["google_note"]}</p>'
               if any(urlsplit(s['url']).hostname == 'news.google.com' for s in a['sources']) else '')
            + (f'<p>{snippet(a, 240 if kind == "lead" else 115)}</p>' if kind != 'rail-item' and a['description'] else '') + '</article>')


TOP_STORIES = 7


def top_stories(articles, now=None, lang='en'):
    """Front-page digest: the highest-ranked stories across all sections.

    Rendered as a ranked list of links, not as story cards, so each story still
    has exactly one card in its own section.
    """
    picks = articles[:TOP_STORIES]
    if not picks:
        return ''
    t = i18n.TEXT[lang]

    def item(a, lead):
        when = a['date']
        image = ''
        if lead and a['image']:
            image = f'<img class="lead-image" src="{escape(a["image"], quote=True)}" alt="" loading="lazy">'
        meta = (f'<div class="meta"><span class="source">{escape(a["sourceName"])}</span> · '
                f'<time datetime="{when.isoformat()}">{when.astimezone(PARIS).strftime("%d.%m %H:%M")}</time> · '
                f'{i18n.count(lang, a["sourceCount"], "source")}{dashboard.new_badge(a, now, t["new"]) if now else ""}</div>')
        heading = 'h3'
        text = f'<p>{snippet(a, 240)}</p>' if lead and a['description'] else ''
        return (f'<li class="{"lead top-lead" if lead else "rail-item"}" lang="{escape(a["language"], quote=True)}">{image}'
                f'<a class="eyebrow" href="#{a["section"].lower()}">{escape(t["sections"].get(a["section"], a["section"]))}</a>'
                f'<{heading}><a href="{escape(a["link"], quote=True)}" rel="noopener noreferrer">{escape(a["title"])}</a></{heading}>'
                f'{meta}{text}</li>')

    rail = ''.join(item(a, False) for a in picks[1:])
    return ('<section class="top-stories" aria-labelledby="top-stories-title">'
            f'<div class="section-heading"><h2 class="section-title" id="top-stories-title">{t["top_stories"]}</h2>'
            f'<span>{t["top_stories_note"]}</span></div>'
            '<div class="portal-grid"><ol class="top-lead-list">' + item(picks[0], True) + '</ol>'
            + (f'<ol class="rail top-rail" start="2">{rail}</ol>' if rail else '') + '</div></section>')


def page(base, canonical, title, body, now, lang='en', home=None, front=False):
    """Wrap a page body. Interface text follows lang (en/fr/pl); front marks a front page."""
    t = i18n.TEXT[i18n.ui_language(lang)]
    home = base if home is None else home
    stamp = now.astimezone(PARIS).isoformat(timespec='seconds')
    site = t['site_title']
    document_title = site if front or title == 'Front Page' else title + ' — ' + site
    return f'''<!DOCTYPE html>
<html lang="{lang}"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&amp;family=Playfair+Display:wght@500;600;700;800&amp;display=swap" rel="stylesheet">
<title>{escape(document_title)}</title><meta name="description" content="{escape(t['description'], quote=True)}">
<meta property="og:type" content="website"><meta property="og:locale" content="{t['og_locale']}"><meta property="og:title" content="{escape(document_title, quote=True)}"><meta property="og:description" content="{escape(t['tagline'], quote=True)}"><meta property="og:url" content="{escape(canonical, quote=True)}">
<meta name="color-scheme" content="dark"><meta name="theme-color" content="#090b0e"><meta name="generated-at" content="{stamp}"><link rel="canonical" href="{escape(canonical, quote=True)}"><link rel="alternate" type="application/rss+xml" title="{escape(SITE_TITLE, quote=True)} RSS" href="{base}rss.xml"><link rel="stylesheet" href="{base}assets/portal.css"></head>
<body><a class="skip-link" href="#main-content">{t['skip']}</a><div class="topline"><div class="shell"><span>{t['topline'][0]}</span><span>{t['topline'][1]}</span></div></div>
<header class="masthead"><div class="shell masthead-row"><div><a class="brand" href="{home}">{escape(site)}</a><div class="brand-sub">{t['tagline']}</div></div><div class="edition">{now.astimezone(PARIS).strftime('%d.%m.%Y')}<br>{t['updated']} <time datetime="{stamp}">{stamp}</time> · Europe/Paris</div><a class="manage-button" href="{base}live.html">{t['live_reader']}</a></div></header>
{body}<footer class="footer"><div class="shell"><a href="{base}sources/">{t['by_source']}</a> · <a href="{base}trending/">{t['trending']}</a> · <a href="{base}archive/">{t['archive']}</a> · <a href="{base}rss.xml">RSS</a><p>{t['footer_note']}</p><p>{t['updated']} {stamp} · Europe/Paris</p></div></footer></body></html>'''


def language_href(base, prefix, lang):
    """English is the default front page; French and Polish live in fr/ and pl/."""
    return f'{base}{prefix}' + ('' if lang == 'en' else f'{lang}/')


def edition_page(articles, base, prefix, language, now, failures):
    """Render a front page. language is 'All' (English default) or en/fr/pl.

    Every language shows the same stories; only the interface text changes,
    because stories are never translated.
    """
    lang = i18n.ui_language(language)
    t = i18n.TEXT[lang]
    labels = t['sections']
    home = language_href(base, prefix, lang)
    nav = f'<nav class="navwrap" aria-label="{t["sections_nav"]}"><div class="shell navrow">'
    for section in MENU:
        nav += f'<a class="nav-button" href="#{section.lower()}">{escape(labels[section])}</a>'
    nav += f'<span class="nav-languages" role="group" aria-label="{t["language_nav"]}">'
    for code in i18n.LANGUAGES:
        current = code == lang
        nav += (f'<a class="nav-language{" active" if current else ""}" href="{language_href(base, prefix, code)}" '
                f'hreflang="{code}" lang="{code}"' + (' aria-current="true"' if current else '')
                + f'>{i18n.LANGUAGE_NAMES[code]}</a>')
    body = nav + '</span></div></nav><main class="shell" id="main-content"><div class="edition-label">'
    body += (f'<h1>{t["front_page"]}</h1><div class="statusline">{i18n.count(lang, len(articles), "story")} · {t["past_day"]} · '
             + t['feeds_unavailable'].format(feeds=i18n.count(lang, len(failures), 'feed')) + '</div></div>')
    if failures:
        body += (f'<details class="feed-failures"><summary>{t["unavailable_feeds"]}</summary><ul>'
                 + ''.join(f'<li>{escape(failure.split(" (", 1)[0])}</li>' for failure in failures) + '</ul></details>')
    body += f'<p class="classification-note">{t["ordering"]}</p>'
    body += top_stories(articles, now, lang)
    if articles:
        body += ('<div class="panel-pair">' + dashboard.most_covered(articles, labels, t)
                 + dashboard.trending_panel(dashboard.trending(articles), base, t) + '</div>')
    for section in MENU:
        items = [a for a in articles if a['section'] == section]
        body += f'<section class="section" id="{section.lower()}" aria-label="{section}"><div class="section-heading"><h2 class="section-title">{escape(labels[section])}</h2><span>{i18n.count(lang, len(items), "story")}</span></div>'
        subgroup = [a for a in items if a.get('subgroup') == 'BNP Paribas'] if section == 'Financial' else []
        if section == 'Financial':
            body += '<p><a href="#bnp-paribas">BNP Paribas</a></p>'
            items = [a for a in items if a.get('subgroup') != 'BNP Paribas']
        if items:
            body += '<div class="portal-grid section-lead">' + story(items[0], 'lead', now, lang)
            body += '<div class="story-grid">' + ''.join(story(a, now=now, lang=lang) for a in items[1:]) + '</div></div>'
        elif not subgroup:
            body += f'<p class="empty">{t["empty_section"]}</p>'
        if section == 'Financial':
            body += '<section id="bnp-paribas" aria-label="BNP Paribas"><div class="section-heading"><h3 class="section-title">BNP Paribas</h3>' + f'<span>{i18n.count(lang, len(subgroup), "story")}</span></div>'
            body += ('<div class="story-grid">' + ''.join(story(a, now=now, lang=lang) for a in subgroup) + '</div>'
                     if subgroup else f'<p class="empty">{t["empty_bnp"]}</p>')
            body += '</section>'
        body += '</section>'
    suffix = '' if language == 'All' else language + '/'
    return page(base, base + prefix + suffix, t['front_page'], body + '</main>', now, lang, home=home, front=True)


def load_stats(history):
    """Daily counts carried over from the previously published site."""
    try:
        days = json.loads((history / 'stats.json').read_text(encoding='utf-8'))['days']
        return {day: value for day, value in days.items() if re.fullmatch(r'\d{4}-\d{2}-\d{2}', day)
                and isinstance(value, dict) and isinstance(value.get('sections'), dict)}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def build(output, base_url, *, now=None, feeds=None, fetcher=None, history_root=None):
    """Atomically install a complete site into absent/empty output; never publish it.

    history_root defaults to repository root; only existing dated editions are copied.
    now must be timezone-aware. feeds/fetcher are offline test injection only.
    Returns edition, article_count, failures, generated_at, and output.
    """
    output = Path(output).resolve()
    if output == ROOT or ROOT in output.parents and output.name in ('assets', 'scripts', 'tests'):
        raise ValueError('Output must be a dedicated staging directory')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('Output must be absent or an empty staging directory')
    base = safe_url(base_url)
    if not base or urlsplit(base).query or urlsplit(base).fragment or not base.endswith('/'):
        raise ValueError('base_url must be an absolute HTTP(S) site URL ending in /, without query or fragment')
    # Escape once for HTML URL attributes; XML receives the unescaped original.
    html_base = escape(base, quote=True)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('now must be timezone-aware')
    edition = now.astimezone(PARIS).date().isoformat()
    articles, failures = collect(default_feeds() if feeds is None else feeds, fetcher or fetch_feed, now)
    articles = enrich_articles(articles)
    data = {'schemaVersion': 2, 'generatedAt': now.astimezone(PARIS).isoformat(timespec='seconds'),
            'sections': list(SECTIONS),
            'articles': [dict(a, date=a['date'].isoformat()) for a in articles]}
    serialized = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.edition-', dir=output.parent))
    try:
        history = Path(history_root) if history_root is not None else ROOT
        if history.exists():
            for path in history.iterdir():
                if re.fullmatch(r'\d{4}-\d{2}-\d{2}', path.name) and path.is_dir() and not path.is_symlink() and (path / 'index.html').is_file():
                    datetime.strptime(path.name, '%Y-%m-%d')
                    shutil.copytree(path, stage / path.name, symlinks=False)
        (stage / 'assets').mkdir()
        (stage / 'articles.json').write_text(serialized, encoding='utf-8')
        shutil.copy2(ROOT / 'assets/portal.css', stage / 'assets/portal.css')
        shutil.copy2(ROOT / 'live.html', stage / 'live.html')
        shutil.copy2(ROOT / 'feed-utils.js', stage / 'feed-utils.js')
        shutil.copy2(ROOT / 'sources.js', stage / 'sources.js')
        for prefix in ('', edition + '/'):
            if prefix and (stage / edition / 'index.html').exists():
                continue  # first published edition of a Paris calendar day is immutable
            for language in ('All', 'pl', 'en', 'fr'):
                relative = prefix + ('' if language == 'All' else language + '/') + 'index.html'
                target = stage / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(edition_page(articles, html_base, prefix, language, now, failures), encoding='utf-8')
            if prefix:
                (stage / edition / 'articles.json').write_text(serialized, encoding='utf-8')
        (stage / 'lang').mkdir()
        for language in ('pl', 'en', 'fr'):
            shutil.copy2(stage / language / 'index.html', stage / 'lang' / f'{language}.html')
        editions = sorted((p.name for p in stage.iterdir() if re.fullmatch(r'\d{4}-\d{2}-\d{2}', p.name) and (p / 'index.html').is_file()), reverse=True)
        stats = load_stats(history)
        stats[edition] = dashboard.day_stats(articles, SECTIONS)
        (stage / 'stats.json').write_text(json.dumps({'schemaVersion': 1, 'days': stats}, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        archive = dashboard.archive_page(html_base, editions, stats, MENU, SECTION_LABELS)
        (stage / 'archive').mkdir()
        (stage / 'archive/index.html').write_text(page(html_base, html_base + 'archive/', 'Archive', archive, now), encoding='utf-8')
        for folder, title, content in (
                ('sources', 'By source', dashboard.sources_page(articles, SECTION_LABELS, now)),
                ('trending', 'Trending', dashboard.trending_page(dashboard.trending(articles), SECTION_LABELS, now))):
            (stage / folder).mkdir()
            body = (f'<main class="shell" id="main-content"><div class="edition-label"><h1>{title}</h1>'
                    f'<div class="statusline"><a href="{html_base}">← Front Page</a></div></div>{content}</main>')
            (stage / folder / 'index.html').write_text(page(html_base, f'{html_base}{folder}/', title, body, now), encoding='utf-8')
        rss = ET.Element('rss', version='2.0')
        channel = ET.SubElement(rss, 'channel')
        for tag, value in [('title', SITE_TITLE), ('link', base), ('description', "Snippets from publishers' RSS feeds, not original summaries."), ('language', 'en')]:
            ET.SubElement(channel, tag).text = value
        ET.SubElement(channel, 'lastBuildDate').text = format_datetime(now)
        for a in articles:
            item = ET.SubElement(channel, 'item')
            for tag, value in [('title', a['title']), ('link', a['link']), ('guid', a['link']), ('description', a['description'][:240]), ('pubDate', format_datetime(a['date']))]:
                ET.SubElement(item, tag).text = value
        ET.ElementTree(rss).write(stage / 'rss.xml', encoding='utf-8', xml_declaration=True)
        shutil.copy2(stage / 'rss.xml', stage / 'feed.xml')
        sitemap = ET.Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
        for relative in sorted(p.relative_to(stage).as_posix() for p in stage.rglob('index.html')):
            url = ET.SubElement(sitemap, 'url')
            ET.SubElement(url, 'loc').text = base + relative.removesuffix('index.html')
        ET.ElementTree(sitemap).write(stage / 'sitemap.xml', encoding='utf-8', xml_declaration=True)
        result = {'edition': edition, 'article_count': len(articles), 'failures': failures, 'generated_at': now.astimezone(PARIS).isoformat(timespec='seconds'), 'output': str(output)}
        (stage / 'build-info.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        os.replace(stage, output)
        return result
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--history-root', type=Path, default=ROOT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    try:
        result = build(args.output, args.base_url, history_root=args.history_root)
    except Exception as error:
        LOG.error('Build refused: %s', error)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
