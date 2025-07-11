use anyhow::Result;
use rmcp::{ServiceExt, transport::stdio};
use rmcp_macros::{tool, tool_handler, tool_router};
use rmcp::{
    handler::server::{router::tool::ToolRouter, tool::Parameters},
    model::{CallToolResult, Content, ErrorData, Implementation, ProtocolVersion, ServerCapabilities, ServerInfo},
    ServerHandler,
};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::env;
use std::future::Future;
use std::sync::Arc;
use tracing;
use tracing_subscriber;
use uuid::Uuid;
use chrono::Utc;
use deadpool_redis::{Config, Runtime, Pool};

#[derive(Debug, Deserialize, schemars::JsonSchema)]
struct UiThinkParams {
    #[schemars(description = "The thought content to process")]
    thought: String,
    #[schemars(description = "Current thought number in sequence")]
    thought_number: i32,
    #[schemars(description = "Total number of thoughts in sequence")]
    total_thoughts: i32,
    #[schemars(description = "Whether another thought is needed")]
    next_thought_needed: bool,
}

#[derive(Debug, Serialize)]
struct ThoughtRecord {
    id: String,
    instance: String,
    thought: String,
    thought_number: i32,
    total_thoughts: i32,
    timestamp: String,
}

#[derive(Clone)]
struct UnifiedThinkServer {
    tool_router: ToolRouter<Self>,
    redis_pool: Arc<Pool>,
}

impl UnifiedThinkServer {
    async fn new() -> Result<Self> {
        // Redis connection configuration
        let redis_url = "redis://:legacymind_redis_pass@192.168.1.160:6379/0";
        let cfg = Config::from_url(redis_url);
        let pool = cfg.create_pool(Some(Runtime::Tokio1))?;
        
        // Test the connection
        let mut conn = pool.get().await?;
        let _: String = redis::cmd("PING").query_async(&mut conn).await?;
        tracing::info!("Redis connection established");
        
        Ok(Self {
            tool_router: Self::tool_router(),
            redis_pool: Arc::new(pool),
        })
    }
}

#[tool_router]
impl UnifiedThinkServer {
    #[tool(description = "Capture and process thoughts from UnifiedIntelligence instances")]
    pub async fn ui_think(
        &self,
        params: Parameters<UiThinkParams>,
    ) -> Result<CallToolResult, ErrorData> {
        // Generate UUID for the thought
        let thought_id = Uuid::new_v4().to_string();
        
        // Get instance_id from environment variable
        let instance_id = env::var("INSTANCE_ID").unwrap_or_else(|_| "test".to_string());
        
        // Create the thought record
        let thought_record = ThoughtRecord {
            id: thought_id.clone(),
            instance: instance_id.clone(),
            thought: params.0.thought,
            thought_number: params.0.thought_number,
            total_thoughts: params.0.total_thoughts,
            timestamp: Utc::now().to_rfc3339(),
        };
        
        // Log the JSON to stderr
        match serde_json::to_string_pretty(&thought_record) {
            Ok(json_record) => {
                tracing::info!("Storing thought: {}", json_record);
            }
            Err(e) => {
                tracing::error!("Failed to serialize thought record: {}", e);
            }
        }
        
        // Store in Redis using JSON.SET
        let key = format!("thought:{}:{}", instance_id, thought_id);
        let json_value = serde_json::to_value(&thought_record)
            .map_err(|e| ErrorData::internal_error(format!("Failed to serialize thought: {}", e), None))?;
        
        // Get connection from pool
        let mut conn = self.redis_pool.get().await
            .map_err(|e| ErrorData::internal_error(format!("Failed to get Redis connection: {}", e), None))?;
        
        // Use JSON.SET command
        let _: () = redis::cmd("JSON.SET")
            .arg(&key)
            .arg("$")
            .arg(json_value.to_string())
            .query_async(&mut *conn)
            .await
            .map_err(|e| ErrorData::internal_error(format!("Failed to store thought in Redis: {}", e), None))?;
        
        tracing::info!("Thought stored in Redis at key: {}", key);
        
        // Return response including next_thought_needed status
        let response = json!({
            "status": "stored",
            "thought_id": thought_id,
            "next_thought_needed": params.0.next_thought_needed
        });
        
        let content = Content::json(response)
            .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
        
        Ok(CallToolResult::success(vec![content]))
    }
}

#[tool_handler]
impl ServerHandler for UnifiedThinkServer {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            protocol_version: ProtocolVersion::V_2024_11_05,
            capabilities: ServerCapabilities::builder()
                .enable_tools()
                .build(),
            server_info: Implementation {
                name: "unified-think".into(),
                version: "0.1.0".into(),
            },
            instructions: Some("UnifiedThink MCP Server for capturing thoughts with Redis persistence".into()),
        }
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing to stderr for MCP compatibility
    tracing_subscriber::fmt()
        .with_target(false)
        .with_ansi(false)
        .with_writer(std::io::stderr)
        .init();
    
    let service = UnifiedThinkServer::new().await?;
    
    // Start the MCP server on stdio transport
    let server = service.serve(stdio()).await?;
    
    // This keeps the server running until the transport closes
    server.waiting().await?;
    
    eprintln!("Server shutting down");
    Ok(())
}