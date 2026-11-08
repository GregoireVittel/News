# What's happening in the World — static news editions

The default portal serves real article HTML without JavaScript, React, Babel,
Tailwind or CDN scripts. Its dark editorial CSS is retained.
The masthead is **What's happening in the World** with the subtitle **What’s happening now…**.
The menu is **World / Poland / France / Global Markets / Tech** (stored sections
`World`, `Poland`, `France`, `Financial`, `Technology`), with **BNP Paribas** nested
under Global Markets. Technology and financial subjects take precedence over geography.
Publisher catalog categories remain provenance, not final story sections.

A switch at the right of the menu offers **English / Français / Polski**. It filters
stories by the language they were written in. Page text stays English. The front page `/`
shows every language; `en/`, `fr/` and `pl/` show only English, French or Polish stories
in every section. Dated editions work the same way. Clicking the active language
again goes back to all languages.

Descriptions are **snippets supplied by the existing publishers' feeds**, as in
the original reader, not original/editorial/AI summaries. No automatic translation
is performed. PAP Mediaroom is not used as a substitute for PAP domestic news.

## Dashboard

The front page in each language (`scripts/dashboard.py`) adds, above the five sections,
*Top stories*, *Most covered* (stories from several outlets) and *Trending* keywords. Stories published within 3 hours of the
build carry a **New** badge. These panels link to stories; each story still has
exactly one card. Extra pages: `sources/` (stories grouped by publisher),
`trending/` (stories per keyword) and `archive/` (editions plus daily trend
sparklines from `stats.json`, which each build carries forward from history).
Page text is English; language pages declare their own `lang`.

## Barometer

`barometer/` (menu: **Barometer**, `scripts/barometer.py`) sets the France + Global Markets
news flow next to the CAC 40. It shows:

- **Today's reading:** a dial from −100 to +100 for the tone of the past 24 hours,
  with zones from Stormy to Sunny.
- **Themes:** story counts for CAC 40 sectors and market-wide drivers (rates, French
  politics, trade, geopolitics), each against its 30-session average.
- **Session charts:** tone and CAC 40 daily change, as two charts on the same dates.
- **Relationship:** a scatter of tone against the next session's move. Correlations stay
  hidden until 20 sessions have both news and prices.

Tone is positive minus negative market words in French, English and Polish, from
headlines and RSS snippets. News after the 17:30 Paris close, or at the weekend, counts
toward the next trading session.

CAC 40 daily closes come from Yahoo Finance's chart endpoint, with Stooq's CSV as a
fallback. Neither needs a key. If both fail, the edition still publishes with the last
saved prices and the log says `CAC 40 source unavailable`.

History is kept in `barometer.json` on the site. Per-story scores are kept for 10 days,
so hourly rebuilds never double count a story, and then folded into one row per session.
On the first build it is filled from the saved daily `articles.json` snapshots.
It shows co-movement, not cause and effect.

## Sentiment

`sentiment/` (menu: **Sentiment**, `scripts/sentiment.py`) is a fear and greed index for French
markets, from 0 (extreme fear) to 100 (extreme greed). Four daily readings are each ranked as a
percentile within their last 756 trading days (about three years; a rank needs at least 252),
then averaged:

| Reading | Raw value | High score means |
|---|---|---|
| Equity momentum | CAC 40 vs its 125-day average, % | further above than usual |
| Volatility | CAC 40 20-day annualised volatility, flipped | calmer than usual |
| Safe haven | EUR/CHF 20-day change, % | franc weakening |
| Stocks vs gold | CAC 40 20-day return minus gold's in euros | shares ahead of gold |

Bands: below 25 extreme fear, 25–45 fear, 45–55 neutral, 55–75 greed, 75+ extreme greed.

Each day's rank uses that day and earlier days only, so history is not rewritten. The index
is left blank when fewer than two readings exist.

Inputs are 10 years of daily closes from Yahoo Finance (`^FCHI`, `EURCHF=X`, `GC=F`,
`EURUSD=X`), fetched every build. If an input fails, its reading is left out. If the CAC 40
fails, the page keeps the previous `sentiment.json`.

