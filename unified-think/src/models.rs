use serde::{Deserialize, Serialize};
use chrono::Utc;

/// Parameters for the ui_think tool
#[derive(Debug, Deserialize, schemars::JsonSchema)]
pub struct UiThinkParams {
    #[schemars(description = "The thought content to process")]
    pub thought: String,
    
    #[schemars(description = "Current thought number in sequence")]
    pub thought_number: i32,
    
    #[schemars(description = "Total number of thoughts in sequence")]
    pub total_thoughts: i32,
    
    #[schemars(description = "Whether another thought is needed")]
    pub next_thought_needed: bool,
    
    #[schemars(description = "Optional chain ID to link thoughts together")]
    pub chain_id: Option<String>,
}

/// Parameters for the ui_recall tool
#[derive(Debug, Deserialize, schemars::JsonSchema)]
pub struct UiRecallParams {
    #[schemars(description = "Search query to find thoughts (e.g., 'Redis performance')")]
    pub query: Option<String>,
    
    #[schemars(description = "Chain ID to retrieve thoughts from (use this OR query, not both)")]
    pub chain_id: Option<String>,
    
    #[schemars(description = "Maximum number of results to return (default: 50)")]
    pub limit: Option<usize>,
    
    #[schemars(description = "Action to perform on results: search, merge, analyze, branch, continue")]
    pub action: Option<String>,
    
    #[schemars(description = "Additional parameters for the action (JSON object)")]
    pub action_params: Option<serde_json::Value>,
}

/// Core thought record structure stored in Redis
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ThoughtRecord {
    pub id: String,
    pub instance: String,
    pub thought: String,
    pub thought_number: i32,
    pub total_thoughts: i32,
    pub timestamp: String,
    pub chain_id: Option<String>,
}

impl ThoughtRecord {
    /// Create a new thought record with generated ID and timestamp
    pub fn new(
        instance: String,
        thought: String,
        thought_number: i32,
        total_thoughts: i32,
        chain_id: Option<String>,
    ) -> Self {
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            instance,
            thought,
            thought_number,
            total_thoughts,
            timestamp: Utc::now().to_rfc3339(),
            chain_id,
        }
    }
}

/// Response from ui_think tool
#[derive(Debug, Serialize)]
pub struct ThinkResponse {
    pub status: String,
    pub thought_id: String,
    pub next_thought_needed: bool,
}

/// Response from ui_recall tool  
#[derive(Debug, Serialize)]
pub struct RecallResponse {
    pub thoughts: Vec<ThoughtRecord>,
    pub total_found: usize,
    pub search_method: String,
    pub search_available: bool,
    pub action: Option<String>,
    pub action_result: Option<serde_json::Value>,
}

/// Chain metadata stored in Redis
#[derive(Debug, Serialize, Deserialize)]
pub struct ChainMetadata {
    pub chain_id: String,
    pub created_at: String,
    pub thought_count: i32,
    pub instance: String,
}