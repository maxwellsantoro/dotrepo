use super::*;
use crate::github::GitHubClient;
use crate::NetworkUsage;
use reqwest::header::{HeaderValue, AUTHORIZATION};
use std::cell::RefCell;
use std::io::{Read, Write};
use std::net::TcpListener;
use std::thread;
use std::time::Instant;

enum Reply {
    Drop,
    Stall,
    Http(u16, &'static str, String),
    Raw(&'static str),
}

fn serve(replies: Vec<Reply>) -> (Url, thread::JoinHandle<Vec<String>>) {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind loopback");
    let address = listener.local_addr().unwrap();
    listener.set_nonblocking(true).unwrap();
    let handle = thread::spawn(move || {
        let mut requests = Vec::new();
        let mut stalled = Vec::new();
        for reply in replies {
            let deadline = Instant::now() + Duration::from_secs(5);
            let mut stream = loop {
                match listener.accept() {
                    Ok((stream, _)) => break stream,
                    Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                        assert!(
                            Instant::now() < deadline,
                            "client did not send expected request"
                        );
                        thread::sleep(Duration::from_millis(2));
                    }
                    Err(error) => panic!("accept failed: {error}"),
                }
            };
            // macOS can inherit O_NONBLOCK from the listening socket; request
            // reads use the explicit timeout on every supported platform.
            stream.set_nonblocking(false).unwrap();
            stream
                .set_read_timeout(Some(Duration::from_secs(2)))
                .unwrap();
            let mut request = Vec::new();
            let mut buffer = [0_u8; 1024];
            while !request.windows(4).any(|part| part == b"\r\n\r\n") {
                let count = stream.read(&mut buffer).expect("read request");
                assert!(count > 0, "client closed before headers");
                request.extend_from_slice(&buffer[..count]);
                assert!(request.len() < 16_384);
            }
            requests.push(String::from_utf8(request).unwrap());
            match reply {
                Reply::Drop => drop(stream),
                Reply::Stall => stalled.push(thread::spawn(move || {
                    thread::sleep(Duration::from_millis(300));
                    drop(stream);
                })),
                Reply::Http(status, body, headers) => {
                    write!(
                        stream,
                        "HTTP/1.1 {status} Fixture\r\nContent-Length: {}\r\nConnection: close\r\n{headers}\r\n{body}",
                        body.len()
                    ).unwrap();
                }
                Reply::Raw(response) => stream.write_all(response.as_bytes()).unwrap(),
            }
        }
        for thread in stalled {
            thread.join().unwrap();
        }
        requests
    });
    let url = Url::parse(&format!(
        "http://{address}/KDE/krita/pinned-commit/rakefile"
    ))
    .unwrap();
    (url, handle)
}

fn client(url: &Url, timeout: Duration) -> HttpGitHubClient {
    let mut headers = HeaderMap::new();
    headers.insert(
        AUTHORIZATION,
        HeaderValue::from_static("Bearer fixture-token"),
    );
    HttpGitHubClient {
        client: Client::builder()
            .no_proxy()
            .default_headers(headers)
            .timeout(timeout)
            .redirect(reqwest::redirect::Policy::limited(0))
            .build()
            .unwrap(),
        api_base_url: url.clone(),
        raw_base_url: url.clone(),
        network: RefCell::new(NetworkUsage::default()),
    }
}

fn ok() -> Reply {
    Reply::Http(200, "ok", String::new())
}

fn limited() -> Reply {
    Reply::Http(429, "limited", String::new())
}

#[test]
fn dropped_get_recovers_without_changing_revision_or_headers() {
    let (url, server) = serve(vec![Reply::Drop, ok()]);
    let client = client(&url, Duration::from_secs(2));
    let mut waits = Vec::new();
    let response = client
        .send_with_retry_using(url, |delay| waits.push(delay))
        .unwrap();
    assert_eq!(response.text().unwrap(), "ok");
    assert_eq!(waits, [Duration::from_secs(2)]);
    let requests = server.join().unwrap();
    assert_eq!(requests.len(), 2);
    for request in requests {
        assert!(request.starts_with("GET /KDE/krita/pinned-commit/rakefile HTTP/1.1\r\n"));
        assert!(request
            .to_ascii_lowercase()
            .contains("authorization: bearer fixture-token\r\n"));
    }
    assert_eq!(client.network_usage().requests, 2);
    assert_eq!(client.network_usage().bytes, 2);
}

#[test]
fn production_retry_reaches_optional_missing_file_after_disconnect() {
    let (url, server) = serve(vec![
        Reply::Drop,
        Reply::Http(404, "missing", String::new()),
    ]);
    let client = client(&url, Duration::from_secs(2));
    assert_eq!(client.get_optional_text(url).unwrap(), None);
    assert_eq!(server.join().unwrap().len(), 2);
    assert_eq!(client.network_usage().requests, 2);
}

#[test]
fn exhausted_transport_budget_preserves_failure_and_cause() {
    let (url, server) = serve(vec![Reply::Drop, Reply::Drop, Reply::Drop, Reply::Drop]);
    let client = client(&url, Duration::from_secs(2));
    let mut waits = Vec::new();
    let error = client
        .send_with_retry_using(url, |delay| waits.push(delay))
        .unwrap_err();
    let message = error.to_string();
    assert!(message.contains("failed to GET"));
    assert!(message.contains("after 3 retries"));
    assert!(
        message.contains("connection") || message.contains("incomplete message"),
        "{message}"
    );
    assert_eq!(
        waits,
        [retry_backoff(0), retry_backoff(1), retry_backoff(2)]
    );
    assert_eq!(server.join().unwrap().len(), 4);
    assert_eq!(client.network_usage().requests, 4);
}

#[test]
fn timeout_can_recover_on_same_bounded_get() {
    let (url, server) = serve(vec![Reply::Stall, ok()]);
    let client = client(&url, Duration::from_millis(100));
    let response = client.send_with_retry_using(url, |_| {}).unwrap();
    assert_eq!(response.text().unwrap(), "ok");
    assert_eq!(server.join().unwrap().len(), 2);
    assert_eq!(client.network_usage().requests, 2);
}

#[test]
fn persistent_timeouts_exhaust_without_hanging_or_becoming_absence() {
    let (url, server) = serve(vec![Reply::Stall, Reply::Stall, Reply::Stall, Reply::Stall]);
    let client = client(&url, Duration::from_millis(100));
    let start = Instant::now();
    let message = client
        .send_with_retry_using(url, |_| {})
        .unwrap_err()
        .to_string();
    assert!(start.elapsed() < Duration::from_secs(3));
    assert!(
        message.contains("after 3 retries") && message.contains("timed out"),
        "{message}"
    );
    assert_eq!(server.join().unwrap().len(), 4);
    assert_eq!(client.network_usage().requests, 4);
}

#[test]
fn mixed_rate_limits_and_transport_failures_share_one_budget() {
    let (url, server) = serve(vec![Reply::Drop, limited(), Reply::Drop, limited()]);
    let client = client(&url, Duration::from_secs(2));
    let mut waits = Vec::new();
    let message = client
        .send_with_retry_using(url, |delay| waits.push(delay))
        .unwrap_err()
        .to_string();
    assert!(message.contains("rate limited after 3 retries"));
    assert_eq!(
        waits,
        [retry_backoff(0), retry_backoff(1), retry_backoff(2)]
    );
    assert_eq!(server.join().unwrap().len(), 4);
    assert_eq!(client.network_usage().requests, 4);
}

#[test]
fn rate_limit_reset_wait_keeps_existing_cap() {
    let reset = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_secs()
        + 3600;
    let (url, server) = serve(vec![
        Reply::Http(
            403,
            "limited",
            format!("x-ratelimit-remaining: 0\r\nx-ratelimit-reset: {reset}\r\n"),
        ),
        ok(),
    ]);
    let client = client(&url, Duration::from_secs(2));
    let mut waits = Vec::new();
    assert_eq!(
        client
            .send_with_retry_using(url, |delay| waits.push(delay))
            .unwrap()
            .status(),
        200
    );
    assert_eq!(waits, [Duration::from_secs(120)]);
    assert_eq!(server.join().unwrap().len(), 2);
}

#[test]
fn permanent_http_error_is_not_retried() {
    let (url, server) = serve(vec![Reply::Http(403, "forbidden", String::new())]);
    let client = client(&url, Duration::from_secs(2));
    let error = client
        .send_with_retry_using(url, |_| panic!("must not retry"))
        .unwrap_err();
    assert!(error.to_string().contains("HTTP 403 forbidden"));
    assert_eq!(server.join().unwrap().len(), 1);
    assert_eq!(client.network_usage().requests, 1);
}

#[test]
fn redirect_policy_error_is_not_retried() {
    let (url, server) = serve(vec![Reply::Http(
        302,
        "",
        "Location: /elsewhere\r\n".into(),
    )]);
    let client = client(&url, Duration::from_secs(2));
    let error = client
        .send_with_retry_using(url, |_| panic!("must not retry"))
        .unwrap_err();
    assert!(error.to_string().contains("after 0 retries"));
    assert_eq!(server.join().unwrap().len(), 1);
    assert_eq!(client.network_usage().requests, 1);
}

#[test]
fn invalid_request_builder_is_not_retried() {
    let url = Url::parse("file:///not-a-github-request").unwrap();
    let client = client(&url, Duration::from_secs(2));
    let error = client
        .send_with_retry_using(url, |_| panic!("must not retry"))
        .unwrap_err();
    assert!(error.to_string().contains("after 0 retries"));
    assert_eq!(client.network_usage().requests, 1);
}

#[test]
fn malformed_json_is_still_a_decode_failure_without_retry() {
    let (url, server) = serve(vec![Reply::Http(200, "{broken", String::new())]);
    let client = client(&url, Duration::from_secs(2));
    let error = client.get_json::<serde_json::Value>(url).unwrap_err();
    assert!(error
        .to_string()
        .contains("failed to decode GitHub response"));
    assert_eq!(server.join().unwrap().len(), 1);
    assert_eq!(client.network_usage().requests, 1);
}

#[test]
fn truncated_body_is_still_a_failure_without_retry_or_absence() {
    let (url, server) = serve(vec![Reply::Raw(
        "HTTP/1.1 200 OK\r\nContent-Length: 20\r\nConnection: close\r\n\r\n{}",
    )]);
    let client = client(&url, Duration::from_secs(2));
    let error = client.get_optional_text(url).unwrap_err();
    assert!(error.to_string().contains("failed to decode text response"));
    assert_eq!(server.join().unwrap().len(), 1);
    assert_eq!(client.network_usage().requests, 1);
}
