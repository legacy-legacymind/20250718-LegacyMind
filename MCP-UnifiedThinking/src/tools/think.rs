use anyhow::{anyhow, Result};
use schemars::JsonSchema;
use serde::Deserialize;
use crate::models::Thought;
use crate::frameworks::{Framework, socratic::Socratic, first_principles::FirstPrinciples};
use crate::service::UnifiedThinkingService; // This will be created later

#[derive(Debug, Deserialize, JsonSchema)]
pub struct ThinkParams {
    pub framework: String,
    pub content: String,
    #[serde(rename = "chainId")]
    pub chain_id: Option<String>,
    #[serde(rename = "thoughtNumber")]
    pub thought_number: Option<u32>,
    #[serde(rename = "nextThoughtNeeded")]
    #[serde(default = "default_next_thought_needed")]
    pub next_thought_needed: bool,
}

fn default_next_thought_needed() -> bool {
    true
}

pub async fn ut_think_impl(
    _service: &UnifiedThinkingService,
    params: ThinkParams,
) -> Result<serde_json::Value> {
    let framework: Box<dyn Framework> = match params.framework.as_str() {
        "socratic" => Box::new(Socratic),
        "first_principles" => Box::new(FirstPrinciples),
        _ => return Err(anyhow!("Unknown framework '{}'", params.framework)),
    };

    let structured_output = framework.apply(&params.content)?;

    // The logic to create and save the Thought object will be added here later.
    // For now, we just return the output.

    Ok(structured_output)
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct RememberParams {
    // No parameters needed for now, will read instanceId from config.
}

pub async fn ut_remember_impl(
    _service: &UnifiedThinkingService,
    _params: RememberParams,
) -> Result<serde_json::Value> {
    // The logic to query Redis and list the thought chains will be implemented here.
    // For now, we return a placeholder.
    Ok(serde_json::json!({
        "chains": [
            {
                "chainId": "placeholder-chain-1",
                "thoughtCount": 5,
                "lastActivity": "2025-07-10T12:00:00Z",
                "is_open": true
            }
        ]
    }))
}