# Sonnet command audit — 2026-10-04

Inspected GitHub's default branch `v2` at commit
`8e7158b2beb8c8269b1b322601214083afc5607f`. The files alongside this report
are unmodified GitHub contents API captures at that commit. Upstream commands
and action references are retained source evidence, not this project's workflow.

The previous overlay scalar, `pip install pytest pytest-xdist`, is setup only.
CI actually invokes `pytest -n auto sonnet --ignore=sonnet/src/conformance/`
after installing three requirement files, the package, pytest, and pytest-xdist.
Its matrix specifies Ubuntu and Python 3.9, 3.10, or 3.11. No working-directory
override is declared; checkout-root execution targets the Sonnet component
and omits conformance tests.

The root directory is inferred from checkout with no `path` input and no
workflow, job, or step working-directory override. This follows GitHub's
[runner workspace contract](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
and [checkout behavior](https://github.com/actions/checkout/tree/v2), rather than
assuming every legacy command has root context.

Disposition: withhold the scalar default, remove its stale value assessment,
and preserve the actual command as a component candidate with explicit context.
Other field timestamps and record-wide age remain unchanged. Context was
inspected from source; the test command was not executed. This known-case audit
does not establish independent consumer savings or correctness across ecosystems.

The retained workflow is also copied verbatim into the command parser's
`tests/fixtures/command-audit/sonnet-ci.yml` regression case. The test checks
runner extraction, while the overlay disposition separately limits scope.
