# RFC 0001: Protocol and ecosystem model

## Status
Draft

## Summary

dotrepo is an open metadata protocol for software repositories, supported by a reference toolchain and a public index.

The protocol exists to create a shared metadata layer that can be used by maintainers, users, agents, and tools. The reference toolchain helps author, validate, query, and synchronize that layer. The index makes repositories mechanically visible even when they have not adopted dotrepo natively.

## Principles

1. **Protocol first**: the schema and trust model matter more than any single tool.
2. **Three-sided value**: the system should benefit maintainers, users, and agents together.
3. **Trust-aware representation**: records must communicate provenance and status.
4. **Useful before adoption**: overlays and the index are permanent parts of the ecosystem, not temporary bootstraps.
5. **Practical compatibility**: dotrepo should coexist with established repository surfaces and platform expectations.

## Day-one scope

### In scope
- a canonical in-repo `.repo` file in TOML format
- external overlay records for public repositories
- a trust and provenance model
- queryable essential metadata
- basic generated repository surfaces and diagnostics

### Out of scope
- universal workspace composition
- plugin ecosystems
- full arbitrary bidirectional parsing of all repo prose
- platform-specific control plane mutation

## Canonical in-repo form

For v0.1, the only canonical in-repo form is a single root `.repo` file.

Bundle mode is reserved for a future version.

## Relationship to the index

The index is a first-class part of the protocol's adoption and utility model. It is the place where overlays, reviewed records, and canonical mirrors can be discovered and compared.
