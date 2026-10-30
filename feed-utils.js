// rss2json dates without a timezone are UTC; ISO dates may already carry an offset.
function parseFeedDate(value) {
  if (typeof value !== 'string' || !value.trim()) return null;
  const normalized = /^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$/.test(value)
    ? value.replace(' ', 'T') + 'Z'
    : value;
  const timestamp = Date.parse(normalized);
  return Number.isFinite(timestamp) ? timestamp : null;
}

function recentUniqueArticles(articles, now = Date.now()) {
  const seen = new Set();
  return articles
    .map(article => ({ article, timestamp: parseFeedDate(article.pubDate) }))
    .filter(({ timestamp }) => timestamp !== null && timestamp >= now - 86400000 && timestamp <= now)
    .sort((a, b) => b.timestamp - a.timestamp)
    .filter(({ article }) => {
      const key = article.link || article.guid;
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .map(({ article }) => article);
}

function reconcileFeeds(defaults, saved, removedUrls = [], retiredUrls = {}) {
  const removed = new Set(removedUrls);
  for (const [oldUrl, newUrl] of Object.entries(retiredUrls)) {
    if (removed.has(oldUrl)) removed.add(newUrl);
  }
  const byUrl = new Map();
  for (const feed of defaults) if (!removed.has(feed.url)) byUrl.set(feed.url, feed);
  for (const feed of Array.isArray(saved) ? saved : []) {
    if (!feed || typeof feed.url !== 'string') continue;
    const url = retiredUrls[feed.url] || feed.url;
    if (removed.has(url)) continue;
    if (byUrl.has(url)) {
      const current = byUrl.get(url);
      byUrl.set(url, { ...feed, ...current });
    } else if (!retiredUrls[feed.url]) {
      byUrl.set(url, feed);
    }
  }
  return [...byUrl.values()];
}

function groupPortalArticles(articles) {
  const lead = articles[0] || null;
  const sections = {};
  for (const article of articles.slice(4)) {
    const category = article.category || 'World';
    (sections[category] ||= []).push(article);
  }
  return { lead, latest: articles.slice(1, 4), sections };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { parseFeedDate, recentUniqueArticles, reconcileFeeds, groupPortalArticles };
}
