# Public edge canary history

This is a lightweight operator log for notable dotrepo × pagedigest public-edge
canary runs. The scheduled workflow and JSON artifacts remain the source of
truth; this page preserves essay-useful milestones.

## First cross-project green run

- checked at: `2026-07-03T01:22:39.626314Z`
- dotrepo snapshot generated at: `2026-07-03T01:15:11.411340336Z`
- dotrepo snapshot digest:
  `c51460ecf2294147e7a73a535cc3ef128fea009b9f32cacd00146f05a48edb31`
- dotrepo repositories: 613
- dotrepo public payloads: 3,066
- dotrepo pagedigest `site_rev`: 2
- pagedigest.org version: 1
- pagedigest.org `site_rev`: 2

Narrative note: this run passed after the public export moved to
content-addressed snapshot paths, so the canary did not catch a mixed-cache
failure; it verified the layout that made that class of failure mechanically
harder to produce.
