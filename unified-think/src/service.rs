use std::sync::Arc;
use std::future::Future;
use rmcp::{
    handler::server::{router::tool::ToolRouter, tool::Parameters},
    model::{CallToolResult, Content, ErrorData, ServerCapabilities, ServerInfo},
    ServerHandler,
};
use rmcp_macros::{tool, tool_handler, tool_router};
use tracing;

use crate::error::UnifiedThinkError;
use crate::models::{UiThinkParams, UiRecallParams, UiIdentityParams};
use crate::redis::RedisManager;
use crate::repository::RedisThoughtRepository;
use crate::handlers::ToolHandlers;
use crate::search_optimization::SearchCache;
use crate::validation::InputValidator;
use crate::rate_limit::RateLimiter;

/// Main service struct for UnifiedThink MCP server
#[derive(Clone)]
pub struct UnifiedThinkService {
    tool_router: ToolRouter<Self>,
    handlers: Arc<ToolHandlers<RedisThoughtRepository>>,
    rate_limiter: Arc<RateLimiter>,
    instance_id: String,
}

impl UnifiedThinkService {
    /// Create a new service instance
    pub async fn new() -> Result<Self, UnifiedThinkError> {
        // Get instance ID from environment
        let instance_id = std::env::var("INSTANCE_ID").unwrap_or_else(|_| "test".to_string());
        tracing::info!("Initializing UnifiedThink service for instance: {}", instance_id);
        
        // Initialize Redis
        let redis_manager = Arc::new(RedisManager::new().await?);
        
        // Initialize Bloom filter for this instance
        redis_manager.init_bloom_filter(&instance_id).await?;
        
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
impl UnifiedThinkService {
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
}

#[tool_handler]
impl ServerHandler for UnifiedThinkService {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            protocol_version: rmcp::model::ProtocolVersion::V_2024_11_05,
            server_info: rmcp::model::Implementation {
                name: "unified-think".into(),
                version: "3.0.0".into(),
            },
            capabilities: ServerCapabilities {
                tools: Some(Default::default()),
                ..Default::default()
            },
            instructions: Some("UnifiedThink MCP Server for Redis-backed thought storage".into()),
        }
    }
}