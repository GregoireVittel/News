#!/usr/bin/env python3
"""Direct-feed static editions. Standard library only; see README for build API."""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
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
    try:
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        try:
            date = parsedate_to_datetime(value)
        except (ValueError, TypeError):
            return None
    return date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date


def category(feed):
    import re
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
        articles.append({'title': title, 'link': link, 'description': plain(fields.get('description') or fields.get('summary') or fields.get('encoded') or fields.get('content', '')), 'date': parse_date(fields.get('pubDate') or fields.get('published') or fields.get('updated') or fields.get('date')), 'image': safe_url(image), 'sourceName': feed['name'], 'language': feed['language'], 'category': category(feed)})
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
import re
import shutil
import tempfile
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from story_classification import enrich_articles
else:
    from .story_classification import enrich_articles

ROOT = Path(__file__).resolve().parents[1]
PARIS = ZoneInfo('Europe/Paris')
LOG = logging.getLogger('edition')
SECTIONS = ('Poland', 'France', 'World', 'Technology')


def default_feeds():
    """Use the same approved publisher catalog as the live reader."""
    text = (ROOT / 'sources.js').read_text()
    catalog, _ = json.JSONDecoder().raw_decode(text.split('const sourceCatalog = ', 1)[1].lstrip())
    return [{key: feed[key] for key in ('url', 'name', 'language', 'category')}
            for feed in catalog if feed.get('url')]


def fetch_feed(feed):
    request = Request(feed['url'], headers={'User-Agent': 'PrzegladStatic/1.0 (RSS reader)', 'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml'})
    with urlopen(request, timeout=15) as response:
        data = response.read(4 * 1024 * 1024 + 1)
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


def snippet(article, length):
    value = article['description']
    return escape(value[:length].rstrip() + ('…' if len(value) > length else ''))


def story(article, kind='story'):
    a = article
    heading = 'h2' if kind == 'lead' else 'h3'
    image = ''
    if kind != 'rail-item':
        if a['image']:
            image = f'<img class="{"lead-image" if kind == "lead" else "story-image"}" src="{escape(a["image"], quote=True)}" alt="" loading="lazy">'
        elif kind == 'lead':
            image = '<div class="lead-placeholder" aria-hidden="true">P.</div>'
    return (f'<article class="{kind}" lang="{escape(a["language"], quote=True)}">{image}'
            f'<div class="eyebrow">{escape(a["section"])}</div><{heading}><a href="{escape(a["link"], quote=True)}" rel="noopener noreferrer">{escape(a["title"])}</a></{heading}>'
            f'<div class="meta"><span class="source">{escape(a["sourceName"])}</span> · <time datetime="{a["date"].isoformat()}">{a["date"].astimezone(PARIS).strftime("%d.%m %H:%M")}</time></div>'
            + f'<div class="meta">{a["sourceCount"]} {"source" if a["sourceCount"] == 1 else "sources"}</div>'
            + '<details class="source-list"><summary>Coverage sources</summary><ul>'
            + ''.join(f'<li><a href="{escape(s["url"], quote=True)}" rel="noopener noreferrer">{escape(s["name"])}</a></li>' for s in a['sources']) + '</ul></details>'
            + (f'<p>{snippet(a, 240 if kind == "lead" else 115)}</p>' if kind != 'rail-item' and a['description'] else '') + '</article>')


