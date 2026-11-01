const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
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
