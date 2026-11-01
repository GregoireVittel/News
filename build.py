#!/usr/bin/env python3
"""Generate a no-JavaScript edition from the existing reader's configured feeds."""
import argparse
import concurrent.futures
import datetime as dt
import email.utils
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

BASE_URL = 'https://gregoirevittel.github.io/News/'
CATEGORIES = ('Poland', 'France', 'Global news and geopolitics', 'Technology, AI and science', 'Financial markets and economics')
UTC = dt.timezone.utc


def text(node, *names):
    for name in names:
        for child in node:
            if child.tag.rsplit('}', 1)[-1].split(':')[-1] == name and child.text:
                return child.text.strip()
    return ''


def parse_date(value):
    if not value:
        return None
    try:
        date = email.utils.parsedate_to_datetime(value)
    except (ValueError, TypeError):
        try:
            date = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
    return date.replace(tzinfo=UTC) if date.tzinfo is None else date.astimezone(UTC)


def parse_feed(data, source, language, category='World'):
    root = ET.fromstring(data)
    items = [n for n in root.iter() if n.tag.rsplit('}', 1)[-1] in ('item', 'entry')]
    result = []
    for item in items:
        link = text(item, 'link')
        if not link:
            link = next((n.get('href', '') for n in item if n.tag.rsplit('}', 1)[-1] == 'link' and n.get('rel', 'alternate') == 'alternate'), '')
        published = parse_date(text(item, 'pubDate', 'published', 'updated', 'date'))
        if not published or urllib.parse.urlsplit(link).scheme not in ('https', 'http'):
            continue
        description = text(item, 'description', 'summary')
        description = html.unescape(re.sub(r'<[^>]*>', ' ', description))
        result.append(dict(title=text(item, 'title'), link=link, published=published, source=source,
                           language=language, category=category, summary=' '.join(description.split())[:240]))
    return result


def configured_feeds(catalog):
    block = catalog.split('const sourceCatalog = ', 1)[1]
    sources, _ = json.JSONDecoder().raw_decode(block.lstrip())
    return [dict(url=feed['url'], language=feed['language'], source=feed['name'], category=feed['category'])
            for feed in sources if feed.get('url')]


def fetch_one(feed):
    try:
        request = urllib.request.Request(feed['url'], headers={'User-Agent': 'PrzegladNews/1.0 (+https://gregoirevittel.github.io/News/)'})
        with urllib.request.urlopen(request, timeout=12) as response:
            data = response.read(3_000_001)
        if len(data) > 3_000_000:
            raise ValueError('feed exceeds size limit')
        return parse_feed(data, feed['source'], feed['language'], feed['category']), None
    except Exception as exc:
        return [], f"{feed['source']}: {exc}"


def fetch_all(feeds):
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(fetch_one, feeds))
    for _, error in results:
        if error:
            print(error, file=sys.stderr)
    return [entry for entries, _ in results for entry in entries]


def clean(entries, now):
    seen = set()
    valid = []
    for item in sorted(entries, key=lambda a: a['published'], reverse=True):
        if not now - dt.timedelta(days=1) <= item['published'] <= now or item['link'] in seen:
            continue
        seen.add(item['link'])
        valid.append(item)
    return valid


