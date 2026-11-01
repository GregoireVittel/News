# Przegląd — static news editions

The default portal serves real article HTML without JavaScript, React, Babel,
Tailwind or CDN scripts. Its original dark editorial CSS, lead/latest layout,
layout and language choices are retained. The sections now follow the approved
Poland / France / Global news and geopolitics / Technology, AI and science /
Financial markets and economics catalog. `pl/`, `en/` and `fr/` are ordinary static language pages; dated
editions have their own language pages. All sections' stories are available
without a JavaScript “View all” control.

Descriptions are **snippets supplied by the existing publishers' feeds**, as in
the original reader, not original/editorial/AI summaries. No automatic translation
is performed. PAP Mediaroom is not used as a substitute for PAP domestic news.

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
`/assets/portal.css`, `/rss.xml`, `/sitemap.xml`, `/build-info.json`,
`/live.html`, `/feed-utils.js` and `/sources.js`. Generated HTML has `lang="pl"`, Open Graph
metadata, canonical URLs and an explicit generated-at timestamp in Europe/Paris.
Articles carry their own language. Asset/navigation URLs include the base path
and work from dated pages. Article URLs must be absolute HTTP(S); text and XML
are escaped and publisher HTML is reduced to plain-text snippets.

The source of truth is **`sources.js`**, shared by both static builders and the
live reader: exactly 27 category entries and 26 publishers (Reuters appears twice).
Only approved publishers are allowed; saved browser preferences cannot restore
excluded feeds. Unavailable approved publishers remain listed with `url: null`
and an explanatory status rather than being replaced with other publishers.
No `sources.yaml` or proxy services are used by the static builder. It fetches
the catalog's enabled URLs directly with `urllib`
(eight workers, 15-second socket timeout per request, 4 MiB response cap), parses
RSS/Atom, keeps valid timestamps from the previous 24 hours, sorts and deduplicates
by article URL. Individual failures are logged to stderr and included in the
JSON report; an empty edition is rejected. There is no fixture fallback.

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

`.github/workflows/daily-edition.yml` builds with `scripts/build_edition.py`,
installs the staged current pages and retains historical editions. Historical
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
