"""Admit the existing reviewed observed class once; serve only compiled bindings."""

from __future__ import annotations

import json

from repodigest_acquire import canonical, sha


def admit(capsule_path, evidence_root, trusted_digest, database, archive):
    import observed_recipe
    import repodigest_store as store

    capsule = observed_recipe.decode(capsule_path.read_bytes())
    request = {
        "task": {
            **{k: capsule["source"][k] for k in ("repository", "revision", "tree")},
            **{
                k: capsule["recipe"][k]
                for k in ("purpose", "scope", "component", "workingDirectory")
            },
        },
        "files": capsule["source"]["files"],
        "dependencies": capsule["source"]["dependencies"],
        "environment": capsule["environment"],
        "recipeSha256": observed_recipe.value_sha(capsule["recipe"]),
        "acceptedLimitations": capsule["assessment"]["limitations"],
        "requirements": {
            "portable": False,
            "fullyReproducibleDependencies": False,
            "maintainerEndorsed": False,
        },
    }
    result = observed_recipe.evaluate(
        capsule, evidence_root, request, trusted_digest=trusted_digest, allow_observed_recipes=True
    )
    if (
        result["established"]["state"] != "established"
        or result["applicable"]["state"] != "suggestible"
    ):
        raise ValueError("observation failed original admission verifier")
    archive.mkdir(parents=True, exist_ok=False)
    observation = {
        "repository": capsule["source"]["repository"],
        "revision": capsule["source"]["revision"],
        "component": capsule["recipe"]["component"] or ".",
        "purpose": capsule["recipe"]["purpose"],
        "knowledgeClass": "observed-recipe",
        "policySha256": store.policy_id(),
        "capsuleSha256": trusted_digest,
        "expectedRequest": request,
        "historicalLead": {
            "recipe": capsule["recipe"],
            "recordedEnvironment": capsule["environment"],
            "established": result["established"],
            "limitations": result["limitations"],
            "evidence": result["evidence"],
            "meaning": "Historical success only; source, environment and execution authority do not transfer.",
        },
    }
    raw = canonical(observation)
    digest = sha(raw)
    if len(raw) > store.MAX_RECORD:
        raise ValueError("observation too large")
    repo = observation["repository"]
    revision = observation["revision"]
    component = observation["component"]
    receipt = {
        "capsuleSha256": trusted_digest,
        "observationSha256": digest,
        "policySha256": store.policy_id(),
        "meaning": "Original reviewed verifier replayed once on admission; no upstream execution.",
    }
    receipt_id = sha(canonical(receipt))
    details = canonical({"dependencies": capsule["source"]["files"], "sourceLeads": []})
    if len(details) > store.MAX_DETAILS:
        raise ValueError("compiled details exceed budget")
    details_id = sha(details)
    record = {
        "repository": repo,
        "revision": revision,
        "tree": capsule["source"]["tree"],
        "component": {
            "path": component,
            "ecosystems": ["Python"],
            "manifests": [],
            "manifestInspected": False,
        },
        "knowledgeClass": "observed-recipe",
        "policySha256": store.policy_id(),
        "admissionSha256": receipt_id,
        "checkedAt": store.stamp(),
        "detailsSha256": details_id,
        "coverage": {
            "meaning": "Legacy observed receipt; no new repository acquisition or execution."
        },
        "facts": {},
        "selections": {
            p: {"instruction": None, "fallbackReasons": ["no-source-qualified-instruction"]}
            for p in ("build", "test")
        },
    }
    body = canonical(record)
    record_digest = sha(body)
    db = store.connect_writer(database)
    with db:
        db.execute("INSERT OR IGNORE INTO objects VALUES(?,?)", (details_id, details))
        db.execute(
            "INSERT OR IGNORE INTO observations VALUES(?,?,?,?,?,?,?)",
            (digest, repo, component, revision, observation["purpose"], store.policy_id(), raw),
        )
        db.execute("INSERT OR IGNORE INTO records VALUES(?,?)", (record_digest, body))
        existing = db.execute(
            "SELECT r.body FROM versions v JOIN records r ON r.digest=v.digest WHERE v.identity=? AND v.revision=? AND v.component=?",
            (repo, revision, component),
        ).fetchone()
        if not existing or json.loads(existing[0]).get("knowledgeClass") == "observed-recipe":
            db.execute(
                "INSERT OR REPLACE INTO versions VALUES(?,?,?,?)",
                (repo, revision, component, record_digest),
            )
        db.execute("INSERT OR IGNORE INTO admissions VALUES(?,?)", (receipt_id, canonical(receipt)))
        if not db.execute("SELECT 1 FROM current WHERE identity=?", (repo,)).fetchone():
            db.execute(
                "INSERT INTO current VALUES(?,?,?,?,?)",
                (repo, revision, record["tree"], record["checkedAt"], trusted_digest),
            )
            db.execute(
                "INSERT INTO discovery(identity,description) VALUES(?,?)",
                (repo, "Legacy observed recipe"),
            )
    db.close()
    (archive / "admission.json").write_bytes(canonical(receipt) + b"\n")
    (archive / "observation.json").write_bytes(raw + b"\n")
    return receipt


