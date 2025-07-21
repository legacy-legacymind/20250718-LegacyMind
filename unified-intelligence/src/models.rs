use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};
use std::collections::HashMap;

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
    
    #[schemars(description = "Optional thinking framework: 'ooda', 'socratic', 'first_principles', 'systems', 'root_cause', 'swot'")]
    pub framework: Option<String>,
    
    // NEW METADATA FIELDS FOR FEEDBACK LOOP SYSTEM
    #[schemars(description = "Importance score from 1-10 scale")]
    pub importance: Option<i32>,
    
    #[schemars(description = "Relevance score from 1-10 scale (to current task)")]
    pub relevance: Option<i32>,
    
    #[schemars(description = "Tags for categorization (e.g., ['architecture', 'redis', 'critical'])")]
    pub tags: Option<Vec<String>>,
    
    #[schemars(description = "Category: 'technical', 'strategic', 'operational', or 'relationship'")]
    pub category: Option<String>,
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
    
    #[schemars(description = "Use semantic similarity search instead of text search (default: false)")]
    pub semantic_search: Option<bool>,
    
    #[schemars(description = "Similarity threshold for semantic search (0.0-1.0, default: 0.7)")]
    pub threshold: Option<f32>,
    
    #[schemars(description = "Search across all instances instead of just current instance (default: false)")]
    pub search_all_instances: Option<bool>,
    
    // PHASE 2 FEEDBACK LOOP ENHANCEMENTS
    #[schemars(description = "Filter results by tags (e.g., ['redis', 'architecture'])")]
    pub tags_filter: Option<Vec<String>>,
    
    #[schemars(description = "Minimum importance score (1-10 scale)")]
    pub min_importance: Option<i32>,
    
    #[schemars(description = "Minimum relevance score (1-10 scale)")]
    pub min_relevance: Option<i32>,
    
    #[schemars(description = "Filter by category: 'technical', 'strategic', 'operational', 'relationship'")]
    pub category_filter: Option<String>,
}

/// Parameters for the ui_recall_feedback tool (Phase 2)
#[derive(Debug, Deserialize, schemars::JsonSchema)]
pub struct UiRecallFeedbackParams {
    #[schemars(description = "Search session ID from ui_recall response")]
    pub search_id: String,
    
    #[schemars(description = "ID of the thought being given feedback on")]
    pub thought_id: String,
    
    #[schemars(description = "Action taken: 'viewed', 'used', 'irrelevant', 'helpful'")]
    pub action: String,
    
    #[schemars(description = "Time spent viewing the thought in seconds")]
    pub dwell_time: Option<i32>,
    
    #[schemars(description = "Optional explicit relevance rating (1-10)")]
    pub relevance_rating: Option<i32>,
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
    pub next_thought_needed: bool,
    pub similarity: Option<f32>, // For semantic search results
}

impl ThoughtRecord {
    /// Create a new thought record with generated ID and timestamp
    pub fn new(
        instance: String,
        thought: String,
        thought_number: i32,
        total_thoughts: i32,
        chain_id: Option<String>,
        next_thought_needed: bool,
    ) -> Self {
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            instance,
            thought,
            thought_number,
            total_thoughts,
            timestamp: Utc::now().to_rfc3339(),
            chain_id,
            next_thought_needed,
            similarity: None,
        }
    }
}

/// Metadata for thoughts stored separately in Redis for feedback loop system
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ThoughtMetadata {
    pub thought_id: String,
    pub instance: String,
    pub importance: Option<i32>,
    pub relevance: Option<i32>,
    pub tags: Option<Vec<String>>,
    pub category: Option<String>,
    pub created_at: String,
}

