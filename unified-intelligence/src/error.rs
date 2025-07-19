use thiserror::Error;

/// Custom error types for UnifiedIntelligence
#[derive(Error, Debug)]
pub enum UnifiedIntelligenceError {
    #[error("Redis error: {0}")]
    Redis(#[from] redis::RedisError),
    
    #[error("Connection pool error: {0}")]
    Pool(#[from] deadpool_redis::PoolError),
    
    #[error("Connection pool creation error: {0}")]
    PoolCreation(String),
    
    #[error("Failed to get connection from pool: {0}")]
    #[allow(dead_code)]
    PoolGet(String),
    
    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),
    
    #[error("JSON error: {0}")]
    Json(serde_json::Error),
    
    #[error("Validation error: {field} - {reason}")]
    Validation { field: String, reason: String },
    
    #[error("Not found: {0}")]
    NotFound(String),
    
    #[error("Invalid action: {0}")]
    #[allow(dead_code)]
    InvalidAction(String),
    
    #[error("Chain operation failed: {0}")]
    #[allow(dead_code)]
    ChainOperation(String),
    
    #[error("Search unavailable: {0}")]
    SearchUnavailable(String),
    
    #[error("Rate limit exceeded")]
    RateLimit,
    
    #[error("Unauthorized access")]
    #[allow(dead_code)]
    Unauthorized,
    
    #[error("Internal error: {0}")]
    Internal(String),
    
    #[error("Operation timed out after {0} seconds")]
    Timeout(u64),
    
    #[error("Configuration error: {0}")]
    Configuration(String),
    
    #[error("Python script error: {0}")]
    Python(String),
}

/// Convert ValidationError to UnifiedIntelligenceError
impl From<crate::validation::ValidationError> for UnifiedIntelligenceError {
    fn from(err: crate::validation::ValidationError) -> Self {
        UnifiedIntelligenceError::Validation {
            field: match &err {
                crate::validation::ValidationError::InvalidChainId { .. } => "chain_id".to_string(),
                crate::validation::ValidationError::InvalidThoughtNumber { .. } => "thought_number".to_string(),
                crate::validation::ValidationError::InvalidInstanceId { .. } => "instance_id".to_string(),
                crate::validation::ValidationError::ThoughtTooLong { .. } => "thought".to_string(),
                crate::validation::ValidationError::EmptyThought => "thought".to_string(),
            },
            reason: err.to_string(),
        }
    }
}


/// Result type alias for convenience
pub type Result<T> = std::result::Result<T, UnifiedIntelligenceError>;