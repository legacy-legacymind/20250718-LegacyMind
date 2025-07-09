use anyhow::{anyhow, Context, Result};
use rmcp::{handler::server::tool::Parameters, model::{CallToolResult, Content, ErrorData}};
use serde::Deserialize;
use schemars::JsonSchema;
use uuid::Uuid;

use crate::service::UnifiedIntelligenceService;
use crate::storage::{redis_pool, Thought};
use crate::core::SignificanceAnalyzer;

#[derive(Debug, Deserialize, JsonSchema)]
pub struct ThinkParams {
    pub content: String,
    pub options: Option<ThinkOptions>,
}

#[derive(Debug, Default, Deserialize, JsonSchema)]
pub struct ThinkOptions {
    #[serde(flatten)]
    pub sequential_options: Option<SequentialOptions>,
}

#[derive(Debug, Default, Deserialize, JsonSchema)]
pub struct SequentialOptions {
    #[serde(rename = "chainId")]
    pub chain_id: Option<String>,
}

pub async fn ui_think_impl(
    service: &UnifiedIntelligenceService,
    params: Parameters<ThinkParams>,
) -> Result<CallToolResult, ErrorData> {
    let result = service.handle_think(params.0).await;

    result.map_err(|e| {
        tracing::error!(error = ?e, "ui_think failed");
        ErrorData::internal_error(format!("{:?}", e), None)
    })
}

impl UnifiedIntelligenceService {
    async fn handle_think(&self, params: ThinkParams) -> Result<CallToolResult> {
        let content = params.content;
        if content.is_empty() {
            return Err(anyhow!("Content cannot be empty"));
        }
        
        let significance = SignificanceAnalyzer::analyze(&content).await;
        let sequential_opts = params.options.and_then(|o| o.sequential_options).unwrap_or_default();
        
        let thought = self.capture_thought(content, significance, sequential_opts).await?;
        
        let result = serde_json::json!({
            "captured": true,
            "thoughtId": thought.id,
            "chainId": thought.chain_id,
        });
        
        Ok(CallToolResult::success(vec![Content::text(result.to_string())]))
    }
    
    async fn capture_thought(
        &self,
        content: String,
        significance: u8,
        seq_opts: SequentialOptions,
    ) -> Result<Thought> {
        let instance_id = self.get_config().instance_id.clone();
        let mut thought = Thought::new(content, significance, instance_id.clone());
        
        thought.chain_id = Some(seq_opts.chain_id.unwrap_or_else(|| Uuid::new_v4().to_string()));
        
        let thought_key = format!("{}:thoughts:{}", instance_id, thought.id);
        redis_pool::set_json(self.get_redis_pool(), &thought_key, &thought)
            .await
            .context("Failed to store thought in Redis")?;
        
        Ok(thought)
    }
}
