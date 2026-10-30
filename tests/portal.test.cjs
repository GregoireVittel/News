const test = require('node:test');
const assert = require('node:assert/strict');
const { reconcileFeeds, groupPortalArticles } = require('../feed-utils.js');

test('adds newly shipped feeds to a previously saved feed selection without duplicating custom feeds', () => {
  const defaults = [{ url: 'old', name: 'Old' }, { url: 'new', name: 'New' }];
  const saved = [{ url: 'old', name: 'Old' }, { url: 'custom', name: 'Custom' }];
  assert.deepEqual(reconcileFeeds(defaults, saved, [] ).map(feed => feed.url), ['old', 'new', 'custom']);
});

test('respects explicit default-feed removals and old saved-feed removals', () => {
  const defaults = [{ url: 'old' }, { url: 'new' }];
  assert.deepEqual(reconcileFeeds(defaults, [{ url: 'new' }], ['old']).map(feed => feed.url), ['new']);
});

test('migrates a retired source URL without restoring a deliberately removed feed', () => {
  const defaults = [{ url: 'https://new.example/rss', name: 'Publisher', language: 'pl' }];
  const saved = [{ url: 'https://old.example/rss', name: 'Publisher', language: 'pl' }];
  const retired = { 'https://old.example/rss': 'https://new.example/rss' };
  assert.deepEqual(reconcileFeeds(defaults, saved, [], retired), defaults);
  assert.deepEqual(reconcileFeeds(defaults, saved, ['https://old.example/rss'], retired), []);
});

test('updates shipped source metadata when an old saved copy uses a different language', () => {
  const defaults = [{ url: 'https://example.com/feed', name: 'Financial Times', language: 'en' }];
  const saved = [{ url: 'https://example.com/feed', name: 'Financial Times', language: 'ft' }];
  assert.deepEqual(reconcileFeeds(defaults, saved, []), defaults);
});

test('groups filtered articles into sections while leaving the lead and latest unique', () => {
  const articles = [
    { link: 'a', category: 'World' },
    { link: 'b', category: 'Business' },
    { link: 'c', category: 'World' },
    { link: 'd', category: 'Technology' },
    { link: 'e', category: 'Business' },
  ];
  const result = groupPortalArticles(articles);
  assert.equal(result.lead.link, 'a');
  assert.deepEqual(result.latest.map(a => a.link), ['b', 'c', 'd']);
  assert.equal(result.sections.World, undefined);
  assert.deepEqual(result.sections.Business.map(a => a.link), ['e']);
});
