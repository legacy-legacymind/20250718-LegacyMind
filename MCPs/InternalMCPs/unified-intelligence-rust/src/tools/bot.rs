use rmcp::{handler::server::tool::Parameters, model::{CallToolResult, Content, ErrorData}};
use serde::Deserialize;
use schemars::JsonSchema;

use crate::service::UnifiedIntelligenceService;

#[derive(Debug, Deserialize, JsonSchema)]
pub struct BotParams {
    message: String,
}

pub async fn ui_bot_impl(
    _service: &UnifiedIntelligenceService,
    params: Parameters<BotParams>,
) -> Result<CallToolResult, ErrorData> {
    let response_text = format!("You said: {}", params.0.message);
    Ok(CallToolResult::success(vec![Content::text(response_text)]))
}
