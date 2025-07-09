use thiserror::Error;

#[derive(Debug, Error)]
pub enum UnifiedError {
    #[error("Redis error: {0}")]
    Redis(#[from] redis::RedisError),
    
    #[error("Pool error: {0}")]
    Pool(#[from] deadpool_redis::PoolError),
    
    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),
    
    #[error("Invalid session: {0}")]
    InvalidSession(String),
    
    #[error("Framework detection failed")]
    FrameworkDetection,
    
    #[error("Invalid parameter: {field} - {reason}")]
    InvalidParameter { field: String, reason: String },
    
    #[error("Not implemented: {0}")]
    NotImplemented(String),
}

// Convert to rmcp errors
impl From<UnifiedError> for rmcp::Error {
    fn from(err: UnifiedError) -> Self {
        match err {
            UnifiedError::InvalidParameter { .. } => {
                rmcp::Error::invalid_params(err.to_string(), None)
            }
            _ => rmcp::Error::internal_error(err.to_string(), None),
        }
    }
}