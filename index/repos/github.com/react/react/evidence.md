# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Ignored component-scoped commands from `compiler/Cargo.toml` as repository defaults.
- Imported repo.build from package.json as `yarn build`.
- Imported repo.test from package.json as `yarn test`.
- Imported repo.toolchain.min from compiler/Cargo.toml as `1.85` (Rust).
- Imported docs.root as `https://react.dev/`. Explicit documentation link at README.md:21: You can find the React documentation [on the website](https://react.dev/).
- Conflicting documentation declarations in README.md; abstained from docs.getting_started.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Fresh verification

Prior verified authority was not inherited: this refresh must qualify using its current field scores.
