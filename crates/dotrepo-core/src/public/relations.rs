use anyhow::Result;
use dotrepo_schema::RelationKind;
use std::collections::{HashMap, HashSet};
use std::path::Path;

use crate::selection::resolve_candidates;
use crate::util::repository_reference_identity;

use super::*;

fn parse_relation_reference(value: &str) -> Option<PublicRepositoryIdentity> {
    let (host, owner, repo) = repository_reference_identity(value)?;
    Some(PublicRepositoryIdentity {
        host,
        owner,
        repo,
        source: None,
    })
}

fn relation_reference_key(identity: &PublicRepositoryIdentity) -> String {
    identity_key(identity).to_ascii_lowercase()
}

fn identity_key(identity: &PublicRepositoryIdentity) -> String {
    format!("{}/{}/{}", identity.host, identity.owner, identity.repo)
}

#[derive(Debug, Clone)]
struct SelectedRelation {
    relationship: &'static str,
    inverse_relationship: &'static str,
    target: String,
    notes: Option<String>,
    trust: Option<PublicRelationTrust>,
}

fn relation_names(kind: RelationKind) -> (&'static str, &'static str) {
    match kind {
        RelationKind::Reference => ("reference", "referenced_by"),
        RelationKind::Alternative => ("alternative", "alternative"),
        RelationKind::Dependency => ("dependency", "depended_on_by"),
        RelationKind::Predecessor => ("predecessor", "successor"),
        RelationKind::Fork => ("fork", "forked_by"),
        RelationKind::Related => ("related", "related"),
    }
}

fn selected_relations(
    index_root: &Path,
    identity: &PublicRepositoryIdentity,
) -> Result<Vec<SelectedRelation>> {
    let scope_root =
        index_repository_scope(index_root, &identity.host, &identity.owner, &identity.repo)?;
    let candidates = resolve_candidates(&scope_root)?;
    Ok(relations_from_selected(&candidates[0]))
}

fn relations_from_selected(selected: &CandidateManifest) -> Vec<SelectedRelation> {
    let Some(relations) = selected.manifest.relations.as_ref() else {
        return Vec::new();
    };
    let mut selected = relations
        .references
        .iter()
        .cloned()
        .map(|target| SelectedRelation {
            relationship: "reference",
            inverse_relationship: "referenced_by",
            target,
            notes: None,
            trust: None,
        })
        .collect::<Vec<_>>();
    selected.extend(relations.links.iter().map(|link| {
        let (relationship, inverse_relationship) = relation_names(link.kind);
        SelectedRelation {
            relationship,
            inverse_relationship,
            target: link.target.clone(),
            notes: link.notes.clone(),
            trust: Some(PublicRelationTrust {
                confidence: link.trust.confidence.clone(),
                provenance: link.trust.provenance.clone(),
                notes: link.trust.notes.clone(),
            }),
        }
    }));
    selected
}

fn relation_item(
    target: String,
    relation: &SelectedRelation,
    direction: &str,
    profile: impl FnOnce(
        &PublicRepositoryIdentity,
    ) -> std::result::Result<PublicProfileSearchItem, Box<PublicErrorDetail>>,
) -> PublicRelationItem {
    let identity = parse_relation_reference(&target);
    let mut item = PublicRelationItem {
        relationship: relation.relationship.into(),
        direction: direction.into(),
        target: target.clone(),
        notes: relation.notes.clone(),
        trust: relation.trust.clone(),
        identity: identity.clone(),
        profile: None,
        error: None,
    };
    if let Some(identity) = identity {
        match profile(&identity) {
            Ok(profile) => {
                item.identity = Some(profile.identity.clone());
                item.profile = Some(Box::new(profile));
            }
            Err(error) => {
                item.error = Some(error);
            }
        }
    }
    item
}

