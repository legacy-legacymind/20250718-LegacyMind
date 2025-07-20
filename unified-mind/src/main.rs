mod error;
mod handlers;
mod models;
mod redis;
mod service;

use error::Result;
use std::env;
use tracing::{error, info};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging
    let filter = env::var("RUST_LOG").unwrap_or_else(|_| "unified_mind=info,rmcp=info".to_string());
    
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| filter.into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();
    
    info!("Starting UnifiedMind MCP server");
    
    // Validate environment
    validate_environment()?;
    
    // Run the service
    if let Err(e) = service::run_service().await {
        error!("Server error: {}", e);
        return Err(e);
    }
    
    Ok(())
}

fn validate_environment() -> Result<()> {
    use crate::error::UnifiedMindError;
    
    // Check required API keys
    if env::var("OPENAI_API_KEY").is_err() {
        return Err(UnifiedMindError::EnvVar("OPENAI_API_KEY not found".to_string()));
    }
    
    if env::var("GROQ_API_KEY").is_err() {
        return Err(UnifiedMindError::EnvVar("GROQ_API_KEY not found".to_string()));
    }
    
    // Log configuration
    info!("Configuration:");
    info!("  REDIS_HOST: {}", env::var("REDIS_HOST").unwrap_or_else(|_| "localhost".to_string()));
    info!("  REDIS_PORT: {}", env::var("REDIS_PORT").unwrap_or_else(|_| "6379".to_string()));
    info!("  QDRANT_HOST: {}", env::var("QDRANT_HOST").unwrap_or_else(|_| "localhost".to_string()));
    info!("  QDRANT_PORT: {}", env::var("QDRANT_PORT").unwrap_or_else(|_| "6334".to_string()));
    info!("  INSTANCE_ID: {}", env::var("INSTANCE_ID").unwrap_or_else(|_| "CC".to_string()));
    info!("  OPENAI_API_KEY: {}", if env::var("OPENAI_API_KEY").is_ok() { "Found" } else { "Not found" });
    info!("  GROQ_API_KEY: {}", if env::var("GROQ_API_KEY").is_ok() { "Found" } else { "Not found" });
    
    Ok(())
}