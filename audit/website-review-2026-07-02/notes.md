# dotrepo Website Review

Date: 2026-07-02
Preview: `uv run python -m http.server 4173 --directory public`

## Captured Steps

1. Home desktop: healthy overall. Strong positioning, useful live snapshot proof, and clear primary actions.
2. Repository inventory desktop: healthy search interaction. The search filters instantly and updates the visible count.
3. Docs desktop: healthy content map, but repeated generic link names weaken accessibility.
4. Efficiency desktop: healthy benchmark page. The metric cards and methodology copy are clear.
5. Writing desktop: healthy, sparse entry point. The page feels unfinished because only one article appears in a large empty section.
6. Home mobile: usable but crowded. The wrapped pill navigation takes about 198px of vertical space, pushing the primary action to the bottom of the first viewport.
7. Repository search for `ripgrep`: healthy interaction. The result count changes to `1 repository` and the matching card remains visible.

## Findings

1. Static preview and plain static hosting return 404 for every `query?path=...` link.
   Severity: medium if production is always served by `dotrepo-public-query` or the Cloudflare Worker; high if `public/` is also expected to work on a generic static host.
   Evidence: `curl http://127.0.0.1:4173/v0/repos/github.com/BurntSushi/ripgrep/query?path=repo.description` returned 404. The homepage and inventory link directly to query routes, for example `public/index.html:611`, `public/index.html:927`, and `public/repositories/index.html:233-235`.
   Recommendation: make the local preview command use `dotrepo-public-query`, or make static-page query links visibly marked as hosted-runtime links. If generic static hosting is in scope, link to precomputed examples or `query-input` artifacts instead.

2. Repeated link labels make screen-reader link lists ambiguous.
   Severity: medium.
   Evidence: Docs cards repeat `Open` (`public/docs/index.html:231`, `public/docs/index.html:239`), and repository cards repeat `Summary`, `Trust`, and `Query` hundreds of times (`public/repositories/index.html:232-235`). Visually this is fine, but assistive technology users browsing by links get many identical names.
   Recommendation: add contextual accessible names, such as `aria-label="Open install documentation"` and `aria-label="Open ripgrep trust report"`.

3. Mobile top navigation occupies too much of the first viewport.
   Severity: low to medium.
   Evidence: at 390x844, the nav measured 198.5px tall, and the first CTA ended at y=816.8. Screenshot: `07-home-mobile-viewport.png`. The current mobile rule stacks the nav but keeps all seven pill links visible (`public/index.html:495-501`).
   Recommendation: collapse secondary links into a compact menu, move Snapshot/GitHub into the footer on mobile, or reduce the nav chip treatment so the first CTA is comfortably visible without scrolling.

4. The repository inventory will become expensive and hard to navigate as the index grows.
   Severity: low now, rising with index size.
   Evidence: `public/repositories/index.html` is 584 KB and contains 1,850 links for 613 repositories. The client-side search loops through every `[data-search-index]` card on every input (`public/repositories/index.html:8205-8222`).
   Recommendation: add pagination or a capped initial result set, preserve the search query in the URL, and consider generating a small search index separate from the full card markup.

## Strengths

- The homepage explains the core value quickly: repository metadata with provenance, selection reason, freshness, and claim context.
- The live snapshot cards make the product feel real rather than aspirational.
- The repository search interaction is simple and fast for the current index size.
- The benchmark page is unusually honest about abstention and measurement limits.

## Evidence Limits

- Screenshots and DOM checks do not prove full WCAG conformance.
- Query route behavior was checked with a plain static local server, not the same-origin hosted-query runtime or Cloudflare Worker.
- External links were not exhaustively crawled.
