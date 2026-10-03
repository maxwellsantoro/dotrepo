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


def percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_intent_rows(intent_summaries: dict) -> str:
    rows = []
    for intent in INTENT_ORDER:
        summary = intent_summaries.get(intent)
        if not isinstance(summary, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{html.escape(INTENT_LABELS.get(intent, intent))}</td>"
            f"<td>{html.escape(str(summary.get('taskCount', 0)))}</td>"
            f"<td>{html.escape(percent(float(summary.get('hitRate', 0.0))))}</td>"
            f"<td>{html.escape(percent(float(summary.get('fieldHitRate', 0.0))))}</td>"
            f"<td>{html.escape(percent(float(summary.get('abstentionRate', 0.0))))}</td>"
            "</tr>"
        )
    return "\n          ".join(rows)


def render_policy_coverage(report: dict | None, base_path: str) -> str:
    if report is None:
        return ""
    rows = []
    for task, counts in report["tasks"].items():
        rows.append(
            f"<tr><td>{html.escape(task)}</td>"
            f"<td>{counts['presentCount']} ({percent(counts['presenceRate'])})</td>"
            f"<td>{counts['acceptableCount']} ({percent(counts['acceptableRate'])})</td>"
            "<td>Not measured</td><td>Not measured</td></tr>"
        )
    raw = site_href(base_path, "/benchmarks/policy-coverage.json")
    return f"""<section class="panel">
      <h2>Which tasks can use a profile without fallback?</h2>
      <p>These counts apply the reference consumer to all {report["profileCount"]} indexed
      primary profiles at export time. Commands require an explicit, high-confidence extraction,
      a source, and a matching check timestamp. Missing, invalidated, inferred, or weaker
      assessments require upstream fallback. Candidate commands do not replace primary commands.</p>
      <div class="table-scroll" role="region" aria-label="Consumer policy coverage" tabindex="0">
      <table><thead><tr><th>Task</th><th>Values present</th><th>Policy acceptable</th>
      <th>Independently correct</th><th>Task completed</th></tr></thead>
      <tbody>{"".join(rows)}</tbody></table></div>
      <p>Presence, policy acceptance, correctness, and completion are separate outcomes.
      The last two require independent evidence; this coverage measurement leaves them unknown.
      An acceptable command is metadata for planning, not permission to execute it.</p>
      <p><a href="{raw}">Policy, per-repository decisions, and fallback reasons (JSON)</a></p>
    </section>"""