fn relation_item_with_profile(
    index_root: &Path,
    target: String,
    relation: &SelectedRelation,
    direction: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> PublicRelationItem {
    relation_item(target, relation, direction, |identity| {
        public_repository_profile_or_error_with_base(
            index_root,
            &identity.host,
            &identity.owner,
            &identity.repo,
            freshness,
            base_path,
        )
        .map(|profile| search_item_from_profile(profile, vec!["relation".into()]))
        .map_err(|error| error.error)
    })
}

pub(super) struct RelationRepository<'a> {
    pub identity: &'a PublicRepositoryIdentity,
    pub selected: &'a CandidateManifest,
    pub profile: &'a PublicResearchProfileResponse,
}

/// Selected records and reverse edges are indexed once for a complete export.
/// A repository response then visits only its outgoing and incoming edges.
pub(super) struct PublicRelationIndex {
    source_keys: Vec<String>,
    outgoing: Vec<Vec<SelectedRelation>>,
    incoming: HashMap<String, Vec<(usize, usize)>>,
    profiles: HashMap<String, std::result::Result<PublicProfileSearchItem, Box<PublicErrorDetail>>>,
}

impl PublicRelationIndex {
    pub(super) fn new(
        index_root: &Path,
        repositories: &[RelationRepository<'_>],
        freshness: &PublicFreshness,
        base_path: &str,
    ) -> Self {
        let source_keys = repositories
            .iter()
            .map(|repository| relation_reference_key(repository.identity))
            .collect::<Vec<_>>();
        let outgoing = repositories
            .iter()
            .map(|repository| relations_from_selected(repository.selected))
            .collect::<Vec<_>>();
        let repository_scopes = repositories
            .iter()
            .enumerate()
            .map(|(index, repository)| {
                (
                    index_root
                        .join("repos")
                        .join(identity_key(repository.identity)),
                    index,
                )
            })
            .collect::<HashMap<_, _>>();
        let mut github_aliases = HashMap::<String, Vec<usize>>::new();
        for (index, repository) in repositories.iter().enumerate() {
            if repository.identity.host.eq_ignore_ascii_case("github.com") {
                github_aliases
                    .entry(source_keys[index].clone())
                    .or_default()
                    .push(index);
            }
        }

        let mut incoming = HashMap::<String, Vec<(usize, usize)>>::new();
        let mut profile_identities = HashMap::new();
        let mut incoming_sources = HashSet::new();
        for (source_index, relations) in outgoing.iter().enumerate() {
            for (relation_index, relation) in relations.iter().enumerate() {
                let Some(target) = parse_relation_reference(&relation.target) else {
                    continue;
                };
                let target_key = relation_reference_key(&target);
                profile_identities.insert(identity_key(&target), target);
                // Self-references remain outgoing, as in the public endpoint.
                if target_key == source_keys[source_index] {
                    continue;
                }
                incoming
                    .entry(target_key)
                    .or_default()
                    .push((source_index, relation_index));
                incoming_sources.insert(source_index);
            }
        }
        for source_index in incoming_sources {
            if let Some(identity) = parse_relation_reference(&source_keys[source_index]) {
                profile_identities.insert(identity_key(&identity), identity);
            }
        }
        let profiles = profile_identities
            .into_iter()
            .map(|(key, identity)| {
                let profile = (|| -> Result<PublicProfileSearchItem> {
                    // Use the existing scope resolver so GitHub casing and
                    // ambiguous-directory errors keep their public semantics.
                    let scope = index_repository_scope(
                        index_root,
                        &identity.host,
                        &identity.owner,
                        &identity.repo,
                    )?;
                    let repository_index = repository_scopes.get(&scope).copied().or_else(|| {
                        // Case-insensitive filesystems may return the requested
                        // spelling rather than the spelling in the inventory.
                        github_aliases
                            .get(&relation_reference_key(&identity))
                            .filter(|matches| matches.len() == 1)
                            .map(|matches| matches[0])
                    });
                    let Some(repository_index) = repository_index else {
                        // Preserve support for a reference resolving to a scope
                        // outside the inventory (for example a directory alias).
                        return public_repository_profile_with_base(
                            index_root,
                            &identity.host,
                            &identity.owner,
                            &identity.repo,
                            freshness.clone(),
                            base_path,
                        )
                        .map(|profile| search_item_from_profile(profile, vec!["relation".into()]));
                    };
                    let repository = &repositories[repository_index];
                    let mut profile = search_item_from_profile(
                        repository.profile.clone(),
                        vec!["relation".into()],
                    );
                    // Public links and identity reflect the reference spelling,
                    // even when its record is found through a GitHub alias.
                    profile.identity = public_identity(
                        &identity.host,
                        &identity.owner,
                        &identity.repo,
                        repository.selected,
                    );
                    profile.links = public_links_with_base(
                        &identity.host,
                        &identity.owner,
                        &identity.repo,
                        PublicLinkKind::Profile,
                        None,
                        base_path,
                    )?;
                    Ok(profile)
                })()
                .map_err(|error| {
                    public_error_response(
                        &identity.host,
                        &identity.owner,
                        &identity.repo,
                        None,
                        freshness.clone(),
                        &error,
                    )
                    .error
                });
                (key, profile)
            })
            .collect();
        Self {
            source_keys,
            outgoing,
            incoming,
            profiles,
        }
    }

    pub(super) fn response(
        &self,
        repository_index: usize,
        identity: PublicRepositoryIdentity,
        freshness: PublicFreshness,
        base_path: &str,
    ) -> Result<PublicRelationsResponse> {
        let profile = |identity: &PublicRepositoryIdentity| {
            self.profiles
                .get(&identity_key(identity))
                .expect("all parsed relation identities were indexed")
                .clone()
        };
        let mut items = self.outgoing[repository_index]
            .iter()
            .map(|relation| relation_item(relation.target.clone(), relation, "outgoing", profile))
            .collect::<Vec<_>>();
        if let Some(incoming) = self.incoming.get(&self.source_keys[repository_index]) {
            for &(source_index, relation_index) in incoming {
                let relation = &self.outgoing[source_index][relation_index];
                items.push(relation_item(
                    self.source_keys[source_index].clone(),
                    &SelectedRelation {
                        relationship: relation.inverse_relationship,
                        ..relation.clone()
                    },
                    "incoming",
                    profile,
                ));
            }
        }
        sort_relation_items(&mut items);
        let links = public_links_with_base(
            &identity.host,
            &identity.owner,
            &identity.repo,
            PublicLinkKind::Relations,
            None,
            base_path,
        )?;
        Ok(PublicRelationsResponse {
            api_version: PUBLIC_API_VERSION,
            freshness,
            identity,
            relation_count: items.len(),
            references: items,
            links,
        })
    }
}

fn sort_relation_items(items: &mut [PublicRelationItem]) {
    items.sort_by(|left, right| {
        left.direction
            .cmp(&right.direction)
            .then_with(|| left.relationship.cmp(&right.relationship))
            .then_with(|| left.target.cmp(&right.target))
    });
}

pub fn public_repository_relations_with_base(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicRelationsResponse> {
    normalize_public_base_path(base_path)?;
    let profile = public_repository_profile_with_base(
        index_root,
        host,
        owner,
        repo,
        freshness.clone(),
        base_path,
    )?;
    let selected_identity = PublicRepositoryIdentity {
        host: host.to_string(),
        owner: owner.to_string(),
        repo: repo.to_string(),
        source: None,
    };
    let selected_key = relation_reference_key(&selected_identity);
    let relations = selected_relations(index_root, &selected_identity)?;

    let mut items = Vec::new();
    for relation in relations {
        items.push(relation_item_with_profile(
            index_root,
            relation.target.clone(),
            &relation,
            "outgoing",
            freshness.clone(),
            base_path,
        ));
    }

    for candidate in list_index_repository_identities(index_root)? {
        let candidate_key = relation_reference_key(&candidate);
        if candidate_key == selected_key {
            continue;
        }
        let relations = selected_relations(index_root, &candidate)?;
        for relation in relations {
            let points_to_selected = parse_relation_reference(&relation.target)
                .map(|target| relation_reference_key(&target) == selected_key)
                .unwrap_or(false);
            if !points_to_selected {
                continue;
            }
            items.push(relation_item_with_profile(
                index_root,
                candidate_key.clone(),
                &SelectedRelation {
                    relationship: relation.inverse_relationship,
                    ..relation.clone()
                },
                "incoming",
                freshness.clone(),
                base_path,
            ));
        }
    }
    sort_relation_items(&mut items);

    Ok(PublicRelationsResponse {
        api_version: PUBLIC_API_VERSION,
        freshness,
        identity: profile.identity,
        relation_count: items.len(),
        references: items,
        links: public_links_with_base(
            host,
            owner,
            repo,
            PublicLinkKind::Relations,
            None,
            base_path,
        )?,
    })
}

pub fn public_repository_relations(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
) -> Result<PublicRelationsResponse> {
    public_repository_relations_with_base(index_root, host, owner, repo, freshness, "/")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn indexed_responses_use_loaded_records_without_reading_the_index_again() {
        let unique = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("clock works")
            .as_nanos();
        let index = std::env::temp_dir().join(format!(
            "dotrepo-relations-index-{}-{unique}",
            std::process::id()
        ));
        for name in ["Source", "Target"] {
            let root = index.join("repos/github.com/example").join(name);
            fs::create_dir_all(&root).expect("repository directory");
            let relations = if name == "Source" {
                "[relations]\nreferences = [\"github.com/example/target\"]"
            } else {
                ""
            };
            fs::write(
                root.join("record.toml"),
                format!(
                    r#"schema = "dotrepo/v0.1"
[record]
mode = "overlay"
status = "imported"
source = "https://github.com/example/{name}"
[record.trust]
confidence = "high"
provenance = ["imported"]
[repo]
name = "{name}"
description = "Loaded {name} profile."
{relations}
"#
                ),
            )
            .expect("record written");
        }
        let freshness = PublicFreshness {
            generated_at: "2026-06-28T12:00:00Z".into(),
            snapshot_digest: "fixture".into(),
            stale_after: None,
        };
        let identities = list_index_repository_identities(&index).expect("inventory");
        let loaded = identities
            .iter()
            .map(|identity| {
                let candidates = resolve_repository_candidates(
                    &index,
                    &identity.host,
                    &identity.owner,
                    &identity.repo,
                )
                .expect("candidates loaded");
                let profile = public_repository_profile_with_candidates(
                    &index,
                    &identity.host,
                    &identity.owner,
                    &identity.repo,
                    &candidates,
                    freshness.clone(),
                    "/",
                )
                .expect("profile loaded");
                (candidates, profile)
            })
            .collect::<Vec<_>>();
        let repositories = identities
            .iter()
            .zip(&loaded)
            .map(|(identity, (candidates, profile))| RelationRepository {
                identity,
                selected: &candidates[0],
                profile,
            })
            .collect::<Vec<_>>();
        let relations = PublicRelationIndex::new(&index, &repositories, &freshness, "/");
        let expected = identities
            .iter()
            .map(|identity| {
                let response = public_repository_relations(
                    &index,
                    &identity.host,
                    &identity.owner,
                    &identity.repo,
                    freshness.clone(),
                )
                .expect("public lookup");
                serde_json::to_value(response).expect("response serializes")
            })
            .collect::<Vec<_>>();
        fs::remove_dir_all(&index).expect("remove all source records");
        for (repository_index, (_, profile)) in loaded.iter().enumerate() {
            let response = relations
                .response(
                    repository_index,
                    profile.identity.clone(),
                    freshness.clone(),
                    "/",
                )
                .expect("cached response requires no source files");
            assert_eq!(
                serde_json::to_value(response).expect("response serializes"),
                expected[repository_index]
            );
        }
    }
}
