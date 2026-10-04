use dotrepo_core::{
    export_public_index_static, public_repository_profile, query_manifest_value,
    validate_manifest_diagnostics, PublicFreshness,
};
use dotrepo_schema::{parse_manifest, ExecutionScope, Manifest, RecordMode};
use serde_json::json;
use std::fs;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};

const FIXTURE: &str = include_str!("fixtures/execution-context/.repo");

fn fixture_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/execution-context")
}

fn manifest() -> Manifest {
    parse_manifest(FIXTURE).unwrap()
}

fn errors(manifest: &Manifest) -> Vec<String> {
    validate_manifest_diagnostics(&fixture_root(), manifest)
        .into_iter()
        .map(|diagnostic| diagnostic.message)
        .collect()
}

#[test]
fn explicit_context_round_trips_and_is_queryable_without_creating_a_scalar() {
    let manifest = manifest();
    assert!(errors(&manifest).is_empty());
    assert!(manifest.repo.test.is_none());
    assert_eq!(
        query_manifest_value(&manifest, "repo.build_context.working_directory").unwrap(),
        json!(".")
    );
    let encoded = toml::to_string(&manifest).unwrap();
    let round_trip = parse_manifest(&encoded).unwrap();
    assert_eq!(manifest.repo.build_context, round_trip.repo.build_context);
    assert_eq!(
        manifest.repo.test_candidates,
        round_trip.repo.test_candidates
    );
}

#[test]
fn context_requires_explicit_scope_directory_and_prerequisites() {
    for line in [
        "scope = \"repository\"\n",
        "working_directory = \".\"\n",
        "prerequisites = [\"Install the Rust toolchain\"]\n",
        "source = \"README.md\"\n",
    ] {
        assert!(
            parse_manifest(&FIXTURE.replacen(line, "", 1)).is_err(),
            "{line}"
        );
    }
    assert!(
        parse_manifest(&FIXTURE.replacen("scope = \"repository\"", "scope = \"unknown\"", 1))
            .is_err()
    );
    assert!(parse_manifest(&FIXTURE.replacen(
        "scope = \"repository\"",
        "scope = \"repository\"\nworkng_directory = \".\"",
        1
    ))
    .is_err());
}

#[test]
fn changing_or_removing_a_command_invalidates_retained_context() {
    let mut manifest = manifest();
    manifest.repo.build = Some("cargo build --release".into());
    assert!(errors(&manifest)
        .iter()
        .any(|error| error.contains("exactly match")));
    manifest.repo.build = None;
    assert!(errors(&manifest)
        .iter()
        .any(|error| error.contains("exactly match")));
    manifest.repo.build_context = None;
    manifest.repo.test_candidates[0].command = "npm run test:unit".into();
    assert!(errors(&manifest)
        .iter()
        .any(|error| error.contains("exactly match")));
}

#[test]
fn context_binding_cannot_change_when_public_scalars_are_trimmed() {
    let mut manifest = manifest();
    manifest.repo.build = Some(" cargo build --workspace ".into());
    manifest.repo.build_context.as_mut().unwrap().command = " cargo build --workspace ".into();
    assert!(errors(&manifest)
        .iter()
        .any(|error| error.contains("public value binding")));
}

#[test]
fn scalar_context_cannot_relabel_component_commands_as_repository_defaults() {
    let mut manifest = manifest();
    manifest.repo.test = Some("npm test".into());
    manifest.repo.test_context = manifest.repo.test_candidates[0].context.clone();
    assert!(errors(&manifest)
        .iter()
        .any(|error| error.contains("scalar commands")));
}

#[test]
fn component_scope_requires_a_component_and_repository_scope_forbids_one() {
    let mut manifest = manifest();
    let context = manifest.repo.test_candidates[0].context.as_mut().unwrap();
    context.component = None;
    assert!(errors(&manifest)
        .iter()
        .any(|error| error.contains("requires component")));
    let context = manifest.repo.test_candidates[0].context.as_mut().unwrap();
    context.scope = ExecutionScope::Repository;
    context.component = Some("packages/ui".into());
    assert!(errors(&manifest)
        .iter()
        .any(|error| error.contains("must omit component")));
}

#[test]
fn paths_are_portable_normalized_and_contained_even_for_overlays() {
    for path in [
        "",
        "../ui",
        "/ui",
        "C:/ui",
        "packages\\ui",
        "a//b",
        "a/../b",
        "a/./b",
        "ui/",
        " ui",
        "ui\n",
    ] {
        let mut manifest = manifest();
        manifest.record.mode = RecordMode::Overlay;
        let context = manifest.repo.test_candidates[0].context.as_mut().unwrap();
        context.working_directory = path.into();
        context.source = path.into();
        context.component = Some(path.into());
        assert!(
            errors(&manifest)
                .iter()
                .filter(|error| error.contains("relative path"))
                .count()
                >= 3,
            "{path:?}"
        );
    }
    let mut manifest = manifest();
    let context = manifest.repo.test_candidates[0].context.as_mut().unwrap();
    context.working_directory = "missing-upstream-component".into();
    assert!(errors(&manifest)
        .iter()
        .any(|error| error.contains("contained directory")));
    manifest.record.mode = RecordMode::Overlay;
    assert!(
        errors(&manifest).is_empty(),
        "overlay paths must not resolve against the index"
    );
}

