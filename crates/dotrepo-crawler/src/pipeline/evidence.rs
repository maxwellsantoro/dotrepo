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
        let method = if value.is_null() {
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
