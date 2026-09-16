# Evidence

- Imported repository name from README.md.
- Imported SECURITY.md, but no explicit contact channel was parsed, so security_contact = "unknown" is intentional.
- Inferred repo.build from .github/workflows/build-ilspy.yml as `dotnet pack ICSharpCode.Decompiler --no-restore`.
- Discovered related relation to github.com/icsharpcode/ILSpy from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.

## Security contact evidence refresh (2026-09-16)

- Replaced `owners.security_contact = "unknown"` with `christoph.wille@gmail.com`.
- Source: [SECURITY.md at `72dbe6f41d480728ffa60bb68d1b95f9118d6b15`](https://github.com/icsharpcode/ILSpy/blob/72dbe6f41d480728ffa60bb68d1b95f9118d6b15/SECURITY.md), fetched at the pinned commit on 2026-09-16.
- Normalized the explicitly documented mailbox `christoph.wille AT gmail.com` to `christoph.wille@gmail.com`; no address was guessed.
- This is a field-scoped correction supported by the above evidence, not a full repository recrawl. Existing crawl timestamps and GitHub head metadata describe the earlier full crawl. This supersedes the earlier contact-absence conclusion; record authority is unchanged.
