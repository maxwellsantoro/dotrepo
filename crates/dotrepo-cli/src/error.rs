use thiserror::Error;

#[derive(Debug, Error)]
#[error("{message}")]
pub struct CliExit {
    pub code: i32,
    pub message: String,
}