The page shows:

- the dial and comparisons with the previous close, a week, a month and a year ago;
- where today sits in the record;
- each reading with its 3-year range;
- the Barometer's news tone, shown alongside but not counted;
- 3-year and full-history charts;
- `sentiment.csv` for download.

## Build (standard-library Python)

```sh
/opt/hermes/.venv/bin/python scripts/build_edition.py \
  --output /tmp/news-site-stage \
  --base-url https://gregoirevittel.github.io/News/ \
  --history-root /path/to/previous/site
```

`--output` must be **absent or empty**, and must be a dedicated staging directory,
not the repository root. The builder constructs a sibling temporary directory,
then atomically renames it into `--output` only after a successful complete build.
Failure leaves output unchanged. It never commits, pushes, schedules or publishes.
The separate publisher must validate/pass its real base URL and install the staged
site. `--base-url` is required: an absolute HTTP(S) URL **ending in `/`**, with no
query/fragment; GitHub project hosting therefore retains the `/News/` prefix.

`--history-root` defaults to this repository. Existing `YYYY-MM-DD/index.html`
directories are copied unchanged from history; only dates with actual index pages
appear in the archive/sitemap. The first published snapshot of a Paris calendar
day is immutable, including on same-day rebuilds; `/` and root language pages
represent the latest build. Point history at the previously published site on
every production build. Do not pass test output as production history.

Output includes `/index.html`, `/pl/`, `/en/`, `/fr/`,
`/YYYY-MM-DD/index.html` and its language pages, `/archive/index.html`,
`/assets/portal.css`, `/rss.xml`, `/sitemap.xml`, `/build-info.json`, `/articles.json`,
`/live.html`, `/feed-utils.js` and `/sources.js`. Generated HTML has `lang="pl"`, Open Graph
metadata, canonical URLs and an explicit generated-at timestamp in Europe/Paris.
Articles carry their own language. Asset/navigation URLs include the base path
and work from dated pages. Article URLs must be absolute HTTP(S); text and XML
are escaped and publisher HTML is reduced to plain-text snippets.

The source of truth is **`sources.js`**, shared by both static builders and the
live reader: the original 27 category entries and 26 publishers (Reuters appears twice),
plus three explicitly approved Google News RSS searches for BNP Paribas (FR/EN/PL).
Only approved feeds are allowed; saved browser preferences cannot restore
excluded feeds. Unavailable approved publishers remain listed with `url: null`
and an explanatory status rather than being replaced with other publishers.
No `sources.yaml` or proxy services are used by the static builder. It fetches
the catalog's enabled URLs directly with `urllib`
(eight workers, 15-second socket timeout per request, 4 MiB response cap), parses
RSS/Atom, keeps valid timestamps from the previous 24 hours, sorts and deduplicates
across sources. Distinct publisher count is the primary importance signal,
followed by publication time and URL as a stable tie-break. Repeated entries
from the same publisher do not inflate coverage. Individual failures are logged to stderr and included in the
JSON report; an empty edition is rejected. There is no fixture fallback.

### Financial News / BNP Paribas

Financial News includes the existing financial markets and economics feeds. Its
BNP Paribas subgroup combines matching publisher-feed stories with Google News
RSS searches for `"BNP Paribas" -tennis -"Indian Wells"` in French, English and
Polish, including BNP Paribas Bank Polska. This scoped search is an explicit
exception to the original publisher-only list: Google results may introduce
other publishers, but arbitrary saved/custom feeds remain disallowed.

The existing **past 24 hours** window applies to the subgroup too; an empty state
does not imply a broken feed. Google controls indexing/results (up to 100 RSS
entries per locale), so this is not a guarantee of exhaustive coverage. Obvious
tournament-only headlines are excluded. Stories retain their actual RSS publisher
names; Google is not counted as an additional publisher. Google News article URLs
are retained as supplied and redirect to publishers; no full articles are scraped.
BNP stories appear once, inside the subgroup, and count toward Financial totals.

### Story data and classification v1

