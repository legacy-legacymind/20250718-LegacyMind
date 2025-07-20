use crate::error::UnifiedMindError;
use crate::handlers::RecallHandler;
use crate::models::UmRecallParams;
use crate::redis::RedisClient;
use rmcp::{
    handler::server::{router::tool::ToolRouter, tool::Parameters},
    model::{CallToolResult, Content, ErrorData, ServerCapabilities, ServerInfo},
    ServerHandler, ServiceExt, transport,
};
use rmcp_macros::{tool, tool_handler, tool_router};
use std::future::Future;
use std::sync::Arc;
use tracing::{error, info};

#[derive(Clone)]
pub struct UnifiedMindService {
    tool_router: ToolRouter<Self>,
    recall_handler: Arc<RecallHandler>,
}

impl UnifiedMindService {
    pub async fn new() -> std::result::Result<Self, UnifiedMindError> {
        info!("Initializing UnifiedMind service");
        
        let redis_client = RedisClient::new().await?;
        let recall_handler = RecallHandler::new(redis_client).await?;
        
        Ok(Self {
            tool_router: Self::tool_router(),
            recall_handler: Arc::new(recall_handler),
        })
    }
}

#[tool_router]
impl UnifiedMindService {
    #[tool(
        name = "um_recall",
        description = "Search and retrieve thoughts with text-based search and temporal/usage weighting"
    )]
    async fn um_recall(&self, params: Parameters<UmRecallParams>) -> std::result::Result<CallToolResult, ErrorData> {
        info!("Processing um_recall request");
        
        match self.recall_handler.recall(params.0).await {
            Ok(result) => {
                let content = Content::json(result)
                    .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            },
            Err(e) => {
                error!("Error in um_recall: {}", e);
                Err(ErrorData::internal_error(e.to_string(), None))
            }
        }
    }
}

#[tool_handler]
impl ServerHandler for UnifiedMindService {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            protocol_version: rmcp::model::ProtocolVersion::V_2024_11_05,
            server_info: rmcp::model::Implementation {
                name: "unified-mind".into(),
                version: env!("CARGO_PKG_VERSION").into(),
            },
            capabilities: ServerCapabilities {
                tools: Some(Default::default()),
                ..Default::default()
            },
            instructions: Some("UnifiedMind MCP Server - Text-based search with temporal and usage weighting for CC_thoughts collection".into()),
        }
    }
}

pub async fn run_service() -> std::result::Result<(), UnifiedMindError> {
    let service = UnifiedMindService::new().await?;
    info!("Starting UnifiedMind MCP server");
    
    // Use the same pattern as unified-intelligence
    let server = service.serve(transport::stdio()).await
        .map_err(|e| crate::error::UnifiedMindError::ServerInit(e.to_string()))?;
    
    // This keeps the server running until the transport closes
    server.waiting().await
        .map_err(|e| crate::error::UnifiedMindError::ServerInit(e.to_string()))?;
    
    info!("Server shutting down");
    Ok(())
}