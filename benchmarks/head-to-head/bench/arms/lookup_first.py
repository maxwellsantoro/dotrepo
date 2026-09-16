"""Whole lookup-first consumer path, including source fallback and its cost.

Uses the shipped reference client's policy. HTTP bytes are not model tokens.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from .base import Arm
from .github_arm import GitHubArm
from ..model import Answer

CLIENT = Path(__file__).resolve().parents[4] / "examples/external-consumer/lookup_before_scrape.py"
SPEC = importlib.util.spec_from_file_location("dotrepo_reference_consumer", CLIENT)
consumer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = consumer
SPEC.loader.exec_module(consumer)


class LookupFirstArm(Arm):
    name = "lookup-first"

    def __init__(self, http, base_url, extractor="heuristic"):
        self.http = http
        self.base = base_url.rstrip("/")
        self.fallback = GitHubArm(http, extractor=extractor)
        self.events = []

    def configuration(self):
        return {
            "base_url": self.base,
            "fallback": self.fallback.configuration(),
            "max_record_age_days": 30,
            "consumer_class": "in-repository-reference",
            "model_usage_measured": False,
            "maintenance_cost_included": False,
        }

    def prefetch(self, repo):
        status, body, size, elapsed = self.http.get(f"{self.base}/v0/repos/{repo}/profile.json")
        self.result = consumer.interpret_http_response(identity=repo, status_code=status, body=body)
        self.cost = (size, elapsed)
        self.fallback_ready = False

    def answer(self, repo, field):
        size, elapsed = self.cost
        self.cost = (0, 0.0)
        path = field.dotrepo_path
        if path in consumer.FIELD_PATHS:
            consumer.evaluate_for_task(self.result, required_fields=[path])
            usable = self.result.usable
            reasons = self.result.fallback_reasons
        else:
            usable, reasons = False, ["unsupported-profile-field"]
        self.events.append(
            {
                "repository": repo,
                "field": field.id,
                "usedProfile": usable,
                "fallbackReasons": reasons,
            }
        )
        if usable:
            value = self.result.profile
            for key in consumer.FIELD_PATHS[path]:
                value = value[key]
            assessment = self.result.profile.get("fieldEvidence", {}).get(path, {})
            confidence = assessment.get("confidence") or (self.result.trust or {}).get("confidence")
            return Answer(
                str(value) if not isinstance(value, (dict, list)) else json.dumps(value),
                confidence,
                "profile:" + assessment.get("method", "record-level-only"),
                size,
                elapsed,
            )
        if not self.fallback_ready:
            self.fallback.prefetch(repo)
            self.fallback_ready = True
        answer = self.fallback.answer(repo, field)
        answer.bytes_over_wire += size
        answer.latency_ms += elapsed
        answer.source = "fallback:" + answer.source
        return answer
