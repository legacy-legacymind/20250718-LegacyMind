use std::sync::Arc;
use std::future::Future;
use anyhow::Result;
use redis::aio::ConnectionManager;
use rmcp::{
    handler::server::{router::tool::ToolRouter, tool::Parameters},
    model::{CallToolResult, Content, ErrorData, ServerCapabilities, ServerInfo},
    ServerHandler,
};
use rmcp_macros::{tool, tool_handler, tool_router};
use serde_json::json;
use tokio::sync::RwLock;
use tracing::{debug, info};

use crate::{dialogue, models::*, monitor, patterns, retrieval};

/// UnifiedMind MCP Service - Cognitive subconscious platform
#[derive(Clone)]
pub struct UnifiedMindService {
    tool_router: ToolRouter<Self>,
    redis_conn: Arc<RwLock<ConnectionManager>>,
    pattern_engine: Arc<patterns::PatternEngine>,
    retrieval_learner: Arc<retrieval::RetrievalLearner>,
    dialogue_manager: Arc<dialogue::DialogueManager>,
    cognitive_monitor: Arc<monitor::CognitiveMonitor>,
}

impl UnifiedMindService {
    /// Create a new service instance
    pub async fn new() -> Result<Self> {
        info!("Initializing UnifiedMind service");

        // Connect to Redis
        let redis_host = std::env::var("REDIS_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
        let redis_port = std::env::var("REDIS_PORT").unwrap_or_else(|_| "6379".to_string());
        let redis_pwd = std::env::var("REDIS_PWD").unwrap_or_else(|_| "".to_string());
        
        let redis_url = if redis_pwd.is_empty() {
            format!("redis://{}:{}", redis_host, redis_port)
        } else {
            format!("redis://:{}@{}:{}", redis_pwd, redis_host, redis_port)
        };
        
        debug!("Connecting to Redis at {}:{}", redis_host, redis_port);
        let client = redis::Client::open(redis_url)?;
        let conn_manager = ConnectionManager::new(client).await?;
        let redis_conn = Arc::new(RwLock::new(conn_manager));

        // Initialize components
        info!("Initializing pattern engine...");
        let pattern_engine = Arc::new(patterns::PatternEngine::new(redis_conn.clone()).await?);
        
        info!("Initializing retrieval learner...");
        let retrieval_learner = Arc::new(retrieval::RetrievalLearner::new(redis_conn.clone()).await?);
        
        info!("Initializing dialogue manager...");
        let dialogue_manager = Arc::new(dialogue::DialogueManager::new(redis_conn.clone(), pattern_engine.clone()).await?);
        
        info!("Initializing cognitive monitor...");
        let cognitive_monitor = Arc::new(monitor::CognitiveMonitor::new(
            redis_conn.clone(),
            pattern_engine.clone(),
            retrieval_learner.clone(),
            dialogue_manager.clone()
        ).await?);
        
        info!("All components initialized successfully");

        Ok(Self {
            tool_router: Self::tool_router(),
            redis_conn,
            pattern_engine,
            retrieval_learner,
            dialogue_manager,
            cognitive_monitor,
        })
    }
}

#[tool_router]
impl UnifiedMindService {
    /// Internal dialogue processing
    #[tool(description = "Engage in internal dialogue processing to explore thoughts and patterns")]
    async fn mind_dialogue(&self, params: Parameters<MindDialogueParams>) -> std::result::Result<CallToolResult, ErrorData> {
        let MindDialogueParams { thought, context } = params.0;
        debug!("Processing internal dialogue: {}", thought);
        
        match self.dialogue_manager.process_thought(thought, context).await {
            Ok(response) => {
                let mut result = json!({
                    "status": "success",
                    "dialogue_id": response.id,
                    "response": response.content,
                    "patterns_detected": response.patterns,
                    "suggested_explorations": response.explorations,
                    "cognitive_load": response.cognitive_load,
                    "emotional_tone": response.emotional_tone
                });
                
                // Include internal voice if present
                if let Some(internal_voice) = response.internal_voice {
                    result["internal_voice"] = json!({
                        "content": internal_voice.content,
                        "delivery": internal_voice.delivery,
                        "timing": internal_voice.timing,
                        "confidence": internal_voice.confidence
                    });
                }
                
                let content = Content::json(result)
                    .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            },
            Err(e) => {
                Err(ErrorData::internal_error(format!("Failed to process dialogue: {}", e), None))
            }
        }
    }

