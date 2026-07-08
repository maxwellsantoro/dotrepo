# Audit sample disposition — 2026-07-08

Source sample: [`audit-sample-20260708.md`](./audit-sample-20260708.md)

Routine audit findings convert to deterministic fixes, fixtures, calibration, or
an explicit “no change” disposition. This note closes the sample.

| Identity | Risk factors | Disposition |
| --- | --- | --- |
| `github.com/awolfly9/IPProxyTool` | missing build/test/security/docs; surprising low completeness | **Honest absence.** Python research/tooling layout without a single primary command or security mailbox. Keep verified; do not invent build/test. Coverage-gap recrawl candidate only if future evidence adds a parseable manifest. |
| `github.com/max-mapper/art-of-node` | missing build/test/security | **Honest absence.** Educational/content repository (JavaScript guide), not a package with a build/test matrix. No parser fix. |
| `github.com/BurntSushi/toml` | missing security_contact/docs | **Accepted partial profile.** Build/test present via `go.mod` inference. Security absence is honest; no SECURITY.md mailbox. |
| `github.com/forkingdog/UITableView-FDTemplateLayoutCell` | missing build/test/security/docs | **Honest absence.** Objective-C/UIKit library without checked-in command surfaces in evidence. No .NET/npm/cargo-style command inference applies. |
| `github.com/itsfatduck/optimizerDuck` | medium confidence; missing build/test | **Converted via promotion path.** Non-actionable `security_contact` normalized to `unknown` (parser now rejects non-actionable URLs); gate-passed auto-promote to `verified`. Build/test remain honestly absent. |
| `github.com/AvaloniaUI/Avalonia` | missing build/test | **Parser/evidence gap, not a silent invent.** `.csproj` inference exists in import (`dotnet build` / `dotnet test`) but crawl evidence for this overlay does not currently materialize root csproj/sln. **Follow-up:** recrawl with supplemental .NET manifest fetch (same class as multi-ecosystem supplemental fetch). Do not hand-write build/test without evidence. |
| `github.com/dotnet/maui` | missing build/test | **Same class as Avalonia.** Large .NET monorepo; wait for recrawl materialization of solution/project files rather than inventing `dotnet build`. |
| `github.com/nginx-proxy/nginx-proxy` | missing security_contact | **Honest absence of mailbox.** Build/test already present. No fabricated contact. |

## System-level conversions from this sample (and related quality queue)

1. **Parser:** non-actionable SECURITY.md URLs (Discord, bare repo homepage, issue
   forms, personal sites, CVE search pages) no longer become
   `owners.security_contact` values. Import leaves contact unset so
   `unknown` / high-confidence absence can apply when SECURITY.md exists
   (`crates/dotrepo-core/src/import/parsing/security.rs`). Regression:
   `non_actionable_security_md_urls_do_not_become_contacts`.
2. **Scoring:** gRPC-style `*-cve-process.md` URLs count as actionable security
   path tokens (`urls.rs` + unit test).
3. **Index cleanup + promotion:** 18 non-actionable contacts normalized to
   `unknown`; scheme-less homepages fixed for clap/moment; **21 gate-passed
   promotions** applied (`verified` 590 → 611).
4. **Distribution (parallel):** lookup-miss fixture + aggregator E2E test;
   `examples/external-consumer/` reference client with tests.

No finding remains untriaged.
