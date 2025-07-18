use std::sync::Arc;
use std::future::Future;
use rmcp::{
    handler::server::{router::tool::ToolRouter, tool::Parameters},
    model::{CallToolResult, Content, ErrorData, ServerCapabilities, ServerInfo},
    ServerHandler,
};
use rmcp_macros::{tool, tool_handler, tool_router};
use tracing;

use crate::error::UnifiedIntelligenceError;
use crate::models::{UiThinkParams, UiRecallParams, UiRecallFeedbackParams, UiIdentityParams, UiDebugEnvParams};
use crate::redis::RedisManager;
use crate::repository::RedisThoughtRepository;
use crate::handlers::ToolHandlers;
use crate::search_optimization::SearchCache;
use crate::validation::InputValidator;
use crate::rate_limit::RateLimiter;

/// Main service struct for UnifiedIntelligence MCP server
#[derive(Clone)]
pub struct UnifiedIntelligenceService {
    tool_router: ToolRouter<Self>,
    handlers: Arc<ToolHandlers<RedisThoughtRepository>>,
    rate_limiter: Arc<RateLimiter>,
    instance_id: String,
}

impl UnifiedIntelligenceService {
    /// Create a new service instance
    pub async fn new() -> Result<Self, UnifiedIntelligenceError> {
        // Get instance ID from environment
        let instance_id = std::env::var("INSTANCE_ID").unwrap_or_else(|_| "test".to_string());
        tracing::info!("Initializing UnifiedIntelligence service for instance: {}", instance_id);
        
        // Initialize Redis
        let redis_manager = Arc::new(RedisManager::new().await?);
        
        // Store OPENAI_API_KEY in Redis if available
        if let Ok(api_key) = std::env::var("OPENAI_API_KEY") {
            if !api_key.is_empty() {
                redis_manager.store_api_key("openai_api_key", &api_key).await?;
                tracing::info!("Stored OPENAI_API_KEY in Redis");
            }
        } else {
            tracing::warn!("OPENAI_API_KEY not found in environment");
        }
        
        // Initialize Bloom filter for this instance - DISABLED (requires RedisBloom)
        // redis_manager.init_bloom_filter(&instance_id).await?;
        
        // Initialize event stream for this instance
        redis_manager.init_event_stream(&instance_id).await?;
        
        // Initialize vector set for semantic search
        redis_manager.init_vector_set(&instance_id).await?;
        
        // Check for search capability
        let search_available = Arc::new(std::sync::atomic::AtomicBool::new(false));
        let search_enabled = redis_manager.create_search_index().await?;
        search_available.store(search_enabled, std::sync::atomic::Ordering::SeqCst);
        
        // Create search cache (5 minute TTL)
        let search_cache = Arc::new(std::sync::Mutex::new(SearchCache::new(300)));
        
        // Create repository with cache
        let repository = Arc::new(RedisThoughtRepository::new(
            redis_manager.clone(),
            search_available.clone(),
            search_cache.clone(),
            instance_id.clone(),
        ));
        
        // Create validator
        let validator = Arc::new(InputValidator::new());
        
        // Create rate limiter (100 requests per minute - reasonable for AI instances)
        let rate_limiter = Arc::new(RateLimiter::new(100, 60));
        
        // Create handlers
        let handlers = Arc::new(ToolHandlers::new(
            repository,
            instance_id.clone(),
            validator,
            search_cache,
            search_available,
        ));
        
        Ok(Self {
            tool_router: Self::tool_router(),
            handlers,
            rate_limiter,
            instance_id,
        })
    }
}

#[tool_router]
impl UnifiedIntelligenceService {
    #[tool(description = "Capture and process thoughts with optional chaining support")]
    pub async fn ui_think(
        &self,
        params: Parameters<UiThinkParams>,
    ) -> std::result::Result<CallToolResult, ErrorData> {
        // Check rate limit
        if let Err(e) = self.rate_limiter.check_rate_limit(&self.instance_id).await {
            tracing::warn!("Rate limit hit for instance {}: {}", self.instance_id, e);
            return Err(ErrorData::invalid_params(
                format!("Rate limit exceeded. Please slow down your requests."), 
                None
            ));
        }
        
        match self.handlers.ui_think(params.0).await {
            Ok(response) => {
                let content = Content::json(response)
                    .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            },
            Err(e) => {
                tracing::error!("ui_think error: {}", e);
                Err(ErrorData::internal_error(e.to_string(), None))
            }
        }
    }
    
