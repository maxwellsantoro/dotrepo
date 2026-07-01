use anyhow::{bail, Result};
use std::collections::BTreeSet;
use std::path::Path;

use super::*;

fn compare_item_from_profile(profile: PublicResearchProfileResponse) -> PublicProfileCompareItem {
    PublicProfileCompareItem {
        identity: profile.identity,
        name: profile.name,
        purpose: profile.purpose,
        homepage: profile.homepage,
        license: profile.license,
        languages: profile.languages,
        topics: profile.topics,
        execution: profile.execution,
        docs: profile.docs,
        ownership: profile.ownership,
        completeness: profile.completeness,
        trust: profile.trust,
        links: profile.links,
    }
}

fn shared_profile_values<F>(items: &[PublicProfileCompareItem], select: F) -> Vec<String>
where
    F: Fn(&PublicProfileCompareItem) -> &[String],
{
    let Some((first, rest)) = items.split_first() else {
        return Vec::new();
    };
    let mut shared = select(first)
        .iter()
        .map(|value| normalize_search_value(value))
        .collect::<BTreeSet<_>>();
    for item in rest {
        let values = select(item)
            .iter()
            .map(|value| normalize_search_value(value))
            .collect::<BTreeSet<_>>();
        shared = shared
            .intersection(&values)
            .cloned()
            .collect::<BTreeSet<_>>();
    }
    select(first)
        .iter()
        .filter(|value| shared.contains(&normalize_search_value(value)))
        .cloned()
        .collect()
}

fn compare_text_values<F>(
    items: &[PublicProfileCompareItem],
    select: F,
) -> Vec<PublicProfileCompareTextValue>
where
    F: Fn(&PublicProfileCompareItem) -> Option<String>,
{
    items
        .iter()
        .map(|item| PublicProfileCompareTextValue {
            identity: item.identity.clone(),
            value: select(item),
        })
        .collect()
}

fn compare_bool_values<F>(
    items: &[PublicProfileCompareItem],
    select: F,
) -> Vec<PublicProfileCompareBoolValue>
where
    F: Fn(&PublicProfileCompareItem) -> bool,
{
    items
        .iter()
        .map(|item| PublicProfileCompareBoolValue {
            identity: item.identity.clone(),
            value: select(item),
        })
        .collect()
}

fn compare_signals(items: &[PublicProfileCompareItem]) -> PublicProfileCompareSignals {
    PublicProfileCompareSignals {
        shared_languages: shared_profile_values(items, |item| &item.languages),
        shared_topics: shared_profile_values(items, |item| &item.topics),
        licenses: compare_text_values(items, |item| item.license.clone()),
        selected_statuses: compare_text_values(items, |item| {
            Some(item.trust.selected_status.clone())
        }),
        confidences: compare_text_values(items, |item| item.trust.confidence.clone()),
        has_build: compare_bool_values(items, |item| item.completeness.has_build),
        has_test: compare_bool_values(items, |item| item.completeness.has_test),
        has_docs: compare_bool_values(items, |item| item.completeness.has_docs),
        has_security_contact: compare_bool_values(items, |item| {
            item.completeness.has_security_contact
        }),
        has_license: compare_bool_values(items, |item| item.completeness.has_license),
    }
}

pub fn public_profile_compare_with_base(
    index_root: &Path,
    identities: &[PublicRepositoryIdentity],
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicProfileCompareResponse> {
    normalize_public_base_path(base_path)?;
    if identities.is_empty() {
        bail!("compare requires at least one repository");
    }
    let mut results = Vec::new();
    for identity in identities {
        let profile = public_repository_profile_with_base(
            index_root,
            &identity.host,
            &identity.owner,
            &identity.repo,
            freshness.clone(),
            base_path,
        )?;
        results.push(compare_item_from_profile(profile));
    }
    let signals = compare_signals(&results);
    Ok(PublicProfileCompareResponse {
        api_version: PUBLIC_API_VERSION,
        freshness,
        repository_count: results.len(),
        results,
        signals,
    })
}

pub fn public_profile_compare(
    index_root: &Path,
    identities: &[PublicRepositoryIdentity],
    freshness: PublicFreshness,
) -> Result<PublicProfileCompareResponse> {
    public_profile_compare_with_base(index_root, identities, freshness, "/")
}
