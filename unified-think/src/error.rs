use thiserror::Error;

/// Custom error types for UnifiedThink
#[derive(Error, Debug)]
pub enum UnifiedThinkError {
    #[error("Redis error: {0}")]
    Redis(#[from] redis::RedisError),
    
    #[error("Connection pool error: {0}")]
    Pool(#[from] deadpool_redis::PoolError),
    
    #[error("Connection pool creation error: {0}")]
    PoolCreation(String),
    
    #[error("Failed to get connection from pool: {0}")]
    PoolGet(String),
    
    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),
    
    #[error("Validation error: {field} - {reason}")]
    Validation { field: String, reason: String },
    
    #[error("Not found: {0}")]
    NotFound(String),
    
    #[error("Invalid action: {0}")]
    InvalidAction(String),
    
    #[error("Chain operation failed: {0}")]
    ChainOperation(String),
    
    #[error("Search unavailable: {0}")]
    SearchUnavailable(String),
    
    #[error("Rate limit exceeded")]
    RateLimit,
    
    #[error("Unauthorized access")]
    Unauthorized,
    
    #[error("Internal error: {0}")]
    Internal(String),
}

/// Convert ValidationError to UnifiedThinkError
impl From<crate::validation::ValidationError> for UnifiedThinkError {
    fn from(err: crate::validation::ValidationError) -> Self {
        UnifiedThinkError::Validation {
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
pub type Result<T> = std::result::Result<T, UnifiedThinkError>;