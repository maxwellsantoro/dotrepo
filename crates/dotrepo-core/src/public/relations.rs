use anyhow::Result;
use dotrepo_schema::RelationKind;
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
    format!("{}/{}/{}", identity.host, identity.owner, identity.repo).to_ascii_lowercase()
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
    let Some(relations) = candidates[0].manifest.relations.as_ref() else {
        return Ok(Vec::new());
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
    Ok(selected)
}

fn relation_item_with_profile(
    index_root: &Path,
    target: String,
    relation: &SelectedRelation,
    direction: &str,
    freshness: PublicFreshness,
    base_path: &str,
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
        match public_repository_profile_or_error_with_base(
            index_root,
            &identity.host,
            &identity.owner,
            &identity.repo,
            freshness,
            base_path,
        ) {
            Ok(profile) => {
                item.identity = Some(profile.identity.clone());
                item.profile = Some(Box::new(search_item_from_profile(
                    profile,
                    vec!["relation".into()],
                )));
            }
            Err(error) => {
                item.error = Some(error.error);
            }
        }
    }
    item
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
    items.sort_by(|left, right| {
        left.direction
            .cmp(&right.direction)
            .then_with(|| left.relationship.cmp(&right.relationship))
            .then_with(|| left.target.cmp(&right.target))
    });

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
