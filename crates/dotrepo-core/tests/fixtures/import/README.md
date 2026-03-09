This fixture pack captures the current import surface for `README.md`, `CODEOWNERS`,
and `SECURITY.md`.

Cases:
- `full-signals`: happy-path `.github` surfaces with imported name, description, owners, and security contact.
- `badge-heavy-readme`: README badges and images before the first real title and description, plus a root `SECURITY.md` URL.
- `setext-heading-readme`: setext-style README heading plus a wrapped paragraph description.
- `html-heading-readme`: centered HTML heading and paragraph tags that still carry real project metadata.
- `root-conventional-files`: root-level `CODEOWNERS` and `SECURITY.md`, with title imported but description inferred.
- `description-only-readme`: README description with no heading, so name is inferred from the directory.
- `security-markdown-link`: `SECURITY.md` exposes a contact channel through markdown link syntax rather than raw tokens.
- `security-contact-unknown`: `SECURITY.md` exists but does not expose a parseable email or URL.
- `no-conventional-surfaces`: no importable conventional files, so the plan falls back entirely to inferred defaults.
- `mixed-codeowners`: deduped `CODEOWNERS` handles and emails without a `SECURITY.md`.