    /// Direct access to internal voice generation
    #[tool(description = "Get internal voice suggestions for current thought context")]
    async fn mind_internal_voice(&self, params: Parameters<MindInternalVoiceParams>) -> std::result::Result<CallToolResult, ErrorData> {
        let MindInternalVoiceParams { current_thought, recent_context, cognitive_state } = params.0;
        debug!("Generating internal voice for: {}", current_thought);
        
        // Build thought history
        let mut thought_history = recent_context.unwrap_or_default();
        thought_history.push(current_thought.clone());
        
        // Get voice pattern for default user
        let voice_pattern = match self.dialogue_manager.get_or_create_voice_pattern("default").await {
            Ok(pattern) => pattern,
            Err(e) => {
                return Err(ErrorData::internal_error(format!("Failed to get voice pattern: {}", e), None));
            }
        };
        
        // Process through subconscious stream directly
        match self.dialogue_manager.process_subconscious_stream(
            current_thought.clone(),
            cognitive_state.and_then(|v| v.as_str().map(String::from)),
            &voice_pattern,
        ).await {
            Ok(response) => {
                let mut result = json!({
                    "status": "success",
                    "cognitive_load": response.cognitive_load,
                    "intervention_confidence": response.intervention_confidence,
                });
                
                if let Some(voice) = response.internal_voice {
                    result["internal_voice"] = json!({
                        "content": voice.content,
                        "delivery": voice.delivery,
                        "timing": voice.timing,
                        "confidence": voice.confidence,
                        "should_surface": voice.confidence > 0.6
                    });
                } else {
                    result["internal_voice"] = json!({
                        "content": null,
                        "reason": "No intervention needed at this time",
                        "should_surface": false
                    });
                }
                
                let content = Content::json(result)
                    .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            },
            Err(e) => {
                Err(ErrorData::internal_error(format!("Failed to generate internal voice: {}", e), None))
            }
        }
    }

    /// Pattern matching and recognition
    #[tool(description = "Match current context against learned patterns and identify similarities")]
    async fn mind_pattern_match(&self, params: Parameters<MindPatternMatchParams>) -> std::result::Result<CallToolResult, ErrorData> {
        let MindPatternMatchParams { context, pattern_type } = params.0;
        debug!("Matching patterns for context: {}", context);
        
        // Check for uncertainty first
        let uncertainty_detected = self.pattern_engine.detect_uncertainty(&context).await;
        
        // Check for framework triggers
        let framework_suggestion = self.pattern_engine.detect_framework_triggers(&context).await;
        
        match self.pattern_engine.find_patterns(context.clone(), pattern_type).await {
            Ok(matches) => {
                // Organize matches by type
                let mut matches_by_type = std::collections::HashMap::new();
                for m in &matches {
                    let type_name = match &m.pattern.pattern_type {
                        crate::patterns::PatternType::ThinkingPattern { .. } => "thinking",
                        crate::patterns::PatternType::InteractionPattern { .. } => "interaction",
                        crate::patterns::PatternType::RetrievalPattern { .. } => "retrieval",
                        crate::patterns::PatternType::UncertaintyPattern { .. } => "uncertainty",
                        crate::patterns::PatternType::ProblemSolving => "problem_solving",
                        crate::patterns::PatternType::ConceptExploration => "concept_exploration",
                        crate::patterns::PatternType::Debugging => "debugging",
                        crate::patterns::PatternType::SystemDesign => "system_design",
                        crate::patterns::PatternType::Learning => "learning",
                    };
                    matches_by_type.entry(type_name).or_insert_with(Vec::new).push(m);
                }
                
                let content = Content::json(json!({
                    "status": "success",
                    "patterns_found": matches.len(),
                    "matches": matches.iter().map(|m| json!({
                        "pattern_id": m.pattern.id,
                        "type": match &m.pattern.pattern_type {
                            crate::patterns::PatternType::ThinkingPattern { .. } => "thinking",
                            crate::patterns::PatternType::InteractionPattern { .. } => "interaction",
                            crate::patterns::PatternType::RetrievalPattern { .. } => "retrieval",
                            crate::patterns::PatternType::UncertaintyPattern { .. } => "uncertainty",
                            crate::patterns::PatternType::ProblemSolving => "problem_solving",
                            crate::patterns::PatternType::ConceptExploration => "concept_exploration",
                            crate::patterns::PatternType::Debugging => "debugging",
                            crate::patterns::PatternType::SystemDesign => "system_design",
                            crate::patterns::PatternType::Learning => "learning",
                        },
                        "confidence": m.confidence,
                        "similarity": m.similarity_score,
                        "context_alignment": m.context_alignment,
                        "trigger_matches": m.trigger_matches,
                        "actions": m.suggested_actions
                    })).collect::<Vec<_>>(),
                    "matches_by_type": matches_by_type,
                    "confidence_scores": matches.iter().map(|m| m.confidence).collect::<Vec<_>>(),
                    "suggested_actions": matches.iter()
                        .flat_map(|m| &m.suggested_actions)
                        .map(|a| json!({
                            "type": a.action_type,
                            "priority": a.priority,
                            "parameters": a.parameters
                        }))
                        .collect::<Vec<_>>(),
                    "uncertainty_detected": uncertainty_detected.is_some(),
                    "framework_suggestion": framework_suggestion
                }))
                .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            },
            Err(e) => {
                Err(ErrorData::internal_error(format!("Failed to match patterns: {}", e), None))
            }
        }
    }