def page(base, canonical, title, body, now):
    stamp = now.astimezone(PARIS).isoformat(timespec='seconds')
    document_title = 'Przegląd' if title == 'Front page' else title + ' — Przegląd'
    return f'''<!DOCTYPE html>
<html lang="pl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&amp;family=Playfair+Display:wght@500;600;700;800&amp;display=swap" rel="stylesheet">
<title>{escape(document_title)}</title><meta name="description" content="What’s happening now… Publisher feed headlines and snippets.">
<meta property="og:type" content="website"><meta property="og:locale" content="pl_PL"><meta property="og:title" content="{escape(document_title, quote=True)}"><meta property="og:description" content="What’s happening now…"><meta property="og:url" content="{escape(canonical, quote=True)}">
<meta name="generated-at" content="{stamp}"><link rel="canonical" href="{escape(canonical, quote=True)}"><link rel="alternate" type="application/rss+xml" title="Przegląd RSS" href="{base}rss.xml"><link rel="stylesheet" href="{base}assets/portal.css"></head>
<body><div class="topline"><div class="shell"><span>THE DAILY BRIEFING · STORIES FROM AROUND THE WORLD</span><span>INDEPENDENT NEWS AGGREGATOR</span></div></div>
<header class="masthead"><div class="shell masthead-row"><div><a class="brand" href="{base}">Przegląd</a><div class="brand-sub">What’s happening now…</div></div><div class="edition">{now.astimezone(PARIS).strftime('%d.%m.%Y')}<br>Wygenerowano: <time datetime="{stamp}">{stamp}</time> · Europe/Paris</div><a class="manage-button" href="{base}live.html">Live (opcjonalnie)</a></div></header>
{body}<footer class="footer"><div class="shell"><a href="{base}archive/">Archiwum</a> · <a href="{base}rss.xml">RSS</a><p>Opisy to fragmenty z kanałów RSS wydawców — dotychczasowe zachowanie, nie autorskie streszczenia. Linki prowadzą do oryginalnych wydawców.</p><p>Wygenerowano {stamp} · Europe/Paris</p></div></footer></body></html>'''


def edition_page(articles, base, prefix, language, now, failures):
    selected = articles if language == 'All' else [a for a in articles if a['language'] == language]
    labels = {'All': 'Front page', 'pl': 'Polski', 'en': 'English', 'fr': 'Français'}
    nav = '<nav class="navwrap" aria-label="News language"><div class="shell navrow">'
    for lang, label in labels.items():
        href = base + prefix + ('' if lang == 'All' else lang + '/')
        nav += f'<a class="nav-button {"active" if lang == language else ""}" href="{href}"' + (' aria-current="page"' if lang == language else '') + f'>{label}</a>'
    body = nav + '</div></nav><main class="shell" id="main-content"><div class="edition-label">'
    body += f'<h1>{"The Front Page" if language == "All" else labels[language] + " Edition"}</h1><div class="statusline">{len(selected)} stories · past 24 hours · {len(failures)} feeds unavailable</div></div>'
    body += '<nav class="section-nav" aria-label="Sections">' + ' · '.join(f'<a href="#{s.lower()}">{s}</a>' for s in SECTIONS) + '</nav>'
    body += '<p class="classification-note">Ordered by distinct publisher count, then recency.</p>'
    for section in SECTIONS:
        items = [a for a in selected if a['section'] == section]
        body += f'<section class="section" id="{section.lower()}" aria-label="{section}"><div class="section-heading"><h2 class="section-title">{section}</h2><span>{len(items)} stories</span></div>'
        if items:
            body += '<div class="portal-grid section-lead">' + story(items[0], 'lead')
            body += '<div class="story-grid">' + ''.join(story(a) for a in items[1:]) + '</div></div>'
        else:
            body += '<p class="empty">No stories in this section for this edition.</p>'
        body += '</section>'
    suffix = '' if language == 'All' else language + '/'
    return page(base, base + prefix + suffix, labels[language], body + '</main>', now)


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
        archive = '<main class="shell"><div class="edition-label"><h1>Archiwum wydań</h1></div><ul>' + ''.join(f'<li><a href="{html_base}{date}/">{date}</a></li>' for date in editions) + '</ul></main>'
        (stage / 'archive').mkdir()
        (stage / 'archive/index.html').write_text(page(html_base, html_base + 'archive/', 'Archiwum', archive, now), encoding='utf-8')
        rss = ET.Element('rss', version='2.0')
        channel = ET.SubElement(rss, 'channel')
        for tag, value in [('title', 'Przegląd'), ('link', base), ('description', 'Fragmenty opisów z kanałów RSS wydawców; nie autorskie streszczenia.'), ('language', 'pl')]:
            ET.SubElement(channel, tag).text = value
        from email.utils import format_datetime
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
