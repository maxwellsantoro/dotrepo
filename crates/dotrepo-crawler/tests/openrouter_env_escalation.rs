use dotrepo_core::{
    import_repository, run_import_escalation, score_import_fields, verify_import_plan,
    AdjudicationProvider, ImportMode, TieredAdjudicationProviders,
};
use dotrepo_crawler::{
    import_escalation_options_from_env, resolve_adjudication_providers_from_env,
};
use std::path::Path;

#[test]
fn openrouter_env_escalation_smoke() {
    if std::env::var("OPENROUTER_API_KEY")
        .ok()
        .filter(|value| !value.trim().is_empty())
        .is_none()
    {
        eprintln!("skipping openrouter_env_escalation_smoke: OPENROUTER_API_KEY not set");
        return;
    }

    let Ok(fixture_root) = std::env::var("FIXTURE_ROOT") else {
        eprintln!("skipping openrouter_env_escalation_smoke: FIXTURE_ROOT not set");
        return;
    };
    let root = Path::new(&fixture_root);
    let source = "https://github.com/example/conflict";
    let mut plan =
        import_repository(root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let verification = verify_import_plan(root, &plan, source);
    let mut scores = score_import_fields(&plan, &verification);
    assert!(
        !scores.summary.unresolved.is_empty(),
        "fixture should start unresolved"
    );

    let options = import_escalation_options_from_env();
    assert!(
        options.max_adjudication_calls > 0,
        "INDEX_MAX_ADJUDICATION_CALLS must be > 0"
    );

    let resolved = resolve_adjudication_providers_from_env().expect("providers resolve");
    let local_primary = resolved
        .local_primary
        .as_ref()
        .map(|provider| provider as &dyn AdjudicationProvider);
    let local_second_opinion = resolved
        .local_second_opinion
        .as_ref()
        .map(|provider| provider as &dyn AdjudicationProvider);
    let api_escalation = resolved
        .api_escalation
        .as_ref()
        .map(|provider| provider as &dyn AdjudicationProvider);

    let report = run_import_escalation(
        root,
        &mut plan,
        &verification,
        &mut scores,
        &options,
        TieredAdjudicationProviders {
            local_primary,
            local_second_opinion,
            api_escalation,
        },
    );

    eprintln!("escalation report: {report:?}");
    assert!(report.model_calls > 0, "expected model calls");
    assert!(report.tokens_used > 0, "expected token usage");
    assert!(
        scores.summary.unresolved.is_empty(),
        "expected unresolved fields to clear: {:?}",
        scores.summary.unresolved
    );
}
