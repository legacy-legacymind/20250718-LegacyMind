use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Thought {
    pub id: String,
    pub content: String,
    pub significance: u8,
    pub framework: Option<String>,
    pub instance_id: String,
    pub session_id: Option<String>,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub tags: Vec<String>,
    // New fields for sequential thinking
    pub chain_id: Option<String>,
    pub thought_number: Option<u32>,
    pub is_revision: Option<bool>,
    pub revises_thought: Option<String>,
    pub branch_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Identity {
    pub name: String,
    pub role: Option<String>,
    pub capabilities: Vec<String>,
    pub instance_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Context {
    pub task: Option<String>,
    pub goals: Vec<String>,
    pub working_memory: serde_json::Value,
    pub instance_id: String,
    pub last_updated: chrono::DateTime<chrono::Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FrameworkAnalysis {
    pub framework: String,
    pub insights: Vec<String>,
    pub confidence: f32,
    pub metadata: serde_json::Value,
}

impl Thought {
    pub fn new(content: String, significance: u8, instance_id: String) -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            content,
            significance,
            framework: None,
            instance_id,
            session_id: None,
            timestamp: chrono::Utc::now(),
            tags: Vec::new(),
            chain_id: None,
            thought_number: None,
            is_revision: None,
            revises_thought: None,
            branch_id: None,
        }
    }
}

impl Context {
    pub fn new(instance_id: String) -> Self {
        Self {
            task: None,
            goals: Vec::new(),
            working_memory: serde_json::json!({}),
            instance_id,
            last_updated: chrono::Utc::now(),
        }
    }
}