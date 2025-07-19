use rmcp::schemars::{self, JsonSchema};
use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct MindDialogueParams {
    pub thought: String,
    pub context: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct MindPatternMatchParams {
    pub context: String,
    pub pattern_type: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct MindSuggestRetrievalParams {
    pub task_description: String,
    #[serde(default)]
    #[schemars(with = "Option<std::collections::HashMap<String, String>>")]
    pub constraints: Option<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct MindLearnOutcomeParams {
    pub task_id: String,
    pub outcome: String,
    #[serde(default)]
    #[schemars(with = "Option<std::collections::HashMap<String, String>>")]
    pub metrics: Option<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct MindDetectUncertaintyParams {
    pub content: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct MindDetectFrameworkParams {
    pub content: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct MindLearnPatternParams {
    pub content: String,
    pub category: Option<String>,
    pub tags: Option<Vec<String>>,
    pub context: Option<String>,
    pub source: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct MindInternalVoiceParams {
    pub current_thought: String,
    pub recent_context: Option<Vec<String>>,
    #[serde(default)]
    #[schemars(with = "Option<String>")]
    pub cognitive_state: Option<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct EmptyParams {}