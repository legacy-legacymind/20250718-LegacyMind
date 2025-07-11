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
    #[schemars(description = "Optional chain ID to link thoughts together")]
    chain_id: Option<String>,
}

#[derive(Debug, Deserialize, schemars::JsonSchema)]
struct UiRecallParams {
    #[schemars(description = "Chain ID to retrieve thoughts from")]
    chain_id: String,
    #[schemars(description = "Maximum number of thoughts to retrieve (default: 50)")]
    limit: Option<usize>,
}

#[derive(Debug, Deserialize, schemars::JsonSchema)]
struct UiListChainsParams {
    #[schemars(description = "Instance ID to filter by (defaults to current instance)")]
    instance_id: Option<String>,
    #[schemars(description = "Maximum number of chains to list (default: 20)")]
    limit: Option<usize>,
}

#[derive(Debug, Serialize, Deserialize)]
struct ThoughtRecord {
    id: String,
    instance: String,
    thought: String,
    thought_number: i32,
    total_thoughts: i32,
    timestamp: String,
    chain_id: Option<String>,
}

#[derive(Debug, Serialize)]
struct ChainSummary {
    chain_id: String,
    instance: String,
    thought_count: usize,
    first_thought: String,
    last_updated: String,
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
        
        // Generate or use provided chain_id
        let chain_id = params.0.chain_id.clone().unwrap_or_else(|| Uuid::new_v4().to_string());
        
        // Clone thought content for reuse
        let thought_content = params.0.thought.clone();
        
        // Create the thought record
        let thought_record = ThoughtRecord {
            id: thought_id.clone(),
            instance: instance_id.clone(),
            thought: thought_content.clone(),
            thought_number: params.0.thought_number,
            total_thoughts: params.0.total_thoughts,
            timestamp: Utc::now().to_rfc3339(),
            chain_id: Some(chain_id.clone()),
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
        let thought_key = format!("thought:{}:{}", instance_id, thought_id);
        let json_value = serde_json::to_value(&thought_record)
            .map_err(|e| ErrorData::internal_error(format!("Failed to serialize thought: {}", e), None))?;
        
        // Get connection from pool
        let mut conn = self.redis_pool.get().await
            .map_err(|e| ErrorData::internal_error(format!("Failed to get Redis connection: {}", e), None))?;
        
        // Store the individual thought
        let _: () = redis::cmd("JSON.SET")
            .arg(&thought_key)
            .arg("$")
            .arg(json_value.to_string())
            .query_async(&mut *conn)
            .await
            .map_err(|e| ErrorData::internal_error(format!("Failed to store thought in Redis: {}", e), None))?;
        
        // Add thought to chain index (using sorted set with timestamp)
        let chain_key = format!("chain:{}:{}", instance_id, chain_id);
        let timestamp = Utc::now().timestamp_millis() as f64;
        let _: () = redis::cmd("ZADD")
            .arg(&chain_key)
            .arg(timestamp)
            .arg(&thought_id)
            .query_async(&mut *conn)
            .await
            .map_err(|e| ErrorData::internal_error(format!("Failed to add thought to chain: {}", e), None))?;
        
        // Update chain metadata
        let chain_meta_key = format!("chain_meta:{}:{}", instance_id, chain_id);
        let chain_meta = json!({
            "chain_id": chain_id,
            "instance": instance_id,
            "last_updated": Utc::now().to_rfc3339(),
            "first_thought": if params.0.thought_number == 1 { Some(thought_content.clone()) } else { None }
        });
        
        if params.0.thought_number == 1 {
            // Create new chain metadata
            let _: () = redis::cmd("JSON.SET")
                .arg(&chain_meta_key)
                .arg("$")
                .arg(chain_meta.to_string())
                .query_async(&mut *conn)
                .await
                .map_err(|e| ErrorData::internal_error(format!("Failed to store chain metadata: {}", e), None))?;
        } else {
            // Update existing chain metadata last_updated
            let _: () = redis::cmd("JSON.SET")
                .arg(&chain_meta_key)
                .arg("$.last_updated")
                .arg(format!("\"{}\"", Utc::now().to_rfc3339()))
                .query_async(&mut *conn)
                .await
                .map_err(|e| ErrorData::internal_error(format!("Failed to update chain metadata: {}", e), None))?;
        }
        
        tracing::info!("Thought stored in Redis at key: {} and added to chain: {}", thought_key, chain_key);
        
        // Return response including next_thought_needed status and chain_id
        let response = json!({
            "status": "stored",
            "thought_id": thought_id,
            "chain_id": chain_id,
            "next_thought_needed": params.0.next_thought_needed
        });
        
        let content = Content::json(response)
            .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
        
        Ok(CallToolResult::success(vec![content]))
    }
    
