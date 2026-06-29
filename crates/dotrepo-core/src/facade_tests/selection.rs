use super::common::*;

#[test]
fn query_manifest_walks_dynamic_paths() {
    let manifest = parse_manifest(
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[record.trust]
confidence = "high"
provenance = ["declared", "verified"]

[repo]
name = "orbit"
description = "Fast local-first sync engine"
languages = ["rust"]

[x.example]
internal_id = "orbit-prod"
"#,
    )
    .expect("manifest parses");

    assert_eq!(
        query_manifest(&manifest, "x.example.internal_id").expect("query succeeds"),
        "\"orbit-prod\""
    );
    assert_eq!(
        query_manifest(&manifest, "trust.provenance").expect("legacy trust alias works"),
        "[\n  \"declared\",\n  \"verified\"\n]"
    );
    assert_eq!(
        query_manifest_value(&manifest, "repo.name").expect("value query succeeds"),
        Value::String("orbit".into())
    );
}

#[test]
fn query_repository_serializes_selection_and_conflicts() {
    let root = temp_dir("query-report");
    fs::write(
        root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[record.trust]
confidence = "high"
provenance = ["declared"]

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
    )
    .expect("manifest written");

    let report = query_repository(&root, "repo.name").expect("query report");
    let json = serde_json::to_value(report).expect("report serializes");
    assert_eq!(
        json["selection"]["reason"],
        Value::String("only_matching_record".into())
    );
    assert_eq!(
        json["selection"]["record"]["record"]["status"],
        Value::String("canonical".into())
    );
    assert_eq!(json["conflicts"], Value::Array(Vec::new()));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn trust_repository_serializes_selection_and_conflicts() {
    let root = temp_dir("trust-report");
    fs::write(
        root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://example.com/orbit"

[record.trust]
confidence = "medium"
provenance = ["imported", "verified"]

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
    )
    .expect("manifest written");

    let report = trust_repository(&root).expect("trust report");
    let json = serde_json::to_value(report).expect("report serializes");
    assert_eq!(
        json["selection"]["reason"],
        Value::String("only_matching_record".into())
    );
    assert_eq!(
        json["selection"]["record"]["record"]["mode"],
        Value::String("overlay".into())
    );
    assert_eq!(json["conflicts"], Value::Array(Vec::new()));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn query_repository_prefers_canonical_over_matching_overlay() {
    let root = temp_dir("query-canonical-preferred");
    fs::write(
        root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[record.trust]
confidence = "high"
provenance = ["declared"]

[repo]
name = "orbit"
description = "Fast local-first sync engine"
homepage = "https://github.com/example/orbit"
build = "cargo build --workspace"
"#,
    )
    .expect("canonical manifest written");
    let overlay_dir = root.join("repos/github.com/example/orbit");
    fs::create_dir_all(&overlay_dir).expect("overlay dir created");
    let claim_dir = overlay_dir.join("claims/2026-03-10-maintainer-claim-01");
    fs::create_dir_all(claim_dir.join("events")).expect("claim dir created");
    fs::write(
        overlay_dir.join("record.toml"),
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
description = "Curated overlay"
build = "cargo test"
"#,
    )
    .expect("overlay manifest written");
    fs::write(
        claim_dir.join("claim.toml"),
        r#"
schema = "dotrepo-claim/v0"

[claim]
id = "github.com/example/orbit/2026-03-10-maintainer-claim-01"
kind = "maintainer_authority"
state = "accepted"
created_at = "2026-03-10T14:30:00Z"
updated_at = "2026-03-12T09:15:00Z"

[identity]
host = "github.com"
owner = "example"
repo = "orbit"

[claimant]
display_name = "Orbit maintainers"
asserted_role = "maintainer"

[target]
index_paths = ["repos/github.com/example/orbit/record.toml"]
record_sources = ["https://github.com/example/orbit"]
canonical_repo_url = "https://github.com/example/orbit"

[resolution]
canonical_record_path = ".repo"
canonical_mirror_path = "repos/github.com/example/orbit/record.toml"
result_event = "events/0002-accepted.toml"
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
        claim_dir.join("events/0002-accepted.toml"),
        r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 2
kind = "accepted"
timestamp = "2026-03-12T09:15:00Z"
actor = "index-reviewer"

[transition]
from = "submitted"
to = "accepted"

[summary]
text = "Accepted claim."
"#,
    )
    .expect("accepted event written");

    let report = query_repository(&root, "repo.build").expect("query report");
    let json = serde_json::to_value(report).expect("query report serializes");
    assert_eq!(
        json["selection"]["reason"],
        Value::String("canonical_preferred".into())
    );
    assert_eq!(
        json["value"],
        Value::String("cargo build --workspace".into())
    );
    assert_eq!(
        json["conflicts"][0]["relationship"],
        Value::String("superseded".into())
    );
    assert_eq!(
        json["conflicts"][0]["reason"],
        Value::String("canonical_preferred".into())
    );
    assert_eq!(
        json["conflicts"][0]["value"],
        Value::String("cargo test".into())
    );
    assert_eq!(
        json["conflicts"][0]["record"]["claim"]["state"],
        Value::String("accepted".into())
    );
    assert_eq!(
        json["conflicts"][0]["record"]["claim"]["handoff"],
        Value::String("superseded".into())
    );

    let trust = trust_repository(&root).expect("trust report");
    let trust_json = serde_json::to_value(trust).expect("trust report serializes");
    assert_eq!(
        trust_json["selection"]["reason"],
        Value::String("canonical_preferred".into())
    );
    assert_eq!(
        trust_json["conflicts"][0]["relationship"],
        Value::String("superseded".into())
    );
    assert_eq!(trust_json["conflicts"][0].get("value"), None);
    assert_eq!(
        trust_json["conflicts"][0]["record"]["claim"]["id"],
        Value::String("github.com/example/orbit/2026-03-10-maintainer-claim-01".into())
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn query_repository_prefers_higher_status_overlay() {
    let root = temp_dir("query-higher-status-overlay");
    let imported_dir = root.join("imported");
    let reviewed_dir = root.join("reviewed");
    fs::create_dir_all(&imported_dir).expect("imported dir created");
    fs::create_dir_all(&reviewed_dir).expect("reviewed dir created");
    fs::write(
        imported_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "low"
provenance = ["imported"]

[repo]
name = "orbit"
description = "Imported overlay"
build = "cargo build"
"#,
    )
    .expect("imported overlay written");
    fs::write(
        reviewed_dir.join("record.toml"),
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
build = "cargo build --locked"
"#,
    )
    .expect("reviewed overlay written");

    let report = query_repository(&root, "repo.build").expect("query report");
    let json = serde_json::to_value(report).expect("query report serializes");
    assert_eq!(
        json["selection"]["reason"],
        Value::String("higher_status_overlay".into())
    );
    assert_eq!(json["value"], Value::String("cargo build --locked".into()));
    assert_eq!(
        json["conflicts"][0]["relationship"],
        Value::String("superseded".into())
    );
    assert_eq!(
        json["conflicts"][0]["reason"],
        Value::String("higher_status_overlay".into())
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn query_repository_surfaces_equal_authority_overlay_conflicts() {
    let root = temp_dir("query-equal-authority-overlay");
    let first_dir = root.join("a");
    let second_dir = root.join("b");
    fs::create_dir_all(&first_dir).expect("first dir created");
    fs::create_dir_all(&second_dir).expect("second dir created");
    fs::write(
        first_dir.join("record.toml"),
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
description = "First reviewed overlay"
build = "cargo build"
"#,
    )
    .expect("first overlay written");
    fs::write(
        second_dir.join("record.toml"),
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
description = "Second reviewed overlay"
build = "cargo test"
"#,
    )
    .expect("second overlay written");

    let report = query_repository(&root, "repo.build").expect("query report");
    let json = serde_json::to_value(report).expect("query report serializes");
    assert_eq!(
        json["selection"]["reason"],
        Value::String("equal_authority_conflict".into())
    );
    assert_eq!(
        json["selection"]["record"]["manifestPath"],
        Value::String("a/record.toml".into())
    );
    assert_eq!(
        json["conflicts"][0]["relationship"],
        Value::String("parallel".into())
    );
    assert_eq!(
        json["conflicts"][0]["reason"],
        Value::String("equal_authority_conflict".into())
    );
    assert_eq!(
        json["conflicts"][0]["value"],
        Value::String("cargo test".into())
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn trust_repository_omits_rejected_claim_context_from_normal_visibility() {
    let root = temp_dir("query-rejected-claim");
    fs::write(
        root.join("record.toml"),
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
    let claim_dir = root.join("claims/2026-03-10-maintainer-claim-01");
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

    let report = trust_repository(&root).expect("trust report");
    let json = serde_json::to_value(report).expect("trust report serializes");
    assert_eq!(
        json["selection"]["record"].get("claim"),
        None,
        "rejected claims should stay in dedicated claim inspection, not normal trust visibility"
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}
