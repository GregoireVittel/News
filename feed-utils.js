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

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { parseFeedDate, recentUniqueArticles };
}
