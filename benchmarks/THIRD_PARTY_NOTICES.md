# Third-party material in benchmarks

DotRepo's MIT [license](../LICENSE) covers its own code and data. Retained upstream
source excerpts keep their own licenses; they are not relicensed by inclusion.

The [November 4 captured-revision audit](third-party-licenses/README.md) owns the
current inventory. It includes exact-commit license/notice texts and hashes,
source capture bindings, exact-version npm package notices and unresolved public
dispositions. Default-branch API classifications are not evidence of the terms
at an earlier captured commit.

Original source captures, historical experiment documents and negative results
remain unchanged. Recovered notices improve traceability; they do not establish
redistribution permission. Three groups have been quarantined from the current tree; the historical reasons remain in the
[disposition record](third-party-licenses/dispositions.json). In particular,
VSCE-Sign's exact 2.1.0 license is now present and contains sharing/publication
restrictions; its captured source files are now quarantined by the owner's explicit decision.

Before distributing a benchmark/source-evidence bundle, run:

```sh
uv run python scripts/check_benchmark_licenses.py --require-clearance
```

The check fails on unresolved current-tree holds or reintroduced quarantined
sources. The original source inventory, notices and Git history remain; the
verified preservation archive stays outside the repository and public outputs.
The archived/history copies retain their own restrictions.
