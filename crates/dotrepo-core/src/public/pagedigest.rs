//! pagedigest manifest emission for the static public export.
//!
//! pagedigest (v1 RC) is a sibling protocol: a single manifest at
//! `/.well-known/pagedigest.json` mapping each covered URL to a monotonic
//! integer revision and an auditable SHA-256 digest, so stateful consumers
//! can detect site changes with one request instead of re-fetching every
//! file. The public export emits one covering the `/v0/repos/` tree.
//!
//! Every exported file embeds the volatile `freshness` block (generation
//! timestamp and snapshot digest), so raw bytes change on every export even
//! when a record's content does not. Publishing revisions keyed to raw bytes
//! would churn the whole manifest per export — the exact failure mode the
//! pagedigest specification warns is worse than no manifest. Revisions are
//! therefore keyed to a *content* digest computed with the top-level
//! `freshness` member removed, while `digest` remains the accurate hash of
//! the full served bytes as the specification requires. The content digest
//! is carried in each entry as the `content_digest` extension field
//! (specification consumers must ignore unknown fields), which makes the
//! manifest itself the durable revision state for the next export.

use anyhow::{anyhow, Context, Result};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

use super::normalize_public_base_path;

/// Manifest location relative to the export root, per the pagedigest
/// specification's normative discovery point.
pub const PAGEDIGEST_RELATIVE_PATH: &str = ".well-known/pagedigest.json";

