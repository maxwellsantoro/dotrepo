use std::fs;
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

#[test]
fn apply_fails_before_inspection_and_preserves_records_and_evidence() {
    let nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let root = std::env::temp_dir().join(format!("dotrepo-promotion-guard-{nonce}"));
    let run = |limit: Option<&str>| {
        let mut command = Command::new(env!("CARGO_BIN_EXE_dotrepo"));
        command.args(["promotion-report", "--index-root"]);
        command.arg(&root).arg("--apply");
        if let Some(limit) = limit {
            command.args(["--limit", limit]);
        }
        command.output().unwrap()
    };
    let assert_disabled = |output: std::process::Output| {
        assert!(!output.status.success());
        assert!(
            String::from_utf8_lossy(&output.stderr).contains("standalone promotion is disabled")
        );
        assert!(output.stdout.is_empty());
    };
    assert_disabled(run(None));
    assert!(!root.exists());

    let dir = root.join("repos/github.com/example/demo");
    fs::create_dir_all(&dir).unwrap();
    // A malformed retained record proves the apply path did not try to parse it.
    fs::write(dir.join("record.toml"), b"unparseable original record\n").unwrap();
    fs::write(dir.join("evidence.md"), b"# Original evidence\n").unwrap();
    for limit in [None, Some("0"), Some("1")] {
        assert_disabled(run(limit));
        assert_eq!(
            fs::read(dir.join("record.toml")).unwrap(),
            b"unparseable original record\n"
        );
        assert_eq!(
            fs::read(dir.join("evidence.md")).unwrap(),
            b"# Original evidence\n"
        );
    }
    fs::remove_dir_all(root).unwrap();
}
