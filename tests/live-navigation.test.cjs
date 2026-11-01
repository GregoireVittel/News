const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { portalSections, filterPortalArticles } = require('../feed-utils.js');

test('live menu exposes Front Page and the four requested topic sections', () => {
  assert.deepEqual(portalSections, [
    { value: 'All', label: 'Front Page' },
    { value: 'Poland', label: 'Polish News' },
    { value: 'France', label: 'French News' },
    { value: 'World', label: 'World News' },
    { value: 'Technology', label: 'Technology' },
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
  const world = articles.filter(a => ['Global news and geopolitics', 'Financial markets and economics'].includes(a.category));
  const technology = articles.filter(a => a.category === 'Technology, AI and science');
  assert.ok(world.length > 0);
  assert.ok(technology.length > 0);
  assert.deepEqual(filterPortalArticles(articles, 'World'), world);
  assert.deepEqual(filterPortalArticles(articles, 'Technology'), technology);
});

test('live ingestion and rendered section order use the same canonical mapping', () => {
  const live = fs.readFileSync(path.join(__dirname, '../live.html'), 'utf8');
  assert.match(live, /category: portalSectionForCategory\(categoryForFeed\(feed\)\)/);
  assert.match(live, /sourceCatalog\.map\(feed => portalSectionForCategory\(feed.category\)\)/);
});
