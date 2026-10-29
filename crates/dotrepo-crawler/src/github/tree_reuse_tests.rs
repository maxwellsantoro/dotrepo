use super::*;
use std::io::{Read, Write};
use std::net::TcpListener;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;

type Reply = (u16, String);
type ObservedRequests = Arc<Mutex<Vec<(String, usize)>>>;

struct Server {
    base: String,
    requests: ObservedRequests,
    stop: Arc<AtomicBool>,
    thread: Option<thread::JoinHandle<()>>,
}

impl Server {
    fn start(reply: impl Fn(&str, usize) -> Reply + Send + 'static) -> Self {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        listener.set_nonblocking(true).unwrap();
        let base = format!("http://{}/", listener.local_addr().unwrap());
        let requests = Arc::new(Mutex::new(Vec::new()));
        let observed = Arc::clone(&requests);
        let stop = Arc::new(AtomicBool::new(false));
        let stopping = Arc::clone(&stop);
        let thread = thread::spawn(move || {
            let mut tree_calls = 0;
            while !stopping.load(Ordering::Relaxed) {
                let (mut stream, _) = match listener.accept() {
                    Ok(value) => value,
                    Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                        thread::sleep(Duration::from_millis(1));
                        continue;
                    }
                    Err(error) => panic!("owned listener: {error}"),
                };
                stream.set_nonblocking(false).unwrap();
                stream
                    .set_read_timeout(Some(Duration::from_secs(2)))
                    .unwrap();
                let mut raw = Vec::new();
                while !raw.ends_with(b"\r\n\r\n") {
                    let mut byte = [0];
                    if stream.read(&mut byte).unwrap() == 0 {
                        break;
                    }
                    raw.push(byte[0]);
                    assert!(raw.len() < 16384);
                }
                let text = String::from_utf8(raw).unwrap();
                let path = text.split_whitespace().nth(1).unwrap().to_string();
                if path.contains("/git/trees/") {
                    tree_calls += 1;
                }
                let (status, body) = reply(&path, tree_calls);
                observed.lock().unwrap().push((path, body.len()));
                write!(stream, "HTTP/1.1 {status} fixture\r\nContent-Length: {}\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{body}", body.len()).unwrap();
            }
        });
        Self {
            base,
            requests,
            stop,
            thread: Some(thread),
        }
    }

    fn client(&self) -> HttpGitHubClient {
        HttpGitHubClient {
            client: Client::builder()
                .timeout(Duration::from_secs(3))
                .no_proxy()
                .build()
                .unwrap(),
            api_base_url: Url::parse(&self.base).unwrap(),
            raw_base_url: Url::parse(&(self.base.clone() + "raw")).unwrap(),
            network: RefCell::new(NetworkUsage::default()),
        }
    }

    fn tree_calls(&self) -> usize {
        self.requests
            .lock()
            .unwrap()
            .iter()
            .filter(|(path, _)| path.contains("/git/trees/"))
            .count()
    }

    fn assert_counters(&self, client: &HttpGitHubClient) {
        let requests = self.requests.lock().unwrap();
        let usage = client.network_usage();
        assert_eq!(usage.requests as usize, requests.len());
        assert_eq!(
            usage.bytes as usize,
            requests.iter().map(|(_, bytes)| bytes).sum::<usize>()
        );
    }
}

impl Drop for Server {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::Relaxed);
        let result = self.thread.take().unwrap().join();
        if !thread::panicking() {
            result.unwrap();
        }
    }
}

fn repository(name: &str) -> RepositoryRef {
    RepositoryRef {
        host: "github.com".into(),
        owner: "owned".into(),
        repo: name.into(),
    }
}

fn languages() -> Vec<String> {
    vec!["TypeScript".into(), "Python".into()]
}