def lookup(db, policy, repo, revision, component, purpose, request, *, include_leads, opt_in):
    out = {"observedRecipe": None}
    if opt_in is not True:
        if request is not None:
            out["observedRefusal"] = ["experimental-policy-opt-in-required"]
        return out
    if include_leads is not True and request is None:
        return out
    leads = []
    qualified = []
    reasons = []
    invalid_cohort = False
    query = "SELECT digest,body FROM observations WHERE identity=? AND component=? AND purpose=? AND policy=?"
    params = [repo, component, purpose, policy]
    if request is not None:
        query += " AND revision=?"
        params.append(revision)
    rows = db.execute(query + " ORDER BY digest LIMIT 11", params).fetchall()
    if request is not None and len(rows) > 10:
        out["observedRefusal"] = ["observation-cohort-over-budget"]
        return out
    if len(rows) > 10:
        out["historicalObservationsTruncated"] = True
    for digest, body in rows[:10]:
        if not isinstance(body, bytes) or len(body) > 131072 or sha(body) != digest:
            invalid_cohort = True
            reasons.append("compiled-observation-integrity-failure")
            continue
        try:
            row = json.loads(body)
            if not isinstance(row, dict):
                raise ValueError("invalid observation")
        except (ValueError, TypeError):
            invalid_cohort = True
            reasons.append("invalid-compiled-observation")
            continue
        if (
            row["policySha256"] != policy
            or row["repository"] != repo
            or row["component"] != component
        ):
            invalid_cohort = True
            reasons.append("observation-binding-or-policy-changed")
            continue
        if row["purpose"] != purpose or (request is not None and row["revision"] != revision):
            invalid_cohort = True
            reasons.append("observation-key-mismatch")
            continue
        if include_leads is True:
            leads.append(
                {
                    "observationSha256": digest,
                    "recordedRevision": row["revision"],
                    **row["historicalLead"],
                }
            )
        if request is not None:
            # Canonical identity compares types, all fields, acceptance and requirements.
            if row["revision"] == revision and canonical(request) == canonical(
                row["expectedRequest"]
            ):
                qualified.append(
                    {
                        "observationSha256": digest,
                        "knowledgeClass": "observed-recipe",
                        "recipe": row["historicalLead"]["recipe"],
                        "meaning": "Suggestible for the exact declared target only. Independently verify the actual target. No execution permission.",
                    }
                )
            else:
                reasons.append("exact-observed-bindings-mismatch")
    if invalid_cohort:
        out["observedRefusal"] = ["invalid-observation-cohort", *reasons]
    elif len(qualified) == 1:
        out["observedRecipe"] = qualified[0]
    elif request is not None:
        out["observedRefusal"] = reasons or ["observation-missing-or-ambiguous"]
    if include_leads is True:
        out["historicalObservations"] = leads
    return out
