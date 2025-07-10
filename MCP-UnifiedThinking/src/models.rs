use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};
use schemars::JsonSchema;

/// Represents a single thought captured by the MCP.
#[derive(Debug, Serialize, Deserialize, JsonSchema)]
pub struct Thought {
    /// A unique identifier for the thought.
    pub id: String,
    /// The instance that generated the thought ("Claude" or "Gemini").
    pub instance_id: String,
    /// The ID of the chain this thought belongs to.
    pub chain_id: String,
    /// The sequential number of the thought within its chain.
    pub thought_number: i32,
    /// The logical framework applied to this thought.
    pub framework: String,
    /// The original, raw content provided by the user.
    pub original_content: String,
    /// The structured output after applying the framework.
    pub structured_output: serde_json::Value,
    /// A flag indicating if the thinking process for this chain is ongoing.
    pub next_thought_needed: bool,
    /// The timestamp of when the thought was created.
    pub timestamp: DateTime<Utc>,
}
