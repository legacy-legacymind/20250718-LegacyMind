use thiserror::Error;

/// Errors that can occur in the ObsidianMCP service
#[derive(Debug, Error)]
pub enum ObsidianMcpError {
    #[error("Invalid vault path: {path}")]
    InvalidVaultPath { path: String },
    
    #[error("File not found: {path}")]
    FileNotFound { path: String },
    
    #[error("Invalid file operation: {operation} on {path}")]
    InvalidFileOperation { operation: String, path: String },
    
    #[error("Vault access denied: {reason}")]
    VaultAccessDenied { reason: String },
    
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    
    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),
    
    #[error("Redis error: {0}")]
    Redis(#[from] redis::RedisError),
    
    #[error("Configuration error: {0}")]
    Config(#[from] config::ConfigError),
    
    #[error("Walk directory error: {0}")]
    WalkDir(#[from] walkdir::Error),
    
    #[error("Invalid markdown: {reason}")]
    InvalidMarkdown { reason: String },
    
    #[error("Search failed: {query}")]
    SearchFailed { query: String },
}

/// Convert ObsidianMcpError to MCP-compatible ErrorData
impl From<ObsidianMcpError> for rmcp::model::ErrorData {
    fn from(err: ObsidianMcpError) -> Self {
        match err {
            ObsidianMcpError::InvalidVaultPath { .. } |
            ObsidianMcpError::InvalidFileOperation { .. } |
            ObsidianMcpError::InvalidMarkdown { .. } => {
                rmcp::model::ErrorData::invalid_params(err.to_string(), None)
            }
            ObsidianMcpError::FileNotFound { .. } => {
                rmcp::model::ErrorData::invalid_request(err.to_string(), None)
            }
            ObsidianMcpError::VaultAccessDenied { .. } => {
                rmcp::model::ErrorData::invalid_request(err.to_string(), None)
            }
            _ => rmcp::model::ErrorData::internal_error(err.to_string(), None),
        }
    }
}

pub type ObsidianResult<T> = std::result::Result<T, ObsidianMcpError>;