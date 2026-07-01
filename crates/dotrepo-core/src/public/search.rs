use anyhow::Result;
use std::path::Path;

use super::*;

pub(crate) fn normalize_search_value(value: &str) -> String {
    value.trim().to_ascii_lowercase()
}

fn contains_normalized(values: &[String], expected: &str) -> bool {
    let expected = normalize_search_value(expected);
    values
        .iter()
        .any(|value| normalize_search_value(value) == expected)
}

fn option_matches_filter(actual: Option<&str>, filters: &[String]) -> bool {
    filters.is_empty()
        || actual
            .map(|value| {
                filters
                    .iter()
                    .any(|filter| normalize_search_value(value) == normalize_search_value(filter))
            })
            .unwrap_or(false)
}

fn profile_matches_filters(
    profile: &PublicResearchProfileResponse,
    options: &PublicProfileSearchOptions,
) -> bool {
    if !options
        .languages
        .iter()
        .all(|language| contains_normalized(&profile.languages, language))
    {
        return false;
    }
    if !options
        .topics
        .iter()
        .all(|topic| contains_normalized(&profile.topics, topic))
    {
        return false;
    }
    if !option_matches_filter(Some(&profile.trust.selected_status), &options.statuses) {
        return false;
    }
    if !option_matches_filter(profile.trust.confidence.as_deref(), &options.confidences) {
        return false;
    }
    if options.require_build && !profile.completeness.has_build {
        return false;
    }
    if options.require_test && !profile.completeness.has_test {
        return false;
    }
    if options.require_docs && !profile.completeness.has_docs {
        return false;
    }
    if options.require_security_contact && !profile.completeness.has_security_contact {
        return false;
    }
    if options.require_license && !profile.completeness.has_license {
        return false;
    }
    true
}

fn profile_query_matches(profile: &PublicResearchProfileResponse, query: &str) -> Vec<String> {
    let query = normalize_search_value(query);
    if query.is_empty() {
        return vec!["all".into()];
    }
    let mut matched = Vec::new();
    let text_fields = [
        (
            "identity",
            format!(
                "{}/{}/{}",
                profile.identity.host, profile.identity.owner, profile.identity.repo
            ),
        ),
        ("name", profile.name.clone()),
        ("purpose", profile.purpose.clone()),
        ("homepage", profile.homepage.clone().unwrap_or_default()),
        ("license", profile.license.clone().unwrap_or_default()),
    ];
    for (field, value) in text_fields {
        if normalize_search_value(&value).contains(&query) {
            matched.push(field.to_string());
        }
    }
    if profile
        .languages
        .iter()
        .any(|language| normalize_search_value(language).contains(&query))
    {
        matched.push("languages".into());
    }
    if profile
        .topics
        .iter()
        .any(|topic| normalize_search_value(topic).contains(&query))
    {
        matched.push("topics".into());
    }
    matched
}

fn completeness_signal_count(completeness: &PublicResearchCompleteness) -> usize {
    [
        completeness.has_build,
        completeness.has_test,
        completeness.has_docs,
        completeness.has_security_contact,
        completeness.has_ownership_signal,
        completeness.has_license,
    ]
    .into_iter()
    .filter(|signal| *signal)
    .count()
}

pub(crate) fn search_ranking_from_profile(
    profile: &PublicResearchProfileResponse,
    matched: &[String],
) -> PublicProfileSearchRanking {
    let completeness_signal_count = completeness_signal_count(&profile.completeness);
    let trust_boost = trust_confidence_boost(profile.trust.confidence.as_deref());
    let mut basis = Vec::new();
    if !matched.is_empty() {
        basis.push("matchedFields".into());
    }
    if completeness_signal_count > 0 {
        basis.push("profileCompleteness".into());
    }
    if trust_boost > 0 {
        basis.push("trustConfidence".into());
    }
    PublicProfileSearchRanking {
        score: matched.len() * 10 + completeness_signal_count + trust_boost,
        matched_field_count: matched.len(),
        completeness_signal_count,
        basis,
    }
}

pub(crate) fn trust_confidence_boost(confidence: Option<&str>) -> usize {
    match confidence.map(|c| c.to_ascii_lowercase()) {
        Some(c) if c == "high" => 3,
        Some(c) if c == "medium" => 1,
        _ => 0,
    }
}

pub(crate) fn search_item_from_profile(
    profile: PublicResearchProfileResponse,
    matched: Vec<String>,
) -> PublicProfileSearchItem {
    let ranking = search_ranking_from_profile(&profile, &matched);
    PublicProfileSearchItem {
        identity: profile.identity,
        name: profile.name,
        purpose: profile.purpose,
        languages: profile.languages,
        topics: profile.topics,
        completeness: profile.completeness,
        trust: profile.trust,
        matched,
        ranking,
        links: profile.links,
    }
}

pub fn public_profile_search_with_base(
    index_root: &Path,
    options: PublicProfileSearchOptions,
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicProfileSearchResponse> {
    normalize_public_base_path(base_path)?;
    let identities = list_index_repository_identities(index_root)?;
    let mut results = Vec::new();
    for identity in &identities {
        let candidates = resolve_repository_candidates(
            index_root,
            &identity.host,
            &identity.owner,
            &identity.repo,
        )?;
        let profile = public_repository_profile_with_candidates(
            index_root,
            &identity.host,
            &identity.owner,
            &identity.repo,
            &candidates,
            freshness.clone(),
            base_path,
        )?;
        if !profile_matches_filters(&profile, &options) {
            continue;
        }
        let matched = if let Some(query) = options.query.as_deref() {
            profile_query_matches(&profile, query)
        } else {
            vec!["filters".into()]
        };
        if matched.is_empty() {
            continue;
        }
        results.push(search_item_from_profile(profile, matched));
    }
    results.sort_by(|left, right| {
        right
            .ranking
            .score
            .cmp(&left.ranking.score)
            .then_with(|| {
                right
                    .ranking
                    .matched_field_count
                    .cmp(&left.ranking.matched_field_count)
            })
            .then_with(|| left.identity.host.cmp(&right.identity.host))
            .then_with(|| left.identity.owner.cmp(&right.identity.owner))
            .then_with(|| left.identity.repo.cmp(&right.identity.repo))
    });
    let matched_count = results.len();
    if let Some(limit) = options.limit {
        results.truncate(limit);
    }

    Ok(PublicProfileSearchResponse {
        api_version: PUBLIC_API_VERSION,
        freshness,
        query: options.query.clone(),
        filters: PublicProfileSearchAppliedFilters {
            languages: options.languages.clone(),
            topics: options.topics.clone(),
            statuses: options.statuses.clone(),
            confidences: options.confidences.clone(),
            require_build: options.require_build,
            require_test: options.require_test,
            require_docs: options.require_docs,
            require_security_contact: options.require_security_contact,
            require_license: options.require_license,
            limit: options.limit,
        },
        total_repository_count: identities.len(),
        matched_count,
        returned_count: results.len(),
        results,
    })
}

pub fn public_profile_search(
    index_root: &Path,
    options: PublicProfileSearchOptions,
    freshness: PublicFreshness,
) -> Result<PublicProfileSearchResponse> {
    public_profile_search_with_base(index_root, options, freshness, "/")
}
