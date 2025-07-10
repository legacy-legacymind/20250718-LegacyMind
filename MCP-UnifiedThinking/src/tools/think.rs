use anyhow::{anyhow, Result};
use schemars::JsonSchema;
use serde::Deserialize;
use uuid::Uuid;
use std::collections::HashMap;
use crate::models::Thought;
use crate::frameworks::{Framework, socratic::Socratic, first_principles::FirstPrinciples};
use crate::service::UnifiedThinkingService;
use redis::AsyncCommands;

#[derive(Debug, Deserialize, JsonSchema)]
pub struct ThinkParams {
    pub framework: String,
    pub content: String,
    #[serde(rename = "chainId")]
    pub chain_id: Option<String>,
    #[serde(rename = "thoughtNumber")]
    pub thought_number: Option<i32>,
    #[serde(rename = "nextThoughtNeeded")]
    #[serde(default = "default_next_thought_needed")]
    pub next_thought_needed: bool,
}

fn default_next_thought_needed() -> bool {
    true
}

pub async fn ut_think_impl(
    service: &UnifiedThinkingService,
    params: ThinkParams,
) -> Result<serde_json::Value> {
    let framework: Box<dyn Framework> = match params.framework.as_str() {
        "socratic" => Box::new(Socratic),
        "first_principles" => Box::new(FirstPrinciples),
        _ => return Err(anyhow!("Unknown framework '{}'", params.framework)),
    };

    let structured_output = framework.apply(&params.content)?;
    let instance_id = service.config.instance_id.clone();
    let thought_id = Uuid::new_v4().to_string();
    let chain_id = params.chain_id.unwrap_or_else(|| Uuid::new_v4().to_string());

    let thought = Thought {
        id: thought_id.clone(),
        instance_id: instance_id.clone(),
        chain_id,
        thought_number: params.thought_number.unwrap_or(1),
        framework: params.framework,
        original_content: params.content,
        structured_output: structured_output.clone(),
        next_thought_needed: params.next_thought_needed,
        timestamp: chrono::Utc::now(),
    };

    let redis_key = format!("{}:thought:{}", instance_id, thought_id);
    let mut conn = service.redis_pool.clone();
    let thought_json = serde_json::to_string(&thought)?;
    
    let _: () = conn.set(redis_key, thought_json).await?;

    Ok(structured_output)
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct RememberParams {
    // No parameters needed for now, will read instanceId from config.
}

pub async fn ut_remember_impl(
    service: &UnifiedThinkingService,
    _params: RememberParams,
) -> Result<serde_json::Value> {
    let instance_id = &service.config.instance_id;
    let mut conn = service.redis_pool.clone();
    let pattern = format!("{}:thought:*", instance_id);
    
    let keys: Vec<String> = redis::cmd("KEYS").arg(&pattern).query_async(&mut conn).await?;

    if keys.is_empty() {
        return Ok(serde_json::json!({
            "instanceId": instance_id,
            "chains": []
        }));
    }

    let thought_jsons: Vec<String> = conn.mget(keys).await?;
    
    let mut chains: HashMap<String, Vec<Thought>> = HashMap::new();
    for json_str in thought_jsons.into_iter().filter(|s| !s.is_empty()) {
        if let Ok(thought) = serde_json::from_str::<Thought>(&json_str) {
            chains.entry(thought.chain_id.clone()).or_default().push(thought);
        }
    }

    let mut chain_summaries = Vec::new();
    for (chain_id, mut thoughts) in chains {
        thoughts.sort_by_key(|t| t.thought_number);
        if let Some(last_thought) = thoughts.last() {
            chain_summaries.push(serde_json::json!({
                "chainId": chain_id,
                "thoughtCount": thoughts.len(),
                "lastActivity": last_thought.timestamp,
                "is_open": last_thought.next_thought_needed,
            }));
        }
    }

    // Explicitly construct the final JSON object to ensure correct type.
    let final_output = serde_json::json!({
        "instanceId": instance_id,
        "chains": chain_summaries
    });

    Ok(final_output)
}