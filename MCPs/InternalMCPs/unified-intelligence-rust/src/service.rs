use anyhow::Result;
use rmcp::{ServerHandler, handler::server::router::tool::ToolRouter, handler::server::tool::Parameters, model::{*, ErrorData}, tool};
use rmcp_macros::{tool_handler, tool_router};
use std::sync::Arc;
use std::collections::HashMap;
use tokio::sync::RwLock;
use std::future::Future;

use crate::storage::redis_pool::{self, RedisPool};
use crate::tools::think::ThinkParams;
use crate::tools::context::ContextParams;
use crate::tools::bot::BotParams;
use crate::utils::SessionResolver;

#[derive(Clone)]
pub struct ServiceConfig {
    pub redis_url: String,
    pub instance_id: String,
}

#[derive(Clone)]
pub struct Session {
    // ... fields ...
}

#[derive(Clone)]
pub struct UnifiedIntelligenceService {
    redis_pool: Arc<RedisPool>,
    sessions: Arc<RwLock<HashMap<String, Session>>>,
    tool_router: ToolRouter<Self>,
    config: Arc<ServiceConfig>,
    session_resolver: Arc<SessionResolver>,
}

#[tool_router]
impl UnifiedIntelligenceService {
    pub async fn new(config: ServiceConfig) -> Result<Self> {
        let redis_pool = Arc::new(redis_pool::create_pool(&config.redis_url).await?);
        
        let session_resolver = Arc::new(SessionResolver::new(Arc::clone(&redis_pool)));
        
        Ok(Self {
            redis_pool,
            sessions: Arc::new(RwLock::new(HashMap::new())),
            tool_router: Self::tool_router(),
            config: Arc::new(config),
            session_resolver,
        })
    }
    
    pub fn get_redis_pool(&self) -> &Arc<RedisPool> {
        &self.redis_pool
    }

    pub fn get_config(&self) -> &Arc<ServiceConfig> {
        &self.config
    }

    #[tool(description = "The Engine - Low-level control over thinking, sessions, and frameworks")]
    pub async fn ui_think(
        &self,
        params: Parameters<ThinkParams>,
    ) -> Result<CallToolResult, ErrorData> {
        crate::tools::think::ui_think_impl(self, params).await
    }
    
    #[tool(description = "The Dashboard - Manages active state including identity, task, goals")]
    pub async fn ui_context(
        &self,
        params: Parameters<ContextParams>,
    ) -> Result<CallToolResult, ErrorData> {
        crate::tools::context::ui_context_impl(self, params).await
    }
    
    #[tool(description = "The Appendage - High-level conversational interface")]
    pub async fn ui_bot(
        &self,
        params: Parameters<BotParams>,
    ) -> Result<CallToolResult, ErrorData> {
        crate::tools::bot::ui_bot_impl(self, params).await
    }
}

#[tool_handler]
impl ServerHandler for UnifiedIntelligenceService {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            protocol_version: ProtocolVersion::V_2024_11_05,
            capabilities: ServerCapabilities::builder()
                .enable_tools()
                .build(),
            server_info: Implementation {
                name: "unified-intelligence".into(),
                version: "3.1.0-rust".into(),
            },
            instructions: Some("Cognitive enhancement through thinking frameworks.".into()),
        }
    }
}