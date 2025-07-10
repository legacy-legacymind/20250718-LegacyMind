use anyhow::Result;
use MCP_UnifiedThinking::{service::{UnifiedThinkingService, ServiceConfig}, models}; // Note: models is unused for now
use rmcp::{ServiceExt, transport::stdio};

#[tokio::main]
async fn main() -> Result<()> {
    // For now, we'll hardcode the instance_id.
    // This will be moved to a config file later.
    let config = ServiceConfig {
        instance_id: "Gemini".to_string(),
    };

    let service = UnifiedThinkingService::new(config).await?;
    let server = service.serve(stdio()).await?;
    server.waiting().await?;
    Ok(())
}