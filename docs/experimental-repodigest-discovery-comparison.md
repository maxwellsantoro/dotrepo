# Experimental fixed-corpus discovery comparison

The local comparison indexes the same 100 frozen repositories in two ways:
`metadata` searches retained names, descriptions, topics and language metadata;
`repodigest` adds admitted source-profile descriptions, keywords, ecosystem and
interface signals, and literal README passages. Both use the same literal query,
OR-prefix SQLite BM25 ranking and metadata-language filter. This measures the
value of adding source knowledge to a competent local metadata index. It is not
a measurement of live GitHub search or agent productivity.

The full frozen local packet is retained on the preserved experimental branch;
see the [evidence inventory](research-evidence-20261030/README.md). This scoped
source delivery contains the comparison adapter and its small independent test
fixtures, not the large compiled study databases. For an operator-managed copy
of a compatible index, compare the two modes from the repository root:

```sh
uv run --offline --no-sync python scripts/repodigest_discovery_compare.py find --index /path/to/discovery-index --mode metadata --query "Rust command line argument parser options help" --language Rust
uv run --offline --no-sync python scripts/repodigest_discovery_compare.py find --index /path/to/discovery-index --mode repodigest --query "Rust command line argument parser options help" --language Rust
```

Both return compact discovery leads. Use `describe --repository
github.com/clap-rs/clap` with the same index/mode arguments for the full selected
record. Metadata mode exposes metadata only. RepoDigest mode exposes its full
admitted profile when available. Source profile absence remains visible through
the metadata-only knowledge label; it does not remove a repository from either
candidate universe. Older source compiler policies require re-admission.

The original experimental MCP service also benefits from the compact `find`
response and declared/derived interface labels. Its language filter continues to
mean manifest ecosystem, while this paired comparator deliberately applies the
same retained metadata-language list in both modes. These are different filter
semantics, stated in each interface; this study does not compare them.

The independent reference set covers 18 requests and all 100 repositories.
Judgments bind raw pinned sources and distinguish supported matches from partial
or uncertain candidates. Counts use the named `o200k_base` tokenizer on canonical
JSON; provider-session billing, transport envelopes and tool-schema context are
outside those counts. Reference-guided source reads are an oracle lower bound,
not observed consumer effort. The [corrected result](research-evidence-20261030/discovery100-correction.md.txt)
found identical supported recall and 86% more response tokens with source
enrichment. The full packet preserves acquisition costs and failures; these
compact result documents are not a reproduction bundle.
