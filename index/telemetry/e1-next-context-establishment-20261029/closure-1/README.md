# Compose source closure 1: default Bake files and module boundary

This addendum leaves the original proposal/freeze unchanged. The task remains
`make test` from the root at Compose commit
`343bb382d2192b88d84af49971bb5cb99bee268c`, with documented repository-default
main-module unit coverage and explicit e2e/separate-module exclusions.

Three read-only GitHub connector calls retained the exact Git commit metadata,
complete nonrecursive root tree, and complete relay tree. The root tree has 27
entries and SHA1 `b10e2fc106b7ea146f5d31f56ca0386688275aa7`; the relay tree has
six entries and SHA1 `ac3e3bb514a8b3963d43a1880a793bd08191efec`. Both returned
tree objects were reconstructed with Git tree serialization and their hashes
matched. The returned commit binds the root pointer; its signature is reported
unsigned, and this packet does not claim independent signature verification or
raw commit-object reconstruction.

Of the eight default Bake filenames identified by the coordinator from official
Docker documentation, only the already-retained `docker-bake.hcl` is present.
`compose.yaml`, `compose.yml`, `docker-compose.yml`, `docker-compose.yaml`,
`docker-bake.json`, `docker-bake.override.json`, and `docker-bake.override.hcl`
are absent from this complete frozen root tree. No additional default files
needed fetching, so zero additional file bodies/bytes were acquired. Root
`go.work` and `go.work.sum` are absent. Root `go.mod` and `relay/go.mod` are regular
blobs bound to their owning trees; the retained relay body declares the separate
`github.com/docker/compose-relay` module with Go 1.23. Five previously retained
route source files also match their exact root-tree blob identities.

`observations.json` retains every default filename's disposition, tree entries,
request/hash ledger and source bindings. `.dockerignore` and `.go-version` are
present in root metadata; their bodies were not fetched under the instruction to
fetch only additional default Bake files. No semantic claim is inferred from
those unseen bytes. The original literal `$(TAGS)` question remains for independent
source assessment; no new executable prerequisite or fatal finding is invented.

This closes the *upstream frozen-tree* default-file presence question. It does not
prove a user's checkout lacks added files, that `BUILDX_BAKE_FILE` or CLI/environment
overrides are absent, or that any environment can execute the recipe. Those remain
explicit consumer applicability conditions.

The proposed automatic establishment checks are in
`automatic-establishment-verifier-spec.json`. A critical gap remains: current core
inputs contain selected files, not an upstream-complete root inventory. A crawler
or local partial materialization cannot establish upstream absence by failing to
read a file it never fetched. Present-file hashes and filesystem nonexistence are
insufficient for this absence-dependent high assessment. The retained tree closes
the source fact for this independent assessment, but no generic proof subsystem
or new importer input contract is created here. The coordinator must choose any
minimal input/materialization change after the completeness disposition.

This is source-only follow-up by the prior E1 extractor/gold author on a known
development case. No command substitution, confidence promotion, new task,
extractor/shared source change, source execution, packages, Docker, Cargo,
providers, evaluated index/profile, or F-05 access occurred. The default lookup
list is supplied by the coordinator's official-documentation review; this worker
made no additional documentation network request. Source-completeness assessment,
implementation ownership and actual execution remain separate gates.
