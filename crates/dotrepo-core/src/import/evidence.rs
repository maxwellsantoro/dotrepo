//! Evidence assembly for imported records: owners/docs field construction,
//! native GitHub-surface compat detection, evidence.md rendering, and
//! conservative (non-fabricating) relation discovery from GitHub facts and
//! package manifests.
use dotrepo_schema::{
    CompatMode, Docs, GitHubCompat, Manifest, Owners, RelationKind, RelationLink, Trust,
};
use std::fs;
use std::path::Path;

use crate::render::{
    render_contributing_body, render_pull_request_template_body, render_security_body,
};
use crate::surfaces::is_banner_line;

use super::parsing::{extract_markdown_links, is_quality_url};
use super::types::{GitHubSnapshotFacts, ImportedFile};
use super::{human_join, IMPORT_README_CANDIDATES};

pub(crate) fn build_imported_owners(
    maintainers: Vec<String>,
    team: Option<String>,
    security_contact: Option<String>,
) -> Option<Owners> {
    if maintainers.is_empty() && team.is_none() && security_contact.is_none() {
        None
    } else {
        Some(Owners {
            maintainers,
            team,
            security_contact,
        })
    }
}

pub(crate) fn build_imported_docs(
    root: Option<String>,
    getting_started: Option<String>,
) -> Option<Docs> {
    if root.is_none() && getting_started.is_none() {
        None
    } else {
        Some(Docs {
            root,
            getting_started,
            architecture: None,
            api: None,
        })
    }
}

/// When README parsing found no docs site, treat a non-forge homepage as docs root.
pub fn infer_docs_root_from_external_homepage(manifest: &mut Manifest) -> bool {
    if manifest
        .docs
        .as_ref()
        .and_then(|docs| docs.root.as_ref())
        .is_some_and(|root| !root.trim().is_empty())
    {
        return false;
    }

    let Some(homepage) = manifest
        .repo
        .homepage
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
    else {
        return false;
    };
    if !is_quality_url(homepage) {
        return false;
    }

    let lower = homepage.to_ascii_lowercase();
    if lower.contains("github.com")
        || lower.contains("gitlab.com")
        || lower.contains("bitbucket.org")
        || lower.contains("sourceforge.net")
    {
        return false;
    }

    let docs = manifest.docs.get_or_insert(Docs {
        root: None,
        getting_started: None,
        architecture: None,
        api: None,
    });
    docs.root = Some(homepage.to_string());
    true
}

pub(crate) fn native_import_github_compat(
    manifest: &Manifest,
    codeowners: Option<&ImportedFile>,
    security: Option<&ImportedFile>,
    contributing: Option<&ImportedFile>,
    pull_request_template: Option<&ImportedFile>,
) -> GitHubCompat {
    GitHubCompat {
        codeowners: Some(
            if codeowners.is_some_and(|file| {
                imported_surface_matches_generated(
                    &file.contents,
                    &render_codeowners_body_for_import(manifest),
                )
            }) {
                CompatMode::Generate
            } else {
                CompatMode::Skip
            },
        ),
        security: Some(
            if security.is_some_and(|file| {
                imported_surface_matches_generated(&file.contents, &render_security_body(manifest))
            }) {
                CompatMode::Generate
            } else {
                CompatMode::Skip
            },
        ),
        contributing: Some(
            if contributing.is_some_and(|file| {
                imported_surface_matches_generated(
                    &file.contents,
                    &render_contributing_body(manifest),
                )
            }) {
                CompatMode::Generate
            } else {
                CompatMode::Skip
            },
        ),
        pull_request_template: Some(
            if pull_request_template.is_some_and(|file| {
                imported_surface_matches_generated(
                    &file.contents,
                    &render_pull_request_template_body(manifest),
                )
            }) {
                CompatMode::Generate
            } else {
                CompatMode::Skip
            },
        ),
    }
}

fn render_codeowners_body_for_import(manifest: &Manifest) -> String {
    let owners = manifest
        .owners
        .as_ref()
        .map(|owners| owners.maintainers.join(" "))
        .unwrap_or_else(|| "@maintainers".into());
    format!("* {}\n", owners)
}

fn imported_surface_matches_generated(current: &str, expected: &str) -> bool {
    normalize_import_surface(current) == normalize_import_surface(expected)
}

fn normalize_import_surface(contents: &str) -> String {
    let without_banner = strip_generated_banner(contents).unwrap_or(contents);
    without_banner.replace("\r\n", "\n").trim().to_string()
}

fn strip_generated_banner(contents: &str) -> Option<&str> {
    let stripped = contents.strip_prefix('\u{feff}').unwrap_or(contents);
    let line_end = stripped.find('\n')?;
    let (first_line, rest) = stripped.split_at(line_end);
    if is_banner_line(first_line) {
        Some(rest.trim_start_matches('\n'))
    } else {
        None
    }
}