fn tree() -> String {
    serde_json::json!({"tree": [
        {"path": "python/setup.py", "type": "blob"},
        {"path": "web/package.json", "type": "blob"},
        {"path": "package.json", "type": "blob"},
        {"path": "python/pyproject.toml", "type": "blob"},
        {"path": "server/package.json", "type": "blob"},
        {"path": "examples/demo/setup.py", "type": "blob"},
        {"path": "sdk/setup.py", "type": "blob"},
        {"path": "src/setup.py", "type": "tree"}
    ]})
    .to_string()
}

fn fixture_reply(path: &str, _: usize) -> Reply {
    if path.contains("/git/trees/") {
        return (200, tree());
    }
    if path.contains("/contents") {
        return (200, "[]".into());
    }
    for (name, bytes) in [
        ("README.md", "# owned\n"),
        ("package.json", "{\"scripts\":{\"test\":\"owned-root\"}}\n"),
        ("pyproject.toml", "[project]\nname = 'owned'\n"),
        ("server/package.json", "owned server bytes\n"),
        ("web/package.json", "owned web bytes\n"),
        ("python/pyproject.toml", "owned python project bytes\n"),
        ("python/setup.py", "owned setup bytes\n"),
    ] {
        let raw_prefix = path.splitn(6, '/').collect::<Vec<_>>();
        if raw_prefix.get(1) == Some(&"raw") && raw_prefix.get(5) == Some(&name) {
            return (200, bytes.into());
        }
    }
    (404, "not found".into())
}

#[test]
fn tree_reuse_preserves_selected_bytes_order_and_real_counters() {
    let server = Server::start(fixture_reply);
    let client = server.client();
    let files = client
        .fetch_repository_files(&repository("mixed"), "fixed-ref", &languages())
        .unwrap();
    let selected: Vec<_> = files
        .extra_files
        .iter()
        .map(|file| {
            (
                file.relative_path.to_string_lossy().to_string(),
                file.contents.clone(),
            )
        })
        .collect();
    assert_eq!(
        selected,
        vec![
            (
                "package.json".into(),
                "{\"scripts\":{\"test\":\"owned-root\"}}\n".into()
            ),
            (
                "pyproject.toml".into(),
                "[project]\nname = 'owned'\n".into()
            ),
            ("server/package.json".into(), "owned server bytes\n".into()),
            ("web/package.json".into(), "owned web bytes\n".into()),
            (
                "python/pyproject.toml".into(),
                "owned python project bytes\n".into()
            ),
            ("python/setup.py".into(), "owned setup bytes\n".into()),
        ]
    );
    assert_eq!(files.readme.unwrap().contents, "# owned\n");
    server.assert_counters(&client);
    assert_eq!(
        server.tree_calls(),
        1,
        "successful tree must be reused by both selectors"
    );
}

#[test]
fn tree_reuse_does_not_cache_404_and_later_selector_can_observe_success() {
    let server = Server::start(|path, count| {
        if path.contains("/git/trees/") && count == 1 {
            (404, "not found".into())
        } else {
            fixture_reply(path, count)
        }
    });
    let client = server.client();
    let files = client
        .fetch_repository_files(&repository("mixed"), "fixed-ref", &languages())
        .unwrap();
    let paths: Vec<_> = files
        .extra_files
        .iter()
        .map(|file| file.relative_path.to_string_lossy().to_string())
        .collect();
    assert_eq!(
        paths,
        vec![
            "package.json",
            "pyproject.toml",
            "python/pyproject.toml",
            "python/setup.py"
        ]
    );
    assert_eq!(server.tree_calls(), 2);
    server.assert_counters(&client);
}

#[test]
fn tree_reuse_is_lazy_when_no_selector_needs_a_tree() {
    let server = Server::start(fixture_reply);
    let client = server.client();
    client
        .fetch_repository_files(&repository("go-only"), "fixed-ref", &["Go".into()])
        .unwrap();
    assert_eq!(server.tree_calls(), 0);
    server.assert_counters(&client);
}

