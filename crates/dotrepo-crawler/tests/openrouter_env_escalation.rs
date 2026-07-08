use dotrepo_core::{
    import_repository, run_import_escalation, score_import_fields, verify_import_plan,
    AdjudicationModelConfidence, AdjudicationModelResponse, AdjudicationProvider,
    AdjudicationProviderResponse, AdjudicationTier, ImportEscalationOptions, ImportMode,
    StubAdjudicationProvider, TieredAdjudicationProviders,
};
use dotrepo_crawler::{
    import_escalation_options_from_env, resolve_adjudication_providers_from_env,
};
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

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

/// Milestone 1 second-opinion live canary.
///
/// Real public repositories almost never produce a low-confidence primary
/// response (they either resolve deterministically or abstain confidently).
/// This canary forces the primary tier to a low-confidence `Absent`, then
/// requires a live HTTP second-opinion provider from the environment to
/// continue the ladder — the missing proof gap from ROADMAP M1.
///
/// Skip when `DOTREPO_ADJUDICATION_SECOND_OPINION_URL` is unset. Requires the
/// OpenRouter sidecar (or equivalent) already listening at that URL.
#[test]
fn second_opinion_live_ladder_from_low_confidence_primary() {
    let second_opinion_url = match std::env::var("DOTREPO_ADJUDICATION_SECOND_OPINION_URL") {
        Ok(value) if !value.trim().is_empty() => value,
        _ => {
            eprintln!(
                "skipping second_opinion_live_ladder_from_low_confidence_primary: \
                 DOTREPO_ADJUDICATION_SECOND_OPINION_URL not set"
            );
            return;
        }
    };
    let _ = second_opinion_url;

    let root = conflict_fixture_dir("second-opinion-live");
    let source = "https://github.com/example/second-opinion-live";
    let mut plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let verification = verify_import_plan(&root, &plan, source);
    let mut scores = score_import_fields(&plan, &verification);
    assert!(
        !scores.summary.unresolved.is_empty(),
        "conflict fixture should start unresolved: {:?}",
        scores.summary.unresolved
    );

    let primary = StubAdjudicationProvider::new(
        AdjudicationTier::LocalPrimary,
        vec![AdjudicationProviderResponse {
            response: AdjudicationModelResponse {
                field: "repo.build".into(),
                value: None,
                confidence: AdjudicationModelConfidence::Low,
                reason: "Canary: forced low-confidence primary abstention".into(),
                source: None,
            },
            tokens_used: 50,
        }],
    );

    let resolved = resolve_adjudication_providers_from_env().expect("providers resolve");
    let second = resolved
        .local_second_opinion
        .as_ref()
        .expect("second-opinion URL set implies provider resolves");
    let api = resolved
        .api_escalation
        .as_ref()
        .map(|provider| provider as &dyn AdjudicationProvider);

    let report = run_import_escalation(
        &root,
        &mut plan,
        &verification,
        &mut scores,
        &ImportEscalationOptions {
            max_adjudication_calls: 4,
            enable_second_opinion: true,
            enable_api_escalation: api.is_some(),
        },
        TieredAdjudicationProviders {
            local_primary: Some(&primary),
            local_second_opinion: Some(second as &dyn AdjudicationProvider),
            api_escalation: api,
        },
    );

    eprintln!("second-opinion live canary report: {report:?}");
    assert!(
        report.model_calls >= 2,
        "expected primary + higher tier calls, got {}",
        report.model_calls
    );
    assert!(
        report
            .adjudication_tiers_used
            .contains(&AdjudicationTier::LocalSecondOpinion)
            || report
                .adjudication_tiers_used
                .contains(&AdjudicationTier::ApiEscalation),
        "expected second-opinion or API tier after low-confidence primary: {:?}",
        report.adjudication_tiers_used
    );
    assert!(report.tokens_used > 50, "expected live provider tokens");

    let _ = fs::remove_dir_all(&root);
}

fn conflict_fixture_dir(label: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("time")
        .as_nanos();
    let root = std::env::temp_dir().join(format!("dotrepo-{label}-{nanos}"));
    fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir");
    fs::write(
        root.join("README.md"),
        "# Conflict canary\n\nTwo same-tier build workflows.\n",
    )
    .expect("readme");
    fs::write(
        root.join(".github/workflows/check.yml"),
        "name: Check\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build --workspace\n",
    )
    .expect("check");
    fs::write(
        root.join(".github/workflows/verify.yml"),
        "name: Verify\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build\n",
    )
    .expect("verify");
    root
}