pub(crate) struct ImportEvidenceNotes<'a> {
    pub(crate) security_contact: Option<&'a str>,
    pub(crate) codeowners_note: Option<&'a str>,
    pub(crate) security_note: Option<&'a str>,
    pub(crate) imported_docs: bool,
}

pub(crate) fn render_import_evidence(
    imported_sources: &[String],
    inferred_fields: &[String],
    notes: ImportEvidenceNotes<'_>,
    command_evidence_bullets: &[String],
    relation_evidence_bullets: &[String],
) -> String {
    let mut bullets = Vec::new();

    if imported_sources.is_empty() {
        bullets.push(
            "No README.md, CODEOWNERS, or SECURITY.md content was imported; this record needs manual completion."
                .to_string(),
        );
    }

    if let Some(readme_path) = imported_sources
        .iter()
        .find(|path| is_imported_readme_path(path))
    {
        bullets.push(readme_import_evidence_bullet(
            inferred_fields,
            notes.imported_docs,
            readme_path,
        ));
    }
    if imported_sources
        .iter()
        .any(|path| path == ".github/CODEOWNERS" || path == "CODEOWNERS")
    {
        let mut bullet = "Imported maintainer candidates from CODEOWNERS.".to_string();
        if let Some(codeowners_note) = notes.codeowners_note {
            bullet.push(' ');
            bullet.push_str(codeowners_note);
        }
        bullets.push(bullet);
    }
    if imported_sources
        .iter()
        .any(|path| path == ".github/SECURITY.md" || path == "SECURITY.md")
    {
        if notes
            .security_contact
            .is_some_and(|contact| contact != "unknown")
        {
            let mut bullet =
                "Imported the security reporting channel from SECURITY.md.".to_string();
            if let Some(security_note) = notes.security_note {
                bullet.push(' ');
                bullet.push_str(security_note);
            }
            bullets.push(bullet);
        } else {
            bullets.push(
                "Imported SECURITY.md, but no explicit contact channel was parsed, so security_contact = \"unknown\" is intentional."
                    .to_string(),
            );
        }
    }

    if !inferred_fields.is_empty() {
        bullets.push(format!(
            "Inferred fallback values for {} because the imported files did not provide enough structured metadata.",
            human_join(inferred_fields)
        ));
    }

    bullets.extend(command_evidence_bullets.iter().cloned());
    bullets.extend(relation_evidence_bullets.iter().cloned());
    bullets.push("This is an overlay record, not a maintainer-controlled canonical record.".into());

    let mut out = String::from("# Evidence\n\n");
    for bullet in bullets {
        out.push_str("- ");
        out.push_str(&bullet);
        out.push('\n');
    }
    out
}

fn is_imported_readme_path(path: &str) -> bool {
    IMPORT_README_CANDIDATES.contains(&path)
}

fn readme_import_evidence_bullet(
    inferred_fields: &[String],
    imported_docs: bool,
    readme_path: &str,
) -> String {
    let imported_name = !inferred_fields.iter().any(|field| field == "repo.name");
    let imported_description = !inferred_fields
        .iter()
        .any(|field| field == "repo.description");

    match (imported_name, imported_description, imported_docs) {
        (true, true, true) => {
            format!(
                "Imported repository name, description, and docs entry points from {}.",
                readme_path
            )
        }
        (true, false, true) => format!(
            "Imported repository name and docs entry points from {}.",
            readme_path
        ),
        (false, true, true) => format!(
            "Imported repository description and docs entry points from {}.",
            readme_path
        ),
        (false, false, true) => format!(
            "Imported repository metadata and docs entry points from {}.",
            readme_path
        ),
        (true, true, false) => {
            format!(
                "Imported repository name and description from {}.",
                readme_path
            )
        }
        (true, false, false) => format!("Imported repository name from {}.", readme_path),
        (false, true, false) => {
            format!("Imported repository description from {}.", readme_path)
        }
        (false, false, false) => {
            format!("Imported repository metadata from {}.", readme_path)
        }
    }
}

/// Pure deterministic discovery of conservative, evidence-backed relations.
/// Returns links + evidence notes to record. Only emits for high-certainty cases
/// (e.g. fork parent from GitHub snapshot facts). No fabrication for native or absent signals.
pub(crate) fn discover_relations_from_github_facts(
    github: Option<&GitHubSnapshotFacts>,
) -> (Vec<RelationLink>, Vec<String>) {
    let mut links = Vec::new();
    let mut notes = Vec::new();
    if let Some(g) = github {
        if g.fork {
            if let Some(parent) = g.parent.as_deref().and_then(trimmed_non_empty_for_target) {
                let target = normalize_relation_target(parent);
                if !target.is_empty() {
                    links.push(RelationLink {
                        kind: RelationKind::Fork,
                        target: target.clone(),
                        notes: Some(
                            "Fork relation discovered from GitHub snapshot parent metadata."
                                .to_string(),
                        ),
                        trust: Trust {
                            confidence: Some("high".to_string()),
                            provenance: vec!["declared".to_string(), "github".to_string()],
                            notes: None,
                        },
                    });
                    notes.push(format!(
                        "Discovered fork-of relation targeting {} from GitHub parent metadata.",
                        target
                    ));
                }
            }
        }
    }
    (links, notes)
}

