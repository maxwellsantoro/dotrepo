# Independent documentation parser amendment review

The final bounded association repair passes this review with no remaining blocking
finding. The reviewer is separate from the initial repair author, with prior
project/importer context. The coordinator authored the final bare-URL amendment
after this review reproduced its neighboring ownership bypass.

The first review ran 19 actual imports against the frozen author CLI and found
four wrong-subject selections through physical docs/start prefixes. `BEFORE.json`
freezes that source, exact inputs and observations. Amendment 1 closed those four;
the independent next run of 31 imports found one remaining bare-URL section
ownership bypass, suggested by the coordinator and independently reproduced here.
`after/FREEZE.json` freezes that intermediate result rather than rewriting it.

The final run uses a coordinator-supplied stable copied CLI with SHA256
`79a4e70fb5c6e80708c27230e6958b51217727069f957d823215c494ab4b0b61`.
All 38 synthetic README imports and both retained real README imports pass.
Cases cover wrapped/list/ordered ownership, third-party tails, full-paragraph
prefixes, neutral titles, custom-domain/project navigation, unrelated license/
code-of-conduct/issue links, own versus third-party docs introductions, and bare
URLs. The original four failures and subsequent bare-URL failure all abstain.
Genuine direct/navigation declarations and neutral docs/start prefixes remain
accepted. The real SwiftLint and MinIO source subsets withhold the wrong fields
without inferring the independently reviewed replacement values.

`after-2/report.json` binds the exact final source and limitations. It retains the
source review of the paragraph cache: monotone line traversal reuses each cached
range, wrapped/list owner text remains in the rendered paragraph, and mixed
multi-link paragraphs do not repeatedly scan the entire paragraph as direct
prose. Selected 1,000/4,000/12,000-line imports took about 0.066/0.251/0.754 seconds
and all abstained. These are whole CLI observations on a shared host, not a
universal complexity proof. The author's deterministic cache build-count control
also remains in the source/focused evidence; this reviewer ran no concurrent Cargo.

The initial attempt to use the shared target binary refused at its hash guard
before any imports because combined gates were rebuilding it. That safe refusal
is retained in `after/startup-safe-refusal.json`; later observations use explicitly
bound copied binaries. No old binary receipt is relabeled as a later build.

This is a bounded lexical Markdown association review, not a full Markdown/HTML
interpreter or all-input proof. Unknown forms may abstain. No domain blacklist,
production edit, network/provider call, upstream execution or Cargo build was
performed by this reviewer. The frozen record corrections/public timestamp gate
remain unchanged. Final coordinator integration/public/release checks remain
separate from these focused controls.
