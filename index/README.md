# dotrepo Seed Index

This directory is a seed version of the future `dotrepo/index` repository.

It exists to make the public-index model concrete early:
- contributors can add overlay records before maintainers adopt dotrepo natively
- CI can validate index-specific contribution rules
- agents and tools can point at a real index layout instead of only RFC text

## Layout

Each record lives under:

```text
index/
  repos/
    <host>/
      <owner>/
        <repo>/
          record.toml
          evidence.md
```

## Day-one rules

- v0.1 seed-index entries use `record.mode = "overlay"`.
- `record.toml` must pass `dotrepo validate`.
- `evidence.md` must exist beside every `record.toml`.
- `record.source` must resolve to the same `<host>/<owner>/<repo>` path used by the index entry.
- `repo.homepage`, when it is a repository URL, must match that same identity.

## Local validation

Run:

```bash
cargo run -p dotrepo-cli -- validate-index
```

CI runs the same command on every push and pull request.
