# Evidence

- Imported repository description from README.md.
- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Inferred repo.build from Cargo.toml as `cargo build --workspace`.
- Inferred repo.test from Cargo.toml as `cargo test --workspace`.
- Imported repo.toolchain.min from rust-toolchain.toml as `1.92.0` (Rust).
- Conflicting documentation declarations in README.md; abstained from docs.root.
- This is an overlay record, not a maintainer-controlled canonical record.
