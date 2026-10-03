use dotrepo_transport::{read_jsonrpc_message, write_jsonrpc_message};
use serde_json::{json, Value};
use std::io::{BufReader, Write};
use std::process::{Command, Stdio};

#[test]
fn malformed_messages_do_not_end_the_stdio_session() {
    let mut child = Command::new(env!("CARGO_BIN_EXE_dotrepo-lsp"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .expect("start LSP");
    let mut input = child.stdin.take().expect("stdin");
    input
        .write_all(b"Content-Length: 1\r\n\r\n{")
        .expect("invalid JSON");
    let messages = [
        json!({"jsonrpc":"2.0","id":0,"method":false}),
        json!({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"rootUri":"untitled:workspace"}}),
        json!({"jsonrpc":"2.0","id":2,"method":"initialize","params":{}}),
        json!({"jsonrpc":"2.0","method":"textDocument/didOpen","params":{"textDocument":{"uri":"untitled:Untitled-1","languageId":"toml","version":1,"text":""}}}),
        json!({"jsonrpc":"2.0","method":"textDocument/didChange","params":{}}),
        json!({"jsonrpc":"2.0","method":"textDocument/didSave","params":{"textDocument":{"uri":"untitled:Untitled-1"}}}),
        json!({"jsonrpc":"2.0","method":"textDocument/didClose","params":{}}),
        json!({"jsonrpc":"2.0","id":3,"method":"textDocument/hover","params":{}}),
        json!({"jsonrpc":"2.0","id":4,"method":"textDocument/completion","params":{"textDocument":{"uri":"untitled:Untitled-1"},"position":{"line":0,"character":0}}}),
        json!({"jsonrpc":"2.0","id":5,"method":"textDocument/codeAction","params":{}}),
        json!({"jsonrpc":"2.0","id":6,"method":"missing","params":{}}),
        json!({"jsonrpc":"2.0","id":7,"method":"shutdown"}),
        json!({"jsonrpc":"2.0","method":"exit"}),
    ];
    for message in messages {
        write_jsonrpc_message(&mut input, &message).expect("write message");
    }
    drop(input);
    let mut output = BufReader::new(child.stdout.take().expect("stdout"));
    let mut responses: Vec<Value> = Vec::new();
    while let Some(payload) = read_jsonrpc_message(&mut output).expect("read response") {
        responses.push(serde_json::from_slice(&payload).expect("JSON response"));
    }
    assert!(child.wait().expect("wait for LSP").success());
    assert_eq!(responses.len(), 9, "notifications must not receive replies");
    assert_eq!(responses[0]["error"]["code"], -32700);
    assert_eq!(responses[1]["error"]["code"], -32600);
    assert_eq!(responses[2]["error"]["code"], -32602);
    assert!(responses[3]["result"]["capabilities"].is_object());
    for response in &responses[4..7] {
        assert_eq!(response["error"]["code"], -32602);
    }
    assert_eq!(responses[7]["error"]["code"], -32601);
    assert_eq!(responses[8]["id"], 7);
    assert!(responses[8]
        .get("result")
        .expect("shutdown result")
        .is_null());
}
