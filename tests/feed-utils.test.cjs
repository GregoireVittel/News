const test = require('node:test');
const assert = require('node:assert/strict');
const { parseFeedDate, recentUniqueArticles } = require('../feed-utils.js');

test('parses rss2json UTC and ISO timestamps without double timezone suffix', () => {
  assert.equal(parseFeedDate('2026-10-30 12:30:00'), Date.parse('2026-10-30T12:30:00Z'));
  assert.equal(parseFeedDate('2026-10-30T12:30:00+02:00'), Date.parse('2026-10-30T10:30:00Z'));
  assert.equal(parseFeedDate(null), null);
  assert.equal(parseFeedDate('nonsense'), null);
});

test('keeps only dated articles from the previous day, sorted newest first', () => {
  const now = Date.parse('2026-10-30T12:00:00Z');
  const input = [
    { link: 'old', pubDate: '2026-10-29 11:59:59' },
    { link: 'recent', pubDate: '2026-10-29 12:00:00' },
    { link: 'latest', pubDate: '2026-10-30 11:00:00' },
    { link: 'undated', pubDate: null },
    { link: 'future', pubDate: '2026-10-31 11:00:00' },
  ];
  assert.deepEqual(recentUniqueArticles(input, now).map(a => a.link), ['latest', 'recent']);
});

test('deduplicates syndicated links even if GUIDs differ', () => {
  const now = Date.parse('2026-10-30T12:00:00Z');
  const items = [
    { link: 'https://example.com/story', guid: 'one', pubDate: '2026-10-30 09:00:00' },
    { link: 'https://example.com/story', guid: 'two', pubDate: '2026-10-30 10:00:00' },
  ];
  assert.deepEqual(recentUniqueArticles(items, now).map(a => a.guid), ['two']);
});
