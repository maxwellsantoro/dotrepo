use anyhow::{anyhow, bail, Context, Result};
use serde::Serialize;
use std::io::{BufRead, Write};

pub fn read_jsonrpc_message(reader: &mut impl BufRead) -> Result<Option<Vec<u8>>> {
    let mut content_length = None;
    let mut saw_header = false;

    loop {
        let mut line = String::new();
        let bytes_read = reader.read_line(&mut line)?;
        if bytes_read == 0 {
            if saw_header {
                bail!("unexpected EOF while reading stdio headers");
            }
            return Ok(None);
        }

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
    let mut payload = vec![0; length];
    reader
        .read_exact(&mut payload)
        .context("unexpected EOF while reading stdio body")?;
    Ok(Some(payload))
}

pub fn write_jsonrpc_message(writer: &mut impl Write, message: &impl Serialize) -> Result<()> {
    let payload = serde_json::to_vec(message)?;
    write!(writer, "Content-Length: {}\r\n\r\n", payload.len())?;
    writer.write_all(&payload)?;
    writer.flush()?;
    Ok(())
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
}
