use anyhow::Result;
use rmcp::{ServiceExt, transport::stdio};
use tracing::info;
use tracing_subscriber::EnvFilter;

mod dialogue;
mod models;
mod monitor;
mod patterns;
mod retrieval;
mod service;

use service::UnifiedMindService;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing to stderr for MCP compatibility
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::from_default_env()
                .add_directive("unified_mind=debug".parse()?)
                .add_directive("rmcp=info".parse()?)
        )
        .with_writer(std::io::stderr)
        .init();

    info!("Starting UnifiedMind MCP service");

    // Create the service
    let service = UnifiedMindService::new().await?;

    // Start the MCP server on stdio transport
    let server = service.serve(stdio()).await?;
    
    // This keeps the server running until the transport closes
    server.waiting().await?;
    
    info!("UnifiedMind service shutting down gracefully");
    Ok(())
}