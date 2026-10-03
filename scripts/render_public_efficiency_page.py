#!/usr/bin/env -S uv run python
"""Render the lookup-efficiency benchmark as a human-readable public page.

Reads a report produced by `scripts/measure_public_lookup_efficiency.py`,
writes `<public-root>/efficiency/index.html` in the site's design language,
and copies the raw report to `<public-root>/benchmarks/lookup-efficiency.json`
so agents can consume the same numbers the page presents.
"""

import argparse
import html
import json
from pathlib import Path

from measure_public_lookup_efficiency import (
    MAX_BATCH_PATHS,
    MAX_BATCH_REPOSITORIES,
    MAX_BATCH_RESULTS,
)
from measure_public_policy_coverage import measure as measure_policy_coverage

from render_public_pages_landing import (
    detect_site_base_path,
    format_timestamp_for_humans,
    load_json,
    render_site_header,
    site_href,
    write_text,
)

INTENT_ORDER = ["overview", "execution", "documentation", "security"]

INTENT_LABELS = {
    "overview": "Overview",
    "execution": "Execution (build & test)",
    "documentation": "Documentation",
    "security": "Security stewardship",
}

POLICY_TASK_LABELS = {
    "build-and-test": "Build and test",
    "description": "Repository description",
    "documentation": "Documentation",
    "build": "Build command",
    "test": "Test command",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render the public lookup-efficiency benchmark page."
    )
    parser.add_argument("--input", dest="input_dir", required=True, help="Public export root")
    parser.add_argument(
        "--benchmark",
        required=True,
        help="Report JSON from measure_public_lookup_efficiency.py",
    )
    return parser.parse_args()


def percent(value: float | None) -> str:
    return "Not measured" if value is None else f"{value * 100:.1f}%"


def render_intent_rows(intent_summaries: dict) -> str:
    rows = []
    for intent in INTENT_ORDER:
        summary = intent_summaries.get(intent)
        if not isinstance(summary, dict):
            continue
        rows.append(
            "<tr>"
            f'<th scope="row">{html.escape(INTENT_LABELS.get(intent, intent))}</th>'
            f"<td>{html.escape(str(summary.get('taskCount', 0)))}</td>"
            f"<td>{percent(summary.get('hitRate'))}</td>"
            f"<td>{percent(summary.get('fieldHitRate'))}</td>"
            f"<td>{percent(summary.get('abstentionRate'))}</td>"
            "</tr>"
        )
    return "\n          ".join(rows)


