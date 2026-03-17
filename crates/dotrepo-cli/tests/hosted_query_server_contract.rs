use serde_json::Value;
use std::fs;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("crate directory has parent")
        .parent()
        .expect("workspace root exists")
        .to_path_buf()
}

fn fixture_index_root() -> PathBuf {
    repo_root()
        .join("crates")
        .join("dotrepo-core")
        .join("tests")
        .join("fixtures")
        .join("public-export")
        .join("fixture-index")
}

fn expected_query_root() -> PathBuf {
    repo_root()
        .join("crates")
        .join("dotrepo-core")
        .join("tests")
        .join("fixtures")
        .join("public-query")
        .join("expected")
}

fn server_bin() -> &'static str {
    env!("CARGO_BIN_EXE_dotrepo-public-query")
}

fn read_expected(name: &str) -> Value {
    serde_json::from_str(
        &fs::read_to_string(expected_query_root().join(name)).expect("expected fixture readable"),
    )
    .expect("expected fixture json parses")
}

fn unused_addr() -> String {
    let listener = TcpListener::bind("127.0.0.1:0").expect("ephemeral port available");
    let addr = listener.local_addr().expect("local addr known");
    drop(listener);
    addr.to_string()
}

struct ServerHandle {
    child: Child,
    addr: String,
}

impl ServerHandle {
    fn spawn(index_root: &Path, base_path: &str) -> Self {
        let addr = unused_addr();
        let child = Command::new(server_bin())
            .args([
                "--index-root",
                index_root.to_str().expect("fixture path is utf-8"),
                "--bind",
                &addr,
                "--base-path",
                base_path,
                "--generated-at",
                "2026-03-10T18:30:00Z",
                "--stale-after",
                "2026-03-11T18:30:00Z",
            ])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .expect("server process spawns");

        let handle = Self { child, addr };
        handle.wait_until_ready();
        handle
    }

    fn wait_until_ready(&self) {
        let deadline = Instant::now() + Duration::from_secs(5);
        while Instant::now() < deadline {
            if let Some((status, body)) = http_get(&self.addr, "/healthz") {
                if status == 200 && body == "ok" {
                    return;
                }
            }
            thread::sleep(Duration::from_millis(50));
        }
        panic!("server did not become ready");
    }
}

impl Drop for ServerHandle {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

fn http_get(addr: &str, target: &str) -> Option<(u16, String)> {
    let mut stream = TcpStream::connect(addr).ok()?;
    write!(
        stream,
        "GET {} HTTP/1.1\r\nHost: {}\r\nConnection: close\r\n\r\n",
        target, addr
    )
    .ok()?;
    stream.flush().ok()?;

    let mut response = String::new();
    stream.read_to_string(&mut response).ok()?;
    let (headers, body) = response.split_once("\r\n\r\n")?;
    let status = headers
        .lines()
        .next()?
        .split_whitespace()
        .nth(1)?
        .parse::<u16>()
        .ok()?;
    Some((status, body.to_string()))
}

fn temp_dir(label: &str) -> PathBuf {
    let unique = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("clock works")
        .as_nanos();
    let path = std::env::temp_dir().join(format!(
        "dotrepo-cli-hosted-query-{}-{}-{}",
        label,
        std::process::id(),
        unique
    ));
    fs::create_dir_all(&path).expect("temp dir created");
    path
}

#[test]
fn hosted_query_server_matches_checked_in_query_fixtures() {
    let server = ServerHandle::spawn(&fixture_index_root(), "/");

    let cases = [
        (
            "/v0/repos/github.com/example/orbit/query?path=repo.description",
            200,
            "orbit-description.json",
        ),
        (
            "/v0/repos/github.com/example/nova/query?path=repo.description",
            200,
            "nova-description.json",
        ),
        (
            "/v0/repos/github.com/example/orbit/query?path=repo.missing_field",
            404,
            "missing-path.json",
        ),
        (
            "/v0/repos/github.com/missing/repo/query?path=repo.description",
            404,
            "missing-repo.json",
        ),
        (
            "/v0/repos/github.com/example%2Fnested/orbit/query?path=repo.description",
            400,
            "invalid-identity.json",
        ),
    ];

    for (target, expected_status, fixture) in cases {
        let (status, body) = http_get(&server.addr, target).expect("request should succeed");
        assert_eq!(status, expected_status, "{target} status drifted");
        let actual = serde_json::from_str::<Value>(&body).expect("response json parses");
        let expected = read_expected(fixture);
        assert_eq!(actual, expected, "{target} body drifted");
    }
}

#[test]
fn hosted_query_server_honors_base_path_and_preserves_equal_authority_conflicts() {
    let root = temp_dir("equal-authority-server");
    let record_dir = root.join("repos/github.com/example/orbit");
    let alt_dir = record_dir.join("alt");
    fs::create_dir_all(&alt_dir).expect("alt dir created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Selected description"
"#,
    )
    .expect("selected record written");
    fs::write(
        alt_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Competing description"
"#,
    )
    .expect("competing record written");

    let server = ServerHandle::spawn(&root, "/dotrepo");
    let (status, body) = http_get(
        &server.addr,
        "/dotrepo/v0/repos/github.com/example/orbit/query?path=repo.description",
    )
    .expect("request should succeed");
    assert_eq!(status, 200);

    let json = serde_json::from_str::<Value>(&body).expect("response json parses");
    assert_eq!(
        json["selection"]["reason"],
        Value::String("equal_authority_conflict".into())
    );
    assert_eq!(
        json["conflicts"][0]["relationship"],
        Value::String("parallel".into())
    );
    assert_eq!(
        json["links"]["self"],
        Value::String("/dotrepo/v0/repos/github.com/example/orbit/query?path=repo.description".into())
    );
    assert_eq!(
        json["links"]["repository"],
        Value::String("/dotrepo/v0/repos/github.com/example/orbit/index.json".into())
    );
    assert_eq!(
        json["links"]["trust"],
        Value::String("/dotrepo/v0/repos/github.com/example/orbit/trust.json".into())
    );
    assert_eq!(
        json["links"]["queryTemplate"],
        Value::String("/dotrepo/v0/repos/github.com/example/orbit/query?path={dot_path}".into())
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}