fn trimmed_non_empty_for_target(s: &str) -> Option<&str> {
    let t = s.trim();
    if t.is_empty() {
        None
    } else {
        Some(t)
    }
}

fn normalize_relation_target(s: &str) -> String {
    let s = s.trim();
    if s.is_empty() {
        return String::new();
    }

    let lowercase = s.to_ascii_lowercase();
    let rest = if let Some(position) = lowercase.find("github.com/") {
        &s[position + "github.com/".len()..]
    } else if s.contains('/') && !s.chars().any(char::is_whitespace) {
        s
    } else {
        return String::new();
    };

    let mut segments = rest.trim_start_matches('/').split('/');
    let Some(owner) = segments
        .next()
        .filter(|segment| valid_github_path_segment(segment))
    else {
        return String::new();
    };
    let Some(repo_with_suffix) = segments.next() else {
        return String::new();
    };
    let repo = repo_with_suffix
        .split(['?', '#'])
        .next()
        .unwrap_or_default()
        .trim_end_matches(".git");
    if !valid_github_path_segment(repo) {
        return String::new();
    }

    format!("github.com/{owner}/{repo}")
}

fn valid_github_path_segment(segment: &str) -> bool {
    !segment.is_empty()
        && segment != "."
        && segment != ".."
        && segment.chars().all(|character| {
            character.is_ascii_alphanumeric() || matches!(character, '-' | '_' | '.')
        })
}

