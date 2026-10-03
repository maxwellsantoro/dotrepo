use std::{
    fs,
    process::Command,
    time::{SystemTime, UNIX_EPOCH},
};

#[test]
fn standalone_apply_rejects_invented_commands_without_writing_evidence() {
    let root = std::env::temp_dir().join(format!(
        "dotrepo-cli-disabled-promotion-{}",
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    let dir = root.join("repos/github.com/example/invented");
    fs::create_dir_all(&dir).unwrap();
    let manifest = r#"
schema = "dotrepo/v0.1"
[record]
mode = "overlay"
status = "imported"
source = "https://github.com/example/invented"
[record.trust]
confidence = "high"
provenance = ["imported"]
[repo]
name = "Invented"
description = "A nonempty description is not verification"
homepage = "https://github.com/example/invented"
build = "invented-build-command --trust-me"
"#;
    fs::write(dir.join("record.toml"), manifest).unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_dotrepo"))
        .args(["promotion-report", "--index-root"])
        .arg(&root)
        .args(["--apply", "--json"])
        .output()
        .unwrap();
    assert!(!output.status.success());
    assert!(String::from_utf8_lossy(&output.stderr).contains("standalone promotion is disabled"));
    assert_eq!(
        fs::read_to_string(dir.join("record.toml")).unwrap(),
        manifest
    );
    assert!(!dir.join("evidence.md").exists());
    fs::remove_dir_all(root).unwrap();
}
