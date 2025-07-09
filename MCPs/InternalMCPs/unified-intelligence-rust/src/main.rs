use anyhow::Result;
use tracing_subscriber;
use rmcp::{ServiceExt, transport::stdio};

mod service;
mod tools;
mod core;
mod storage;
mod utils;
mod monitors;
mod processors;

use service::UnifiedIntelligenceService;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing to stderr (stdout is used for MCP protocol)
    tracing_subscriber::fmt()
        .with_writer(std::io::stderr)
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "unified_intelligence_rust=info,rmcp=info".into()),
        )
        .init();

    tracing::info!("Starting UnifiedIntelligence Rust v3.0.0");

    // Configuration from environment
    let config = service::ServiceConfig {
        redis_url: std::env::var("REDIS_URL")
            .unwrap_or_else(|_| "redis://localhost:6379".to_string()),
        instance_id: std::env::var("INSTANCE_ID")
            .unwrap_or_else(|_| "default".to_string()),
    };

    tracing::info!("Connecting to Redis at: {}", config.redis_url);
    tracing::info!("Instance ID: {}", config.instance_id);

    // Create service
    let service = UnifiedIntelligenceService::new(config).await?;

    tracing::info!("Service initialized, starting MCP server on stdio");

    // Serve on stdio
    let server = service.serve(stdio()).await.inspect_err(|e| {
        tracing::error!("serving error: {:?}", e);
    })?;

    server.waiting().await?;
    Ok(())
}