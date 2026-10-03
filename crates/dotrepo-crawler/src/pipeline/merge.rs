//! GitHub snapshot merge into import manifests and identity-safe homepage handling.

use crate::{CrawlDiagnostic, GitHubRepositorySnapshot, RepositoryRef};
use dotrepo_core::{infer_docs_root_from_external_homepage, repository_identity};
use dotrepo_schema::Manifest;
use toml::Value;

// Must match dotrepo_core::validation's code-host list used by the
// repo.homepage identity check in validate_manifest().
const CODE_HOSTS: &[&str] = &["github.com", "gitlab.com", "bitbucket.org"];

pub(crate) fn merge_snapshot_fields(
    repository: &RepositoryRef,
    source_url: &str,
    manifest: &mut Manifest,
    snapshot: &GitHubRepositorySnapshot,
) -> Vec<CrawlDiagnostic> {
    let mut diagnostics = Vec::new();
    let mut merged_fields = Vec::new();

    if manifest.repo.name.trim().is_empty() {
        manifest.repo.name = repository.repo.clone();
        merged_fields.push("repo.name");
    }

    if let Some(description) = trimmed_non_empty(snapshot.description.as_deref()) {
        if trimmed_non_empty(Some(manifest.repo.description.as_str())) != Some(description) {
            manifest.repo.description = description.to_string();
            merged_fields.push("repo.description");
        }
    }

    let current_homepage = trimmed_non_empty(manifest.repo.homepage.as_deref());
    let should_replace_homepage =
        current_homepage.is_none() || current_homepage == Some(source_url.trim());
    if should_replace_homepage {
        if let Some(homepage) = trimmed_non_empty(snapshot.homepage.as_deref()) {
            // GitHub's repository "Website" field is maintainer-set free text
            // and occasionally points at a different repository entirely
            // (e.g. a renamed/duplicated project left pointing at its
            // original). validate_manifest() rejects a repo.homepage that
            // resolves to a different code-host identity than the record
            // itself, so merging such a value here would write an overlay
            // that immediately fails validate-index. Skip the merge (keep
            // the existing, self-consistent value) rather than write an
            // inconsistent record.
            let conflicts_with_identity = homepage_conflicts_with_identity(repository, homepage);
            if conflicts_with_identity {
                diagnostics.push(CrawlDiagnostic::warning(
                    "pipeline.homepage_identity_conflict",
                    format!(
                        "skipped GitHub-reported homepage {homepage:?}: resolves to a different repository identity than github.com/{}/{}",
                        repository.owner, repository.repo
                    ),
                ));
            } else {
                manifest.repo.homepage = Some(homepage.to_string());
                merged_fields.push("repo.homepage");
            }
        }
    }

    if let Some(license) = trimmed_non_empty(snapshot.license.as_deref()) {
        manifest.repo.license = Some(license.to_string());
        merged_fields.push("repo.license");
    }

    if let Some(visibility) = trimmed_non_empty(snapshot.visibility.as_deref()) {
        manifest.repo.visibility = Some(visibility.to_string());
        merged_fields.push("repo.visibility");
    }

    let languages = normalized_list(&snapshot.languages);
    if !languages.is_empty() {
        manifest.repo.languages = languages;
        merged_fields.push("repo.languages");
    }

    let topics = normalized_list(&snapshot.topics);
    if !topics.is_empty() {
        manifest.repo.topics = topics;
        merged_fields.push("repo.topics");
    }

    if infer_docs_root_from_external_homepage(manifest) {
        merged_fields.push("docs.root");
    }

    manifest
        .x
        .insert("github".into(), github_extension(snapshot, source_url));
    diagnostics.push(CrawlDiagnostic::info(
        "pipeline.github_extension",
        "recorded GitHub crawler metadata under x.github",
    ));

    if !merged_fields.is_empty() {
        diagnostics.push(CrawlDiagnostic::info(
            "pipeline.github_merge",
            format!(
                "augmented {} from GitHub repository metadata",
                merged_fields.join(", ")
            ),
        ));
    }

    diagnostics
}