const PAGEDIGEST_VERSION: u64 = 1;
const PAGEDIGEST_COVERED_RELATIVE_PREFIX: &str = "v0/repos/";
const PAGEDIGEST_COVERAGE_MODE_PREFIXES: &str = "prefixes";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PagedigestManifest {
    pub version: u64,
    pub generated: String,
    pub site_rev: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub coverage: Option<PagedigestCoverage>,
    pub entries: BTreeMap<String, PagedigestEntry>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PagedigestCoverage {
    pub mode: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub prefixes: Option<Vec<String>>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PagedigestEntry {
    pub rev: u64,
    pub digest: String,
    /// Exporter extension (ignored by specification consumers): hash of the
    /// entry's JSON with the top-level `freshness` member removed, so `rev`
    /// tracks material content change rather than per-export timestamp churn.
    #[serde(default)]
    pub content_digest: String,
}

/// Load a previously published manifest to carry revision state forward.
///
/// Returns `Ok(None)` when no manifest exists at `path` (first export).
/// A present-but-unreadable manifest is an error rather than `None`:
/// silently reseeding revisions to 1 would violate the monotonicity
/// contract for consumers that cached earlier revisions.
pub fn load_pagedigest_manifest(path: &Path) -> Result<Option<PagedigestManifest>> {
    if !path.is_file() {
        return Ok(None);
    }
    let text = fs::read_to_string(path).with_context(|| {
        format!(
            "failed to read previous pagedigest manifest {}",
            path.display()
        )
    })?;
    let manifest = serde_json::from_str::<PagedigestManifest>(&text).with_context(|| {
        format!(
            "failed to parse previous pagedigest manifest {}",
            path.display()
        )
    })?;
    Ok(Some(manifest))
}

/// Build the pagedigest manifest for one export's outputs.
///
/// Coverage is intentionally partial: only files under `v0/repos/` are
/// listed, because they are the stable, publicly served content surface.
/// `v0/meta.json` and `v0/files.json` change on every export by design, and
/// `query-input/` files are not publicly routable on the hosted origin.
pub fn build_pagedigest_manifest(
    previous: Option<&PagedigestManifest>,
    generated_at: &str,
    base_path: &str,
    out_root: &Path,
    outputs: &[(PathBuf, String)],
) -> Result<PagedigestManifest> {
    let base = normalize_public_base_path(base_path)?;
    let covered_url_prefix = format!("{base}/{PAGEDIGEST_COVERED_RELATIVE_PREFIX}");

    let mut entries = BTreeMap::new();
    let mut changed = false;
    for (path, contents) in outputs {
        let relative = crate::relative_to_root(out_root, path)?;
        let relative = relative.display().to_string();
        if !relative.starts_with(PAGEDIGEST_COVERED_RELATIVE_PREFIX) {
            continue;
        }
        let key = format!("{base}/{relative}");
        let digest = format!("sha256:{}", sha256_hex(contents.as_bytes()));
        let content_digest = format!("sha256:{}", content_sha256(contents));
        let rev = match previous.and_then(|manifest| manifest.entries.get(&key)) {
            Some(prior) if prior.content_digest == content_digest => prior.rev,
            Some(prior) => {
                changed = true;
                prior.rev + 1
            }
            None => {
                changed = true;
                1
            }
        };
        entries.insert(
            key,
            PagedigestEntry {
                rev,
                digest,
                content_digest,
            },
        );
    }

    let coverage = PagedigestCoverage {
        mode: PAGEDIGEST_COVERAGE_MODE_PREFIXES.to_string(),
        prefixes: Some(vec![covered_url_prefix]),
    };

    let site_rev = match previous {
        None => 1,
        Some(prior) => {
            let removed = prior.entries.keys().any(|key| !entries.contains_key(key));
            let coverage_changed = prior.coverage.as_ref() != Some(&coverage);
            if changed || removed || coverage_changed {
                prior
                    .site_rev
                    .checked_add(1)
                    .ok_or_else(|| anyhow!("pagedigest site_rev overflow"))?
            } else {
                prior.site_rev
            }
        }
    };

    Ok(PagedigestManifest {
        version: PAGEDIGEST_VERSION,
        generated: generated_at.to_string(),
        site_rev,
        coverage: Some(coverage),
        entries,
    })
}

fn sha256_hex(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    format!("{:x}", hasher.finalize())
}

/// Hash the material content of an exported JSON document: the parsed value
/// with the volatile top-level `freshness` member removed, re-serialized
/// compactly (serde_json orders object keys deterministically). Non-JSON
/// content falls back to hashing the raw bytes.
fn content_sha256(contents: &str) -> String {
    match serde_json::from_str::<serde_json::Value>(contents) {
        Ok(mut value) => {
            if let Some(object) = value.as_object_mut() {
                object.remove("freshness");
            }
            match serde_json::to_string(&value) {
                Ok(canonical) => sha256_hex(canonical.as_bytes()),
                Err(_) => sha256_hex(contents.as_bytes()),
            }
        }
        Err(_) => sha256_hex(contents.as_bytes()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_outputs(
        root: &Path,
        freshness_stamp: &str,
        orbit_body: &str,
    ) -> Vec<(PathBuf, String)> {
        vec![
            (
                root.join("v0/meta.json"),
                format!("{{\"generatedAt\":\"{freshness_stamp}\"}}"),
            ),
            (
                root.join("v0/repos/github.com/example/orbit/profile.json"),
                format!(
                    "{{\"freshness\":{{\"generatedAt\":\"{freshness_stamp}\"}},\"purpose\":\"{orbit_body}\"}}"
                ),
            ),
            (
                root.join("query-input/github.com/example/orbit.json"),
                format!("{{\"freshness\":{{\"generatedAt\":\"{freshness_stamp}\"}}}}"),
            ),
        ]
    }

    #[test]
    fn first_export_seeds_revisions_at_one_and_covers_only_repo_files() {
        let root = PathBuf::from("/export");
        let outputs = sample_outputs(&root, "2026-03-10T18:30:00Z", "orbital tooling");
        let manifest =
            build_pagedigest_manifest(None, "2026-03-10T18:30:00Z", "/", &root, &outputs)
                .expect("manifest builds");

        assert_eq!(manifest.version, 1);
        assert_eq!(manifest.site_rev, 1);
        assert_eq!(manifest.generated, "2026-03-10T18:30:00Z");
        assert_eq!(
            manifest.coverage.as_ref().unwrap().prefixes,
            Some(vec!["/v0/repos/".to_string()])
        );
        assert_eq!(manifest.entries.len(), 1);
        let entry = &manifest.entries["/v0/repos/github.com/example/orbit/profile.json"];
        assert_eq!(entry.rev, 1);
        assert!(entry.digest.starts_with("sha256:"));
        assert!(entry.content_digest.starts_with("sha256:"));
        assert_ne!(entry.digest, entry.content_digest);
    }

    #[test]
    fn freshness_only_churn_keeps_revisions_and_site_rev_but_updates_digest() {
        let root = PathBuf::from("/export");
        let first = sample_outputs(&root, "2026-03-10T18:30:00Z", "orbital tooling");
        let previous = build_pagedigest_manifest(None, "2026-03-10T18:30:00Z", "/", &root, &first)
            .expect("first manifest builds");

        let second = sample_outputs(&root, "2026-03-11T18:30:00Z", "orbital tooling");
        let manifest =
            build_pagedigest_manifest(Some(&previous), "2026-03-11T18:30:00Z", "/", &root, &second)
                .expect("second manifest builds");

        assert_eq!(manifest.site_rev, previous.site_rev);
        let key = "/v0/repos/github.com/example/orbit/profile.json";
        assert_eq!(manifest.entries[key].rev, previous.entries[key].rev);
        assert_ne!(manifest.entries[key].digest, previous.entries[key].digest);
        assert_eq!(
            manifest.entries[key].content_digest,
            previous.entries[key].content_digest
        );
    }

    #[test]
    fn content_change_increments_rev_and_site_rev() {
        let root = PathBuf::from("/export");
        let first = sample_outputs(&root, "2026-03-10T18:30:00Z", "orbital tooling");
        let previous = build_pagedigest_manifest(None, "2026-03-10T18:30:00Z", "/", &root, &first)
            .expect("first manifest builds");

        let second = sample_outputs(&root, "2026-03-11T18:30:00Z", "revised orbital tooling");
        let manifest =
            build_pagedigest_manifest(Some(&previous), "2026-03-11T18:30:00Z", "/", &root, &second)
                .expect("second manifest builds");

        assert_eq!(manifest.site_rev, previous.site_rev + 1);
        let key = "/v0/repos/github.com/example/orbit/profile.json";
        assert_eq!(manifest.entries[key].rev, previous.entries[key].rev + 1);
    }

    #[test]
    fn added_and_removed_urls_increment_site_rev() {
        let root = PathBuf::from("/export");
        let first = sample_outputs(&root, "2026-03-10T18:30:00Z", "orbital tooling");
        let previous = build_pagedigest_manifest(None, "2026-03-10T18:30:00Z", "/", &root, &first)
            .expect("first manifest builds");

        let mut with_added = sample_outputs(&root, "2026-03-10T18:30:00Z", "orbital tooling");
        with_added.push((
            root.join("v0/repos/github.com/example/nova/profile.json"),
            "{\"freshness\":{},\"purpose\":\"nova\"}".to_string(),
        ));
        let added = build_pagedigest_manifest(
            Some(&previous),
            "2026-03-11T18:30:00Z",
            "/",
            &root,
            &with_added,
        )
        .expect("manifest with addition builds");
        assert_eq!(added.site_rev, previous.site_rev + 1);
        assert_eq!(
            added.entries["/v0/repos/github.com/example/nova/profile.json"].rev,
            1
        );
        assert_eq!(
            added.entries["/v0/repos/github.com/example/orbit/profile.json"].rev,
            previous.entries["/v0/repos/github.com/example/orbit/profile.json"].rev
        );

        let removed =
            build_pagedigest_manifest(Some(&added), "2026-03-12T18:30:00Z", "/", &root, &first)
                .expect("manifest with removal builds");
        assert_eq!(removed.site_rev, added.site_rev + 1);
        assert!(!removed
            .entries
            .contains_key("/v0/repos/github.com/example/nova/profile.json"));
    }

    #[test]
    fn hosted_base_path_prefixes_keys_and_coverage() {
        let root = PathBuf::from("/export");
        let outputs = sample_outputs(&root, "2026-03-10T18:30:00Z", "orbital tooling");
        let manifest =
            build_pagedigest_manifest(None, "2026-03-10T18:30:00Z", "/dotrepo", &root, &outputs)
                .expect("manifest builds");

        assert!(manifest
            .entries
            .contains_key("/dotrepo/v0/repos/github.com/example/orbit/profile.json"));
        assert_eq!(
            manifest.coverage.as_ref().unwrap().prefixes,
            Some(vec!["/dotrepo/v0/repos/".to_string()])
        );
    }

    #[test]
    fn previous_manifest_round_trips_through_serialization() {
        let root = PathBuf::from("/export");
        let outputs = sample_outputs(&root, "2026-03-10T18:30:00Z", "orbital tooling");
        let manifest =
            build_pagedigest_manifest(None, "2026-03-10T18:30:00Z", "/", &root, &outputs)
                .expect("manifest builds");
        let serialized = serde_json::to_string_pretty(&manifest).expect("serializes");
        let parsed = serde_json::from_str::<PagedigestManifest>(&serialized).expect("round-trips");
        assert_eq!(parsed, manifest);
    }
}