    #[tool(description = "Search, retrieve, and manipulate stored thoughts")]
    pub async fn ui_recall(
        &self,
        params: Parameters<UiRecallParams>,
    ) -> std::result::Result<CallToolResult, ErrorData> {
        // Check rate limit
        if let Err(e) = self.rate_limiter.check_rate_limit(&self.instance_id).await {
            tracing::warn!("Rate limit hit for instance {}: {}", self.instance_id, e);
            return Err(ErrorData::invalid_params(
                format!("Rate limit exceeded. Please slow down your requests."), 
                None
            ));
        }
        
        match self.handlers.ui_recall(params.0).await {
            Ok(response) => {
                let content = Content::json(response)
                    .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            },
            Err(e) => {
                tracing::error!("ui_recall error: {}", e);
                Err(ErrorData::internal_error(e.to_string(), None))
            }
        }
    }
    
    #[tool(description = "Record feedback on search results to improve future searches")]
    pub async fn ui_recall_feedback(
        &self,
        params: Parameters<UiRecallFeedbackParams>,
    ) -> std::result::Result<CallToolResult, ErrorData> {
        // Check rate limit
        if let Err(e) = self.rate_limiter.check_rate_limit(&self.instance_id).await {
            tracing::warn!("Rate limit hit for instance {}: {}", self.instance_id, e);
            return Err(ErrorData::invalid_params(
                format!("Rate limit exceeded. Please slow down your requests."), 
                None
            ));
        }
        
        match self.handlers.ui_recall_feedback(params.0).await {
            Ok(response) => {
                let content = Content::json(response)
                    .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            },
            Err(e) => {
                tracing::error!("ui_recall_feedback error: {}", e);
                Err(ErrorData::internal_error(e.to_string(), None))
            }
        }
    }
    
    #[tool(description = "View and manage persistent identity through structured categories")]
    pub async fn ui_identity(
        &self,
        params: Parameters<UiIdentityParams>,
    ) -> std::result::Result<CallToolResult, ErrorData> {
        // Check rate limit
        if let Err(e) = self.rate_limiter.check_rate_limit(&self.instance_id).await {
            tracing::warn!("Rate limit hit for instance {}: {}", self.instance_id, e);
            return Err(ErrorData::invalid_params(
                format!("Rate limit exceeded. Please slow down your requests."), 
                None
            ));
        }
        
        match self.handlers.ui_identity(params.0).await {
            Ok(response) => {
                let content = Content::json(response)
                    .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            },
            Err(e) => {
                tracing::error!("ui_identity error: {}", e);
                Err(ErrorData::internal_error(e.to_string(), None))
            }
        }
    }
    
    #[tool(description = "Debug tool to view masked environment variables (OPENAI_API_KEY, REDIS_PASSWORD, INSTANCE_ID)")]
    pub async fn ui_debug_env(
        &self,
        params: Parameters<UiDebugEnvParams>,
    ) -> std::result::Result<CallToolResult, ErrorData> {
        match self.handlers.ui_debug_env(params.0).await {
            Ok(response) => {
                let content = Content::json(response)
                    .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            },
            Err(e) => {
                tracing::error!("ui_debug_env error: {}", e);
                Err(ErrorData::internal_error(e.to_string(), None))
            }
        }
    }
}

#[tool_handler]
impl ServerHandler for UnifiedIntelligenceService {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            protocol_version: rmcp::model::ProtocolVersion::V_2024_11_05,
            server_info: rmcp::model::Implementation {
                name: "unified-intelligence".into(),
                version: "3.0.0".into(),
            },
            capabilities: ServerCapabilities {
                tools: Some(Default::default()),
                ..Default::default()
            },
            instructions: Some("UnifiedIntelligence MCP Server for Redis-backed thought storage".into()),
        }
    }
}