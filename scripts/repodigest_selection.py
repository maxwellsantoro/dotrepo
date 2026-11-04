"""Bounded, process-local repository selection over existing retained assessments.

This is a consumer workflow, not a new source policy or capability interpreter.
Source/assessment admissions and frozen experiments remain unchanged.
"""

from __future__ import annotations

import copy
import re
import sqlite3

import repodigest_requirements as assessment
from repodigest_acquire import canonical, identity
from repodigest_discovery import LANGUAGES

MAX_QUERIES = 3
MAX_CANDIDATES = 4
MAX_SELECTIONS = 16
MAX_BODY = 32768
KEY_PAGE = 16


def describe(store, repository, *, revision=None, offset=0, limit=30):
    """Accept the same exact revision argument as lookup and source tools."""
    current = store.describe(repository, offset=offset, limit=limit)
    if revision is None:
        return current
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("revision must be exactly 40 lowercase hexadecimal characters")
    current["requestedRevision"] = revision
    if current.get("indexedRevision") == revision:
        return current
    repo = identity(repository)
    try:
        _, record = assessment.source_record(
            store, {"repository": repo, "revision": revision, "component": "."}
        )
    except (ValueError, KeyError, TypeError) as error:
        return {
            "repository": repo,
            "requestedRevision": revision,
            "currentIndexedRevision": current.get("indexedRevision"),
            "state": "unavailable",
            "missingEvidence": [str(error)],
            "components": [],
        }
    rows = store.db.execute(
        "SELECT component FROM versions WHERE identity=? AND revision=? ORDER BY component LIMIT ? OFFSET ?",
        (repo, revision, limit + 1, offset),
    ).fetchall()
    return {
        "repository": repo,
        "requestedRevision": revision,
        "indexedRevision": revision,
        "currentIndexedRevision": current.get("indexedRevision"),
        "tree": record["tree"],
        "checkedAt": record["checkedAt"],
        "discoveryProfile": store.profile(repo, revision),
        "components": [row[0] for row in rows[:limit]],
        "nextOffset": offset + limit if len(rows) > limit else None,
    }


def knowledge(store, repository, revision, offset=0):
    """Page assessment-bearing components independently of manifest components."""
    if type(offset) is not int or offset < 0:
        raise ValueError("requirementOffset must be a nonnegative integer")
    result = {"requirementKnowledge": [], "requirementKnowledgeNextOffset": None}
    if revision is None:
        return result
    try:
        rows = store.db.execute(
            "SELECT v.component FROM versions v WHERE v.identity=? AND v.revision=? "
            "AND EXISTS (SELECT 1 FROM requirement_sets r WHERE r.repository=v.identity "
            "AND r.component=v.component AND r.policy=?) ORDER BY v.component LIMIT ? OFFSET ?",
            (repository, revision, assessment.policy_id(), KEY_PAGE + 1, offset),
        ).fetchall()
    except sqlite3.OperationalError as error:
        if "no such table" not in str(error):
            raise
        return result
    for index, (component,) in enumerate(rows[:KEY_PAGE]):
        item = {
            "component": component,
            **assessment.available(
                store, {"repository": repository, "revision": revision, "component": component}
            ),
        }
        # Never silently turn a refused key index into evidence of no capability.
        if len(canonical(item)) + 256 > 8192:
            item = {
                "component": component,
                "claimKeys": [],
                "missingEvidence": ["assessment key index exceeds 8 KiB; inspect original sources"],
            }
        if len(canonical(result)) + len(canonical(item)) + 32 > 8192:
            result["requirementKnowledgeNextOffset"] = offset + index
            break
        result["requirementKnowledge"].append(item)
    else:
        if len(rows) > KEY_PAGE:
            result["requirementKnowledgeNextOffset"] = offset + KEY_PAGE
    return result


def bounded_limit(value, maximum):
    if type(value) is not int or value < 1:
        raise ValueError(f"limit must be a positive integer (maximum {maximum})")
    return min(value, maximum)


def with_limit(function, maximum):
    """Oversized page requests are capped explicitly; invalid types still refuse."""

    def call(*pos, **args):
        requested = args.get("limit")
        if requested is not None:
            args["limit"] = bounded_limit(requested, maximum)
        result = function(*pos, **args)
        if requested is not None and requested > maximum:
            result = {
                **result,
                "limitAdjustment": {"requested": requested, "applied": maximum},
            }
        return result

    return call


