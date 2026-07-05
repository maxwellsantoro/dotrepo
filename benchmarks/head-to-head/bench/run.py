from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import yaml

from .cache import ResponseCache
from .fields import FIELDS_BY_ID
from .model import Answer, GoldItem, Outcome, FieldClass, score_answer
from .arms.base import Http
from .arms.github_arm import GitHubArm
from .arms.dotrepo_arm import DotrepoArm


def load_repo_dotenv() -> None:
    """Load dotrepo/.env for local benchmark runs without overriding the shell."""
    if os.environ.get("DOTREPO_BENCH_LOAD_DOTENV", "1").lower() in {"0", "false", "no"}:
        return
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def load_gold(path: str) -> List[GoldItem]:
    doc = yaml.safe_load(open(path))
    items = []
    for repo, fields in doc["repos"].items():
        for fid, spec in fields.items():
            gold = spec if not isinstance(spec, dict) else spec.get("gold")
            note = spec.get("note", "") if isinstance(spec, dict) else ""
            items.append(GoldItem(repo=repo, field_id=fid, gold=gold, note=note))
    return items


def build_arm(name: str, http: Http, base_url: str, extractor: str):
    if name == "github":
        return GitHubArm(http, extractor=extractor)
    if name == "dotrepo":
        return DotrepoArm(http, base_url=base_url)
    raise SystemExit(f"unknown arm: {name}")


def run(gold: List[GoldItem], arm) -> Dict:
    by_repo: Dict[str, List[GoldItem]] = defaultdict(list)
    for g in gold:
        by_repo[g.repo].append(g)
    rows = []
    for repo, items in by_repo.items():
        try:
            arm.prefetch(repo)
        except Exception as e:
            for g in items:
                rows.append(_row(repo, g, Answer(None, None, f"prefetch-error:{e}"), Outcome.ABSTAINED))
            continue
        for g in items:
            field = FIELDS_BY_ID.get(g.field_id)
            if field is None:
                continue
            ans = arm.answer(repo, field)
            out = score_answer(field, ans, g.gold)
            rows.append(_row(repo, g, ans, out))
    return {"arm": arm.name, "rows": rows, "summary": summarize(rows)}


def _row(repo, g, ans: Answer, out: Outcome):
    f = FIELDS_BY_ID.get(g.field_id)
    return {
        "repo": repo, "field": g.field_id,
        "field_class": f.field_class.value if f else "?",
        "gold": g.gold, "got": ans.value, "confidence": ans.confidence,
        "outcome": out.value, "source": ans.source,
        "bytes": ans.bytes_over_wire, "latency_ms": round(ans.latency_ms, 1),
    }


def summarize(rows: List[dict]) -> dict:
    scored = [r for r in rows if r["outcome"] != Outcome.NO_GOLD.value]
    n = len(scored) or 1
    c = lambda o: sum(1 for r in scored if r["outcome"] == o)
    correct = c(Outcome.CORRECT.value)
    cwrong = c(Outcome.CONFIDENTLY_WRONG.value)
    answered = sum(1 for r in scored if r["outcome"] != Outcome.ABSTAINED.value)

    def bucket(fc):
        b = [r for r in scored if r["field_class"] == fc]
        bn = len(b) or 1
        return {
            "n": len(b),
            "accuracy": round(sum(1 for r in b if r["outcome"] == "correct") / bn, 3),
            "confidently_wrong": sum(1 for r in b if r["outcome"] == "confidently_wrong"),
        }

    return {
        "n_scored": len(scored),
        "accuracy": round(correct / n, 3),                       # correct / all scored
        "precision": round(correct / (answered or 1), 3),         # correct / answered
        "coverage": round(answered / n, 3),                       # answered / all scored
        "confidently_wrong": cwrong,
        "confidently_wrong_rate": round(cwrong / n, 3),           # the trust-critical metric
        "wrong_hedged": c(Outcome.WRONG_HEDGED.value),
        "abstained": c(Outcome.ABSTAINED.value),
        "total_bytes": sum(r["bytes"] for r in rows),
        "approx_tokens": round(sum(r["bytes"] for r in rows) / 4),
        "total_latency_ms": round(sum(r["latency_ms"] for r in rows), 1),
        "by_class": {"github_native": bucket("github_native"), "buried": bucket("buried")},
    }


def markdown(results: List[Dict]) -> str:
    L = ["# dotrepo benchmark — head-to-head", ""]
    L.append("| metric | " + " | ".join(r["arm"] for r in results) + " |")
    L.append("|" + "---|" * (len(results) + 1))
    def line(label, key, pct=False, sub=None):
        vals = []
        for r in results:
            s = r["summary"]
            v = s[sub][key] if sub else s[key]
            vals.append(f"{v:.1%}" if pct else str(v))
        L.append(f"| {label} | " + " | ".join(vals) + " |")
    line("scored questions", "n_scored")
    line("accuracy (correct / all)", "accuracy", pct=True)
    line("precision (correct / answered)", "precision", pct=True)
    line("coverage (answered / all)", "coverage", pct=True)
    line("**confidently wrong** (count)", "confidently_wrong")
    line("**confidently-wrong rate**", "confidently_wrong_rate", pct=True)
    line("abstained", "abstained")
    line("approx tokens over wire", "approx_tokens")
    line("total latency (ms)", "total_latency_ms")
    L += ["", "### Buried fields only (dotrepo's thesis)", ""]
    L.append("| metric | " + " | ".join(r["arm"] for r in results) + " |")
    L.append("|" + "---|" * (len(results) + 1))
    def bline(label, key, pct=False):
        vals = []
        for r in results:
            v = r["summary"]["by_class"]["buried"][key]
            vals.append(f"{v:.1%}" if pct else str(v))
        L.append(f"| {label} | " + " | ".join(vals) + " |")
    bline("buried accuracy", "accuracy", pct=True)
    bline("buried confidently-wrong", "confidently_wrong")
    L += ["", "_A win for dotrepo is: higher buried accuracy AND fewer confidently-wrong "
          "answers AND fewer tokens. If it doesn't clear all three, it isn't paying rent._", ""]
    return "\n".join(L)


def main():
    load_repo_dotenv()

    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default="gold.yaml")
    ap.add_argument("--arms", default="github,dotrepo")
    ap.add_argument("--base-url", default="https://dotrepo.org")
    ap.add_argument("--extractor", default="heuristic", choices=["heuristic", "llm"])
    ap.add_argument("--out", default="results")
    ap.add_argument("--cache-mode", default="off", choices=["off", "freeze", "replay"])
    ap.add_argument("--cache-dir", default="results/fixtures")
    args = ap.parse_args()

    gold = load_gold(args.gold)
    cache = ResponseCache(args.cache_dir, args.cache_mode)
    http = Http(cache=cache)
    os.makedirs(args.out, exist_ok=True)

    results = []
    for name in [a.strip() for a in args.arms.split(",") if a.strip()]:
        arm = build_arm(name, http, args.base_url, args.extractor)
        results.append(run(gold, arm))

    with open(os.path.join(args.out, "results.json"), "w") as f:
        json.dump(results, f, indent=2)
    md = markdown(results)
    with open(os.path.join(args.out, "report.md"), "w") as f:
        f.write(md)
    print(md)
    print(f"\nwrote {args.out}/results.json and {args.out}/report.md")


if __name__ == "__main__":
    main()
