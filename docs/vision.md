# Vision

## dotrepo in one sentence

dotrepo is an open metadata protocol for repositories that lets maintainers, users, and coding agents share the same structured understanding of a project.

## The system

dotrepo is best understood as three connected parts:

- **the protocol** gives repositories a shared metadata vocabulary
- **the toolchain** makes that vocabulary usable in practice
- **the index** lets any public repository become machine-legible immediately through overlays, while giving maintainers a path to claim and verify authoritative records

## The three-sided value

### Maintainers

Maintainers get a practical way to keep essential repository metadata coherent, queryable, and synchronized with familiar repository surfaces.

### Users

Users get better discovery, comparison, and orientation. Repositories become easier to understand without relying only on prose, heuristics, or social guesswork.

### Agents and tools

Agents and tools get direct access to structured facts like ownership, docs entry points, build and test commands, trust level, and provenance.

## What dotrepo is not trying to do

- replace source code
- replace documentation
- flatten projects into generic templates
- pretend inferred overlays are authoritative
- force a single authoring workflow on every repo

## The strategic insight

The index and overlay model mean dotrepo becomes useful before maintainers adopt it. That breaks the usual chicken-and-egg problem for standards.

A public overlay can make a repo mechanically visible today. A maintainer can later claim that representation by adopting a canonical in-repo `.repo` record. That creates a healthy flywheel instead of a forced migration.
