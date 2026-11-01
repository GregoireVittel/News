const test = require('node:test');
const assert = require('node:assert/strict');
const { reconcileFeeds } = require('../feed-utils.js');

test('exclusive policy discards unapproved saved feeds and restores canonical publisher metadata', () => {
  const approved = [{url:'https://approved.example/rss', name:'Approved', language:'en'}];
  const saved = [{url:'https://removed.example/rss', name:'Removed'}, {...approved[0], name:'Spoofed'}];
  assert.deepEqual(reconcileFeeds(approved, saved, [], {}, true), approved);
});

test('catalog exactly matches the requested 27 category entries and 26 publishers', () => {
  const catalog = require('../sources.js');
  const expected = {
    Poland: ['Reuters','Notes from Poland','Gazeta Wyborcza','PAP','Bankier.pl'],
    France: ['AFP','Le Monde','Les Échos','franceinfo','Mediapart'],
    'Global news and geopolitics': ['Reuters','Associated Press (AP)','BBC News','Financial Times','POLITICO Europe','The Economist'],
    'Technology, AI and science': ['MIT Technology Review','Ars Technica','The Verge','TechCrunch','Nature','The Decoder'],
    'Financial markets and economics': ['Bloomberg','The Wall Street Journal','Bank for International Settlements (BIS)','European Central Bank (ECB)','OECD']
  };
  assert.equal(catalog.length,27);
  assert.equal(new Set(catalog.map(s=>s.name)).size,26);
  assert.deepEqual([...new Set(catalog.map(s=>s.category))],Object.keys(expected));
  for (const [category,names] of Object.entries(expected)) {
    assert.deepEqual(catalog.filter(s=>s.category===category).map(s=>s.name),names);
  }
  assert.ok(catalog.every(s=>s.status && ['en','pl','fr'].includes(s.language)));
  assert.equal(new Set(catalog.filter(s=>s.url).map(s=>s.url)).size,catalog.filter(s=>s.url).length);
});
