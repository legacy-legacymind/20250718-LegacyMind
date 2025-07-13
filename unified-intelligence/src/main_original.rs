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
use std::collections::HashMap;
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
    #[schemars(description = "Search query to find thoughts (e.g., 'Redis performance')")]
    query: Option<String>,
    #[schemars(description = "Chain ID to retrieve thoughts from (use this OR query, not both)")]
    chain_id: Option<String>,
    #[schemars(description = "Maximum number of results to return (default: 50)")]
    limit: Option<usize>,
    #[schemars(description = "Action to perform on results: search, merge, analyze, branch, continue")]
    action: Option<String>,
    #[schemars(description = "Additional parameters for the action (JSON object)")]
    action_params: Option<serde_json::Value>,
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
        
        let server = Self {
            tool_router: Self::tool_router(),
            redis_pool: Arc::new(pool),
        };
        
        // Create search index for thoughts
        server.create_search_index().await?;
        
        Ok(server)
    }
    
    async fn create_search_index(&self) -> Result<()> {
        let mut conn = self.redis_pool.get().await?;
        
        // Check if index already exists
        let index_exists: Result<Vec<String>, _> = redis::cmd("FT._LIST")
            .query_async(&mut *conn)
            .await;
        
        if let Ok(indices) = index_exists {
            if indices.contains(&"idx:thoughts".to_string()) {
                tracing::info!("Search index already exists");
                return Ok(());
            }
        }
        
        // Create the index on JSON fields
        let result: Result<String, _> = redis::cmd("FT.CREATE")
            .arg("idx:thoughts")
            .arg("ON").arg("JSON")
            .arg("PREFIX").arg("1").arg("thought:")
            .arg("SCHEMA")
            .arg("$.thought").arg("AS").arg("content").arg("TEXT")
            .arg("$.instance").arg("AS").arg("instance").arg("TAG")
            .arg("$.chain_id").arg("AS").arg("chain_id").arg("TAG")
            .arg("$.timestamp").arg("AS").arg("timestamp").arg("TEXT")
            .query_async(&mut *conn)
            .await;
        
        match result {
            Ok(_) => {
                tracing::info!("Search index created successfully");
                Ok(())
            }
            Err(e) => {
                tracing::warn!("Failed to create search index: {} - continuing without search", e);
                Ok(()) // Don't fail startup if search isn't available
            }
        }
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
    
    #[tool(description = "Search for thoughts or retrieve from chain, with optional actions")]
    pub async fn ui_recall(
        &self,
        params: Parameters<UiRecallParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let instance_id = env::var("INSTANCE_ID").unwrap_or_else(|_| "test".to_string());
        let limit = params.0.limit.unwrap_or(50);
        
        // Get connection from pool
        let mut conn = self.redis_pool.get().await
            .map_err(|e| ErrorData::internal_error(format!("Failed to get Redis connection: {}", e), None))?;
        
        // Determine if we're searching or retrieving a specific chain
        let (thoughts, source_info) = if let Some(query) = &params.0.query {
            // Search mode
            self.search_thoughts(&mut conn, query, &instance_id, limit).await?
        } else if let Some(chain_id) = &params.0.chain_id {
            // Chain retrieval mode (existing functionality)
            let thoughts = self.get_chain_thoughts(&mut conn, chain_id, &instance_id, limit).await?;
            let info = json!({
                "mode": "chain",
                "chain_id": chain_id,
                "total": thoughts.len()
            });
            (thoughts, info)
        } else {
            return Err(ErrorData::invalid_params("Must provide either 'query' or 'chain_id'", None));
        };
        
        // Handle actions if specified
        let response = if let Some(action) = &params.0.action {
            match action.as_str() {
                "search" | "" | "none" => {
                    // Just return search results
                    json!({
                        "source": source_info,
                        "thoughts": thoughts,
                        "available_actions": ["branch", "merge", "analyze", "continue"]
                    })
                }
                "analyze" => {
                    self.analyze_thoughts(&thoughts, &params.0.action_params).await?
                }
                "merge" => {
                    self.merge_chains(&mut conn, &thoughts, &params.0.action_params, &instance_id).await?
                }
                "branch" => {
                    self.branch_from_thought(&mut conn, &params.0.action_params, &instance_id).await?
                }
                "continue" => {
                    self.continue_chain(&mut conn, &params.0.action_params, &instance_id).await?
                }
                _ => {
                    return Err(ErrorData::invalid_params(
                        format!("Unknown action: {}. Valid actions: search, analyze, merge, branch, continue", action), 
                        None
                    ));
                }
            }
        } else {
            // No action specified, just return results
            json!({
                "source": source_info,
                "thoughts": thoughts,
                "available_actions": ["branch", "merge", "analyze", "continue"]
            })
        };
        
        let content = Content::json(response)
            .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
        
        Ok(CallToolResult::success(vec![content]))
    }
    
    // Helper method to search thoughts
    async fn search_thoughts(
        &self,
        conn: &mut deadpool_redis::Connection,
        query: &str,
        instance_id: &str,
        limit: usize
    ) -> Result<(Vec<ThoughtRecord>, serde_json::Value), ErrorData> {
        // Try to use FT.SEARCH if available
        let search_query = format!("@content:{}", query);
        let search_result: Result<Vec<(String, Vec<(String, String)>)>, _> = redis::cmd("FT.SEARCH")
            .arg("idx:thoughts")
            .arg(&search_query)
            .arg("LIMIT").arg(0).arg(limit)
            .query_async(&mut *conn)
            .await;
        
        let thoughts = if let Ok(results) = search_result {
            // Parse search results
            let mut found_thoughts = Vec::new();
            for (i, (key, _fields)) in results.iter().enumerate() {
                if i == 0 { continue; } // Skip count
                
                // Get the full thought record
                let json_result: Result<Option<String>, _> = redis::cmd("JSON.GET")
                    .arg(key)
                    .arg("$")
                    .query_async(&mut *conn)
                    .await;
                
                if let Ok(Some(json_str)) = json_result {
                    if let Ok(json_array) = serde_json::from_str::<Vec<serde_json::Value>>(&json_str) {
                        if let Some(thought_value) = json_array.first() {
                            if let Ok(thought) = serde_json::from_value::<ThoughtRecord>(thought_value.clone()) {
                                found_thoughts.push(thought);
                            }
                        }
                    }
                }
            }
            found_thoughts
        } else {
            // Fallback: scan all thoughts and do simple substring match
            let pattern = format!("thought:{}:*", instance_id);
            let mut cursor = "0".to_string();
            let mut found_thoughts = Vec::new();
            
            loop {
                let (new_cursor, keys): (String, Vec<String>) = redis::cmd("SCAN")
                    .arg(&cursor)
                    .arg("MATCH").arg(&pattern)
                    .arg("COUNT").arg(100)
                    .query_async(&mut *conn)
                    .await
                    .map_err(|e| ErrorData::internal_error(format!("SCAN failed: {}", e), None))?;
                
                for key in keys {
                    let json_result: Result<Option<String>, _> = redis::cmd("JSON.GET")
                        .arg(&key)
                        .arg("$")
                        .query_async(&mut *conn)
                        .await;
                    
                    if let Ok(Some(json_str)) = json_result
                    {
                        if let Ok(json_array) = serde_json::from_str::<Vec<serde_json::Value>>(&json_str) {
                            if let Some(thought_value) = json_array.first() {
                                if let Ok(thought) = serde_json::from_value::<ThoughtRecord>(thought_value.clone()) {
                                    if thought.thought.to_lowercase().contains(&query.to_lowercase()) {
                                        found_thoughts.push(thought);
                                        if found_thoughts.len() >= limit {
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                
                cursor = new_cursor;
                if cursor == "0" || found_thoughts.len() >= limit {
                    break;
                }
            }
            found_thoughts
        };
        
        let info = json!({
            "mode": "search",
            "query": query,
            "found": thoughts.len()
        });
        
        Ok((thoughts, info))
    }
    
    // Helper method to get thoughts from a specific chain
    async fn get_chain_thoughts(
        &self,
        conn: &mut deadpool_redis::Connection,
        chain_id: &str,
        instance_id: &str,
        limit: usize
    ) -> Result<Vec<ThoughtRecord>, ErrorData> {
        let chain_key = format!("chain:{}:{}", instance_id, chain_id);
        let thought_ids: Vec<String> = redis::cmd("ZRANGE")
            .arg(&chain_key)
            .arg(0)
            .arg(limit as isize - 1)
            .query_async(&mut *conn)
            .await
            .map_err(|e| ErrorData::internal_error(format!("Failed to retrieve chain: {}", e), None))?;
        
        let mut thoughts = Vec::new();
        for thought_id in thought_ids {
            let thought_key = format!("thought:{}:{}", instance_id, thought_id);
            let json_result: Result<Option<String>, _> = redis::cmd("JSON.GET")
                .arg(&thought_key)
                .arg("$")
                .query_async(&mut *conn)
                .await;
            
            if let Ok(Some(json_str)) = json_result
            {
                if let Ok(json_array) = serde_json::from_str::<Vec<serde_json::Value>>(&json_str) {
                    if let Some(thought_value) = json_array.first() {
                        if let Ok(thought) = serde_json::from_value::<ThoughtRecord>(thought_value.clone()) {
                            thoughts.push(thought);
                        }
                    }
                }
            }
        }
        
        Ok(thoughts)
    }
    
    // Analyze thoughts for patterns and insights
    async fn analyze_thoughts(
        &self,
        thoughts: &[ThoughtRecord],
        _params: &Option<serde_json::Value>
    ) -> Result<serde_json::Value, ErrorData> {
        if thoughts.is_empty() {
            return Ok(json!({
                "analysis": {
                    "total_thoughts": 0,
                    "message": "No thoughts to analyze"
                }
            }));
        }
        
        // Basic analysis
        let total = thoughts.len();
        let avg_length = thoughts.iter().map(|t| t.thought.len()).sum::<usize>() / total;
        
        // Find most common words (simple frequency analysis)
        let mut word_freq = HashMap::new();
        for thought in thoughts {
            for word in thought.thought.split_whitespace() {
                let word = word.to_lowercase();
                if word.len() > 3 { // Skip small words
                    *word_freq.entry(word).or_insert(0) += 1;
                }
            }
        }
        
        let mut top_words: Vec<_> = word_freq.into_iter().collect();
        top_words.sort_by(|a, b| b.1.cmp(&a.1));
        top_words.truncate(10);
        
        Ok(json!({
            "analysis": {
                "total_thoughts": total,
                "average_length": avg_length,
                "top_keywords": top_words,
                "chain_distribution": thoughts.iter()
                    .filter_map(|t| t.chain_id.as_ref())
                    .fold(HashMap::new(), |mut acc, chain| {
                        *acc.entry(chain.clone()).or_insert(0) += 1;
                        acc
                    })
            }
        }))
    }
    
    // Merge multiple chains into one
    async fn merge_chains(
        &self,
        conn: &mut deadpool_redis::Connection,
        thoughts: &[ThoughtRecord],
        params: &Option<serde_json::Value>,
        instance_id: &str
    ) -> Result<serde_json::Value, ErrorData> {
        let params = params.as_ref()
            .ok_or_else(|| ErrorData::invalid_params("action_params required for merge", None))?;
        
        let new_chain_name = params.get("new_chain_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| ErrorData::invalid_params("new_chain_name required", None))?;
        
        let new_chain_id = Uuid::new_v4().to_string();
        let new_chain_key = format!("chain:{}:{}", instance_id, new_chain_id);
        
        // Add all thoughts to new chain in chronological order
        let mut pipe = redis::pipe();
        for (i, thought) in thoughts.iter().enumerate() {
            pipe.cmd("ZADD")
                .arg(&new_chain_key)
                .arg(i as f64)
                .arg(&thought.id);
        }
        
        let _: () = pipe.query_async(&mut *conn)
            .await
            .map_err(|e| ErrorData::internal_error(format!("Failed to create merged chain: {}", e), None))?;
        
        Ok(json!({
            "action": "merge",
            "result": {
                "new_chain_id": new_chain_id,
                "new_chain_name": new_chain_name,
                "thought_count": thoughts.len()
            }
        }))
    }
    
    // Branch from a specific thought
    async fn branch_from_thought(
        &self,
        _conn: &mut deadpool_redis::Connection,
        params: &Option<serde_json::Value>,
        _instance_id: &str
    ) -> Result<serde_json::Value, ErrorData> {
        let params = params.as_ref()
            .ok_or_else(|| ErrorData::invalid_params("action_params required for branch", None))?;
        
        let thought_id = params.get("thought_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| ErrorData::invalid_params("thought_id required", None))?;
        
        let new_chain_name = params.get("new_chain_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| ErrorData::invalid_params("new_chain_name required", None))?;
        
        let new_chain_id = Uuid::new_v4().to_string();
        
        Ok(json!({
            "action": "branch",
            "result": {
                "new_chain_id": new_chain_id,
                "new_chain_name": new_chain_name,
                "branched_from": thought_id,
                "message": "Use ui_think with this chain_id to continue the branched chain"
            }
        }))
    }
    
    // Continue an existing chain
    async fn continue_chain(
        &self,
        _conn: &mut deadpool_redis::Connection,
        params: &Option<serde_json::Value>,
        _instance_id: &str
    ) -> Result<serde_json::Value, ErrorData> {
        let params = params.as_ref()
            .ok_or_else(|| ErrorData::invalid_params("action_params required for continue", None))?;
        
        let chain_id = params.get("chain_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| ErrorData::invalid_params("chain_id required", None))?;
        
        Ok(json!({
            "action": "continue",
            "result": {
                "chain_id": chain_id,
                "message": "Use ui_think with this chain_id to add more thoughts"
            }
        }))
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