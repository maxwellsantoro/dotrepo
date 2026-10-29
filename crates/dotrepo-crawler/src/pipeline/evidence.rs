//! Retain field assessments instead of flattening them into record confidence.
use dotrepo_core::{query_manifest_value, FieldConfidence, FieldScoreReport, ImportPlan};
use toml::{map::Map, Value};

pub(super) fn retain_field_evidence(plan: &mut ImportPlan, scores: &FieldScoreReport) {
    let mut fields = Map::new();
    for score in &scores.scores {
        let value = query_manifest_value(&plan.manifest, &score.field).unwrap_or_default();
        let (state, confidence) = match score.confidence {
            FieldConfidence::HighConfidencePresent => ("present", "high"),
            FieldConfidence::MediumConfidencePresent => ("present", "medium"),
            FieldConfidence::HighConfidenceAbsent => ("not_found", "high"),
            FieldConfidence::Suspect => ("suspect", "low"),
            FieldConfidence::Unresolved => ("unresolved", "low"),
        };
        let method = if value.is_null() && score.confidence == FieldConfidence::Unresolved {
            "unresolved"
        } else if value.is_null() {
            "not_found_in_inspected_sources"
        } else if plan.inferred_fields.contains(&score.field) {
            "inferred"
        } else if score.source.is_some() {
            "extracted"
        } else {
            "unspecified"
        };
        let mut metadata = Map::new();
        for (key, value) in [
            ("state", state.to_string()),
            ("confidence", confidence.to_string()),
            ("method", method.to_string()),
            ("reason", score.reason.clone()),
            ("valueJson", value.to_string()),
        ] {
            metadata.insert(key.into(), Value::String(value));
        }
        if let Some(source) = &score.source {
            metadata.insert("source".into(), Value::String(source.clone()));
        }
        if let Some(checked) = &plan.manifest.record.generated_at {
            metadata.insert("checkedAt".into(), Value::String(checked.clone()));
        }
        // Preserve a source-closure attachment only while its exact candidate,
        // context source and assessment time remain bound. The new field score
        // above still replaces confidence; retained grammar cannot mint high.
        if let Some(previous) = plan
            .manifest
            .x
            .get("dotrepo")
            .and_then(|extension| extension.get("field_evidence"))
            .and_then(|fields| fields.get(&score.field))
        {
            let same_value = previous
                .get("valueJson")
                .and_then(Value::as_str)
                .and_then(|raw| serde_json::from_str::<serde_json::Value>(raw).ok())
                .as_ref()
                == Some(&value);
            let same_source = previous.get("source") == metadata.get("source");
            let same_time = previous.get("checkedAt") == metadata.get("checkedAt");
            if same_value && same_source && same_time {
                if let Some(bindings) = previous.get("sourceBindingsJson").and_then(Value::as_str) {
                    metadata.insert("sourceBindingsJson".into(), Value::String(bindings.into()));
                }
            }
        }
        fields.insert(score.field.clone(), Value::Table(metadata));
    }
    let extension = plan
        .manifest
        .x
        .entry("dotrepo".into())
        .or_insert_with(|| Value::Table(Map::new()));
    if let Some(extension) = extension.as_table_mut() {
        extension.insert("field_evidence".into(), Value::Table(fields));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use dotrepo_core::{FieldScore, FieldScoreSummary, ImportCommandCandidates};

    fn plan_and_scores() -> (ImportPlan, FieldScoreReport) {
        let manifest = toml::from_str(
            r#"
schema = "dotrepo/v0.1"
[record]
mode = "overlay"
status = "imported"
generated_at = "2026-10-29T06:00:00Z"
[repo]
name = "fixture"
description = "Source attachment fixture"
[[repo.test_candidates]]
command = "pytest fixture"
source = "README.md"
[repo.test_candidates.context]
command = "pytest fixture"
working_directory = "."
scope = "repository"
prerequisites = ["Use the documented setup"]
source = "README.md"
"#,
        )
        .unwrap();
        let mut plan = ImportPlan {
            manifest_path: "record.toml".into(),
            manifest,
            manifest_text: String::new(),
            evidence_path: None,
            evidence_text: None,
            imported_sources: vec!["README.md".into()],
            inferred_fields: Vec::new(),
            command_candidates: ImportCommandCandidates::default(),
            github: None,
        };
        let field = "repo.test_candidates.0";
        let value = query_manifest_value(&plan.manifest, field).unwrap();
        let entry = Value::Table(
            [
                ("state".into(), Value::String("present".into())),
                ("method".into(), Value::String("extracted".into())),
                ("confidence".into(), Value::String("high".into())),
                ("source".into(), Value::String("README.md".into())),
                (
                    "checkedAt".into(),
                    Value::String("2026-10-29T06:00:00Z".into()),
                ),
                ("valueJson".into(), Value::String(value.to_string())),
                ("sourceBindingsJson".into(), Value::String("[]".into())),
            ]
            .into_iter()
            .collect(),
        );
        plan.manifest.x.insert(
            "dotrepo".into(),
            Value::Table(
                [(
                    "field_evidence".into(),
                    Value::Table([(field.into(), entry)].into_iter().collect()),
                )]
                .into_iter()
                .collect(),
            ),
        );
        let scores = FieldScoreReport {
            scores: vec![FieldScore {
                field: field.into(),
                confidence: FieldConfidence::MediumConfidencePresent,
                source: Some("README.md".into()),
                value: Some(value.to_string()),
                reason: "Independent completeness review remains unresolved".into(),
            }],
            summary: FieldScoreSummary {
                high_confidence_present: Vec::new(),
                medium_confidence_present: vec![field.into()],
                suspect: Vec::new(),
                high_confidence_absent: Vec::new(),
                unresolved: Vec::new(),
                eligible_for_auto_publish: false,
            },
        };
        (plan, scores)
    }

    #[test]
    fn context_source_attachment_requires_exact_tuple_source_and_time() {
        for change in ["none", "tuple", "source", "time"] {
            let (mut plan, scores) = plan_and_scores();
            match change {
                "tuple" => plan.manifest.repo.test_candidates[0]
                    .context
                    .as_mut()
                    .unwrap()
                    .prerequisites
                    .clear(),
                "source" => {
                    plan.manifest.x.get_mut("dotrepo").unwrap()["field_evidence"]
                        ["repo.test_candidates.0"]["source"] = Value::String("OTHER.md".into())
                }
                "time" => plan.manifest.record.generated_at = Some("2026-10-29T07:00:00Z".into()),
                _ => {}
            }
            retain_field_evidence(&mut plan, &scores);
            let assessment =
                &plan.manifest.x["dotrepo"]["field_evidence"]["repo.test_candidates.0"];
            assert_eq!(assessment["confidence"].as_str(), Some("medium"));
            assert_eq!(
                assessment.get("sourceBindingsJson").is_some(),
                change == "none",
                "{change}"
            );
        }
    }
}
