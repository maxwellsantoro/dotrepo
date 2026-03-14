# Public query fixture pack

This fixture pack locks the public query wrapper contract against a small,
reviewable set of deterministic success and error cases.

It reuses the public-export fixture index and adds checked-in expected JSON for:

- a plain overlay query response
- a claim-aware query response
- `query_path_not_found`
- `repository_not_found`
- `invalid_repository_identity`

The fixture goal is narrower than the static public export pack: this one keeps
the non-exported query wrapper machine-readable and reviewable while the public
surface is still static-first.
