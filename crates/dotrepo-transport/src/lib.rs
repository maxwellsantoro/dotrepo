use anyhow::{anyhow, bail, Context, Result};
use serde::Serialize;
use serde_json::{json, Value};
use std::io::{BufRead, Write};

const MAX_JSONRPC_MESSAGE_BYTES: usize = 8 * 1024 * 1024;
const MAX_JSONRPC_HEADER_LINE_BYTES: usize = 8 * 1024;
const MAX_JSONRPC_HEADER_BYTES: usize = 64 * 1024;

pub fn read_jsonrpc_message(reader: &mut impl BufRead) -> Result<Option<Vec<u8>>> {
    let mut content_length = None;
    let mut saw_header = false;
    let mut header_bytes_read = 0usize;

    loop {
        let Some(line) = read_header_line(reader, &mut header_bytes_read)? else {
            if saw_header {
                bail!("unexpected EOF while reading stdio headers");
            }
            return Ok(None);
        };

        let trimmed = line.trim_end_matches(['\r', '\n']);
        if trimmed.is_empty() {
            break;
        }

        saw_header = true;
        if let Some(value) = trimmed.strip_prefix("Content-Length:") {
            content_length = Some(
                value
                    .trim()
                    .parse::<usize>()
                    .context("invalid Content-Length header")?,
            );
        }
    }

    let length = content_length.ok_or_else(|| anyhow!("missing Content-Length header"))?;
    if length > MAX_JSONRPC_MESSAGE_BYTES {
        bail!(
            "Content-Length {} exceeds max frame size {}",
            length,
            MAX_JSONRPC_MESSAGE_BYTES
        );
    }
    let mut payload = vec![0; length];
    reader
        .read_exact(&mut payload)
        .context("unexpected EOF while reading stdio body")?;
    Ok(Some(payload))
}

fn read_header_line(reader: &mut impl BufRead, total_bytes: &mut usize) -> Result<Option<String>> {
    let mut line = Vec::new();

    loop {
        let available = reader.fill_buf()?;
        if available.is_empty() {
            if line.is_empty() {
                return Ok(None);
            }
            bail!("unexpected EOF while reading stdio headers");
        }

        let bytes_to_take = available
            .iter()
            .position(|byte| *byte == b'\n')
            .map(|pos| pos + 1)
            .unwrap_or(available.len());

        if line.len() + bytes_to_take > MAX_JSONRPC_HEADER_LINE_BYTES {
            bail!(
                "stdio header line exceeds max size {}",
                MAX_JSONRPC_HEADER_LINE_BYTES
            );
        }
        if *total_bytes + bytes_to_take > MAX_JSONRPC_HEADER_BYTES {
            bail!("stdio headers exceed max size {}", MAX_JSONRPC_HEADER_BYTES);
        }

        line.extend_from_slice(&available[..bytes_to_take]);
        *total_bytes += bytes_to_take;
        let found_newline = available[..bytes_to_take].contains(&b'\n');
        reader.consume(bytes_to_take);

        if found_newline {
            break;
        }
    }

    String::from_utf8(line)
        .context("stdio headers must be valid UTF-8")
        .map(Some)
}

pub fn write_jsonrpc_message(writer: &mut impl Write, message: &impl Serialize) -> Result<()> {
    let payload = serde_json::to_vec(message)?;
    write!(writer, "Content-Length: {}\r\n\r\n", payload.len())?;
    writer.write_all(&payload)?;
    writer.flush()?;
    Ok(())
}

pub const JSONRPC_VERSION: &str = "2.0";

pub fn jsonrpc_response(id: Value, result: Value) -> Value {
    json!({
        "jsonrpc": JSONRPC_VERSION,
        "id": id,
        "result": result
    })
}

pub fn jsonrpc_error_response(id: Value, code: i64, message: String, data: Option<Value>) -> Value {
    let mut error = json!({
        "code": code,
        "message": message,
    });
    if let Some(data) = data {
        error["data"] = data;
    }
    json!({
        "jsonrpc": JSONRPC_VERSION,
        "id": id,
        "error": error
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{json, Value};
    use std::io::{BufReader, Cursor};

    #[test]
    fn message_framing_round_trips() {
        let message = json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "ping"
        });
        let mut bytes = Vec::new();
        write_jsonrpc_message(&mut bytes, &message).expect("message written");

        let mut reader = BufReader::new(Cursor::new(bytes));
        let payload = read_jsonrpc_message(&mut reader)
            .expect("message read")
            .expect("payload present");
        let decoded: Value = serde_json::from_slice(&payload).expect("payload decodes");
        assert_eq!(decoded, message);
    }

    #[test]
    fn read_jsonrpc_message_rejects_invalid_content_length() {
        let mut reader = BufReader::new(Cursor::new(b"Content-Length: nope\r\n\r\n{}".to_vec()));
        let err = read_jsonrpc_message(&mut reader).expect_err("invalid header rejected");
        assert!(err.to_string().contains("invalid Content-Length header"));
    }

    #[test]
    fn read_jsonrpc_message_rejects_missing_content_length() {
        let mut reader = BufReader::new(Cursor::new(
            b"Content-Type: application/json\r\n\r\n{}".to_vec(),
        ));
        let err = read_jsonrpc_message(&mut reader).expect_err("missing header rejected");
        assert!(err.to_string().contains("missing Content-Length header"));
    }

    #[test]
    fn read_jsonrpc_message_rejects_truncated_headers() {
        let mut reader = BufReader::new(Cursor::new(b"Content-Length: 2".to_vec()));
        let err = read_jsonrpc_message(&mut reader).expect_err("truncated header rejected");
        assert!(err
            .to_string()
            .contains("unexpected EOF while reading stdio headers"));
    }

    #[test]
    fn read_jsonrpc_message_rejects_truncated_body() {
        let mut reader = BufReader::new(Cursor::new(b"Content-Length: 4\r\n\r\n{}".to_vec()));
        let err = read_jsonrpc_message(&mut reader).expect_err("truncated body rejected");
        assert!(err
            .to_string()
            .contains("unexpected EOF while reading stdio body"));
    }

    #[test]
    fn read_jsonrpc_message_rejects_oversized_content_length() {
        let oversized = MAX_JSONRPC_MESSAGE_BYTES + 1;
        let mut reader = BufReader::new(Cursor::new(
            format!("Content-Length: {oversized}\r\n\r\n").into_bytes(),
        ));
        let err = read_jsonrpc_message(&mut reader).expect_err("oversized body rejected");
        assert!(err.to_string().contains("exceeds max frame size"));
    }

    #[test]
    fn read_jsonrpc_message_rejects_oversized_header_line() {
        let oversized = "a".repeat(MAX_JSONRPC_HEADER_LINE_BYTES);
        let mut reader = BufReader::new(Cursor::new(
            format!("X-Fill: {oversized}\r\n\r\n").into_bytes(),
        ));
        let err = read_jsonrpc_message(&mut reader).expect_err("oversized header rejected");
        assert!(err.to_string().contains("header line exceeds max size"));
    }
}
