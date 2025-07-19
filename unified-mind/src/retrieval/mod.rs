use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;

use crate::patterns::PatternType;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConversationPattern {
    pub pattern_type: PatternType,
    pub context: String,
    pub confidence: f32,
    pub timestamp: DateTime<Utc>,
    pub metadata: HashMap<String, serde_json::Value>,
}

#[derive(Error, Debug)]
pub enum RetrievalError {
    #[error("UnifiedIntelligence unavailable: {0}")]
    ServiceUnavailable(String),
    #[error("Query failed: {0}")]
    QueryFailed(String),
    #[error("Invalid strategy: {0}")]
    InvalidStrategy(String),
    #[error("HTTP error: {0}")]
    HttpError(#[from] reqwest::Error),
    #[error("Serialization error: {0}")]
    SerializationError(#[from] serde_json::Error),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Memory {
    pub id: String,
    pub content: String,
    pub metadata: HashMap<String, serde_json::Value>,
    pub relevance_score: f32,
    pub timestamp: DateTime<Utc>,
    pub thought_chain_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Context {
    pub thought_id: String,
    pub chain_id: String,
    pub related_thoughts: Vec<Memory>,
    pub metadata: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum RetrievalStrategy {
    SimilarIssues {
        problem_description: String,
        include_solutions: bool,
        time_window_days: Option<u32>,
    },
    ContextualMemories {
        context_keywords: Vec<String>,
        relevance_threshold: f32,
        limit: usize,
    },
    FrameworkExamples {
        framework_type: String,
        pattern_type: PatternType,
        min_success_score: f32,
    },
    RecentConversations {
        topic_keywords: Vec<String>,
        hours_back: u32,
        min_relevance: f32,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryParams {
    pub strategy: RetrievalStrategy,
    pub threshold: f32,
    pub limit: usize,
    pub include_metadata: bool,
}

impl Default for QueryParams {
    fn default() -> Self {
        Self {
            strategy: RetrievalStrategy::ContextualMemories {
                context_keywords: vec![],
                relevance_threshold: 0.7,
                limit: 10,
            },
            threshold: 0.7,
            limit: 10,
            include_metadata: true,
        }
    }
}

#[async_trait]
pub trait MemoryInterface: Send + Sync {
    async fn query_memories(&self, params: QueryParams) -> Result<Vec<Memory>, RetrievalError>;
    
    async fn get_thought_context(&self, thought_id: &str) -> Result<Context, RetrievalError>;
    
    async fn semantic_search(
        &self,
        query: &str,
        threshold: f32,
        limit: usize,
    ) -> Result<Vec<Memory>, RetrievalError>;
    
    async fn chain_lookup(&self, chain_id: &str) -> Result<Vec<Memory>, RetrievalError>;
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StrategyEffectiveness {
    pub strategy_type: String,
    pub pattern_matches: HashMap<String, f32>, // pattern_type -> effectiveness_score
    pub avg_relevance: f32,
    pub usage_count: u32,
    pub success_rate: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RetrievalOutcome {
    pub strategy: RetrievalStrategy,
    pub results_count: usize,
    pub avg_relevance: f32,
    pub was_helpful: bool,
    pub pattern_context: Option<ConversationPattern>,
}

pub struct StrategyLearner {
    effectiveness_map: HashMap<String, StrategyEffectiveness>,
    pattern_strategy_map: HashMap<String, Vec<(String, f32)>>, // pattern_type_name -> [(strategy, score)]
    optimization_history: Vec<(QueryParams, RetrievalOutcome)>,
}

impl StrategyLearner {
    pub fn new() -> Self {
        Self {
            effectiveness_map: HashMap::new(),
            pattern_strategy_map: HashMap::new(),
            optimization_history: Vec::new(),
        }
    }

    pub fn suggest_strategy(&self, pattern: &ConversationPattern) -> RetrievalStrategy {
        // Find best strategy for this pattern type
        let pattern_type_name = self.pattern_type_to_string(&pattern.pattern_type);
        if let Some(strategies) = self.pattern_strategy_map.get(&pattern_type_name) {
            if let Some((best_strategy, _)) = strategies.first() {
                return self.create_strategy_for_pattern(best_strategy, pattern);
            }
        }

        // Default strategies based on pattern type
        match &pattern.pattern_type {
            PatternType::ThinkingPattern { .. } => RetrievalStrategy::ContextualMemories {
                context_keywords: self.extract_keywords(&pattern.context),
                relevance_threshold: 0.75,
                limit: 15,
            },
            PatternType::ProblemSolving => RetrievalStrategy::SimilarIssues {
                problem_description: pattern.context.clone(),
                include_solutions: true,
                time_window_days: Some(90),
            },
            PatternType::ConceptExploration => RetrievalStrategy::FrameworkExamples {
                framework_type: "conceptual".to_string(),
                pattern_type: pattern.pattern_type.clone(),
                min_success_score: 0.7,
            },
            PatternType::Debugging => RetrievalStrategy::SimilarIssues {
                problem_description: pattern.context.clone(),
                include_solutions: true,
                time_window_days: Some(30),
            },
            PatternType::SystemDesign => RetrievalStrategy::FrameworkExamples {
                framework_type: "architectural".to_string(),
                pattern_type: pattern.pattern_type.clone(),
                min_success_score: 0.8,
            },
            PatternType::Learning => RetrievalStrategy::RecentConversations {
                topic_keywords: self.extract_keywords(&pattern.context),
                hours_back: 168, // 1 week
                min_relevance: 0.6,
            },
            PatternType::InteractionPattern { .. } => RetrievalStrategy::RecentConversations {
                topic_keywords: self.extract_keywords(&pattern.context),
                hours_back: 72,
                min_relevance: 0.7,
            },
            PatternType::RetrievalPattern { .. } => RetrievalStrategy::ContextualMemories {
                context_keywords: self.extract_keywords(&pattern.context),
                relevance_threshold: 0.8,
                limit: 20,
            },
            PatternType::UncertaintyPattern { .. } => RetrievalStrategy::SimilarIssues {
                problem_description: pattern.context.clone(),
                include_solutions: true,
                time_window_days: Some(60),
            },
        }
    }

    pub fn learn_from_outcome(&mut self, outcome: RetrievalOutcome) {
        self.optimization_history.push((
            QueryParams {
                strategy: outcome.strategy.clone(),
                threshold: 0.7,
                limit: 10,
                include_metadata: true,
            },
            outcome.clone(),
        ));

        // Update effectiveness map
        let strategy_key = self.strategy_to_key(&outcome.strategy);
        let effectiveness = self
            .effectiveness_map
            .entry(strategy_key.clone())
            .or_insert_with(|| StrategyEffectiveness {
                strategy_type: strategy_key.clone(),
                pattern_matches: HashMap::new(),
                avg_relevance: 0.0,
                usage_count: 0,
                success_rate: 0.0,
            });

        // Update metrics
        effectiveness.usage_count += 1;
        effectiveness.avg_relevance = (effectiveness.avg_relevance
            * (effectiveness.usage_count - 1) as f32
            + outcome.avg_relevance)
            / effectiveness.usage_count as f32;

        if outcome.was_helpful {
            effectiveness.success_rate = (effectiveness.success_rate
                * (effectiveness.usage_count - 1) as f32
                + 1.0)
                / effectiveness.usage_count as f32;
        }

        // Update pattern-specific effectiveness
        if let Some(pattern) = &outcome.pattern_context {
            let pattern_key = format!("{:?}", pattern.pattern_type);
            let current_score = effectiveness
                .pattern_matches
                .entry(pattern_key.clone())
                .or_insert(0.0);
            *current_score = (*current_score * 0.8) + (outcome.avg_relevance * 0.2);
            let score_copy = *current_score;
            
            // Drop the mutable borrow before calling update_pattern_strategy_map
            drop(effectiveness);
            
            // Update pattern-strategy mapping
            self.update_pattern_strategy_map(&pattern.pattern_type, &strategy_key, score_copy);
        }
    }

    pub fn optimize_params(&self, base_params: QueryParams) -> QueryParams {
        let strategy_key = self.strategy_to_key(&base_params.strategy);
        
        if let Some(effectiveness) = self.effectiveness_map.get(&strategy_key) {
            // Adjust parameters based on historical performance
            let optimized_threshold = if effectiveness.avg_relevance > 0.8 {
                base_params.threshold * 1.1 // Be more selective
            } else if effectiveness.avg_relevance < 0.5 {
                base_params.threshold * 0.9 // Be less selective
            } else {
                base_params.threshold
            };

            let optimized_limit = if effectiveness.success_rate > 0.8 {
                base_params.limit // Keep current limit
            } else {
                (base_params.limit as f32 * 1.2) as usize // Get more results
            };

            QueryParams {
                threshold: optimized_threshold.clamp(0.5, 0.95),
                limit: optimized_limit.min(50),
                ..base_params
            }
        } else {
            base_params
        }
    }

    fn extract_keywords(&self, text: &str) -> Vec<String> {
        // Simple keyword extraction - in practice, would use NLP
        text.split_whitespace()
            .filter(|w| w.len() > 4)
            .take(5)
            .map(|w| w.to_lowercase())
            .collect()
    }

    fn strategy_to_key(&self, strategy: &RetrievalStrategy) -> String {
        match strategy {
            RetrievalStrategy::SimilarIssues { .. } => "similar_issues".to_string(),
            RetrievalStrategy::ContextualMemories { .. } => "contextual_memories".to_string(),
            RetrievalStrategy::FrameworkExamples { .. } => "framework_examples".to_string(),
            RetrievalStrategy::RecentConversations { .. } => "recent_conversations".to_string(),
        }
    }

    fn create_strategy_for_pattern(
        &self,
        strategy_type: &str,
        pattern: &ConversationPattern,
    ) -> RetrievalStrategy {
        match strategy_type {
            "similar_issues" => RetrievalStrategy::SimilarIssues {
                problem_description: pattern.context.clone(),
                include_solutions: true,
                time_window_days: Some(60),
            },
            "contextual_memories" => RetrievalStrategy::ContextualMemories {
                context_keywords: self.extract_keywords(&pattern.context),
                relevance_threshold: 0.75,
                limit: 20,
            },
            "framework_examples" => RetrievalStrategy::FrameworkExamples {
                framework_type: "general".to_string(),
                pattern_type: pattern.pattern_type.clone(),
                min_success_score: 0.7,
            },
            _ => RetrievalStrategy::RecentConversations {
                topic_keywords: self.extract_keywords(&pattern.context),
                hours_back: 48,
                min_relevance: 0.65,
            },
        }
    }

    fn update_pattern_strategy_map(
        &mut self,
        pattern_type: &PatternType,
        strategy_key: &str,
        score: f32,
    ) {
        let pattern_type_name = self.pattern_type_to_string(pattern_type);
        let strategies = self
            .pattern_strategy_map
            .entry(pattern_type_name)
            .or_insert_with(Vec::new);

        // Update or insert strategy score
        if let Some(pos) = strategies.iter().position(|(s, _)| s == strategy_key) {
            strategies[pos].1 = score;
        } else {
            strategies.push((strategy_key.to_string(), score));
        }

        // Keep sorted by score (descending)
        strategies.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

        // Keep only top 5 strategies per pattern
        strategies.truncate(5);
    }

    fn pattern_type_to_string(&self, pattern_type: &PatternType) -> String {
        match pattern_type {
            PatternType::ThinkingPattern { .. } => "thinking".to_string(),
            PatternType::InteractionPattern { .. } => "interaction".to_string(),
            PatternType::RetrievalPattern { .. } => "retrieval".to_string(),
            PatternType::UncertaintyPattern { .. } => "uncertainty".to_string(),
            PatternType::ProblemSolving => "problem_solving".to_string(),
            PatternType::ConceptExploration => "concept_exploration".to_string(),
            PatternType::Debugging => "debugging".to_string(),
            PatternType::SystemDesign => "system_design".to_string(),
            PatternType::Learning => "learning".to_string(),
        }
    }

}

// HTTP Client implementation
pub struct UnifiedIntelligenceClient {
    base_url: String,
    client: reqwest::Client,
}

impl UnifiedIntelligenceClient {
    pub fn new(base_url: String) -> Self {
        Self {
            base_url,
            client: reqwest::Client::new(),
        }
    }

    async fn call_mcp_tool(
        &self,
        tool_name: &str,
        params: serde_json::Value,
    ) -> Result<serde_json::Value, RetrievalError> {
        let response = self
            .client
            .post(&format!("{}/tools/{}", self.base_url, tool_name))
            .json(&params)
            .send()
            .await?;

        if !response.status().is_success() {
            return Err(RetrievalError::QueryFailed(format!(
                "MCP tool {} returned status: {}",
                tool_name,
                response.status()
            )));
        }

        Ok(response.json().await?)
    }
}

#[async_trait]
impl MemoryInterface for UnifiedIntelligenceClient {
    async fn query_memories(&self, params: QueryParams) -> Result<Vec<Memory>, RetrievalError> {
        let query = match &params.strategy {
            RetrievalStrategy::SimilarIssues {
                problem_description,
                ..
            } => problem_description.clone(),
            RetrievalStrategy::ContextualMemories {
                context_keywords, ..
            } => context_keywords.join(" "),
            RetrievalStrategy::FrameworkExamples { framework_type, .. } => {
                format!("framework:{}", framework_type)
            }
            RetrievalStrategy::RecentConversations { topic_keywords, .. } => {
                topic_keywords.join(" ")
            }
        };

        self.semantic_search(&query, params.threshold, params.limit)
            .await
    }

    async fn get_thought_context(&self, thought_id: &str) -> Result<Context, RetrievalError> {
        let params = serde_json::json!({
            "thought_id": thought_id
        });

        let result = self.call_mcp_tool("ui_recall", params).await?;
        
        // Parse result into Context
        let context: Context = serde_json::from_value(result)?;
        Ok(context)
    }

    async fn semantic_search(
        &self,
        query: &str,
        threshold: f32,
        limit: usize,
    ) -> Result<Vec<Memory>, RetrievalError> {
        let params = serde_json::json!({
            "operation": "semantic_search",
            "query": query,
            "threshold": threshold,
            "limit": limit
        });

        let result = self.call_mcp_tool("ui_recall", params).await?;
        
        // Parse result into Vec<Memory>
        let memories: Vec<Memory> = serde_json::from_value(result)?;
        Ok(memories)
    }

    async fn chain_lookup(&self, chain_id: &str) -> Result<Vec<Memory>, RetrievalError> {
        let params = serde_json::json!({
            "operation": "chain_lookup",
            "chain_id": chain_id
        });

        let result = self.call_mcp_tool("ui_recall", params).await?;
        
        // Parse result into Vec<Memory>
        let memories: Vec<Memory> = serde_json::from_value(result)?;
        Ok(memories)
    }
}

// RetrievalLearner is the main struct exposed to the service
pub struct RetrievalLearner {
    strategy_learner: StrategyLearner,
    client: UnifiedIntelligenceClient,
}

impl RetrievalLearner {
    pub async fn new(_redis_conn: std::sync::Arc<tokio::sync::RwLock<redis::aio::ConnectionManager>>) -> Result<Self, RetrievalError> {
        // TODO: Make UnifiedIntelligence URL configurable
        // For now, using a stub that won't try to connect during initialization
        let ui_url = std::env::var("UNIFIED_INTELLIGENCE_URL")
            .unwrap_or_else(|_| "http://localhost:3000".to_string());
        
        Ok(Self {
            strategy_learner: StrategyLearner::new(),
            client: UnifiedIntelligenceClient::new(ui_url),
        })
    }

    pub async fn retrieve_context(&self, pattern: &ConversationPattern) -> Result<Vec<Memory>, RetrievalError> {
        let strategy = self.strategy_learner.suggest_strategy(pattern);
        let params = QueryParams {
            strategy,
            limit: 10,
            threshold: 0.7,
            include_metadata: true,
        };
        
        self.client.query_memories(params).await
    }

    pub fn learn_from_outcome(&mut self, outcome: RetrievalOutcome) {
        self.strategy_learner.learn_from_outcome(outcome);
    }

    pub async fn suggest_strategies(&self, task_description: &str, _constraints: serde_json::Value) -> Result<Vec<RetrievalStrategy>, RetrievalError> {
        // Create a temporary conversation pattern from the task description
        let pattern = ConversationPattern {
            pattern_type: PatternType::ProblemSolving,
            context: task_description.to_string(),
            confidence: 0.8,
            timestamp: chrono::Utc::now(),
            metadata: HashMap::new(),
        };
        
        let strategy = self.strategy_learner.suggest_strategy(&pattern);
        Ok(vec![strategy])
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_strategy_learner_initialization() {
        let learner = StrategyLearner::new();
        assert!(learner.effectiveness_map.is_empty());
        assert!(learner.pattern_strategy_map.is_empty());
    }

    #[test]
    fn test_default_strategy_selection() {
        let learner = StrategyLearner::new();
        let pattern = ConversationPattern {
            pattern_type: PatternType::ProblemSolving,
            context: "Debug memory leak issue".to_string(),
            confidence: 0.85,
            timestamp: Utc::now(),
            metadata: HashMap::new(),
        };

        match learner.suggest_strategy(&pattern) {
            RetrievalStrategy::SimilarIssues { .. } => {}
            _ => panic!("Expected SimilarIssues strategy for ProblemSolving pattern"),
        }
    }

    #[test]
    fn test_outcome_learning() {
        let mut learner = StrategyLearner::new();
        let outcome = RetrievalOutcome {
            strategy: RetrievalStrategy::SimilarIssues {
                problem_description: "test".to_string(),
                include_solutions: true,
                time_window_days: Some(30),
            },
            results_count: 5,
            avg_relevance: 0.85,
            was_helpful: true,
            pattern_context: Some(ConversationPattern {
                pattern_type: PatternType::ProblemSolving,
                context: "test".to_string(),
                confidence: 0.9,
                timestamp: Utc::now(),
                metadata: HashMap::new(),
            }),
        };

        learner.learn_from_outcome(outcome);
        assert_eq!(learner.effectiveness_map.len(), 1);
        assert!(learner.effectiveness_map.contains_key("similar_issues"));
    }
}