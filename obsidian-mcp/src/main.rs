use anyhow::Result;
use rmcp::{ServiceExt, transport::stdio};
use tracing_subscriber;

mod models;
mod error;
mod config;
mod vault;
mod service;

use crate::service::ObsidianMcpService;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing to stderr for MCP compatibility
    tracing_subscriber::fmt()
        .with_target(false)
        .with_ansi(false)
        .with_writer(std::io::stderr)
        .init();

    tracing::info!("Starting ObsidianMCP server");

    let service = ObsidianMcpService::new().await?;
    
    // Start the MCP server on stdio transport
    let server = service.serve(stdio()).await?;
    
    tracing::info!("ObsidianMCP server ready for connections");
    
    // This keeps the server running until the transport closes
    server.waiting().await?;
    
    tracing::info!("ObsidianMCP server shutting down");
    Ok(())
}