# RSS News Feeder

A static, browser-based RSS reader that shows articles from the previous 24 hours without ads in the reader. Open `index.html` in a browser or host the repository as a static site. Feed preferences are saved in your browser's local storage.

The page uses React, Tailwind, Babel and the rss2json API from public CDNs; an internet connection is required. If a feed cannot be loaded, the page reports the number of unavailable feeds. Use **Refresh** to retry without reloading the page.

Run date filtering and deduplication tests with `node --test tests/*.test.cjs` (Node.js 18+).