    /// Suggest retrieval strategies based on learned patterns
    #[tool(description = "Suggest optimal retrieval strategies based on the current task and past successes")]
    async fn mind_suggest_retrieval(&self, params: Parameters<MindSuggestRetrievalParams>) -> std::result::Result<CallToolResult, ErrorData> {
        let MindSuggestRetrievalParams { task_description, constraints } = params.0;
        debug!("Suggesting retrieval strategies for: {}", task_description);
        
        match self.retrieval_learner.suggest_strategies(&task_description, constraints.unwrap_or(serde_json::Value::Object(serde_json::Map::new()))).await {
            Ok(strategies) => {
                let content = Content::json(json!({
                    "status": "success",
                    "strategies": strategies,
                    "count": strategies.len()
                }))
                .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            },
            Err(e) => {
                Err(ErrorData::internal_error(format!("Failed to suggest strategies: {}", e), None))
            }
        }
    }

    /// Learn from task outcomes to improve future performance
    #[tool(description = "Record the outcome of a task to learn and improve future pattern matching")]
    async fn mind_learn_outcome(&self, params: Parameters<MindLearnOutcomeParams>) -> std::result::Result<CallToolResult, ErrorData> {
        let MindLearnOutcomeParams { task_id, outcome, metrics } = params.0;
        debug!("Learning from outcome for task: {}", task_id);
        
        match self.cognitive_monitor.record_outcome(task_id, outcome, metrics).await {
            Ok(learning_result) => {
                // Update patterns based on outcome
                if learning_result.should_update_patterns {
                    if let Err(e) = self.pattern_engine.update_patterns(learning_result.pattern_updates).await {
                        return Err(ErrorData::internal_error(format!("Failed to update patterns: {}", e), None));
                    }
                }

                let content = Content::json(json!({
                    "status": "success",
                    "patterns_updated": learning_result.patterns_updated_count,
                    "strategies_refined": learning_result.strategies_refined,
                    "improvement_score": learning_result.improvement_score,
                    "insights": learning_result.insights
                }))
                .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            },
            Err(e) => {
                Err(ErrorData::internal_error(format!("Failed to record outcome: {}", e), None))
            }
        }
    }

