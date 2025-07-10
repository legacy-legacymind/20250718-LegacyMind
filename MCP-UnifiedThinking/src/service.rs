use anyhow::Result;
use rmcp::{
    handler::server::{router::tool::ToolRouter, tool::Parameters},
    model::{CallToolResult, Content, ErrorData, Implementation, ProtocolVersion, ServerCapabilities, ServerInfo},
    tool, ServerHandler,
};
use rmcp_macros::{tool_handler, tool_router};
use std::sync::Arc;
use crate::{
    storage::redis_pool::RedisPool,
    tools::think::{ut_remember_impl, ut_think_impl, RememberParams, ThinkParams},
};

#[derive(Clone)]
pub struct ServiceConfig {
    pub instance_id: String,
    pub redis_pool: RedisPool,
}

#[derive(Clone)]
pub struct UnifiedThinkingService {
    pub tool_router: ToolRouter<Self>,
    pub config: Arc<ServiceConfig>,
    pub redis_pool: RedisPool,
}

impl UnifiedThinkingService {
    pub async fn new(config: ServiceConfig) -> Result<Self> {
        Ok(Self {
            tool_router: Self::tool_router(),
            redis_pool: config.redis_pool.clone(),
            config: Arc::new(config),
        })
    }
}

#[tool_router]
impl UnifiedThinkingService {
    #[tool(description = "The core thinking engine. Applies a mandatory framework to content.")]
    pub async fn ut_think(
        &self,
        params: Parameters<ThinkParams>,
    ) -> Result<CallToolResult, ErrorData> {
        ut_think_impl(self, params.0).await
            .map(|result| {
                let content = Content::json(result)?;
                Ok(CallToolResult::success(vec![content]))
            })
            .and_then(|res| res) // Flatten the Result<Result<...>>
            .map_err(|e| ErrorData::internal_error(format!("{:?}", e), None))
    }

    #[tool(description = "Lists all thought chains for the current instance.")]
    pub async fn ut_remember(
        &self,
        params: Parameters<RememberParams>,
    ) -> Result<CallToolResult, ErrorData> {
        ut_remember_impl(self, params.0).await
            .map(|result| {
                let content = Content::json(result)?;
                Ok(CallToolResult::success(vec![content]))
            })
            .and_then(|res| res) // Flatten the Result<Result<...>>
            .map_err(|e| ErrorData::internal_error(format!("{:?}", e), None))
    }
}

#[tool_handler]
impl ServerHandler for UnifiedThinkingService {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            protocol_version: ProtocolVersion::V_2024_11_05,
            capabilities: ServerCapabilities::builder()
                .enable_tools()
                .build(),
            server_info: Implementation {
                name: "mcp-unified-thinking".into(),
                version: "0.1.0".into(),
            },
            instructions: Some("A tool for structured, framework-driven thinking.".into()),
        }
    }
}
