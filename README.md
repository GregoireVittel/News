# Przegląd

The front page (`index.html`) is a generated **static edition**: articles are in HTML and readable with JavaScript disabled. The optional interactive RSS reader is at [`live.html`](live.html).

## Exclusive source policy

`sources.js` is the shared authoritative catalog: exactly 27 category entries representing 26 distinct publishers, with Reuters listed under both Poland and Global news and geopolitics. The five sections are Poland; France; Global news and geopolitics; Technology, AI and science; Financial markets and economics. No publishers outside this catalog are permitted. Saved browser feeds are reconciled against the allowlist, and the reader permits only re-enabling approved feeds, not arbitrary additions. Explicit removal preferences for approved feeds are preserved.

Entries without a verified accessible public RSS feed remain in the catalog with `url: null` and an explicit status. They supply no articles until an authorized endpoint is configured. In particular PAP Mediaroom press releases are not substituted for PAP domestic news. Feed metadata availability does not imply full-article access; publisher subscriptions and paywalls remain in force. Historical archived editions are preserved as historical records.

`build.py` reads the shared `sources.js` catalog, fetches public RSS/Atom feeds directly, selects dated articles from the preceding 24 hours, and writes the front page, `archive/YYYY-MM-DD.html`, language editions, `archive/index.html`, `feed.xml`, and `sitemap.xml`. A generated-at timestamp appears in the header. No source is invented when a feed fails; unavailable feeds are printed to stderr. A build with zero recent articles fails instead of replacing the edition. A partial-feed build can still succeed.

Run `python3 build.py` to refresh. Override the canonical URL with `--base-url URL` if the site moves. Run tests with `python3 -m unittest discover -s tests -p 'test_build.py' && node --test tests/*.test.cjs`.

The scheduled GitHub Action (`daily-edition.yml`) builds at 06:15 UTC, commits the new edition and archive, and deploys the static site using GitHub Pages Actions. The Pages source must be **GitHub Actions**, and the repository must allow Actions write permissions; otherwise the deployment needs configuration. Scheduled GitHub workflows can be delayed by GitHub. Successful local generation does not establish that GitHub Pages has deployed.

The static edition uses publishers' RSS descriptions as excerpts, **not original editorial summaries**. Cross-source story merging, follow-up detection, and build-failure notification are not part of this phase.
