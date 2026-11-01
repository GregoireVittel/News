# Przegląd — static news editions

The default portal serves real article HTML without JavaScript, React, Babel,
Tailwind or CDN scripts. Its original dark editorial CSS, lead/latest layout,
World / Business / Technology / Sports / Lifestyle sections and language choices
are retained. `pl/`, `en/` and `fr/` are ordinary static language pages; dated
editions have their own language pages. All sections' stories are available
without a JavaScript “View all” control.

Descriptions are **snippets supplied by the existing publishers' feeds**, as in
the original reader, not original/editorial/AI summaries. PAP Mediaroom includes
press releases. No source additions, source-quality reclassification, automatic
translation or later proposed steps 4–6 are implemented.

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
`/live.html` and `/feed-utils.js`. Generated HTML has `lang="pl"`, Open Graph
metadata, canonical URLs and an explicit generated-at timestamp in Europe/Paris.
Articles carry their own language. Asset/navigation URLs include the base path
and work from dated pages. Article URLs must be absolute HTTP(S); text and XML
are escaped and publisher HTML is reduced to plain-text snippets.

The source of truth remains the original **inline `defaultFeedUrls` JavaScript
array in `live.html`**. No `sources.yaml`, new sources or proxy services are used
by the static builder. It fetches these 34 existing URLs directly with `urllib`
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

## Optional Live reader

`live.html` is the preserved original React reader, explicitly opt-in via “Live”.
It refreshes every **three minutes**, retains local-storage feed preferences,
and requires its original CDN scripts/rss2json/proxy services. No automatic
refresh or script dependency is imposed on the static default page.

## Tests

```sh
/opt/hermes/.venv/bin/python -m unittest discover -s tests -p 'test_build_edition.py' -v
node --test tests/*.test.cjs
```

All fixture titles/publishers are marked `TEST ONLY`; fixtures are created only
inside automatically cleaned temporary test directories and are never published.
Tests cover RSS/Atom, safe URLs, deduplication, Paris date rollover, no-JS HTML,
language filtering, XML validity, archive integrity, immutable history, partial
feed failures and empty-edition refusal. The original JavaScript tests still
verify the opt-in live reader's shared helpers.