def render_policy_coverage(report: dict | None, base_path: str) -> str:
    if report is None:
        return """<section class="section" aria-labelledby="coverage-heading">
      <h2 id="coverage-heading">Usable coverage is unavailable</h2>
      <p>No consumer-policy report was supplied. Field presence alone cannot establish
      which profiles can be used without upstream fallback.</p>
    </section>"""
    profile_count = report["profileCount"]
    if not profile_count:
        return """<section class="section" aria-labelledby="coverage-heading">
      <h2 id="coverage-heading">No profiles evaluated</h2>
      <p>Consumer-policy coverage is not available for an empty export.</p>
    </section>"""
    tasks = report["tasks"]
    ordered_tasks = [task for task in POLICY_TASK_LABELS if task in tasks]
    ordered_tasks.extend(task for task in tasks if task not in POLICY_TASK_LABELS)
    groups = []
    rows = []
    for task in ordered_tasks:
        counts = tasks[task]
        label = html.escape(POLICY_TASK_LABELS.get(task, task))
        bars = []
        for name, key, style in (
            ("Fields present", "presenceRate", "present"),
            ("Policy acceptable", "acceptableRate", "acceptable"),
        ):
            rate = counts[key]
            count = counts["presentCount" if style == "present" else "acceptableCount"]
            bars.append(
                '<div class="coverage-bar">'
                f'<span class="coverage-bar__label">{name}</span>'
                '<span class="coverage-bar__track" aria-hidden="true">'
                f'<span class="coverage-bar__fill coverage-bar__fill--{style}" '
                f'style="width: {rate * 100:.4f}%"></span></span>'
                f'<span class="coverage-bar__value">{percent(rate)} '
                f"<span>({count:,} / {profile_count:,})</span></span></div>"
            )
        groups.append(f'<li class="coverage-group"><h3>{label}</h3>{"".join(bars)}</li>')
        rows.append(
            f'<tr><th scope="row">{label}</th>'
            f"<td>{counts['presentCount']} ({percent(counts['presenceRate'])})</td>"
            f"<td>{counts['acceptableCount']} ({percent(counts['acceptableRate'])})</td>"
            "<td>Not measured</td><td>Not measured</td></tr>"
        )
    combined = tasks.get("build-and-test")
    takeaway = ""
    if combined is not None:
        fallback_count = profile_count - combined["acceptableCount"]
        takeaway = f"""<p class="coverage-takeaway"><strong>{percent(combined["acceptableRate"])}
      pass the build-and-test policy.</strong> {fallback_count:,} of {profile_count:,}
      profiles ({percent(fallback_count / profile_count)}) require upstream fallback
      for those two commands.</p>"""
    evaluated_at = html.escape(
        format_timestamp_for_humans(str(report.get("evaluatedAt", "unknown")))
    )
    raw = site_href(base_path, "/benchmarks/policy-coverage.json")
    return f"""<section class="section coverage" aria-labelledby="coverage-heading">
      <h2 id="coverage-heading">Fields present vs. policy acceptable</h2>
      {takeaway}
      <figure class="coverage-chart" aria-labelledby="coverage-heading coverage-caption">
        <figcaption id="coverage-caption">All {profile_count:,} primary profiles,
        evaluated {evaluated_at}. Each pair uses the same 0–100% scale.</figcaption>
        <div class="coverage-axis" aria-hidden="true"><span>0%</span><span>50%</span><span>100%</span></div>
        <ul class="coverage-groups">{"".join(groups)}</ul>
      </figure>
      <p>Fields present means every field needed for that task contains a value.
      Policy acceptable means the reference consumer accepts the profile without source fallback
      at the evaluation time. Commands require explicit, high-confidence extraction,
      a source, and a matching check timestamp. Inferred or weaker assessments and
      candidate commands do not qualify.</p>
      <p><strong>Independent correctness and task completion: Not measured.</strong>
      Policy acceptance is metadata for planning, not permission to execute commands.</p>
      <p><a href="{raw}">Policy, per-repository decisions, and fallback reasons (JSON)</a></p>
      <details class="data-details"><summary>View coverage as a data table</summary>
      <div class="table-scroll" role="region" aria-label="Consumer policy coverage" tabindex="0">
      <table><caption>Coverage out of {profile_count:,} primary profiles</caption>
      <thead><tr><th scope="col">Task</th><th scope="col">Fields present</th>
      <th scope="col">Policy acceptable</th><th scope="col">Independently correct</th>
      <th scope="col">Task completed</th></tr></thead>
      <tbody>{"".join(rows)}</tbody></table></div>
      </details>
    </section>"""


