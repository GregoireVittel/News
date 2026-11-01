const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { portalSections, filterPortalArticles } = require('../feed-utils.js');

test('live menu exposes Front Page and the five requested topic sections', () => {
  assert.deepEqual(portalSections, [
    { value: 'All', label: 'Front Page' },
    { value: 'Poland', label: 'Polish News' },
    { value: 'France', label: 'French News' },
    { value: 'World', label: 'World News' },
    { value: 'Technology', label: 'Technology' },
    { value: 'Financial', label: 'Financial News' },
  ]);
  const live = fs.readFileSync(path.join(__dirname, '../live.html'), 'utf8');
  assert.match(live, /<SectionFilter selectedSection=\{selectedSection\} onSelectSection=\{setSelectedSection\}/);
  assert.match(live, /portalSections\.map/);
  assert.match(live, /onClick=\{\(\) => onSelectSection\(section.value\)\}/);
  assert.match(live, /filterPortalArticles\(articles, selectedSection\)/);
  assert.doesNotMatch(live, /<LanguageFilter|Przegląd/);
});

test('live section selection filters topics, not article language', () => {
  const articles = [
    { link: 'tech', category: 'Technology', language: 'fr' },
    { link: 'poland', category: 'Poland', language: 'en' },
    { link: 'france', category: 'France', language: 'pl' },
    { link: 'world', category: 'World', language: 'fr' },
  ];
  assert.deepEqual(filterPortalArticles(articles, 'All'), articles);
  for (const section of ['Technology', 'Poland', 'France', 'World']) {
    assert.deepEqual(filterPortalArticles(articles, section), articles.filter(a => a.category === section));
  }
  assert.deepEqual(filterPortalArticles([], 'Technology'), []);
});

test('actual publisher categories populate World News and Technology', () => {
  const context = {};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../sources.js'), 'utf8') + ';globalThis.feeds = sourceCatalog;', context);
  const articles = Array.from(context.feeds, feed => ({ ...feed, link: feed.url }));
  const world = articles.filter(a => a.category === 'Global news and geopolitics');
  const technology = articles.filter(a => a.category === 'Technology, AI and science');
  assert.ok(world.length > 0);
  assert.ok(technology.length > 0);
  assert.deepEqual(filterPortalArticles(articles, 'World'), world);
  assert.deepEqual(filterPortalArticles(articles, 'Technology'), technology);
  assert.deepEqual(filterPortalArticles(articles, 'Financial'), articles.filter(a => a.category === 'Financial markets and economics'));
});

test('live ingestion and rendered section order use the same canonical mapping', () => {
  const live = fs.readFileSync(path.join(__dirname, '../live.html'), 'utf8');
  assert.match(live, /normalizeFeedItems\(items, \{ \.\.\.feed, category: categoryForFeed\(feed\) \}\)/);
  assert.match(live, /sourceCatalog\.map\(feed => portalSectionForCategory\(feed.category\)\)/);
});

test('live Financial News renders a nested BNP group with all its stories and an empty state', () => {
  const live = fs.readFileSync(path.join(__dirname, '../live.html'), 'utf8');
  assert.match(live, /partitionFinancialArticles\(articles\)/);
  assert.match(live, /id="financial"/);
  assert.match(live, /id="bnp-paribas"/);
  assert.match(live, /href="#bnp-paribas"/);
  assert.match(live, /bnp\.map\(article => <Story/);
  assert.match(live, /No BNP Paribas bank stories in the past 24 hours/);
  assert.match(live, /source: field\(item, 'source'\)/);
});