#[test]
fn tree_reuse_successful_empty_tree_is_reused() {
    let server = Server::start(|path, count| {
        if path.contains("/git/trees/") {
            (200, "{\"tree\":[]}".into())
        } else {
            fixture_reply(path, count)
        }
    });
    let client = server.client();
    let files = client
        .fetch_repository_files(&repository("empty"), "fixed-ref", &languages())
        .unwrap();
    assert_eq!(files.extra_files.len(), 2);
    assert_eq!(server.tree_calls(), 1);
    server.assert_counters(&client);
}

#[test]
fn tree_reuse_non_200_or_malformed_response_keeps_fatal_error() {
    for (status, body) in [(500, "owned server error"), (200, "not json")] {
        let server = Server::start(move |path, count| {
            if path.contains("/git/trees/") {
                (status, body.into())
            } else {
                fixture_reply(path, count)
            }
        });
        let client = server.client();
        assert!(client
            .fetch_repository_files(&repository("broken"), "fixed-ref", &languages())
            .is_err());
        assert_eq!(server.tree_calls(), 1);
        server.assert_counters(&client);
    }
}

#[test]
fn tree_reuse_is_scoped_to_each_invocation_repository_and_ref() {
    let server = Server::start(fixture_reply);
    let client = server.client();
    for (repo, reference) in [
        ("first", "one"),
        ("first", "one"),
        ("first", "two"),
        ("second", "one"),
    ] {
        client
            .fetch_repository_files(&repository(repo), reference, &languages())
            .unwrap();
    }
    assert_eq!(server.tree_calls(), 4);
    let requests = server.requests.lock().unwrap();
    let paths: Vec<_> = requests
        .iter()
        .filter(|(path, _)| path.contains("/git/trees/"))
        .map(|(path, _)| path.as_str())
        .collect();
    assert_eq!(
        paths,
        vec![
            "/repos/owned/first/git/trees/one?recursive=1",
            "/repos/owned/first/git/trees/one?recursive=1",
            "/repos/owned/first/git/trees/two?recursive=1",
            "/repos/owned/second/git/trees/one?recursive=1"
        ]
    );
    drop(requests);
    server.assert_counters(&client);
}

#[test]
fn tree_reuse_serves_rust_and_dotnet_without_changing_root_probe_or_selection() {
    for other in ["Rust", "C#"] {
        let server = Server::start(|path, count| {
            if path.contains("/git/trees/") {
                let mut value: serde_json::Value = serde_json::from_str(&tree()).unwrap();
                value["tree"].as_array_mut().unwrap().extend([
                    serde_json::json!({"path":"rust/Cargo.toml", "type":"blob"}),
                    serde_json::json!({"path":"dotnet/App.csproj", "type":"blob"}),
                ]);
                return (200, value.to_string());
            }
            if path.starts_with("/raw/") && path.ends_with("/rust/Cargo.toml") {
                return (200, "owned nested Rust manifest\n".into());
            }
            if path.starts_with("/raw/") && path.ends_with("/dotnet/App.csproj") {
                return (200, "owned nested .NET manifest\n".into());
            }
            fixture_reply(path, count)
        });
        let client = server.client();
        let files = client
            .fetch_repository_files(
                &repository("three-languages"),
                "fixed-ref",
                &["TypeScript".into(), "Python".into(), other.into()],
            )
            .unwrap();
        let last = files.extra_files.last().unwrap();
        let expected = if other == "Rust" {
            ("rust/Cargo.toml", "owned nested Rust manifest\n")
        } else {
            ("dotnet/App.csproj", "owned nested .NET manifest\n")
        };
        assert_eq!(last.relative_path.to_str().unwrap(), expected.0);
        assert_eq!(last.contents, expected.1);
        assert_eq!(server.tree_calls(), 1);
        if other == "Rust" {
            // Preserve the pre-existing duplicate root probe; this patch only
            // coalesces successful tree responses, not raw-file requests.
            let requests = server.requests.lock().unwrap();
            assert_eq!(
                requests
                    .iter()
                    .filter(|(path, _)| path.ends_with("/fixed-ref/Cargo.toml"))
                    .count(),
                2
            );
        }
        server.assert_counters(&client);
    }
}