/// Conservative discovery from package manifests (Cargo.toml / package.json) + README
/// for declared github urls in repository/homepage fields or explicit cross-links.
/// Adds Related/Reference based on signals (never fabricates). Covers homepage
/// cross-links and manifest-declared github ids per checklist.
pub(crate) fn discover_relations_from_manifest_files(
    root: &Path,
) -> Option<(Vec<RelationLink>, Vec<String>)> {
    let mut links = Vec::new();
    let mut notes = Vec::new();

    // Cargo.toml - use toml for [package] section (repository + homepage)
    if let Ok(text) = fs::read_to_string(root.join("Cargo.toml"))
        .or_else(|_| fs::read_to_string(root.join("cargo.toml")))
    {
        if let Ok(val) = toml::from_str::<toml::Value>(&text) {
            if let Some(pkg) = val.get("package") {
                for key in ["repository", "homepage"] {
                    if let Some(v) = pkg.get(key).and_then(|x| x.as_str()) {
                        if v.contains("github.com") {
                            if let Some(tgt) = extract_github_target_from_str(v) {
                                let already = links.iter().any(|l: &RelationLink| l.target == tgt);
                                if !tgt.is_empty() && !already {
                                    links.push(RelationLink {
                                        kind: RelationKind::Related,
                                        target: tgt.clone(),
                                        notes: Some(format!("Declared {} in Cargo.toml.", key)),
                                        trust: Trust {
                                            confidence: Some("low".to_string()),
                                            provenance: vec![
                                                "declared".to_string(),
                                                "manifest".to_string(),
                                            ],
                                            notes: None,
                                        },
                                    });
                                    notes.push(format!(
                                        "Discovered related relation to {} from Cargo.toml {}.",
                                        tgt, key
                                    ));
                                }
                            }
                        }
                    }
                }
            }
        } else {
            // fallback crude scan
            for line in text.lines() {
                let lower = line.to_ascii_lowercase();
                if (lower.contains("repository") || lower.contains("homepage"))
                    && lower.contains("github.com")
                {
                    if let Some(url) = extract_first_github_url(line) {
                        let tgt = normalize_relation_target(&url);
                        if !tgt.is_empty() && !links.iter().any(|l| l.target == tgt) {
                            links.push(RelationLink {
                                kind: RelationKind::Related,
                                target: tgt.clone(),
                                notes: Some(
                                    "Declared homepage/repository in Cargo.toml.".to_string(),
                                ),
                                trust: Trust {
                                    confidence: Some("low".to_string()),
                                    provenance: vec![
                                        "declared".to_string(),
                                        "manifest".to_string(),
                                    ],
                                    notes: None,
                                },
                            });
                            notes.push(format!(
                                "Discovered related relation to {} from Cargo.toml.",
                                tgt
                            ));
                            break;
                        }
                    }
                }
            }
        }
    }

    // package.json - repository + homepage (object or string)
    if let Ok(text) = fs::read_to_string(root.join("package.json")) {
        if let Ok(val) = serde_json::from_str::<serde_json::Value>(&text) {
            for key in ["repository", "homepage"] {
                let v = if key == "repository" {
                    val.get(key).and_then(|r| {
                        if let Some(s) = r.as_str() {
                            Some(s.to_string())
                        } else {
                            r.get("url").and_then(|u| u.as_str()).map(|s| s.to_string())
                        }
                    })
                } else {
                    val.get(key).and_then(|h| h.as_str()).map(|s| s.to_string())
                };
                if let Some(s) = v {
                    if s.contains("github.com") {
                        if let Some(tgt) = extract_github_target_from_str(&s) {
                            if !tgt.is_empty() && !links.iter().any(|l| l.target == tgt) {
                                links.push(RelationLink {
                                    kind: RelationKind::Related,
                                    target: tgt.clone(),
                                    notes: Some(format!("Declared {} in package.json.", key)),
                                    trust: Trust {
                                        confidence: Some("low".to_string()),
                                        provenance: vec![
                                            "declared".to_string(),
                                            "manifest".to_string(),
                                        ],
                                        notes: None,
                                    },
                                });
                                notes.push(format!(
                                    "Discovered related relation to {} from package.json {}.",
                                    tgt, key
                                ));
                            }
                        }
                    }
                }
            }
        }
    }

    // README cross-links for homepage-style or "see also" / related github (using markdown extractor if available)
    if let Ok(readme) = fs::read_to_string(root.join("README.md"))
        .or_else(|_| fs::read_to_string(root.join("README")))
    {
        let lowered = readme.to_ascii_lowercase();
        if lowered.contains("github.com")
            && (lowered.contains("see also")
                || lowered.contains("related")
                || lowered.contains("homepage")
                || lowered.contains("fork"))
        {
            for (label, url) in extract_markdown_links(&readme) {
                // use existing parser (in scope via pub(crate) reexport)
                if url.contains("github.com") {
                    if let Some(tgt) = extract_github_target_from_str(&url) {
                        if !tgt.is_empty() && !links.iter().any(|l| l.target == tgt) {
                            links.push(RelationLink {
                                kind: RelationKind::Related,
                                target: tgt.clone(),
                                notes: Some(format!("Cross-link from README: {}", label)),
                                trust: Trust {
                                    confidence: Some("low".to_string()),
                                    provenance: vec!["declared".to_string(), "readme".to_string()],
                                    notes: None,
                                },
                            });
                            notes.push(format!(
                                "Discovered related relation to {} from README cross-link.",
                                tgt
                            ));
                            break;
                        }
                    }
                }
            }
        }
    }

    if links.is_empty() {
        None
    } else {
        Some((links, notes))
    }
}

fn extract_first_github_url(text: &str) -> Option<String> {
    let candidates = ["https://github.com/", "http://github.com/", "github.com/"];
    for cand in candidates {
        if let Some(pos) = text.find(cand) {
            let start = pos;
            let rest = &text[start..];
            let mut end = rest.len();
            for (i, c) in rest.char_indices() {
                if c.is_whitespace() || matches!(c, '"' | '\'' | ',' | ']' | '}' | ')' | '>') {
                    end = i;
                    break;
                }
            }
            let url = rest[..end]
                .trim_matches(|c: char| {
                    matches!(c, '"' | '\'' | ',' | ' ' | ')' | ']' | '}' | '>' | '<')
                })
                .to_string();
            if url.contains('/') {
                return Some(url);
            }
        }
    }
    None
}

fn extract_github_target_from_str(s: &str) -> Option<String> {
    if s.contains("github.com") {
        let t = normalize_relation_target(s);
        if !t.is_empty() {
            Some(t)
        } else {
            None
        }
    } else {
        None
    }
}

#[cfg(test)]
mod relation_target_tests {
    use super::normalize_relation_target;

    #[test]
    fn github_relation_targets_are_reduced_to_repository_identity() {
        for (input, expected) in [
            (
                "https://github.com/syncthing/syncthing/tree/main?tab=readme-ov-file#related",
                "github.com/syncthing/syncthing",
            ),
            (
                "git+https://github.com/example/project.git",
                "github.com/example/project",
            ),
            ("example/project#readme", "github.com/example/project"),
        ] {
            assert_eq!(normalize_relation_target(input), expected);
        }
    }

    #[test]
    fn malformed_github_relation_targets_are_rejected() {
        for input in [
            "https://github.com/syncthing",
            "https://github.com//syncthing",
            "https://github.com/syncthing/%2F",
            "not a repository",
        ] {
            assert_eq!(normalize_relation_target(input), "");
        }
    }
}