#[test]
fn prerequisites_are_explicit_descriptions_and_empty_list_is_preserved() {
    let mut manifest = manifest();
    manifest.repo.build_context.as_mut().unwrap().prerequisites = vec!["".into()];
    assert!(errors(&manifest)
        .iter()
        .any(|error| error.contains("prerequisites")));
    manifest.repo.build_context.as_mut().unwrap().prerequisites = vec!["setup\nrun".into()];
    assert!(errors(&manifest)
        .iter()
        .any(|error| error.contains("prerequisites")));
    manifest
        .repo
        .build_context
        .as_mut()
        .unwrap()
        .prerequisites
        .clear();
    assert!(errors(&manifest).is_empty());
    assert_eq!(
        query_manifest_value(&manifest, "repo.build_context.prerequisites").unwrap(),
        json!([])
    );
}

struct Scratch(PathBuf);

impl Scratch {
    fn new() -> Self {
        static COUNTER: AtomicU64 = AtomicU64::new(0);
        let path = std::env::temp_dir().join(format!(
            "dotrepo-execution-{}-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos(),
            COUNTER.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir_all(&path).unwrap();
        Self(path)
    }
}

impl Drop for Scratch {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

#[test]
fn public_profile_and_static_export_preserve_context_with_camel_case_keys() {
    let scratch = Scratch::new();
    let record = scratch.0.join("index/repos/github.com/example/context");
    fs::create_dir_all(&record).unwrap();
    let mut manifest = manifest();
    manifest.record.mode = RecordMode::Overlay;
    fs::write(
        record.join("record.toml"),
        toml::to_string(&manifest).unwrap(),
    )
    .unwrap();
    fs::write(
        record.join("evidence.md"),
        "# Evidence\nExplicit fixture context.\n",
    )
    .unwrap();
    let freshness = PublicFreshness {
        generated_at: "2026-10-04T00:00:00Z".into(),
        snapshot_digest: "fixture".into(),
        stale_after: None,
    };
    let index = scratch.0.join("index");
    let profile = serde_json::to_value(
        public_repository_profile(
            &index,
            "github.com",
            "example",
            "context",
            freshness.clone(),
        )
        .unwrap(),
    )
    .unwrap();
    let context = &profile["execution"]["testCandidates"][0]["context"];
    assert_eq!(context["workingDirectory"], "packages/ui");
    assert_eq!(context["component"], "packages/ui");
    assert_eq!(context["scope"], "component");
    assert_eq!(
        context["prerequisites"],
        json!(["Install Node.js and run npm ci in packages/ui"])
    );
    assert!(profile["execution"].get("test").is_none());
    assert_eq!(
        profile["execution"]["buildContext"]["command"],
        "cargo build --workspace"
    );
    let output = scratch.0.join("public");
    let outputs = export_public_index_static(&index, &output, freshness).unwrap();
    let (_, payload) = outputs
        .iter()
        .find(|(path, _)| path == &output.join("v0/repos/github.com/example/context/profile.json"))
        .unwrap();
    let exported: serde_json::Value = serde_json::from_str(payload).unwrap();
    assert_eq!(exported["execution"], profile["execution"]);
    let compatibility: serde_json::Value =
        serde_json::from_str(include_str!("fixtures/public-contract/compatibility.json")).unwrap();
    for context in [&profile["execution"]["buildContext"], context] {
        for key in compatibility["executionContext"]["requiredKeys"]
            .as_array()
            .unwrap()
        {
            assert!(context.get(key.as_str().unwrap()).is_some());
        }
        assert!(compatibility["executionContext"]["scopeValues"]
            .as_array()
            .unwrap()
            .contains(&context["scope"]));
        let supported = compatibility["executionContext"]["requiredKeys"]
            .as_array()
            .unwrap()
            .iter()
            .chain(
                compatibility["executionContext"]["optionalKeys"]
                    .as_array()
                    .unwrap(),
            );
        let keys: Vec<_> = supported.map(|key| key.as_str().unwrap()).collect();
        assert!(context
            .as_object()
            .unwrap()
            .keys()
            .all(|key| keys.contains(&key.as_str())));
    }
    let optional = compatibility["profile"]["executionOptionalKeys"]
        .as_array()
        .unwrap();
    assert!(profile["execution"]
        .as_object()
        .unwrap()
        .keys()
        .all(|key| optional.contains(&json!(key))));
}

#[test]
fn legacy_commands_do_not_gain_invented_context() {
    let mut manifest = manifest();
    manifest.repo.build_context = None;
    manifest.repo.test_candidates[0].context = None;
    assert!(errors(&manifest).is_empty());
    let json = serde_json::to_value(manifest).unwrap();
    assert!(json["repo"].get("build_context").is_none());
    assert!(json["repo"]["test_candidates"][0].get("context").is_none());
}

#[cfg(unix)]
#[test]
fn native_context_rejects_symlink_escape() {
    let scratch = Scratch::new();
    let root = scratch.0.join("root");
    let outside = scratch.0.join("outside");
    fs::create_dir_all(&root).unwrap();
    fs::create_dir_all(&outside).unwrap();
    fs::write(root.join("README.md"), "evidence").unwrap();
    std::os::unix::fs::symlink(&outside, root.join("packages")).unwrap();
    let mut manifest = manifest();
    manifest.repo.test_candidates.clear();
    manifest.repo.build_context.as_mut().unwrap().source = "packages/source.md".into();
    fs::write(outside.join("source.md"), "outside").unwrap();
    let diagnostics = validate_manifest_diagnostics(&root, &manifest);
    assert!(diagnostics
        .iter()
        .any(|error| error.message.contains("contained file")));
}
