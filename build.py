#!/usr/bin/env python3
"""Generate a no-JavaScript edition from the existing reader's configured feeds."""
import argparse
import concurrent.futures
import datetime as dt
import email.utils
import html
import json
import re
import shutil
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape
from scripts.build_edition import SECTIONS, SITE_TITLE, edition_page, page as portal_page
from scripts.story_classification import enrich_articles

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
        request = urllib.request.Request(feed['url'], headers={'User-Agent': 'WorldNews/1.0 (+https://gregoirevittel.github.io/News/)'})
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
        key = (item['link'], item['source'].casefold())
        if not now - dt.timedelta(days=1) <= item['published'] <= now or key in seen:
            continue
        seen.add(key)
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

    articles = enrich_articles([dict(title=a['title'], link=a['link'],
                                    description=a['summary'], date=a['published'],
                                    image=a.get('image', ''), sourceName=a['source'],
                                    language=a['language'], category=a['category']) for a in current])
    articles.sort(key=lambda article: (article['sourceCount'], article['date']), reverse=True)
    data = dict(schemaVersion=2, generatedAt=now.isoformat(), sections=list(SECTIONS),
                articles=articles)
    (root / 'articles.json').write_text(
        json.dumps(data, ensure_ascii=False, indent=2,
                   default=lambda value: value.isoformat()) + '\n', encoding='utf-8')
    html_base = html.escape(base_url, quote=True)
    (root / 'assets').mkdir(exist_ok=True)
    portal_css = Path(__file__).resolve().parent / 'assets/portal.css'
    target_css = root / 'assets/portal.css'
    if portal_css.resolve() != target_css.resolve():
        shutil.copy2(portal_css, target_css)

    def compatibility_page(rendered, canonical, language='pl'):
        # Retain legacy URLs and UTC build metadata while sharing all story markup.
        rendered = re.sub(r'(<link rel="canonical" href=")[^"]*',
                          lambda match: match[1] + html.escape(canonical, quote=True), rendered)
        rendered = re.sub(r'(<meta property="og:url" content=")[^"]*',
                          lambda match: match[1] + html.escape(canonical, quote=True), rendered)
        rendered = rendered.replace('<html lang="pl">', f'<html lang="{language}">')
        for lang in ('pl', 'en', 'fr'):
            rendered = rendered.replace(f'href="{html_base}{lang}/"',
                                        f'href="{html_base}lang/{lang}.html"')
        rendered = rendered.replace(f'href="{html_base}rss.xml"', f'href="{html_base}feed.xml"')
        return rendered.replace('</head>', f'<style>{css}</style>'
                                f'<meta name="legacy-generated-at" content="{now.isoformat()}"></head>')

    def legacy_edition(language, canonical):
        return compatibility_page(edition_page(articles, html_base, '', language, now, []),
                                  canonical, 'pl' if language == 'All' else language)

    (root / 'index.html').write_text(legacy_edition('All', base_url), encoding='utf-8')
    archive_target = archive_dir / f'{date}.html'
    if not archive_target.exists():
        archive_target.write_text(legacy_edition('All', base_url + f'archive/{date}.html'), encoding='utf-8')
    for language in ('pl', 'en', 'fr'):
        (root / 'lang' / f'{language}.html').write_text(legacy_edition(language, base_url + f'lang/{language}.html'), encoding='utf-8')
    body = f'<main class="shell"><h1>Previous editions</h1><p>{archive_links}</p></main>'
    archive_page = compatibility_page(portal_page(html_base, html_base + 'archive/', 'Archive', body, now), base_url + 'archive/')
    (archive_dir / 'index.html').write_text(archive_page, encoding='utf-8')
    rss_items = ''.join(f'<item><title>{xml_escape(a["title"])}</title><link>{xml_escape(a["link"])}</link><guid isPermaLink="true">{xml_escape(a["link"])}</guid><pubDate>{email.utils.format_datetime(a["date"])}</pubDate><description>{xml_escape(a["sourceName"] + ": " + a["description"])}</description></item>' for a in articles)
    (root / 'feed.xml').write_text(f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{xml_escape(SITE_TITLE)}</title><link>{xml_escape(base_url)}</link><description>Daily headlines</description>{rss_items}</channel></rss>', encoding='utf-8')
    urls = [base_url, base_url + 'archive/', base_url + 'feed.xml'] + [base_url + f'lang/{lang}.html' for lang in ('pl', 'en', 'fr')] + [base_url + f'archive/{name}.html' for name in archive_names]
    (root / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(f'<url><loc>{xml_escape(url)}</loc></url>' for url in urls) + '</urlset>', encoding='utf-8')
    return len(articles)


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
