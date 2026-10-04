# Command source regression evidence

`sonnet-ci.yml` is an unchanged capture of Google DeepMind Sonnet's
`.github/workflows/ci.yml` at commit
`8e7158b2beb8c8269b1b322601214083afc5607f`, inspected on 2026-10-04.
See `benchmarks/command-audit-2026-10-04/sonnet/` for the source context and
overlay disposition. Upstream Python commands and unpinned action references
are source evidence, not instructions for dotrepo's tooling or CI.