def generate(root, entries, now, base_url=BASE_URL):
    base_url = base_url.rstrip('/') + '/'
    current = clean(entries, now)
    if not current:
        raise ValueError('No recent articles: refusing to replace the current edition')
    reader = (root / 'live.html').read_text(encoding='utf-8')
    css = reader.split('<style>', 1)[1].split('</style>', 1)[0]
    date = now.date().isoformat()
    archive_dir = root / 'archive'
    archive_dir.mkdir(exist_ok=True)
    (root / 'lang').mkdir(exist_ok=True)
    archive_names = sorted([p.stem for p in archive_dir.glob('????-??-??.html')] + [date], reverse=True)
    archive_names = list(dict.fromkeys(archive_names))
    archive_links = ' · '.join(f'<a href="{base_url}archive/{name}.html">{name}</a>' for name in archive_names)

    def article(item, tag='h3', klass='story'):
        link = html.escape(item['link'], quote=True)
        title = html.escape(item['title'])
        summary = html.escape(item['summary'])
        source = html.escape(item['source'])
        published = item['published'].isoformat()
        return (f'<article class="{klass}"><div class="eyebrow">{html.escape(item["category"])}</div>'
                f'<{tag}><a href="{link}" rel="noopener noreferrer">{title}</a></{tag}>'
                f'<div class="meta"><span class="source">{source}</span> · <time datetime="{published}">{item["published"].strftime("%d %b %Y %H:%M UTC")}</time></div>'
                f'{"<p>" + summary + "</p>" if summary else ""}</article>')

    def page(items, title, canonical, page_lang='pl'):
        head = (f'<!doctype html><html lang="{page_lang}"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width, initial-scale=1">'
                f'<title>{html.escape(title)} · Przegląd</title>'
                f'<meta name="description" content="Przegląd — news edition for {date}, linked to original publishers.">'
                f'<link rel="canonical" href="{html.escape(canonical, quote=True)}">'
                f'<link rel="alternate" type="application/rss+xml" title="Przegląd RSS" href="{base_url}feed.xml">'
                f'<meta property="og:type" content="website"><meta property="og:title" content="{html.escape(title, quote=True)} · Przegląd">'
                f'<meta property="og:url" content="{html.escape(canonical, quote=True)}">'
                f'<meta property="og:description" content="Independent headlines linked to their publishers.">'
                f'<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">'
                f'<style>{css}</style></head><body>')
        nav = ' '.join(f'<a class="nav-button" href="{base_url}{path}">{label}</a>' for path, label in
                       (('', 'Front page'), ('lang/pl.html', 'Polski'), ('lang/en.html', 'English'), ('lang/fr.html', 'Français'), ('archive/', 'Archive'), ('live.html', 'Live reader')))
        body = (f'<div class="topline"><div class="shell">THE DAILY BRIEFING · STORIES FROM AROUND THE WORLD</div></div>'
                f'<header class="masthead"><div class="shell masthead-row"><a class="brand" href="{base_url}">Przegląd<span class="brand-mark">.</span></a>'
                f'<div class="edition">Edition {date}<br>Generated <time datetime="{now.isoformat()}">{now.strftime("%d %b %Y %H:%M UTC")}</time></div></div></header>'
                f'<nav class="navwrap" aria-label="News navigation"><div class="shell navrow">{nav}</div></nav>'
                f'<main class="shell" id="main-content"><div class="edition-label"><h1>{html.escape(title)}</h1><span class="statusline">{len(items)} stories · past 24 hours</span></div>')
        if items:
            lead, latest = items[0], items[1:4]
            body += (f'<div class="portal-grid"><div class="lead">{article(lead, "h2", "lead")}</div>'
                     f'<aside class="rail" aria-label="Latest headlines"><h2 class="rail-title">The latest</h2>'
                     f'{"".join(article(item, klass="rail-item") for item in latest)}</aside></div>')
            for category in CATEGORIES:
                selected = [item for item in items[4:] if item['category'] == category]
                if selected:
                    body += (f'<section class="section" aria-label="{category}"><div class="section-heading"><h2 class="section-title">{category}</h2>'
                             f'<span>{len(selected)} stories</span></div><div class="story-grid">'
                             f'{"".join(article(item) for item in selected)}</div></section>')
        else:
            body += '<p class="empty">No stories in this language for this edition.</p>'
        body += (f'<footer class="footer"><p>Archive: {archive_links}</p><p>Independent headlines linked to their original publishers.</p></footer></main></body></html>')
        return head + body

    (root / 'index.html').write_text(page(current, f'The Front Page · {date}', base_url), encoding='utf-8')
    (archive_dir / f'{date}.html').write_text(page(current, f'Edition {date}', base_url + f'archive/{date}.html'), encoding='utf-8')
    for language, label in [('pl', 'Polski'), ('en', 'English'), ('fr', 'Français')]:
        (root / 'lang' / f'{language}.html').write_text(page([a for a in current if a['language'] == language], label, base_url + f'lang/{language}.html', language), encoding='utf-8')
    archive_page = page([], 'Archive', base_url + 'archive/')
    archive_page = archive_page.replace('<p class="empty">No stories in this language for this edition.</p>',
                                        f'<section class="section"><h2 class="section-title">Previous editions</h2><p>{archive_links}</p></section>')
    (archive_dir / 'index.html').write_text(archive_page, encoding='utf-8')
    rss_items = ''.join(f'<item><title>{xml_escape(a["title"])}</title><link>{xml_escape(a["link"])}</link><guid isPermaLink="true">{xml_escape(a["link"])}</guid><pubDate>{email.utils.format_datetime(a["published"])}</pubDate><description>{xml_escape(a["source"] + ": " + a["summary"])}</description></item>' for a in current)
    (root / 'feed.xml').write_text(f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Przegląd</title><link>{xml_escape(base_url)}</link><description>Daily headlines</description>{rss_items}</channel></rss>', encoding='utf-8')
    urls = [base_url, base_url + 'archive/', base_url + 'feed.xml'] + [base_url + f'lang/{lang}.html' for lang in ('pl', 'en', 'fr')] + [base_url + f'archive/{name}.html' for name in archive_names]
    (root / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(f'<url><loc>{xml_escape(url)}</loc></url>' for url in urls) + '</urlset>', encoding='utf-8')
    return len(current)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--base-url', default=BASE_URL)
    args = parser.parse_args()
    now = dt.datetime.now(UTC)
    feeds = configured_feeds((args.root / 'sources.js').read_text(encoding='utf-8'))
    if not feeds:
        raise RuntimeError('No public feeds configured in source catalog')
    entries = fetch_all(feeds)
    count = generate(args.root, entries, now, args.base_url)
    print(f'Generated {count} stories from {len(feeds)} configured feeds at {now.isoformat()}')


if __name__ == '__main__':
    main()
