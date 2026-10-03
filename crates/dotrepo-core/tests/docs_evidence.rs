use dotrepo_core::{
    import_repository, score_import_fields, verify_import_plan, FieldConfidence, ImportMode,
};
use std::path::PathBuf;

#[test]
fn imported_docs_assessments_survive_public_evidence_validation() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures/import/docs-third-party-readme");
    let plan = dotrepo_core::import_repository_with_options(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/astral-sh/uv"),
        &dotrepo_core::ImportOptions {
            generated_at: Some("2026-09-21T00:00:00Z".into()),
            ..Default::default()
        },
    )
    .expect("import");
    let scores = dotrepo_core::score_index_record_for_promotion(&plan.manifest);
    for field in ["docs.root", "docs.getting_started"] {
        let score = scores
            .iter()
            .find(|score| score.field == field)
            .expect("score");
        assert_eq!(score.confidence, FieldConfidence::HighConfidencePresent);
        assert_eq!(score.source.as_deref(), Some("README.md"));
    }
}

#[test]
fn ambiguous_documentation_stays_unresolved_even_with_a_homepage() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures/import/docs-ambiguous-readme");
    let mut plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit"),
    )
    .expect("import");
    plan.manifest.repo.homepage = Some("https://orbit.example".into());
    assert!(!dotrepo_core::infer_docs_root_from_external_homepage(
        &mut plan.manifest
    ));
    let scores = score_import_fields(
        &plan,
        &verify_import_plan(&root, &plan, "https://github.com/example/orbit"),
    );
    let score = scores
        .scores
        .iter()
        .find(|score| score.field == "docs.root")
        .expect("docs score");
    assert_eq!(score.confidence, FieldConfidence::Unresolved);
    assert!(score.value.is_none());
    assert!(plan
        .evidence_text
        .as_ref()
        .expect("evidence")
        .contains("Conflicting documentation declarations"));
}

#[test]
fn documentation_confidence_requires_evidence_for_the_selected_value() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures/import/docs-third-party-readme");
    let mut plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/astral-sh/uv"),
    )
    .expect("import");
    let scores = score_import_fields(
        &plan,
        &verify_import_plan(&root, &plan, "https://github.com/astral-sh/uv"),
    );
    for field in ["docs.root", "docs.getting_started"] {
        let score = scores
            .scores
            .iter()
            .find(|score| score.field == field)
            .expect("score");
        assert_eq!(score.confidence, FieldConfidence::HighConfidencePresent);
        assert_eq!(score.source.as_deref(), Some("README.md"));
        assert!(score.reason.contains("README.md:"));
        let evidence = plan.evidence_text.as_ref().expect("evidence");
        assert!(evidence.lines().any(
            |line| line.contains(field) && line.contains(score.value.as_ref().expect("value"))
        ));
    }
    plan.manifest.docs.as_mut().expect("docs").root = Some("https://trio.readthedocs.io/".into());
    let scores = score_import_fields(
        &plan,
        &verify_import_plan(&root, &plan, "https://github.com/astral-sh/uv"),
    );
    let root_score = scores
        .scores
        .iter()
        .find(|score| score.field == "docs.root")
        .expect("root score");
    assert_eq!(
        root_score.confidence,
        FieldConfidence::MediumConfidencePresent
    );
    assert!(
        root_score.source.is_none(),
        "stale evidence must not ground a replacement URL"
    );
    plan.manifest.x.clear();
    let scores = score_import_fields(
        &plan,
        &verify_import_plan(&root, &plan, "https://github.com/astral-sh/uv"),
    );
    assert!(scores
        .scores
        .iter()
        .filter(|score| score.field.starts_with("docs."))
        .all(|score| score.confidence == FieldConfidence::MediumConfidencePresent));
}
