use super::common::*;

#[test]
fn public_repository_summary_includes_freshness_links_and_artifacts() {
    let root = temp_dir("public-summary");
    let record_dir = root.join("repos/github.com/example/orbit");
    fs::create_dir_all(&record_dir).expect("record dir created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["imported", "verified"]
notes = "Reviewed overlay."

[repo]
name = "orbit"
description = "Reviewed overlay"
homepage = "https://github.com/example/orbit"

[owners]
team = "@example/orbit-team"
security_contact = "security@example.com"

[docs]
root = "https://example.com/orbit/docs"
getting_started = "https://example.com/orbit/docs/start"
"#,
    )
    .expect("record written");
    fs::write(
        record_dir.join("evidence.md"),
        "# Evidence\n\n- imported from the upstream repository\n",
    )
    .expect("evidence written");

    let response = public_repository_summary(
        &root,
        "github.com",
        "example",
        "orbit",
        sample_public_freshness(),
    )
    .expect("public summary builds");
    let json = serde_json::to_value(response).expect("summary serializes");
    assert_eq!(json["apiVersion"], Value::String("v0".into()));
    assert_eq!(
        json["freshness"]["generatedAt"],
        Value::String("2026-03-10T18:30:00Z".into())
    );
    assert_eq!(
        json["freshness"]["snapshotDigest"],
        Value::String("snapshot-123".into())
    );
    assert_eq!(
        json["repository"]["gettingStarted"],
        Value::String("https://example.com/orbit/docs/start".into())
    );
    assert_eq!(
        json["selection"]["record"]["artifacts"]["evidencePath"],
        Value::String("repos/github.com/example/orbit/evidence.md".into())
    );
    assert_eq!(
        json["links"]["self"],
        Value::String("/v0/repos/github.com/example/orbit/index.json".into())
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn public_repository_query_preserves_competing_values() {
    let root = temp_dir("public-query");
    let record_dir = root.join("repos/github.com/example/orbit");
    let alt_dir = record_dir.join("alt");
    fs::create_dir_all(&alt_dir).expect("alt dir created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Selected description"
"#,
    )
    .expect("selected record written");
    fs::write(
        alt_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Competing description"
"#,
    )
    .expect("competing record written");

    let response = public_repository_query(
        &root,
        "github.com",
        "example",
        "orbit",
        "repo.description",
        sample_public_freshness(),
    )
    .expect("public query builds");
    let json = serde_json::to_value(response).expect("query serializes");
    assert_eq!(
        json["selection"]["reason"],
        Value::String("equal_authority_conflict".into())
    );
    assert_eq!(json["value"], Value::String("Competing description".into()));
    assert_eq!(
        json["conflicts"][0]["relationship"],
        Value::String("parallel".into())
    );
    assert_eq!(
        json["conflicts"][0]["value"],
        Value::String("Selected description".into())
    );
    assert_eq!(
        json["links"]["self"],
        Value::String("/v0/repos/github.com/example/orbit/query?path=repo.description".into())
    );
    assert_eq!(
        json["links"]["repository"],
        Value::String("/v0/repos/github.com/example/orbit/index.json".into())
    );
    assert_eq!(
        json["links"]["trust"],
        Value::String("/v0/repos/github.com/example/orbit/trust.json".into())
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn public_repository_query_rejects_dot_segments_in_identity() {
    let response = public_repository_query_or_error(
        Path::new("."),
        "github.com",
        "..",
        "orbit",
        "repo.description",
        sample_public_freshness(),
    )
    .expect_err("invalid identity rejected");

    assert_eq!(
        response.error.code,
        PublicErrorCode::InvalidRepositoryIdentity
    );
    assert_eq!(
        response.error.message,
        "invalid repository identity: owner must be a single path segment"
    );
}

#[test]
fn public_repository_summary_omits_rejected_claim_context() {
    let root = temp_dir("public-rejected-claim");
    let record_dir = root.join("repos/github.com/example/orbit");
    fs::create_dir_all(&record_dir).expect("record dir created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["imported", "verified"]

[repo]
name = "orbit"
description = "Reviewed overlay"
"#,
    )
    .expect("record written");
    fs::write(record_dir.join("evidence.md"), "# Evidence\n").expect("evidence written");
    let claim_dir = record_dir.join("claims/2026-03-10-maintainer-claim-01");
    fs::create_dir_all(claim_dir.join("events")).expect("claim dir created");
    fs::write(
        claim_dir.join("claim.toml"),
        r#"
schema = "dotrepo-claim/v0"

[claim]
id = "github.com/example/orbit/2026-03-10-maintainer-claim-01"
kind = "maintainer_authority"
state = "rejected"
created_at = "2026-03-10T14:30:00Z"
updated_at = "2026-03-10T15:00:00Z"

[identity]
host = "github.com"
owner = "example"
repo = "orbit"

[claimant]
display_name = "Orbit maintainers"
asserted_role = "maintainer"

[target]
record_sources = ["https://github.com/example/orbit"]
"#,
    )
    .expect("claim written");
    fs::write(
        claim_dir.join("events/0001-submitted.toml"),
        r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 1
kind = "submitted"
timestamp = "2026-03-10T14:30:00Z"
actor = "claimant"

[transition]
from = "draft"
to = "submitted"

[summary]
text = "Submitted claim."
"#,
    )
    .expect("submitted event written");
    fs::write(
        claim_dir.join("events/0002-rejected.toml"),
        r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 2
kind = "rejected"
timestamp = "2026-03-10T15:00:00Z"
actor = "index-reviewer"

[transition]
from = "submitted"
to = "rejected"

[summary]
text = "Rejected claim."
"#,
    )
    .expect("rejected event written");

    let response = public_repository_summary(
        &root,
        "github.com",
        "example",
        "orbit",
        sample_public_freshness(),
    )
    .expect("public summary builds");
    let json = serde_json::to_value(response).expect("summary serializes");
    assert_eq!(
        json["selection"]["record"].get("claim"),
        None,
        "rejected claims should stay out of ordinary public repository responses"
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn export_public_index_static_emits_meta_summary_trust_and_query_input_files() {
    let root = temp_dir("public-export");
    let record_dir = root.join("repos/github.com/example/orbit");
    fs::create_dir_all(&record_dir).expect("record dir created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Reviewed overlay"
"#,
    )
    .expect("record written");
    fs::write(record_dir.join("evidence.md"), "# Evidence\n").expect("evidence written");

    let out = root.join("public");
    let outputs =
        export_public_index_static(&root, &out, sample_public_freshness()).expect("export");
    let rendered = outputs
        .iter()
        .map(|(path, contents)| {
            (
                path.strip_prefix(&root).unwrap().display().to_string(),
                contents.clone(),
            )
        })
        .collect::<Vec<_>>();

    assert!(rendered
        .iter()
        .any(|(path, _)| path == "public/v0/meta.json"));
    assert!(rendered
        .iter()
        .any(|(path, _)| path == "public/v0/repos/index.json"));
    assert!(rendered
        .iter()
        .any(|(path, _)| path == "public/v0/files.json"));
    assert!(rendered
        .iter()
        .any(|(path, _)| path == "public/v0/repos/github.com/example/orbit/index.json"));
    assert!(rendered
        .iter()
        .any(|(path, _)| path == "public/v0/repos/github.com/example/orbit/trust.json"));
    assert!(rendered
        .iter()
        .any(|(path, _)| path == "public/v0/repos/github.com/example/orbit/profile.json"));
    assert!(rendered
        .iter()
        .any(|(path, _)| path == "public/v0/repos/github.com/example/orbit/relations.json"));
    assert!(rendered
        .iter()
        .any(|(path, _)| path == "public/query-input/github.com/example/orbit.json"));
    assert!(rendered.iter().any(|(path, contents)| {
        path == "public/v0/repos/index.json"
            && contents.contains("\"repositoryCount\": 1")
            && contents.contains("\"repo\": \"orbit\"")
    }));
    assert!(rendered.iter().any(|(path, contents)| {
        path == "public/v0/meta.json"
            && contents.contains("\"strategy\": \"static_summary_trust_and_profile\"")
    }));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn public_query_input_snapshot_matches_direct_query_semantics() {
    let root = temp_dir("public-query-input");
    let record_dir = root.join("repos/github.com/example/orbit");
    let alt_dir = record_dir.join("alt");
    fs::create_dir_all(&alt_dir).expect("record dirs created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Selected description"
"#,
    )
    .expect("selected record written");
    fs::write(record_dir.join("evidence.md"), "# Evidence\n").expect("evidence written");
    fs::write(
        alt_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Competing description"
"#,
    )
    .expect("competing record written");

    let freshness = sample_public_freshness();
    let snapshot =
        public_query_input_snapshot(&root, "github.com", "example", "orbit", freshness.clone())
            .expect("query input snapshot builds");
    let round_tripped = serde_json::from_str::<PublicQueryInputSnapshot>(
        &serde_json::to_string(&snapshot).expect("snapshot serializes"),
    )
    .expect("snapshot round trips");

    let direct = public_repository_query_with_base(
        &root,
        "github.com",
        "example",
        "orbit",
        "repo.description",
        freshness.clone(),
        "/dotrepo",
    )
    .expect("direct query succeeds");
    let via_snapshot = public_repository_query_from_input_with_base(
        &round_tripped,
        "repo.description",
        freshness,
        "/dotrepo",
    )
    .expect("snapshot query succeeds");

    assert_eq!(
        serde_json::to_value(via_snapshot).expect("snapshot response serializes"),
        serde_json::to_value(direct).expect("direct response serializes")
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

