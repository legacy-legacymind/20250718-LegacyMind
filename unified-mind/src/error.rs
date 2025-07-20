use thiserror::Error;
use rmcp::model::ErrorData;

#[derive(Error, Debug)]
pub enum UnifiedMindError {
    #[error("Redis error: {0}")]
    Redis(#[from] redis::RedisError),
    
    #[error("Redis pool error: {0}")]
    RedisPool(#[from] deadpool_redis::PoolError),
    
    #[error("Qdrant error: {0}")]
    Qdrant(#[from] qdrant_client::QdrantError),
    
    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),
    
    
    #[error("Environment variable error: {0}")]
    EnvVar(String),
    
    #[error("Invalid configuration: {0}")]
    Config(String),
    
    #[error("Cache miss")]
    CacheMiss,
    
    #[error("No results found")]
    NoResults,
    
    #[error("Invalid parameter: {0}")]
    InvalidParameter(String),
    
    #[error("Server initialization error: {0}")]
    ServerInit(String),
    
    #[error("Other error: {0}")]
    Other(#[from] anyhow::Error),
}

pub type Result<T> = std::result::Result<T, UnifiedMindError>;

impl From<UnifiedMindError> for ErrorData {
    fn from(err: UnifiedMindError) -> Self {
        match err {
            UnifiedMindError::InvalidParameter(msg) => ErrorData::invalid_params(msg, None),
            UnifiedMindError::NoResults => ErrorData::internal_error("No results found", None),
            UnifiedMindError::CacheMiss => ErrorData::internal_error("Cache miss", None),
            _ => ErrorData::internal_error(err.to_string(), None),
        }
    }
}