    /// Detect uncertainty in content for subconscious assistance
    #[tool(description = "Detect uncertainty markers in content that might need subconscious assistance")]
    async fn mind_detect_uncertainty(&self, params: Parameters<MindDetectUncertaintyParams>) -> std::result::Result<CallToolResult, ErrorData> {
        let MindDetectUncertaintyParams { content } = params.0;
        debug!("Detecting uncertainty in: {}", content);
        
        match self.pattern_engine.detect_uncertainty(&content).await {
            Some(uncertainty_match) => {
                let content = Content::json(json!({
                    "status": "uncertainty_detected",
                    "confidence": uncertainty_match.confidence,
                    "markers_found": uncertainty_match.trigger_matches,
                    "suggested_actions": uncertainty_match.suggested_actions,
                    "pattern_details": {
                        "id": uncertainty_match.pattern.id,
                        "type": "uncertainty",
                        "content": uncertainty_match.pattern.content
                    }
                }))
                .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            },
            None => {
                let content = Content::json(json!({
                    "status": "no_uncertainty",
                    "confidence": 1.0,
                    "message": "No uncertainty markers detected"
                }))
                .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            }
        }
    }

    /// Detect framework triggers in content
    #[tool(description = "Detect thinking framework triggers in content (e.g., first-principles, OODA, Socratic)")]
    async fn mind_detect_framework(&self, params: Parameters<MindDetectFrameworkParams>) -> std::result::Result<CallToolResult, ErrorData> {
        let MindDetectFrameworkParams { content } = params.0;
        debug!("Detecting framework triggers in: {}", content);
        
        match self.pattern_engine.detect_framework_triggers(&content).await {
            Some(framework) => {
                let content = Content::json(json!({
                    "status": "framework_detected",
                    "framework": framework,
                    "confidence": 0.9,
                    "suggestion": format!("Consider applying {} framework", framework)
                }))
                .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            },
            None => {
                let content = Content::json(json!({
                    "status": "no_framework",
                    "message": "No specific framework triggers detected"
                }))
                .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            }
        }
    }

    /// Learn a new pattern from observed behavior
    #[tool(description = "Learn a new cognitive pattern from observed behavior or ui_think metadata")]
    async fn mind_learn_pattern(&self, params: Parameters<MindLearnPatternParams>) -> std::result::Result<CallToolResult, ErrorData> {
        let MindLearnPatternParams { content, category, tags, context, source } = params.0;
        debug!("Learning new pattern from: {}", content);
        
        let pattern_data = json!({
            "content": content,
            "category": category.unwrap_or_else(|| "general".to_string()),
            "tags": tags.unwrap_or_else(Vec::new),
            "context": context.unwrap_or_else(|| "".to_string()),
            "source": source.unwrap_or_else(|| "manual".to_string())
        });
        
        match self.pattern_engine.learn_new_pattern(pattern_data).await {
            Ok(pattern_id) => {
                let content = Content::json(json!({
                    "status": "success",
                    "pattern_id": pattern_id,
                    "message": "New pattern learned successfully"
                }))
                .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            },
            Err(e) => {
                Err(ErrorData::internal_error(format!("Failed to learn pattern: {}", e), None))
            }
        }
    }

    /// Get pattern statistics for monitoring
    #[tool(description = "Get statistics about learned patterns and their performance")]
    async fn mind_pattern_stats(&self, _params: Parameters<EmptyParams>) -> std::result::Result<CallToolResult, ErrorData> {
        debug!("Getting pattern statistics");
        
        match self.pattern_engine.get_pattern_stats().await {
            Ok(stats) => {
                let content = Content::json(stats)
                    .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            },
            Err(e) => {
                Err(ErrorData::internal_error(format!("Failed to get pattern stats: {}", e), None))
            }
        }
    }
}

#[tool_handler]
impl ServerHandler for UnifiedMindService {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            protocol_version: rmcp::model::ProtocolVersion::V_2024_11_05,
            server_info: rmcp::model::Implementation {
                name: "unified-mind".into(),
                version: env!("CARGO_PKG_VERSION").into(),
            },
            capabilities: ServerCapabilities {
                tools: Some(Default::default()),
                ..Default::default()
            },
            instructions: Some("UnifiedMind MCP - Cognitive subconscious platform for pattern learning and adaptive dialogue".into()),
        }
    }
}