class Selection:
    """At most 16 workflows per server process, three searches/four leads each.

    No source fetch, model call, database write, or execution. The session ledger
    records unfinished attempts rather than counting only finalized decisions.
    """

    def __init__(self, store, find, describe_repository):
        self.store = store
        self.find = find
        self.describe = describe_repository
        self.sessions = {}

    def shortlist(self, queries, selectionId=None, language=None):
        if language is not None and (not isinstance(language, str) or language not in LANGUAGES):
            raise ValueError("unsupported language; use an advertised language or omit the filter")
        if not isinstance(queries, list) or not 1 <= len(queries) <= MAX_QUERIES:
            raise ValueError("supply 1..3 discovery queries; reuse selectionId for follow-up")
        for query in queries:
            if not isinstance(query, str) or not query.strip() or len(query) > 200:
                raise ValueError("each query must contain 1..200 characters")
        if selectionId is None:
            if len(self.sessions) >= MAX_SELECTIONS:
                raise ValueError("session capacity reached; export status and start a new server")
            selectionId = f"selection-{len(self.sessions) + 1}"
            self.sessions[selectionId] = {
                "selectionId": selectionId,
                "state": "unfinished",
                "searches": [],
                "repositories": [],
                "reusedQueries": 0,
                "omittedLeads": 0,
                "language": language,
                "leadGroups": [],
            }
        session = self._session(selectionId)
        if session["state"] != "unfinished":
            raise ValueError("selection already finalized; its retained decision is immutable")
        if language is None:
            language = session["language"]
        if language != session["language"]:
            raise ValueError("keep the selection's original language filter")
        for query in queries:
            normalized = " ".join(query.casefold().split())
            if any(row["normalized"] == normalized for row in session["searches"]):
                session["reusedQueries"] += 1
                continue
            if len(session["searches"]) >= MAX_QUERIES:
                break
            attempt = {"query": query, "normalized": normalized, "state": "started"}
            session["searches"].append(attempt)
            try:
                args = {"query": query, "limit": MAX_CANDIDATES}
                if language is not None:
                    args["language"] = language
                found = self.find(**args)
                attempt.update(
                    state="completed",
                    returned=len(found["repositories"]),
                    moreCandidates=found.get("moreCandidates", False),
                    refusedCandidates=found.get("refusedCandidates", 0),
                )
                session["leadGroups"].append(found["repositories"][:MAX_CANDIDATES])
            except (ValueError, KeyError, TypeError) as error:
                attempt.update(state="failed", error=str(error)[:200])
        # Round-robin gives later precise queries a slot without an unbounded union.
        # This is a declared allocation rule, not a suitability reranker.
        leads = {}
        for rank in range(MAX_CANDIDATES):
            for group in session["leadGroups"]:
                if rank < len(group):
                    leads.setdefault(group[rank]["repository"], group[rank])
        session["omittedLeads"] = max(0, len(leads) - MAX_CANDIDATES)
        session["repositories"] = []
        for repo, lead in list(leads.items())[:MAX_CANDIDATES]:
            try:
                described = self.describe(repository=repo)
                candidate = {
                    "repository": repo,
                    "discoveryRevision": lead.get("revision"),
                    "revision": described.get("indexedRevision"),
                    "sourceCheckedAt": described.get("checkedAt"),
                    "purpose": lead.get("purpose"),
                    "requirementKnowledge": described.get("requirementKnowledge", []),
                    "requirementKnowledgeNextOffset": described.get(
                        "requirementKnowledgeNextOffset"
                    ),
                    "missingEvidence": described.get("missingEvidence", []),
                }
            except (ValueError, KeyError, TypeError) as error:
                candidate = {"repository": repo, "missingEvidence": [str(error)[:200]]}
            session["repositories"].append(candidate)
        return self._view(session)

    def _view(self, session):
        result = copy.deepcopy(
            {key: value for key, value in session.items() if key != "leadGroups"}
        )
        result["remainingQueries"] = MAX_QUERIES - len(session["searches"])
        result["nextAction"] = (
            "Map mandatory requirements to the visible keys; use qualify/source.list/source.read "
            "only for a shortlisted candidate's gaps. Finish with decide, including unmapped "
            "requirements. Stop searches when the budget is exhausted; absent leads are not "
            "proof of global absence. Repeat calls must reuse this selectionId."
        )
        result["coverage"] = "bounded shortlist; neither exhaustive nor live-current"
        result["allocation"] = "round-robin query ranks; latest shortlist replaces earlier leads"
        if len(canonical(result)) > MAX_BODY:
            # Preserve candidate identity and an actionable gap without returning huge context.
            for candidate in result["repositories"]:
                candidate["requirementKnowledge"] = []
                candidate["missingEvidence"] = ["shortlist response budget; use describe for keys"]
        if len(canonical(result)) > MAX_BODY:
            raise ValueError("shortlist exceeds 32 KiB; attempt remains unfinished")
        return result

    def _session(self, selection_id):
        if not isinstance(selection_id, str) or selection_id not in self.sessions:
            raise ValueError("unknown selectionId; begin with shortlist")
        return self.sessions[selection_id]

    def decide(self, selectionId, candidates, requirements, unmappedRequirements=None):
        session = self._session(selectionId)
        if session["state"] != "unfinished":
            raise ValueError("selection already finalized; consult selection_status")
        if not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES:
            raise ValueError("choose 0..4 exact targets from this shortlist")
        targets = [assessment.target(candidate) for candidate in candidates]
        repos = {item["repository"] for item in session["repositories"]}
        if any(target["repository"] not in repos for target in targets):
            raise ValueError("candidate was not in this selection's bounded shortlist")
        if not isinstance(requirements, list) or len(requirements) > assessment.MAX_REQUIREMENTS:
            raise ValueError("supply 0..8 explicitly mapped requirements")
        unmapped = [] if unmappedRequirements is None else unmappedRequirements
        if (
            not isinstance(unmapped, list)
            or len(unmapped) > 8
            or any(not isinstance(item, str) or not 1 <= len(item) <= 320 for item in unmapped)
        ):
            raise ValueError("supply 0..8 unmapped mandatory requirements of 1..320 characters")
        # Validate syntax even when the shortlist has no candidates.
        for requirement in requirements:
            if (
                not isinstance(requirement, dict)
                or set(requirement) != {"key", "expected"}
                or not isinstance(requirement["key"], str)
                or not assessment.KEY.fullmatch(requirement["key"])
                or type(requirement["expected"]) is not bool
            ):
                raise ValueError("each requirement needs an exact claim key and boolean expected")
        findings, supported, errors = [], [], []
        for target in targets:
            try:
                result = (
                    assessment.qualify(self.store, [target], requirements) if requirements else None
                )
                item = result["candidates"][0] if result else {**target, "findings": []}
            except (ValueError, KeyError, TypeError) as error:
                item = {**target, "findings": [], "missingEvidence": [str(error)[:200]]}
                errors.append({**target, "error": str(error)[:200]})
            statuses = [finding["status"] for finding in item["findings"]]
            item["disposition"] = (
                "contradicted"
                if "contradicted" in statuses
                else "supported"
                if requirements
                and not unmapped
                and len(statuses) == len(requirements)
                and all(status == "supported" for status in statuses)
                else "unknown"
            )
            if item["disposition"] == "supported":
                supported.append(target)
            findings.append(item)
        result = {
            "selectionId": selectionId,
            "state": "completed",
            "disposition": "preliminary-selection" if supported else "none-established",
            "supportedCandidates": supported,
            "candidates": findings,
            "requirements": requirements,
            "unmappedRequirements": unmapped,
            "noneEstablishedReason": None
            if supported
            else "no-candidate-targets"
            if not targets
            else "unmapped-mandatory-requirements"
            if unmapped or not requirements
            else "all-targets-contradicted"
            if all(item["disposition"] == "contradicted" for item in findings)
            else "insufficient-or-conflicting-evidence",
            "searches": session["searches"],
            "failures": errors,
            "meaning": "Only the caller-mapped mandatory source requirements were checked. Supported is preliminary source support, not best choice, runtime success, current HEAD, or execution authority. None established applies only to these targets and evidence; it does not prove no suitable project exists.",
            "sourceFallback": "For unknowns inspect source.list/source.read at the exact revision; a new source conclusion needs its own attributed evidence. Do not repeat exhausted catalog searches.",
            "authorized": "not-granted",
        }
        if len(canonical(result)) > MAX_BODY:
            raise ValueError("decision exceeds 32 KiB; narrow targets; attempt remains unfinished")
        session["state"] = "completed"
        session["decision"] = copy.deepcopy(result)
        return result

    def status(self, selectionId=None):
        if selectionId is not None:
            session = self._session(selectionId)
            return (
                copy.deepcopy(session["decision"]) if "decision" in session else self._view(session)
            )
        return {
            "attempts": len(self.sessions),
            "completed": sum(s["state"] == "completed" for s in self.sessions.values()),
            "unfinished": [key for key, s in self.sessions.items() if s["state"] == "unfinished"],
            "searchCalls": sum(len(s["searches"]) for s in self.sessions.values()),
            "failedSearchCalls": sum(
                row["state"] == "failed" for s in self.sessions.values() for row in s["searches"]
            ),
            "meaning": "Process-local workflow accounting. Export before server exit. No model token, wall-time, billing, origin savings, or consumer correctness measurement is inferred.",
        }