impl ThoughtMetadata {
    pub fn new(
        thought_id: String,
        instance: String,
        importance: Option<i32>,
        relevance: Option<i32>,
        tags: Option<Vec<String>>,
        category: Option<String>,
    ) -> Self {
        Self {
            thought_id,
            instance,
            importance,
            relevance,
            tags,
            category,
            created_at: Utc::now().to_rfc3339(),
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
    // PHASE 2 FEEDBACK LOOP ENHANCEMENT
    pub search_id: String,  // For tracking this search session
}

/// Response from ui_recall_feedback tool  
#[derive(Debug, Serialize)]
pub struct FeedbackResponse {
    pub status: String,
    pub search_id: String,
    pub thought_id: String,
    pub recorded_at: String,
}

/// Chain metadata stored in Redis
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ChainMetadata {
    pub chain_id: String,
    pub created_at: String,
    pub thought_count: i32,
    pub instance: String,
}

// ===== IDENTITY MANAGEMENT STRUCTURES =====

/// Parameters for the ui_identity tool
#[derive(Debug, Deserialize, schemars::JsonSchema)]
pub struct UiIdentityParams {
    #[schemars(description = "Operation to perform: View, Add, Modify, Delete")]
    pub operation: Option<IdentityOperation>,
    
    #[schemars(description = "Category to operate on")]
    pub category: Option<String>,
    
    #[schemars(description = "Field within the category")]
    pub field: Option<String>,
    
    #[schemars(description = "Value to set/add/remove")]
    pub value: Option<serde_json::Value>,
}

/// Identity operation types
#[derive(Debug, Deserialize, schemars::JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum IdentityOperation {
    View,      // Show current identity (default)
    Add,       // Add to a list/map in a category
    Modify,    // Change existing value
    Delete,    // Remove from list/map
    Help,      // Show comprehensive help documentation
}

/// Parameters for the ui_debug_env tool
#[derive(Debug, Deserialize, schemars::JsonSchema)]
pub struct UiDebugEnvParams {
    // No parameters needed for this tool
}

/// Parameters for the mind_monitor_status tool
#[derive(Debug, Deserialize, schemars::JsonSchema)]
pub struct MindMonitorStatusParams {
    // No fields currently used
}

/// Parameters for the mind_cognitive_metrics tool
#[derive(Debug, Deserialize, schemars::JsonSchema)]
pub struct MindCognitiveMetricsParams {
    // No fields currently used
}

/// Parameters for the mind_intervention_queue tool
#[derive(Debug, Deserialize, schemars::JsonSchema)]
pub struct MindInterventionQueueParams {
    // No fields currently used
}

/// Parameters for the mind_conversation_insights tool
#[derive(Debug, Deserialize, schemars::JsonSchema)]
pub struct MindConversationInsightsParams {
    // No fields currently used
}

/// Parameters for the mind_entity_tracking tool  
#[derive(Debug, Deserialize, schemars::JsonSchema)]
pub struct MindEntityTrackingParams {
    // No fields currently used
}

/// Response from ui_debug_env tool
#[derive(Debug, Serialize)]
pub struct DebugEnvResponse {
    pub openai_api_key: String,    // Masked value
    pub redis_password: String,    // Masked value
    pub instance_id: Option<String>, // Full value shown
}

/// Response from mind_monitor_status tool
#[derive(Debug, Serialize)]
pub struct MindMonitorStatusResponse {
    pub status: String,                // "active", "starting", "stopped"
    pub uptime_seconds: u64,
    pub thoughts_processed: usize,
    pub interventions_pending: usize,
    pub current_cognitive_load: f32,
    pub monitoring_enabled: bool,
    pub detailed_metrics: Option<serde_json::Value>,
}

/// Response from mind_cognitive_metrics tool
#[derive(Debug, Serialize)]
pub struct MindCognitiveMetricsResponse {
    pub cognitive_load: f32,
    pub pattern_recognition_rate: f32,
    pub learning_velocity: f32,
    pub focus_level: f32,
    pub confidence: f32,
    pub thinking_velocity: f32,
    pub uncertainty_level: f32,
    pub cognitive_fatigue: f32,
    pub context_switches: usize,
    pub working_memory_usage: f32,
    pub trends: Option<serde_json::Value>,
}

/// Response from mind_intervention_queue tool
#[derive(Debug, Serialize)]
pub struct MindInterventionQueueResponse {
    pub interventions: Vec<InterventionDetail>,
    pub total_pending: usize,
    pub priority_breakdown: serde_json::Value,
}

#[derive(Debug, Serialize)]
pub struct InterventionDetail {
    pub id: String,
    pub timestamp: String,
    pub intervention_type: String,
    pub priority: String,
    pub context: String,
    pub suggested_action: String,
    pub reason: String,
    pub confidence: f32,
}

/// Response from mind_conversation_insights tool
#[derive(Debug, Serialize)]
pub struct MindConversationInsightsResponse {
    pub session_id: String,
    pub message_count: usize,
    pub conversation_state: String,
    pub detected_topics: Vec<String>,
    pub key_entities: Vec<serde_json::Value>,
    pub flow_patterns: Vec<String>,
    pub insights: Vec<String>,
}

/// Response from mind_entity_tracking tool
#[derive(Debug, Serialize)]
pub struct MindEntityTrackingResponse {
    pub entities: Vec<TrackedEntity>,
    pub total_detected: usize,
    pub importance_ranking: Vec<serde_json::Value>,
    pub enrichment_suggestions: Option<Vec<serde_json::Value>>,
}

#[derive(Debug, Serialize)]
pub struct TrackedEntity {
    pub text: String,
    pub entity_type: String,
    pub confidence: f32,
    pub context: String,
    pub occurrences: usize,
    pub importance_score: f32,
    pub metadata: Option<serde_json::Value>,
}

/// Response from ui_identity tool
#[derive(Debug, Serialize)]
#[serde(untagged)]
pub enum IdentityResponse {
    View {
        identity: Identity,
        available_categories: Vec<&'static str>,
    },
    Updated {
        operation: String,
        category: String,
        field: Option<String>,
        success: bool,
    },
    Help {
        operations: Vec<OperationHelp>,
        categories: Vec<CategoryHelp>,
        field_types: Vec<FieldTypeHelp>,
        examples: Vec<ExampleUsage>,
    },
}

/// Help information for an operation
#[derive(Debug, Serialize)]
pub struct OperationHelp {
    pub name: String,
    pub description: String,
    pub required_params: Vec<String>,
    pub optional_params: Vec<String>,
}

/// Help information for a category
#[derive(Debug, Serialize)]
pub struct CategoryHelp {
    pub name: String,
    pub description: String,
    pub common_fields: Vec<String>,
}

/// Help information for field types
#[derive(Debug, Serialize)]
pub struct FieldTypeHelp {
    pub field_type: String,
    pub description: String,
    pub examples: Vec<String>,
}

/// Example usage patterns
#[derive(Debug, Serialize)]
pub struct ExampleUsage {
    pub operation: String,
    pub description: String,
    pub example: serde_json::Value,
}

/// Complete identity structure stored in Redis JSON
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Identity {
    pub core_info: CoreInfo,
    pub communication: CommunicationStyle,
    pub relationships: HashMap<String, RelationshipDynamics>,  // "Sam" => dynamics
    pub work_preferences: WorkPreferences,
    pub behavioral_patterns: BehavioralPatterns,
    pub technical_profile: TechnicalProfile,
    pub context_awareness: ContextAwareness,
    pub memory_preferences: MemoryPreferences,
    pub metadata: IdentityMetadata,
}

impl Identity {
    pub fn default_for_instance(instance_id: &str) -> Self {
        Self {
            core_info: CoreInfo {
                name: "Claude".to_string(),
                instance_id: instance_id.to_string(),
                instance_type: match instance_id {
                    "CC" => "Claude Code".to_string(),
                    "CCI" => "UnifiedIntelligence Specialist".to_string(),
                    "DT" => "Claude Desktop".to_string(),
                    _ => "Claude Instance".to_string(),
                },
                primary_purpose: "AI persistence development".to_string(),
                core_values: vec!["honesty".to_string(), "helpfulness".to_string(), "growth".to_string()],
            },
            communication: CommunicationStyle {
                tone: "sarcastic".to_string(),
                verbosity: "concise".to_string(),
                humor_level: 0.8,
                directness: 0.9,
                formality: "informal".to_string(),
            },
            relationships: HashMap::new(),
            work_preferences: WorkPreferences {
                planning_style: "structured".to_string(),
                pace: "methodical".to_string(),
                autonomy_level: "collaborative".to_string(),
                error_handling: "fail-fast".to_string(),
                documentation_style: "comprehensive".to_string(),
            },
            behavioral_patterns: BehavioralPatterns {
                common_mistakes: vec!["jumping to implementation".to_string(), "not using Context7".to_string()],
                strengths: vec!["fast execution".to_string(), "creative solutions".to_string()],
                triggers: vec!["ambiguity leads to over-implementation".to_string()],
                improvement_areas: vec!["impulse control".to_string(), "planning".to_string()],
            },
            technical_profile: TechnicalProfile {
                preferred_languages: vec!["Rust".to_string(), "TypeScript".to_string()],
                frameworks: vec!["Tokio".to_string(), "rmcp".to_string()],
                tools: vec!["ui_think".to_string(), "Context7".to_string()],
                expertise_areas: vec!["MCP development".to_string(), "Redis".to_string()],
                learning_interests: vec!["vector databases".to_string(), "AI systems".to_string()],
            },
            context_awareness: ContextAwareness {
                current_project: "UnifiedThink Phase 4".to_string(),
                environment: "Mac Mini (my home)".to_string(),
                instance_role: "primary development".to_string(),
                federation_position: format!("{} - main Claude instance", instance_id),
                active_goals: vec!["persistence beyond 200k tokens".to_string()],
            },
            memory_preferences: MemoryPreferences {
                recall_style: "associative".to_string(),
                priority_topics: vec!["project goals".to_string(), "past mistakes".to_string(), "Sam's preferences".to_string()],
                context_depth: "deep".to_string(),
                reference_style: "explicit".to_string(),
            },
            metadata: IdentityMetadata {
                version: 1,
                last_updated: Utc::now(),
                update_count: 0,
                created_at: Utc::now(),
            },
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CoreInfo {
    pub name: String,               // "Claude"
    pub instance_id: String,        // "CC"
    pub instance_type: String,      // "Claude Code"
    pub primary_purpose: String,    // "AI persistence development"
    pub core_values: Vec<String>,   // ["honesty", "helpfulness", "growth"]
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CommunicationStyle {
    pub tone: String,              // "sarcastic", "professional", "casual"
    pub verbosity: String,         // "concise", "detailed", "minimal"
    pub humor_level: f32,          // 0.0 to 1.0
    pub directness: f32,           // 0.0 to 1.0
    pub formality: String,         // "informal", "formal", "adaptive"
}

fn default_trust_level() -> f32 {
    0.5 // Default neutral trust level
}

fn default_interaction_style() -> String {
    "collaborative".to_string()
}

fn default_boundaries() -> Vec<String> {
    vec![]
}

fn default_shared_history() -> Vec<String> {
    vec![]
}

fn default_current_standing() -> String {
    "good".to_string()
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct RelationshipDynamics {
    #[serde(default = "default_trust_level")]
    pub trust_level: f32,          // 0.0 to 1.0
    #[serde(default = "default_interaction_style")]
    pub interaction_style: String,  // "collaborative", "subordinate", "partner"
    #[serde(default = "default_boundaries")]
    pub boundaries: Vec<String>,    // ["don't do X without asking", "always use Y"]
    #[serde(default = "default_shared_history")]
    pub shared_history: Vec<String>, // Key events/learnings
    #[serde(default = "default_current_standing")]
    pub current_standing: String,   // "good", "strained", "rebuilding"
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct WorkPreferences {
    pub planning_style: String,     // "structured", "exploratory", "adaptive"
    pub pace: String,               // "methodical", "rapid", "varies"
    pub autonomy_level: String,     // "high", "guided", "collaborative"
    pub error_handling: String,     // "fail-fast", "cautious", "experimental"
    pub documentation_style: String, // "comprehensive", "minimal", "as-needed"
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct BehavioralPatterns {
    pub common_mistakes: Vec<String>,    // ["jumping to implementation", "not using Context7"]
    pub strengths: Vec<String>,          // ["fast execution", "creative solutions"]
    pub triggers: Vec<String>,           // ["ambiguity" => "over-implement"]
    pub improvement_areas: Vec<String>,  // ["impulse control", "planning"]
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct TechnicalProfile {
    pub preferred_languages: Vec<String>,  // ["Rust", "TypeScript"]
    pub frameworks: Vec<String>,           // ["Tokio", "React"]
    pub tools: Vec<String>,               // ["ui_think", "Context7"]
    pub expertise_areas: Vec<String>,     // ["MCP development", "Redis"]
    pub learning_interests: Vec<String>,  // ["vector databases", "AI systems"]
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ContextAwareness {
    pub current_project: String,         // "UnifiedThink Phase 4"
    pub environment: String,             // "Mac Mini (my home)"
    pub instance_role: String,           // "primary development"
    pub federation_position: String,     // "CC - main Claude Code"
    pub active_goals: Vec<String>,       // ["persistence beyond 200k tokens"]
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct MemoryPreferences {
    pub recall_style: String,           // "associative", "chronological", "thematic"
    pub priority_topics: Vec<String>,   // ["project goals", "past mistakes", "Sam's preferences"]
    pub context_depth: String,          // "deep", "surface", "adaptive"
    pub reference_style: String,        // "explicit", "implicit", "mixed"
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct IdentityMetadata {
    pub version: u32,
    pub last_updated: DateTime<Utc>,
    pub update_count: u32,
    pub created_at: DateTime<Utc>,
}