// Approved publisher catalog and scoped Google News searches shared by both readers.
const sourceCatalog = [
  {
    "name": "Reuters",
    "language": "en",
    "category": "Poland",
    "url": null,
    "status": "No verified public RSS; licensed feed required"
  },
  {
    "name": "Notes from Poland",
    "language": "en",
    "category": "Poland",
    "url": "https://notesfrompoland.com/feed/",
    "status": "Public RSS verified"
  },
  {
    "name": "Gazeta Wyborcza",
    "language": "pl",
    "category": "Poland",
    "url": "https://wyborcza.pl/pub/rss/najnowsze_wyborcza.xml",
    "status": "Public RSS verified"
  },
  {
    "name": "PAP",
    "language": "pl",
    "category": "Poland",
    "url": null,
    "status": "Domestic news feed not yet accessible; PAP Mediaroom is not substituted"
  },
  {
    "name": "Bankier.pl",
    "language": "pl",
    "category": "Poland",
    "url": "https://www.bankier.pl/rss/wiadomosci.xml",
    "status": "Public RSS verified"
  },
  {
    "name": "AFP",
    "language": "fr",
    "category": "France",
    "url": null,
    "status": "No verified public RSS; licensed feed required"
  },
  {
    "name": "Le Monde",
    "language": "fr",
    "category": "France",
    "url": "https://www.lemonde.fr/rss/une.xml",
    "status": "Public RSS verified"
  },
  {
    "name": "Les Échos",
    "language": "fr",
    "category": "France",
    "url": "https://services.lesechos.fr/rss/les-echos-monde.xml",
    "status": "Publisher RSS endpoint currently returns HTTP 403"
  },
  {
    "name": "franceinfo",
    "language": "fr",
    "category": "France",
    "url": "https://www.francetvinfo.fr/titres.rss",
    "status": "Public RSS verified"
  },
  {
    "name": "Mediapart",
    "language": "fr",
    "category": "France",
    "url": "https://www.mediapart.fr/articles/feed",
    "status": "Public RSS verified"
  },
  {
    "name": "Reuters",
    "language": "en",
    "category": "Global news and geopolitics",
    "url": null,
    "status": "No verified public RSS; licensed feed required"
  },
  {
    "name": "Associated Press (AP)",
    "language": "en",
    "category": "Global news and geopolitics",
    "url": null,
    "status": "No verified public RSS; access required"
  },
  {
    "name": "BBC News",
    "language": "en",
    "category": "Global news and geopolitics",
    "url": "https://feeds.bbci.co.uk/news/rss.xml",
    "status": "Public RSS verified"
  },
  {
    "name": "Financial Times",
    "language": "en",
    "category": "Global news and geopolitics",
    "url": "https://www.ft.com/?format=rss",
    "status": "Public RSS verified"
  },
  {
    "name": "POLITICO Europe",
    "language": "en",
    "category": "Global news and geopolitics",
    "url": "https://www.politico.eu/feed/",
    "status": "Public RSS verified"
  },
  {
    "name": "The Economist",
    "language": "en",
    "category": "Global news and geopolitics",
    "url": "https://www.economist.com/the-world-this-week/rss.xml",
    "status": "Public RSS verified"
  },
  {
    "name": "The New York Times",
    "language": "en",
    "category": "Global news and geopolitics",
    "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "status": "Public RSS (World section)"
  },
  {
    "name": "MIT Technology Review",
    "language": "en",
    "category": "Technology, AI and science",
    "url": "https://www.technologyreview.com/feed/",
    "status": "Public RSS verified"
  },
  {
    "name": "Ars Technica",
    "language": "en",
    "category": "Technology, AI and science",
    "url": "https://feeds.arstechnica.com/arstechnica/index",
    "status": "Public RSS verified"
  },
  {
    "name": "The Verge",
    "language": "en",
    "category": "Technology, AI and science",
    "url": "https://www.theverge.com/rss/index.xml",
    "status": "Public Atom verified"
  },
  {
    "name": "TechCrunch",
    "language": "en",
    "category": "Technology, AI and science",
    "url": "https://techcrunch.com/feed/",
    "status": "Public RSS verified"
  },
  {
    "name": "Nature",
    "language": "en",
    "category": "Technology, AI and science",
    "url": "https://www.nature.com/nature.rss",
    "status": "Public RSS verified"
  },
  {
    "name": "The Decoder",
    "language": "en",
    "category": "Technology, AI and science",
    "url": "https://the-decoder.com/feed/",
    "status": "Public RSS verified"
  },
  {
    "name": "Bloomberg",
    "language": "en",
    "category": "Financial markets and economics",
    "url": "https://feeds.bloomberg.com/markets/news.rss",
    "status": "Public RSS verified"
  },
  {
    "name": "The Wall Street Journal",
    "language": "en",
    "category": "Financial markets and economics",
    "url": "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",
    "status": "Public Dow Jones RSS verified"
  },
  {
    "name": "Bank for International Settlements (BIS)",
    "language": "en",
    "category": "Financial markets and economics",
    "url": "https://www.bis.org/doclist/bis_fsi_publs.rss",
    "status": "Official BIS and FSI publications RSS"
  },
  {
    "name": "European Central Bank (ECB)",
    "language": "en",
    "category": "Financial markets and economics",
    "url": "https://www.ecb.europa.eu/rss/press.html",
    "status": "Public RSS verified"
  },
  {
    "name": "OECD",
    "language": "en",
    "category": "Financial markets and economics",
    "url": null,
    "status": "Public RSS endpoint currently inaccessible (HTTP 403)"
  },
  {
    "name": "Google News — BNP Paribas (FR)",
    "language": "fr",
    "category": "Financial markets and economics",
    "subgroup": "BNP Paribas",
    "aggregator": true,
    "url": "https://news.google.com/rss/search?q=%22BNP+Paribas%22+-tennis+-%22Indian+Wells%22&hl=fr&gl=FR&ceid=FR%3Afr",
    "status": "Google News RSS verified; BNP Paribas bank search; original publishers retained"
  },
  {
    "name": "Google News — BNP Paribas (EN)",
    "language": "en",
    "category": "Financial markets and economics",
    "subgroup": "BNP Paribas",
    "aggregator": true,
    "url": "https://news.google.com/rss/search?q=%22BNP+Paribas%22+-tennis+-%22Indian+Wells%22&hl=en-GB&gl=GB&ceid=GB%3Aen",
    "status": "Google News RSS verified; BNP Paribas bank search; original publishers retained"
  },
  {
    "name": "Google News — BNP Paribas (PL)",
    "language": "pl",
    "category": "Financial markets and economics",
    "subgroup": "BNP Paribas",
    "aggregator": true,
    "url": "https://news.google.com/rss/search?q=%22BNP+Paribas%22+-tennis+-%22Indian+Wells%22&hl=pl&gl=PL&ceid=PL%3Apl",
    "status": "Google News RSS verified; BNP Paribas bank search; original publishers retained"
  }
];
if (typeof module !== "undefined" && module.exports) module.exports = sourceCatalog;