def render_efficiency_page(report: dict, base_path: str, policy_report: dict | None = None) -> str:
    summary = report.get("summary", {})
    generated_at = format_timestamp_for_humans(str(report.get("generatedAt", "unknown")))
    repository_count = summary.get("repositoryCount", 0)
    task_count = summary.get("taskCount", 0)
    request_reduction = percent(summary.get("requestReductionRate"))
    dotrepo_requests = summary.get("dotrepoBatchQueryRequests", 0)
    scrape_requests = summary.get("scrapeProxyRequests", 0)
    task_hit_rate = percent(summary.get("hitRate"))
    field_hit_rate = percent(summary.get("fieldHitRate"))
    abstention_rate = percent(summary.get("abstentionRate"))
    dotrepo_mb = float(summary.get("dotrepoBytes", 0)) / (1024 * 1024)
    proxy_mb = float(summary.get("scrapeProxyBytes", 0)) / (1024 * 1024)
    intent_rows = render_intent_rows(summary.get("intentSummaries", {}))
    raw_href = site_href(base_path, "/benchmarks/lookup-efficiency.json")
    policy_section = render_policy_coverage(policy_report, base_path)
    payload_comparison = ""
    if proxy_mb:
        payload_comparison = (
            f"The dotrepo artifacts are {dotrepo_mb / proxy_mb:.2f}× the proxy size. "
            if dotrepo_mb > proxy_mb
            else "The dotrepo artifacts are no larger than this local proxy. "
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Ccircle cx='32' cy='32' r='20' fill='%23141414'/%3E%3C/svg%3E">
  <title>Efficiency · dotrepo</title>
  <meta name="description" content="Field presence, consumer-policy acceptance, modeled requests, and measured payload sizes for the dotrepo public index.">
  <style>
    :root {{
      color-scheme: light;
      --paper: #f6f1e8;
      --paper-strong: #efe6d7;
      --ink: #16181b;
      --muted: #5c635d;
      --line: rgba(54, 46, 28, 0.14);
      --accent: #116466;
      --accent-strong: #0d494b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: var(--paper);
      font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
      line-height: 1.55;
    }}
    a {{ color: var(--accent-strong); text-underline-offset: 0.2em; }}
    a:hover {{ text-decoration-thickness: 2px; }}
    :focus-visible {{ outline: 3px solid var(--accent); outline-offset: 4px; }}
    .page {{ max-width: 1120px; margin: 0 auto; padding: 28px 24px 64px; }}
    .nav {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 30px; }}
    .brand {{ display: flex; align-items: baseline; gap: 12px; }}
    .brand__mark {{
      display: inline-flex; align-items: baseline; gap: 0.06em;
      font-family: "JetBrains Mono", ui-monospace, monospace;
      font-size: 1.4rem; font-weight: 500; letter-spacing: -0.01em;
      color: var(--ink); text-decoration: none;
    }}
    .brand__dot {{
      display: inline-block; width: 0.40em; height: 0.40em; border-radius: 50%;
      background: currentColor; flex-shrink: 0; translate: 0 -0.05em;
    }}
    .brand__tag {{ font-size: 0.88rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); }}
    .nav__links {{ display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 12px; }}
    .nav__links a {{ padding: 10px 12px; border-radius: 6px; text-decoration: none; }}
    .nav__links a[aria-current="page"] {{
      background: var(--accent); color: white;
    }}
    .hero {{ padding: 18px 0 30px; }}
    .hero h1 {{ margin: 0 0 10px; font-size: clamp(1.85rem, 4vw, 2.5rem); line-height: 1.15; letter-spacing: -0.025em; }}
    .hero p {{ margin: 0; max-width: 74ch; color: var(--muted); font-size: 1.06rem; line-height: 1.6; }}
    .hero .stamp {{ margin-top: 12px; font-size: 0.9rem; color: var(--muted); }}
    .section {{ padding: 28px 0; border-top: 1px solid var(--line); }}
    .section h2 {{ margin: 0 0 12px; font-size: 1.35rem; line-height: 1.3; }}
    .section p {{ margin: 0 0 12px; color: var(--muted); max-width: 84ch; }}
    .section p:last-child {{ margin-bottom: 0; }}
    .coverage-takeaway {{ font-size: 1.12rem; }}
    .coverage-takeaway strong {{ color: var(--accent-strong); }}
    .coverage-chart {{ margin: 20px 0; max-width: 920px; }}
    .coverage-chart figcaption {{ color: var(--muted); font-size: 0.9rem; margin-bottom: 16px; }}
    .coverage-axis {{ display: flex; justify-content: space-between; margin: 0 184px 0 146px; font-size: 0.8rem; color: var(--muted); }}
    .coverage-groups {{ list-style: none; padding: 0; margin: 0; }}
    .coverage-group {{ padding: 12px 0 16px; border-bottom: 1px solid var(--line); }}
    .coverage-group h3 {{ font-size: 1rem; margin: 0 0 6px; font-weight: 600; }}
    .coverage-bar {{ display: grid; grid-template-columns: 134px minmax(0, 1fr) 172px; gap: 12px; align-items: center; margin-top: 5px; }}
    .coverage-bar__label {{ font-size: 0.88rem; color: var(--muted); }}
    .coverage-bar__track {{ display: block; height: 12px; background: var(--paper-strong); }}
    .coverage-bar__fill {{ display: block; height: 100%; }}
    .coverage-bar__fill--present {{ background: #68756e; }}
    .coverage-bar__fill--acceptable {{ background: var(--accent); }}
    .coverage-bar__value {{ font-size: 0.95rem; font-variant-numeric: tabular-nums; white-space: nowrap; }}
    .coverage-bar__value span {{ color: var(--muted); font-size: 0.86rem; }}
    .data-details {{ margin-top: 18px; }}
    summary {{ cursor: pointer; color: var(--accent-strong); padding: 10px 0; font-weight: 600; }}
    .presence-summary {{ display: flex; flex-wrap: wrap; gap: 12px 30px; margin: 20px 0; }}
    .presence-summary div {{ flex: 1 1 180px; }}
    .presence-summary dt {{ color: var(--muted); font-size: 0.9rem; }}
    .presence-summary dd {{ margin: 2px 0 0; font-size: 1.3rem; font-variant-numeric: tabular-nums; }}
    .costs {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 32px; margin: 20px 0; }}
    .costs h3 {{ font-size: 1rem; margin: 0 0 8px; }}
    .costs dl {{ margin: 0 0 12px; }}
    .costs dl div {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px; border-bottom: 1px solid var(--line); padding: 8px 0; }}
    .costs dt {{ color: var(--muted); }}
    .costs dd {{ margin: 0; font-size: 1.16rem; font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; }}
    .costs .costs__note {{ font-size: 0.9rem; }}
    .table-scroll {{ overflow-x: auto; max-width: 100%; }}
    code {{ overflow-wrap: anywhere; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.95rem; }}
    caption {{ text-align: left; padding: 8px 12px; font-size: 0.88rem; color: var(--muted); }}
    th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--line); }}
    th[scope="col"] {{ font-size: 0.78rem; letter-spacing: 0.04em; text-transform: uppercase; color: var(--muted); }}
    th[scope="row"] {{ font-weight: 500; }}
    td:not(:first-child), th:not(:first-child) {{ text-align: right; font-variant-numeric: tabular-nums; }}
    code, pre {{ font-family: "JetBrains Mono", ui-monospace, monospace; font-size: 0.88em; }}
    pre {{
      background: var(--paper-strong); border-radius: 6px;
      padding: 14px 16px; overflow-x: auto; line-height: 1.5;
    }}
    .footer {{ display: flex; flex-wrap: wrap; gap: 14px; margin-top: 40px; font-size: 0.88rem; color: var(--muted); }}
    @media (max-width: 720px) {{
      .page {{ padding: 18px 18px 48px; }}
      .nav {{ align-items: flex-start; flex-direction: column; }}
      .nav__links {{
        width: 100%;
        flex-wrap: nowrap;
        justify-content: flex-start;
        overflow-x: auto;
        gap: 8px;
        padding-bottom: 4px;
      }}
      .nav__links a {{ flex: 0 0 auto; padding: 10px 12px; }}
      .brand__tag {{ font-size: 0.75rem; }}
      .hero {{ padding-top: 4px; }}
      .section {{ padding: 24px 0; }}
      .coverage-axis {{ margin: 0 0 8px; }}
      .coverage-bar {{ grid-template-columns: minmax(0, 1fr) auto; gap: 5px 10px; margin-top: 9px; }}
      .coverage-bar__track {{ grid-column: 1 / -1; grid-row: 2; }}
      .coverage-bar__value {{ grid-column: 2; grid-row: 1; }}
      .coverage-group {{ padding: 14px 0 18px; }}
      .coverage-bar__label {{ font-size: 0.82rem; }}
      .coverage-bar__value {{ font-size: 0.88rem; }}
      .coverage-bar__value span {{ font-size: 0.78rem; }}
      .costs {{ grid-template-columns: 1fr; gap: 20px; }}
      .presence-summary {{ gap: 12px; }}
      .presence-summary div {{ flex-basis: 140px; }}
    }}
    @media print {{
      .nav__links, .footer {{ display: none; }}
      body {{ background: white; }}
      .coverage-bar__track, .coverage-bar__fill {{ print-color-adjust: exact; }}
      .coverage-group, .costs {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    {render_site_header(base_path, active="efficiency")}

    <main>
    <section class="hero">
      <h1>What a lookup can answer</h1>
      <p>Start with usable metadata coverage and the need for upstream fallback.
      Then compare modeled request counts and measured payload costs.
      These reports do not establish end-to-end agent savings.</p>
      <p class="stamp">Lookup report generated {html.escape(generated_at)} ·
      <a href="{raw_href}">Lookup report (JSON)</a></p>
    </section>

    {policy_section}

    <section class="section" aria-labelledby="presence-heading">
      <h2 id="presence-heading">Field presence across the research workload</h2>
      <p>The deterministic research workload asks four fixed questions of each repository:
      {html.escape(str(task_count))} tasks across {html.escape(str(repository_count))} repositories.
      This counts populated values, without applying the consumer policy above.</p>
      <dl class="presence-summary">
        <div><dt>Tasks with all fields present</dt><dd>{task_hit_rate}</dd></div>
        <div><dt>Requested fields present</dt><dd>{field_hit_rate}</dd></div>
        <div><dt>Requested fields missing</dt><dd>{abstention_rate}</dd></div>
      </dl>
      <p>Missing fields alone do not establish correct abstention. None of these presence
      rates establish factual accuracy or successful task completion.</p>
      <div class="table-scroll" role="region" aria-label="Per-intent results" tabindex="0">
      <table>
        <caption>Presence by research intent</caption>
        <thead>
          <tr><th scope="col">Intent</th><th scope="col">Tasks</th>
          <th scope="col">All fields present</th><th scope="col">Fields present</th>
          <th scope="col">Fields missing</th></tr>
        </thead>
        <tbody>
          {intent_rows}
        </tbody>
      </table>
      </div>
    </section>

    <section class="section" aria-labelledby="cost-heading">
      <h2 id="cost-heading">Modeled requests and measured payloads</h2>
      <p>Batching reduces the modeled lookup count. It does not remove fallback work,
      and fewer requests do not necessarily mean fewer bytes.</p>
      <div class="costs">
        <div>
          <h3>Requests · modeled</h3>
          <dl>
            <div><dt>dotrepo batch GETs</dt><dd>{html.escape(str(dotrepo_requests))}</dd></div>
            <div><dt>Local proxy file fetches</dt><dd>{html.escape(str(scrape_requests))}</dd></div>
          </dl>
          <p class="costs__note">{request_reduction} modeled request reduction.
          Excludes source fallback, refresh work, cache behavior, retries, and model inference.</p>
        </div>
        <div>
          <h3>Artifact size · measured</h3>
          <dl>
            <div><dt>dotrepo profiles + query input</dt><dd>{dotrepo_mb:.1f} MiB</dd></div>
            <div><dt>Local record + evidence proxy</dt><dd>{proxy_mb:.1f} MiB</dd></div>
          </dl>
          <p class="costs__note">{payload_comparison}These are local artifact sizes,
          not live GitHub traffic or measured batch-response bytes. 1 MiB = 1,048,576 bytes.</p>
        </div>
      </div>
      <details>
        <summary>How the request model and byte counts work</summary>
        <p>For {html.escape(str(repository_count))} repositories and
        {html.escape(str(summary.get("uniqueFieldCount", 0)))} distinct requested fields,
        the harness batches up to {MAX_BATCH_REPOSITORIES} repositories,
        {MAX_BATCH_PATHS} paths, and {MAX_BATCH_RESULTS} results per request.
        The proxy counts one fetch for each unique checked-in <code>record.toml</code>
        and <code>evidence.md</code> file needed for the same repositories.</p>
        <p>Byte totals count each unique public <code>profile.json</code> and
        <code>query-input</code> artifact once, then compare them with the local proxy files.
        Evidence and freshness metadata have a payload cost; other extraction systems
        can preserve them too.</p>
      </details>
      <p>Correct abstention and factual accuracy require independently sourced expected answers.
      The <a href="https://github.com/maxwellsantoro/dotrepo/tree/main/benchmarks/head-to-head">head-to-head benchmark</a>
      retains favorable and unfavorable results. Historical fixes do not establish current out-of-sample accuracy.</p>
      <p>Actual task cost must include fallback requests, source bytes, latency, model usage,
      and an allocated share of index maintenance. No measured end-to-end savings claim is made here.</p>
    </section>

    <section class="section">
      <h2>Reproduce it</h2>
      <p>The workload builder and measurement harness are deterministic and ship in the
      repository. The release gate re-runs them against a versioned baseline on every
      release.</p>
      <pre>uv run python scripts/build_public_lookup_workload.py \\
  --public-root public --mode research --limit 0 \\
  --output /tmp/workload.json

uv run python scripts/measure_public_lookup_efficiency.py \\
  --public-root public --index-root index \\
  --workload /tmp/workload.json \\
  --output-json /tmp/lookup-efficiency.json

uv run python scripts/measure_public_policy_coverage.py \\
  --public-root public \\
  --output-json /tmp/policy-coverage.json</pre>
      <p>Methodology details: <a href="https://github.com/maxwellsantoro/dotrepo/blob/main/docs/public-lookup-efficiency-benchmark.md"><code>docs/public-lookup-efficiency-benchmark.md</code></a></p>
    </section>
    </main>

    <footer class="footer">
      <span>Canonical public origin: <a href="https://dotrepo.org/">dotrepo.org</a></span>
      <span>Raw report: <a href="{raw_href}"><code>/benchmarks/lookup-efficiency.json</code></a></span>
      <span>Source: <a href="https://github.com/maxwellsantoro/dotrepo">github.com/maxwellsantoro/dotrepo</a></span>
    </footer>
  </div>
</body>
</html>
"""


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    report = load_json(Path(args.benchmark))
    if report.get("schema") != "dotrepo-public-lookup-efficiency/v0":
        raise SystemExit(f"unexpected benchmark report schema: {args.benchmark}")
    inventory = load_json(input_dir / "v0" / "repos" / "index.json")
    base_path = detect_site_base_path(inventory)

    # The report embeds the local workload path used at measurement time;
    # publishing a build machine's filesystem layout serves nobody.
    if isinstance(report.get("workload"), dict):
        report["workload"].pop("path", None)
    # Per-task results are ~2.5 MB of detail that belongs in the repo's gate
    # artifacts, not the published aggregate; keep the hosted report compact.
    if "tasks" in report:
        report["tasks"] = []
        report.setdefault("notes", []).append(
            "per-task results are omitted from the published report; "
            "regenerate them locally with scripts/measure_public_lookup_efficiency.py"
        )

    policy_report = measure_policy_coverage(input_dir)
    write_text(
        input_dir / "efficiency" / "index.html",
        render_efficiency_page(report, base_path, policy_report),
    )
    write_text(
        input_dir / "benchmarks" / "policy-coverage.json",
        json.dumps(policy_report, indent=2) + "\n",
    )
    write_text(
        input_dir / "benchmarks" / "lookup-efficiency.json",
        json.dumps(report, indent=2, sort_keys=True) + "\n",
    )
    print(input_dir / "efficiency" / "index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
