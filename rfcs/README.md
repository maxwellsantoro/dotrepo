# Design records

RFCs preserve protocol decisions and proposals. Their recorded status is not a
release inventory or active task queue. Use [the reference guide](../docs/reference-overview.md)
for current surfaces, [release compatibility](../docs/release-compatibility.md)
for installed binaries, and [the roadmap](../ROADMAP.md) for execution order.
Code, fixture contracts, and the public compatibility manifest define executable
behavior. An implementation does not retroactively mark a draft accepted.

For agent execution, take a dependency-ready packet from
[the roadmap](../ROADMAP.md) and use [the team execution guide](../docs/agent-execution.md).
Read only the design records for the contract that packet changes: schema and
execution use 0002/0020/0021, selection and claims use 0004/0008–0012, generation
uses 0005, transports use 0003/0006/0007, and public wire/export behavior uses
0016–0019. Consult the linked current guides and executable fixtures before
treating an RFC's illustrative payload, phase, or command as shipped behavior.

| RFC | Recorded status | Scope and current use |
| --- | --- | --- |
| [0001: Protocol/ecosystem](0001-protocol-and-ecosystem.md) | Draft | Three-part model and single root manifest |
| [0002: Schema](0002-schema-v0.1.md) | Draft | Manifest shape; see schema types and validation for support |
| [0003: CLI/query](0003-cli-and-query-contract.md) | Draft | Foundational command/selection contract; current CLI adds authoring and public helpers |
| [0004: Index/trust](0004-index-and-trust-model.md) | Draft | Identity, precedence, and conflict semantics; manual contribution path alongside autonomous overlays |
| [0005: Sync](0005-sync-and-generated-artifacts.md) | Draft | Generation and managed-region design; current supported IDs and states live in sync boundaries |
| [0006: MCP](0006-mcp-server-contract.md) | Accepted | Tools and shared core reports; response/safeguard details differ by release |
| [0007: LSP/VS Code](0007-lsp-and-vscode-scope.md) | Draft | Initial editor scope; current LSP also provides limited adoption code actions |
| [0008: Claim lifecycle](0008-maintainer-claim-lifecycle.md) | Draft | Actors and lifecycle |
| [0009: Claim artifacts](0009-claim-request-and-audit-trail.md) | Draft | Durable records and event ledger |
| [0010: Handoff](0010-overlay-to-canonical-handoff.md) | Draft | Acceptance distinct from canonical publication |
| [0011: Failure/correction](0011-claim-failure-and-correction-rules.md) | Draft | Explicit unsuccessful outcomes and append-only corrections |
| [0012: Claim visibility](0012-claim-history-and-superseded-overlay-visibility.md) | Draft | Claim context and full inspection separate from record selection |
| [0013: Claim implementation phases](0013-phased-maintainer-claim-implementation-plan.md) | Draft, historical sequencing | Artifact, inspection, and reviewer phases implemented; self-service submission/identity proof deferred |
| [0014: Bundle mode](0014-bundle-mode-design.md) | Draft, deferred | Proposed artifact container; existing release/export tarballs do not implement this proposal |
| [0015: Workspace/relations](0015-workspace-and-relations-model.md) | Draft, partially implemented | Research relations implemented; workspace kinds and operational composition deferred |
| [0016: Public serving](0016-public-index-site-and-query-api.md) | Accepted | Initial identity-first surface; current implementation also supports search, compare, and relations |
| [0017: Repository summary](0017-public-repository-summary-response.md) | Accepted | Summary selection, fields, and links |
| [0018: Static serving/freshness](0018-static-public-serving-and-freshness.md) | Accepted | Export-first delivery and shared freshness semantics |
| [0019: Trust/query wrappers](0019-public-trust-and-query-wrappers.md) | Accepted | Trust, query, and machine-readable errors |
| [0020: Command candidates](0020-multi-ecosystem-command-candidates.md) | Implemented | Additive ambiguity candidates |
| [0021: Execution context](0021-value-bound-execution-context.md) | Implemented, extraction deferred | Optional exact-command context, scope, directory, prerequisites, and source |

For practical claim commands, use [the operator workflow](../docs/maintainer-claim-review-workflow.md).
For public wire compatibility, use [the contract guide](../docs/public-api-compatibility.md)
and its linked fixture/test rather than inferring a full response from an RFC example.
