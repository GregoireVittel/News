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