def render_efficiency_page(report: dict, base_path: str, policy_report: dict | None = None) -> str:
    summary = report.get("summary", {})
    generated_at = format_timestamp_for_humans(str(report.get("generatedAt", "unknown")))
    repository_count = summary.get("repositoryCount", 0)
    task_count = summary.get("taskCount", 0)
    request_reduction = percent(float(summary.get("requestReductionRate", 0.0)))
    dotrepo_requests = summary.get("dotrepoBatchQueryRequests", 0)
    scrape_requests = summary.get("scrapeProxyRequests", 0)
    task_hit_rate = percent(float(summary.get("hitRate", 0.0)))
    field_hit_rate = percent(float(summary.get("fieldHitRate", 0.0)))
    abstention_rate = percent(float(summary.get("abstentionRate", 0.0)))
    dotrepo_mb = float(summary.get("dotrepoBytes", 0)) / (1024 * 1024)
    proxy_mb = float(summary.get("scrapeProxyBytes", 0)) / (1024 * 1024)
    intent_rows = render_intent_rows(summary.get("intentSummaries", {}))
    raw_href = site_href(base_path, "/benchmarks/lookup-efficiency.json")
    policy_section = render_policy_coverage(policy_report, base_path)

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
      --panel: rgba(255, 251, 244, 0.84);
      --line: rgba(54, 46, 28, 0.14);
      --accent: #116466;
      --accent-strong: #0d494b;
      --signal: #c4572e;
      --shadow: 0 18px 60px rgba(23, 27, 31, 0.12);
      --radius: 22px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(17, 100, 102, 0.18), transparent 34%),
        radial-gradient(circle at top right, rgba(196, 87, 46, 0.12), transparent 30%),
        linear-gradient(180deg, #fbf6ec 0%, var(--paper) 54%, var(--paper-strong) 100%);
      font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
    }}
    a {{ color: inherit; text-decoration: none; }}
    .page {{ max-width: 1180px; margin: 0 auto; padding: 28px 18px 80px; }}
    .nav {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 30px; }}
    .brand {{ display: flex; align-items: baseline; gap: 12px; }}
    .brand__mark {{
      display: inline-flex; align-items: baseline; gap: 0.06em;
      font-family: "JetBrains Mono", ui-monospace, monospace;
      font-size: 1.4rem; font-weight: 500; letter-spacing: -0.01em;
    }}
    .brand__dot {{
      display: inline-block; width: 0.40em; height: 0.40em; border-radius: 50%;
      background: currentColor; flex-shrink: 0; translate: 0 -0.05em;
    }}
    .brand__tag {{ font-size: 0.88rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); }}
    .nav__links {{ display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 12px; }}
    .nav__links a {{ padding: 10px 14px; border: 1px solid var(--line); border-radius: 999px; background: rgba(255, 255, 255, 0.48); }}
    .nav__links a[aria-current="page"] {{
      background: linear-gradient(135deg, var(--accent) 0%, #0b4b5a 100%);
      color: white; border-color: transparent;
    }}
    .hero h1 {{ margin: 0 0 10px; font-size: clamp(2rem, 4.4vw, 3rem); line-height: 1.08; }}
    .hero p {{ margin: 0; max-width: 74ch; color: var(--muted); font-size: 1.06rem; line-height: 1.6; }}
    .hero .stamp {{ margin-top: 12px; font-size: 0.9rem; color: var(--muted); }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin: 30px 0; }}
    .metric {{
      background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius);
      box-shadow: var(--shadow); padding: 20px 22px;
    }}
    .metric__value {{ font-family: "JetBrains Mono", ui-monospace, monospace; font-size: 1.9rem; font-weight: 600; }}
    .metric__value--accent {{ color: var(--accent-strong); }}
    .metric__label {{ margin-top: 6px; font-size: 0.92rem; color: var(--muted); line-height: 1.4; }}
    .panel {{
      background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius);
      box-shadow: var(--shadow); padding: 26px 28px; margin-bottom: 22px;
    }}
    .panel h2 {{ margin: 0 0 12px; font-size: 1.3rem; }}
    .panel p {{ margin: 0 0 12px; color: var(--muted); line-height: 1.6; max-width: 84ch; }}
    .panel p:last-child {{ margin-bottom: 0; }}
    .table-scroll {{ overflow-x: auto; }}
    code {{ overflow-wrap: anywhere; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.98rem; }}
    th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--line); }}
    th {{ font-size: 0.82rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }}
    td:not(:first-child), th:not(:first-child) {{ text-align: right; font-variant-numeric: tabular-nums; }}
    code, pre {{ font-family: "JetBrains Mono", ui-monospace, monospace; font-size: 0.88em; }}
    pre {{
      background: rgba(22, 24, 27, 0.04); border: 1px solid var(--line); border-radius: 12px;
      padding: 14px 16px; overflow-x: auto; line-height: 1.5;
    }}
    .footer {{ display: flex; flex-wrap: wrap; gap: 14px; margin-top: 40px; font-size: 0.88rem; color: var(--muted); }}
    @media (max-width: 720px) {{
      .page {{ padding: 18px 14px 56px; }}
      .nav {{ align-items: flex-start; flex-direction: column; }}
      .nav__links {{
        width: 100%;
        flex-wrap: nowrap;
        justify-content: flex-start;
        overflow-x: auto;
        gap: 8px;
        padding-bottom: 4px;
      }}
      .nav__links a {{ flex: 0 0 auto; padding: 8px 12px; }}
      .panel {{ padding: 22px; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    {render_site_header(base_path, active="efficiency")}

    <section class="hero">
      <h1>Lookup coverage and modeled efficiency</h1>
      <p>This deterministic workload checks field presence for {html.escape(str(task_count))}
      tasks across {html.escape(str(repository_count))} indexed repositories.
      It measures completeness and payload sizes, and models batch requests.
      It does not establish factual accuracy, current upstream verification, or end-to-end agent savings.</p>
      <p class="stamp">Report generated {html.escape(generated_at)} · regenerated with each release gate · <a href="{raw_href}"><code>raw JSON</code></a></p>
    </section>

    <div class="metrics">
      <div class="metric">
        <div class="metric__value metric__value--accent">{html.escape(request_reduction)}</div>
        <div class="metric__label">modeled request reduction: {html.escape(str(dotrepo_requests))} batch lookups versus {html.escape(str(scrape_requests))} local proxy fetches</div>
      </div>
      <div class="metric">
        <div class="metric__value">{html.escape(task_hit_rate)}</div>
        <div class="metric__label">task hit rate — every field a research task asked for was present</div>
      </div>
      <div class="metric">
        <div class="metric__value">{html.escape(field_hit_rate)}</div>
        <div class="metric__label">field hit rate — individual requested fields contained nonempty values</div>
      </div>
      <div class="metric">
        <div class="metric__value">{html.escape(abstention_rate)}</div>
        <div class="metric__label">missing fields — absence alone does not establish correct abstention</div>
      </div>
    </div>

    {policy_section}

    <section class="panel">
      <h2>Per-intent presence results</h2>
      <p>The workload asks the same four questions of every repository, chosen before
      looking at which answers exist — so the numbers cannot flatter the index by only
      asking questions it can answer.</p>
      <div class="table-scroll" role="region" aria-label="Per-intent results" tabindex="0">
      <table>
        <thead>
          <tr><th>Intent</th><th>Tasks</th><th>Task hit rate</th><th>Field hit rate</th><th>Missing fields</th></tr>
        </thead>
        <tbody>
          {intent_rows}
        </tbody>
      </table>
      </div>
    </section>

    <section class="panel">
      <h2>What the numbers mean — and what they don't claim</h2>
      <p>The request model estimates {html.escape(str(dotrepo_requests))} batch GETs
      versus {html.escape(str(scrape_requests))} local record/evidence file fetches.
      It excludes source fallback, refresh work, cache behavior, retries, and model inference.</p>
      <p>The dotrepo payload is {dotrepo_mb:.1f}&nbsp;MB; the local normalized proxy is
      {proxy_mb:.1f}&nbsp;MB. These are measured artifact sizes, not live GitHub traffic.
      Evidence and freshness metadata have a payload cost; other extraction systems can preserve them too.</p>
      <p>Correct abstention and factual accuracy require independently sourced expected answers.
      The <a href="https://github.com/maxwellsantoro/dotrepo/tree/main/benchmarks/head-to-head">head-to-head benchmark</a>
      retains favorable and unfavorable results. Historical fixes do not establish current out-of-sample accuracy.</p>
      <p>Actual task cost must include fallback requests, source bytes, latency, model usage,
      and an allocated share of index maintenance. No measured end-to-end savings claim is made here.</p>
    </section>

    <section class="panel">
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
  --output-json /tmp/lookup-efficiency.json</pre>
      <p>Methodology details: <a href="https://github.com/maxwellsantoro/dotrepo/blob/main/docs/public-lookup-efficiency-benchmark.md"><code>docs/public-lookup-efficiency-benchmark.md</code></a></p>
    </section>

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
