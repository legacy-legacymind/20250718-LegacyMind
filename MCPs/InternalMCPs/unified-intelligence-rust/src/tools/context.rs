use anyhow::{anyhow, Context, Result};
use rmcp::{handler::server::tool::Parameters, model::{CallToolResult, Content, ErrorData}};
use serde::Deserialize;
use schemars::JsonSchema;

use crate::service::UnifiedIntelligenceService;
use crate::storage::{redis_pool, Identity};

#[derive(Debug, Deserialize, JsonSchema)]
pub struct ContextParams {
    action: String,
    data: Option<serde_json::Value>,
}

pub async fn ui_context_impl(
    service: &UnifiedIntelligenceService,
    params: Parameters<ContextParams>,
) -> Result<CallToolResult, ErrorData> {
    let params = params.0;
    let result = async {
        match params.action.as_str() {
            "set_identity" => {
                let data = params.data.context("Data is required for set_identity")?;
                service.handle_set_identity(data).await
            }
            _ => Err(anyhow!("Unknown action: {}", params.action)),
        }
    }.await;

    result.map_err(|e| {
        tracing::error!(error = ?e, "ui_context action '{}' failed", params.action);
        ErrorData::internal_error(format!("{:?}", e), None)
    })
}

impl UnifiedIntelligenceService {
    async fn handle_set_identity(&self, data: serde_json::Value) -> Result<CallToolResult> {
        let identity: Identity = serde_json::from_value(data).context("Failed to deserialize identity")?;
        let identity_key = format!("{}:identity", self.get_config().instance_id);
        
        redis_pool::set_json(self.get_redis_pool(), &identity_key, &identity)
            .await
            .context("Failed to store identity in Redis")?;
        
        Ok(CallToolResult::success(vec![Content::text(serde_json::to_string(&serde_json::json!({
            "success": true,
        }))?)]))
    }
}
