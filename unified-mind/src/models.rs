use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use schemars::JsonSchema;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct UmRecallParams {
    /// Search query
    pub query: String,
    
    /// Maximum number of results to return (default: 20)
    #[serde(default = "default_limit")]
    pub limit: usize,
    
    /// Similarity threshold for semantic search (0.0-1.0, default: 0.35)
    #[serde(default = "default_threshold")]
    pub threshold: f32,
    
    /// Search across all instances instead of just current instance (default: false)
    #[serde(default)]
    pub search_all_instances: bool,
    
    
    /// Optional instance filter (e.g., ["CC", "DT"])
    #[serde(default)]
    pub instance_filter: Option<Vec<String>>,
    
    /// Optional category filter
    #[serde(default)]
    pub category_filter: Option<String>,
    
    /// Optional tags filter
    #[serde(default)]
    pub tags_filter: Option<Vec<String>>,
}

fn default_limit() -> usize {
    20
}

fn default_threshold() -> f32 {
    0.35
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UmRecallResult {
    /// Array of retrieved thoughts
    pub thoughts: Vec<Thought>,
    
    /// Total number of results before limiting
    pub total_count: usize,
    
    /// Search metadata
    pub metadata: SearchMetadata,
    
    /// Optional synthesized answer from Groq
    #[serde(skip_serializing_if = "Option::is_none")]
    pub synthesis: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Thought {
    pub id: Uuid,
    pub content: String,
    pub category: Option<String>,
    pub tags: Vec<String>,
    pub instance_id: String,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub importance: i32,
    pub relevance: i32,
    
    /// Computed scores
    #[serde(skip_serializing_if = "Option::is_none")]
    pub semantic_score: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub temporal_score: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub usage_score: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub combined_score: Option<f32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchMetadata {
    pub query: String,
    pub execution_time_ms: u64,
    pub cache_hit: bool,
    pub search_type: SearchType,
    pub instance_id: String,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SearchType {
    InstanceSpecific,
    Federated,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CachedResult {
    pub result: UmRecallResult,
    pub cached_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct FeedbackParams {
    /// Search session ID
    pub search_id: String,
    
    /// Thought ID being rated
    pub thought_id: String,
    
    /// User rating: -1 (thumbs down), 0 (neutral), 1 (thumbs up)
    #[serde(default)]
    pub rating: Option<i8>,
    
    /// Relevance score (1-10)
    #[serde(default)]
    pub relevance: Option<i32>,
    
    /// Feedback action type
    #[serde(default)]
    pub action: Option<FeedbackAction>,
    
    /// Action-specific value
    #[serde(default)]
    pub value: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum FeedbackAction {
    Click,
    Copy,
    Dwell,
    Expand,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FeedbackResult {
    pub success: bool,
    pub message: String,
}

