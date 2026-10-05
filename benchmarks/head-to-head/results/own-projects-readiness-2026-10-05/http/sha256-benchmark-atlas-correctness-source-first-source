# SHA-256 Benchmark Atlas

[![SHA-256 campaign](https://github.com/maxwellsantoro/sha256-benchmark-atlas/actions/workflows/campaign.yml/badge.svg)](https://github.com/maxwellsantoro/sha256-benchmark-atlas/actions/workflows/campaign.yml)

Public atlas of **SHA-256 implementations** across languages and libraries: correctness first, then comparative performance with explicit provenance.

This is **not** a “fastest programming language” shootout. Many language APIs wrap the same native backend (often OpenSSL). The registry records:

```text
language interface → library → implementation → backend → CPU path
```

Design notes and motivation: [`GitHub-CI-Limits.md`](GitHub-CI-Limits.md). Pain points that should feed a future general harness live in [`PAIN.md`](PAIN.md).

## Layout

```text
implementations/     per-candidate runners (same CLI contract)
registry/            admitted / excluded implementations + provenance
vectors/             NIST / FIPS short-message vectors
harness via          `uv run sha256-atlas ...`
results/             campaign outputs (fingerprints, correctness, benches)
analysis/            summarization helpers
.github/workflows/   multi-shard GitHub Actions experimental blocks
```

## Runner contract

Every implementation exposes:

```text
hash                 # stdin bytes → hex digest on stdout
verify               # batch: repeated [u32 BE length][msg] → hex digest per line
bench SIZE ITERS [SEED]
                     # → JSON {"ns_total","hashes","size","digest"}
```

Timing loops run **inside** the candidate process (startup cost is not the measurement).
Correctness uses `verify` so thousands of cases share one process.

## Quick start

Requires: `uv`, a C compiler, OpenSSL headers (`libssl-dev` / Homebrew `openssl`), Rust (`cargo`), Go, Node, Java JDK.

On macOS with Homebrew OpenSSL:

```bash
export PKG_CONFIG_PATH="$(brew --prefix openssl)/lib/pkgconfig"
export PATH="/opt/homebrew/opt/openjdk@21/bin:$PATH"   # if needed
```

```bash
uv sync
uv run sha256-atlas fingerprint
uv run sha256-atlas build
uv run sha256-atlas correctness --cases 1000 --skip-million
uv run sha256-atlas bench --reps 3 --max-size 65536 -o results/local-bench.json
# or one shot:
uv run sha256-atlas campaign --reps 3 --cases 1000 --max-size 65536 --skip-million
uv run sha256-atlas summarize results/*/bench.json
```

## Experiment design (GitHub Actions)

Each workflow job is one **experimental block**:

1. Fingerprint CPU / OS / toolchains / SHA-NI flags  
2. Build all admitted candidates  
3. Correctness gate (NIST + boundaries + PRNG); only passers are timed  
4. **Interleaved** benches of all candidates on that same VM  
5. Upload raw JSON artifacts; an aggregate job summarizes ratios  

Host-to-host speed variation is a nuisance factor. On-machine ratios \(T_A / T_B\) cancel much of it.

## Latest campaign ([run #33234020231](https://github.com/maxwellsantoro/sha256-benchmark-atlas/actions/runs/33234020231))

12 independent GitHub-hosted blocks (10× `ubuntu-24.04`, 2× `ubuntu-24.04-arm`), 5 interleaved reps, 10k correctness cases, sizes 0–1 MiB, all 19 admitted implementations passing correctness and benched. Aggregate: [`results/latest/summary.json`](results/latest/summary.json).

| Message size | Fastest (median ns/hash) | Bulk throughput @ 1 MiB |
|---|---|---|
| 0 B | rust-sha2 (75 ns) | — |
| 64 B | rust-sha2 (95 ns) | — |
| 1 MiB | rust-ring ≈ rust-sha2 ≈ go-stdlib ≈ python-hashlib (~1.59 GB/s) | same OpenSSL backend cluster |

At 1 MiB, six independent OpenSSL front-ends — **python-hashlib**, **c-openssl**, **rust-openssl**, **python-cryptography**, **ruby-openssl**, **node-crypto** — converge within ~1% (spread ratio 1.008×): consistent with measuring the same underlying native primitive through different front ends. **zig-std** and **java-jdk** are ~1.1–1.2× slower; **php-hash** ~6×; **c-ref** ~7.5×; **java-bouncycastle** (pure-Java, no hardware SHA intrinsics) ~10×; **python-pure** orders of magnitude slower (expected).

## Leaderboards (conceptual)

| Board | Question |
|---|---|
| production | Fastest normal API in an ecosystem (native accel OK) |
| native | Ecosystem-owned impl, not a foreign crypto wrap |
| portable | No SHA-NI / arch asm |
| pure-language | Mostly written in the named language |
| reference | Pedagogical clarity |

## Adding an implementation

1. Add a runner under `implementations/<id>/` obeying the CLI contract (`hash`, `verify`, `bench`)
2. Register it in `registry/implementations.yaml` with provenance, backend, and status
3. Open a PR — CI builds, verifies, and benches it interleaved with the rest

Currently admitted: **19** implementations across C, Rust, Go, Python, JavaScript (Node/Bun), Ruby, PHP, Java, and Zig — spanning OpenSSL, BoringSSL, libsodium, mbedTLS, ring, RustCrypto, Bouncy Castle, Go stdlib, Zig stdlib, and reference paths.

## Claims this repo will and will not make

**Will:** On the observed population of runners in campaign \(X\), implementation A beat B at size \(n\) in \(k/k\) blocks, with median on-machine ratio \(R\).

**Will not:** Absolute ns/op on a specific unnamed Azure host as a hardware datasheet.