pub(crate) fn append_github_evidence(
    evidence_text: Option<String>,
    manifest: &Manifest,
    snapshot: &GitHubRepositorySnapshot,
) -> Option<String> {
    let mut evidence = evidence_text?;
    let mut bullets = Vec::new();
    let description_constrained = trimmed_non_empty(Some(manifest.repo.description.as_str()))
        == trimmed_non_empty(snapshot.description.as_deref());

    let homepage = trimmed_non_empty(manifest.repo.homepage.as_deref());
    if homepage.is_some() && homepage == trimmed_non_empty(snapshot.homepage.as_deref()) {
        bullets.push("Augmented repo.homepage from GitHub repository metadata.".to_string());
    }
    if manifest.repo.license.as_deref() == trimmed_non_empty(snapshot.license.as_deref()) {
        bullets.push("Augmented repo.license from GitHub repository metadata.".to_string());
    }
    if manifest.repo.visibility.as_deref() == trimmed_non_empty(snapshot.visibility.as_deref()) {
        bullets.push("Augmented repo.visibility from GitHub repository metadata.".to_string());
    }
    if !manifest.repo.languages.is_empty()
        && manifest.repo.languages == normalized_list(&snapshot.languages)
    {
        bullets.push("Augmented repo.languages from GitHub repository metadata.".to_string());
    }
    if !manifest.repo.topics.is_empty() && manifest.repo.topics == normalized_list(&snapshot.topics)
    {
        bullets.push("Augmented repo.topics from GitHub repository metadata.".to_string());
    }
    if description_constrained {
        evidence = remove_readme_description_claim(evidence);
        bullets.push("Constrained repo.description with GitHub repository metadata.".to_string());
    }
    bullets.push(
        "Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state)."
            .to_string(),
    );

    if !evidence.ends_with('\n') {
        evidence.push('\n');
    }
    for bullet in bullets {
        evidence.push_str("- ");
        evidence.push_str(&bullet);
        evidence.push('\n');
    }
    Some(evidence)
}

pub(crate) fn remove_readme_description_claim(mut evidence: String) -> String {
    for readme_path in ["README.md", "README.mdx"] {
        evidence = evidence.replace(
            &format!(
                "- Imported repository name, description, and docs entry points from {readme_path}.\n"
            ),
            &format!("- Imported repository name and docs entry points from {readme_path}.\n"),
        );
        evidence = evidence.replace(
            &format!(
                "- Imported repository description and docs entry points from {readme_path}.\n"
            ),
            &format!("- Imported repository docs entry points from {readme_path}.\n"),
        );
        evidence = evidence.replace(
            &format!("- Imported repository name and description from {readme_path}.\n"),
            &format!("- Imported repository name from {readme_path}.\n"),
        );
        evidence = evidence.replace(
            &format!("- Imported repository description from {readme_path}.\n"),
            "",
        );
    }
    evidence
}

pub(crate) fn github_extension(snapshot: &GitHubRepositorySnapshot, source_url: &str) -> Value {
    let mut github = toml::map::Map::new();
    github.insert("html_url".into(), Value::String(source_url.to_string()));
    github.insert(
        "clone_url".into(),
        Value::String(snapshot.clone_url.clone()),
    );
    github.insert(
        "default_branch".into(),
        Value::String(snapshot.default_branch.clone()),
    );
    github.insert("archived".into(), Value::Boolean(snapshot.archived));
    github.insert("fork".into(), Value::Boolean(snapshot.fork));
    if let Some(head_sha) = trimmed_non_empty(snapshot.head_sha.as_deref()) {
        github.insert("head_sha".into(), Value::String(head_sha.to_string()));
    }
    if let Some(stars) = snapshot.stars {
        github.insert("stars".into(), Value::Integer(stars as i64));
    }
    Value::Table(github)
}

pub(crate) fn manifest_is_missing_description(manifest: &Manifest) -> bool {
    let description = manifest.repo.description.trim();
    description.is_empty()
        || description == "Imported repository metadata; review and refine before relying on it."
}

pub(crate) fn normalized_list(values: &[String]) -> Vec<String> {
    let mut normalized = Vec::new();
    for value in values {
        if let Some(value) = trimmed_non_empty(Some(value.as_str())) {
            if !normalized.iter().any(|existing| existing == value) {
                normalized.push(value.to_string());
            }
        }
    }
    normalized
}

pub(crate) fn trimmed_non_empty(value: Option<&str>) -> Option<&str> {
    value.map(str::trim).filter(|value| !value.is_empty())
}

pub(crate) fn homepage_conflicts_with_identity(repository: &RepositoryRef, homepage: &str) -> bool {
    repository_identity(homepage).is_some_and(|(host, owner, repo)| {
        CODE_HOSTS.contains(&host.as_str())
            && (host != repository.host || owner != repository.owner || repo != repository.repo)
    })
}
