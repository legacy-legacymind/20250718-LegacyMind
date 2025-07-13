use anyhow::Result;
use rmcp::{ServiceExt, transport::stdio};
use tracing_subscriber;

mod models;
mod error;
mod redis;
mod repository;
mod handlers;
mod service;
mod search_optimization;
mod validation;
mod rate_limit;
mod lua_scripts;
// mod embeddings;
// mod vector_service;
mod redisvl_service;
mod visual;
mod frameworks;

use crate::service::UnifiedIntelligenceService;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing to stderr for MCP compatibility
    tracing_subscriber::fmt()
        .with_target(false)
        .with_ansi(false)
        .with_writer(std::io::stderr)
        .init();
    
    let service = UnifiedIntelligenceService::new().await?;
    
    // Start the MCP server on stdio transport
    let server = service.serve(stdio()).await?;
    
    // This keeps the server running until the transport closes
    server.waiting().await?;
    
    eprintln!("Server shutting down");
    Ok(())
}