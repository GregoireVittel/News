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

function reconcileFeeds(defaults, saved, removedUrls = [], retiredUrls = {}, exclusive = false) {
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
    } else if (!exclusive && !retiredUrls[feed.url]) {
      byUrl.set(url, feed);
    }
  }
  return [...byUrl.values()];
}

function portalSectionForCategory(category) {
  if (category === 'Technology, AI and science') return 'Technology';
  if (category === 'Financial markets and economics') return 'Financial';
  if (category === 'Global news and geopolitics') return 'World';
  return category || 'World';
}

function normalizeFeedItems(items, feed) {
  return items.flatMap(item => {
    const title = item.title || '';
    const text = title + ' ' + (item.description || '').replace(/<[^>]*>/g, ' ');
    const mentionsBnp = /\bbnp\s+paribas\b/i.test(text);
    const tournament = /\b(?:tennis|indian wells|roland.garros|bnp paribas open)\b/i.test(title);
    const banking = /\b(?:bank\w*|banqu\w*|bancair\w*|stock\w*|buyback|dividend\w*|profit\w*|financ\w*|invest\w*|benefice\w*|bourse|zysk\w*|gield\w*)\b/i.test(title);
    const bnp = mentionsBnp && (!tournament || banking);
    if (feed.subgroup === 'BNP Paribas' && !bnp) return [];
    const publisher = typeof item.source === 'string' ? item.source : item.source?.title;
    const titlePublisher = title.includes(' - ') ? title.slice(title.lastIndexOf(' - ') + 3) : '';
    return [{ ...item,
      sourceName: feed.aggregator ? (publisher || titlePublisher || feed.name) : feed.name,
      language: feed.language,
      category: bnp ? 'Financial' : portalSectionForCategory(feed.category),
      ...(bnp ? { subgroup: 'BNP Paribas' } : {}),
    }];
  });
}

function partitionFinancialArticles(articles) {
  const general = [], financial = [], bnp = [];
  for (const article of articles) {
    if (article.subgroup === 'BNP Paribas') bnp.push(article);
    else if (portalSectionForCategory(article.category) === 'Financial') financial.push(article);
    else general.push(article);
  }
  return { general, financial, bnp };
}

function groupPortalArticles(articles) {
  const lead = articles[0] || null;
  const sections = {};
  for (const article of articles.slice(4)) {
    const category = portalSectionForCategory(article.category);
    (sections[category] ||= []).push(article);
  }
  return { lead, latest: articles.slice(1, 4), sections };
}

const portalSections = [
  { value: 'All', label: 'Front Page' },
  { value: 'Poland', label: 'Polish News' },
  { value: 'France', label: 'French News' },
  { value: 'World', label: 'World News' },
  { value: 'Technology', label: 'Technology' },
  { value: 'Financial', label: 'Financial News' },
];

function filterPortalArticles(articles, selectedSection) {
  return selectedSection === 'All'
    ? articles
    : articles.filter(article => portalSectionForCategory(article.category) === selectedSection);
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { parseFeedDate, recentUniqueArticles, reconcileFeeds, groupPortalArticles, portalSections, filterPortalArticles, portalSectionForCategory, normalizeFeedItems, partitionFinancialArticles };
}
