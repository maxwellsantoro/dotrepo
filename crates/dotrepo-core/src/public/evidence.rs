//! Public assessment metadata must stay bound to the value that was checked.
use dotrepo_schema::Manifest;
use serde_json::Value;
use std::collections::BTreeMap;
use time::{format_description::well_known::Rfc3339, OffsetDateTime};

pub(super) fn record_age(record: Option<&str>, exported: &str) -> (String, Option<i64>) {
    let parsed = record
        .and_then(|v| OffsetDateTime::parse(v, &Rfc3339).ok())
        .zip(OffsetDateTime::parse(exported, &Rfc3339).ok());
    match parsed {
        Some((record, exported)) if record <= exported => {
            let age = exported - record;
            (
                if age > time::Duration::days(30) {
                    "stale"
                } else {
                    "fresh"
                }
                .into(),
                Some(age.whole_days()),
            )
        }
        _ => ("unknown".into(), None),
    }
}

pub(super) fn field_evidence(manifest: &Manifest) -> BTreeMap<String, Value> {
    let Some(fields) = manifest
        .x
        .get("dotrepo")
        .and_then(|v| v.get("field_evidence"))
        .and_then(|v| v.as_table())
    else {
        return BTreeMap::new();
    };
    fields
        .iter()
        .filter_map(|(path, metadata)| {
            let mut metadata = serde_json::to_value(metadata).ok()?;
            let object = metadata.as_object_mut()?;
            let bound_value: Value =
                serde_json::from_str(object.remove("valueJson")?.as_str()?).ok()?;
            let current = crate::query_manifest_value(manifest, path).unwrap_or(Value::Null);
            if current != bound_value {
                return None;
            }
            // Do not carry an earlier assessment across a later record refresh.
            if object.get("checkedAt").and_then(Value::as_str)
                != manifest.record.generated_at.as_deref()
            {
                return None;
            }
            // Older field scorers used the first imported file as a security
            // source, even when it was only a README. Do not publish that guess.
            if path == "owners.security_contact"
                && object
                    .get("source")
                    .and_then(Value::as_str)
                    .is_some_and(|source| !source.to_ascii_lowercase().ends_with("security.md"))
            {
                object.remove("source");
                object.insert("method".into(), Value::String("unspecified".into()));
            }
            Some((path.clone(), metadata))
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn changing_a_fact_or_check_time_invalidates_its_assessment() {
        let mut manifest: Manifest = toml::from_str(
            r#"
schema = "dotrepo/v0.1"
[record]
mode = "overlay"
status = "imported"
generated_at = "2026-09-16T00:00:00Z"
[repo]
name = "Example"
description = "Example project"
[x.dotrepo.field_evidence."repo.name"]
valueJson = '"Example"'
checkedAt = "2026-09-16T00:00:00Z"
method = "extracted"
confidence = "medium"
"#,
        )
        .unwrap();
        assert_eq!(
            field_evidence(&manifest)["repo.name"]["confidence"],
            "medium"
        );
        manifest.repo.name = "Different".into();
        assert!(field_evidence(&manifest).is_empty());
        manifest.repo.name = "Example".into();
        manifest.record.generated_at = Some("2026-09-17T00:00:00Z".into());
        assert!(field_evidence(&manifest).is_empty());
    }

    #[test]
    fn fresh_export_cannot_rejuvenate_old_or_invalid_records() {
        assert_eq!(
            record_age(Some("2026-07-06T00:00:00Z"), "2026-09-16T00:00:00Z"),
            ("stale".into(), Some(72))
        );
        assert_eq!(
            record_age(None, "2026-09-16T00:00:00Z"),
            ("unknown".into(), None)
        );
        assert_eq!(
            record_age(Some("2026-09-17T00:00:00Z"), "2026-09-16T00:00:00Z"),
            ("unknown".into(), None)
        );
        assert_eq!(
            record_age(Some("2026-08-17T00:00:00Z"), "2026-09-16T00:00:00Z"),
            ("fresh".into(), Some(30))
        );
    }
}
