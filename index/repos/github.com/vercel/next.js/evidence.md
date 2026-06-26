# Evidence

- No README.md, CODEOWNERS, or SECURITY.md content was imported; this record needs manual completion.
- Inferred fallback values for `repo.name` and `repo.description` because the imported files did not provide enough structured metadata.
- Left `repo.build` unset because `Cargo.toml` and `package.json` suggested conflicting build commands.
- Left `repo.test` unset because `Cargo.toml` and `package.json` suggested conflicting test commands.
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.build` unset after model escalation: The repository contains both a Rust workspace and a Node.js package, representing two distinct primary build systems. No single primary build command can be selected without bias..
- Left `repo.test` unset after model escalation: The candidates represent mutually exclusive language ecosystems (Rust vs Node.js); no single primary value can represent the repository as a whole..
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Filled repo.description from GitHub repository metadata when the README surface did not provide one.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