`articles.json` is the generation-time data used to render the page; JavaScript
does not load it. It has `schemaVersion: 2`, `generatedAt`, `sections` and
`articles`. Each article retains publisher fields and adds:

- `sourceCategory`: the original catalog category (provenance).
- `section`, `sectionReason`: exactly one final section and its rule explanation.
- `classification`: versioned method and the text/category inputs used.
- `sources`: original publisher names and article URLs for the story cluster.
- `sourceCount`, `importance.sourceCount`: distinct publisher coverage, not an
  editorial impact score.

Source counts measure coverage, not independent corroboration: publishers can
syndicate the same reporting. Stories are ordered by distinct publisher count,
then publication time, with the URL as a deterministic tie-break.

Clustering is deliberately conservative to avoid merging different events about
the same subject: canonical URLs, near-identical substantive title tokens, or
narrow service-resumption signatures with the same entity/action/object/cause
and no conflicting numbers. Supported phrase variants include English, French
and Polish; arbitrary multilingual paraphrases may remain separate. Semantic
query parameters are retained; known tracking parameters do not distinguish
stories. There is no automatic translation or external classifier service.
The dated edition also stores its own `articles.json` when first generated;
historical snapshots are not retroactively reclassified. `/lang/*.html` and
`/feed.xml` are generated aliases of the canonical language pages and RSS.

### Python API used by the publisher

```python
from scripts.build_edition import build
report = build(output, base_url, history_root=previous_site)
```

Signature: `build(output, base_url, *, now=None, feeds=None, fetcher=None,
history_root=None) -> dict`. `output` and `history_root` accept strings or Paths.
Optional `now` must be timezone-aware (default: current UTC instant, edition date
converted to Europe/Paris). `feeds` and `fetcher(feed) -> bytes` exist for isolated
offline tests only; production callers should omit them. The report contains
`edition`, `article_count`, `failures`, `generated_at`, and `output`.
Invalid inputs/empty editions raise `ValueError`; other I/O failures propagate.
The CLI logs failures, prints the JSON report on success and exits nonzero on
failure. Never call this with the live repository as output.

## Scheduled publication and compatibility

The site is rebuilt every hour (starting at :57 Europe/Paris) by
`.github/workflows/update-clock.yml`: a self-chaining workflow that waits in a job
until the next slot, starts `daily-edition.yml` with
`workflow_dispatch`, then starts its next run (`scripts/update_clock.py`). GitHub's
cron proved unreliable here; a cron line only restarts the clock if the chain breaks.
To restart it by hand, run **Update clock** from the Actions tab.
`daily-edition.yml` keeps UTC cron lines for CET and CEST as a fallback, filtered
by `scripts/schedule_gate.py`; it builds with `scripts/build_edition.py`,
deploys the staged site straight to GitHub Pages and keeps it on the `site`
branch with only two commits, the current and the previous version
(`scripts/site_branch.sh`); nothing generated is committed to `main`. Each
build reads dated editions and `stats.json` from the previous version. Historical
snapshots are preserved unchanged and may contain formerly permitted publishers.
The older `build.py` command and `/lang/*.html`, `/feed.xml`, and dated
`/archive/*.html` URLs remain available for compatibility; it reads the same
approved catalog. The canonical language URLs are `/pl/`, `/en/`, and `/fr/`.

## Optional Live reader

`live.html` is the preserved original React reader, explicitly opt-in via “Live”.
It refreshes every **three minutes**, retains local-storage feed preferences,
and requires its original CDN scripts/rss2json/proxy services. No automatic
refresh or script dependency is imposed on the static default page.

## Tests

```sh
/opt/hermes/.venv/bin/python -m unittest discover -s tests -p 'test_build*.py' -v
node --test tests/*.test.cjs
```

All fixture titles/publishers are marked `TEST ONLY`; fixtures are created only
inside automatically cleaned temporary test directories and are never published.
Tests cover RSS/Atom, safe URLs, deduplication, Paris date rollover, no-JS HTML,
language filtering, XML validity, archive integrity, immutable history, partial
feed failures and empty-edition refusal. The original JavaScript tests still
verify the opt-in live reader's shared helpers.