    #[tool(description = "Retrieve thoughts from a specific chain")]
    pub async fn ui_recall(
        &self,
        params: Parameters<UiRecallParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let instance_id = env::var("INSTANCE_ID").unwrap_or_else(|_| "test".to_string());
        let limit = params.0.limit.unwrap_or(50);
        
        // Get connection from pool
        let mut conn = self.redis_pool.get().await
            .map_err(|e| ErrorData::internal_error(format!("Failed to get Redis connection: {}", e), None))?;
        
        // Get thought IDs from chain (in chronological order)
        let chain_key = format!("chain:{}:{}", instance_id, params.0.chain_id);
        let thought_ids: Vec<String> = redis::cmd("ZRANGE")
            .arg(&chain_key)
            .arg(0)
            .arg(limit as isize - 1)
            .query_async(&mut *conn)
            .await
            .map_err(|e| ErrorData::internal_error(format!("Failed to retrieve chain: {}", e), None))?;
        
        if thought_ids.is_empty() {
            let response = json!({
                "chain_id": params.0.chain_id,
                "thoughts": [],
                "total": 0
            });
            
            let content = Content::json(response)
                .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
            
            return Ok(CallToolResult::success(vec![content]));
        }
        
        // Retrieve each thought
        let mut thoughts = Vec::new();
        for thought_id in &thought_ids {
            let thought_key = format!("thought:{}:{}", instance_id, thought_id);
            let thought_json: Option<String> = redis::cmd("JSON.GET")
                .arg(&thought_key)
                .arg("$")
                .query_async(&mut *conn)
                .await
                .map_err(|e| ErrorData::internal_error(format!("Failed to retrieve thought {}: {}", thought_id, e), None))?;
            
            if let Some(json_str) = thought_json {
                // Parse the JSON array response from Redis JSON.GET
                if let Ok(json_array) = serde_json::from_str::<Vec<serde_json::Value>>(&json_str) {
                    if let Some(thought_value) = json_array.first() {
                        if let Ok(thought_record) = serde_json::from_value::<ThoughtRecord>(thought_value.clone()) {
                            thoughts.push(thought_record);
                        }
                    }
                }
            }
        }
        
        let response = json!({
            "chain_id": params.0.chain_id,
            "thoughts": thoughts,
            "total": thoughts.len()
        });
        
        let content = Content::json(response)
            .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
        
        Ok(CallToolResult::success(vec![content]))
    }
    
    #[tool(description = "List available thought chains")]
    pub async fn ui_list_chains(
        &self,
        params: Parameters<UiListChainsParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let instance_id = params.0.instance_id.clone()
            .unwrap_or_else(|| env::var("INSTANCE_ID").unwrap_or_else(|_| "test".to_string()));
        let limit = params.0.limit.unwrap_or(20);
        
        // Get connection from pool
        let mut conn = self.redis_pool.get().await
            .map_err(|e| ErrorData::internal_error(format!("Failed to get Redis connection: {}", e), None))?;
        
        // Find all chain metadata keys for this instance
        let pattern = format!("chain_meta:{}:*", instance_id);
        let chain_keys: Vec<String> = redis::cmd("KEYS")
            .arg(&pattern)
            .query_async(&mut *conn)
            .await
            .map_err(|e| ErrorData::internal_error(format!("Failed to list chain keys: {}", e), None))?;
        
        let mut chains = Vec::new();
        for chain_key in chain_keys.iter().take(limit) {
            // Get chain metadata
            let chain_meta_json: Option<String> = redis::cmd("JSON.GET")
                .arg(chain_key)
                .arg("$")
                .query_async(&mut *conn)
                .await
                .map_err(|e| ErrorData::internal_error(format!("Failed to retrieve chain metadata: {}", e), None))?;
            
            if let Some(json_str) = chain_meta_json {
                if let Ok(json_array) = serde_json::from_str::<Vec<serde_json::Value>>(&json_str) {
                    if let Some(meta_value) = json_array.first() {
                        let chain_id = meta_value.get("chain_id").and_then(|v| v.as_str()).unwrap_or("unknown");
                        let last_updated = meta_value.get("last_updated").and_then(|v| v.as_str()).unwrap_or("unknown");
                        let first_thought = meta_value.get("first_thought").and_then(|v| v.as_str()).unwrap_or("No content");
                        
                        // Get thought count from chain
                        let chain_data_key = format!("chain:{}:{}", instance_id, chain_id);
                        let thought_count: usize = redis::cmd("ZCARD")
                            .arg(&chain_data_key)
                            .query_async(&mut *conn)
                            .await
                            .unwrap_or(0);
                        
                        let chain_summary = ChainSummary {
                            chain_id: chain_id.to_string(),
                            instance: instance_id.clone(),
                            thought_count,
                            first_thought: first_thought.to_string(),
                            last_updated: last_updated.to_string(),
                        };
                        
                        chains.push(chain_summary);
                    }
                }
            }
        }
        
        let response = json!({
            "instance": instance_id,
            "chains": chains,
            "total": chains.len()
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