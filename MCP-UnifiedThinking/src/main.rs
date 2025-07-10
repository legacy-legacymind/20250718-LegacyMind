use anyhow::Result;
use MCP_UnifiedThinking::{
    service::{UnifiedThinkingService, ServiceConfig},
    storage::redis_pool,
};
use rmcp::{ServiceExt, transport::stdio};

#[tokio::main]
async fn main() -> Result<()> {
    let redis_url = "redis://:legacymind_redis_pass@127.0.0.1/"; // This should be moved to config later
    let redis_pool = redis_pool::create_pool(redis_url).await?;

    let config = ServiceConfig {
        instance_id: std::env::var("INSTANCE_ID").unwrap_or_else(|_| "default".to_string()),
        redis_pool,
    };

    let service = UnifiedThinkingService::new(config).await?;
    let server = service.serve(stdio()).await?;
    server.waiting().await?;
    Ok(())
}