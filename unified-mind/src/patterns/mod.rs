use anyhow::Result;
use chrono::{DateTime, Utc};
use redis::aio::ConnectionManager;
use redis::AsyncCommands;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;

// Pattern Types with detailed structures
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "type")]
pub enum PatternType {
    ThinkingPattern {
        triggers: Vec<String>,
        frameworks: Vec<String>,
        success_rate: f64,
        context_keywords: Vec<String>,
    },
    InteractionPattern {
        communication_style: String,
        preferred_detail_level: String,
        response_expectations: Vec<String>,
        emotional_indicators: Vec<String>,
    },
    RetrievalPattern {
        query_triggers: Vec<String>,
        context_depth: u32,
        time_relevance: String, // recent, historical, all
        memory_types: Vec<String>,
    },
    UncertaintyPattern {
        uncertainty_markers: Vec<String>,
        confidence_threshold: f64,
        help_indicators: Vec<String>,
        clarification_needs: Vec<String>,
    },
    ProblemSolving,
    ConceptExploration,
    Debugging,
    SystemDesign,
    Learning,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Pattern {
    pub id: String,
    pub pattern_type: PatternType,
    pub content: String,
    pub confidence: f64,
    pub frequency: u32,
    pub success_count: u32,
    pub failure_count: u32,
    pub last_matched: DateTime<Utc>,
    pub created_at: DateTime<Utc>,
    pub actions: Vec<PatternAction>,
    pub metadata: PatternMetadata,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PatternAction {
    pub action_type: String,
    pub parameters: serde_json::Value,
    pub priority: u8,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PatternMetadata {
    pub tags: Vec<String>,
    pub category: String,
    pub learning_source: String,
    pub context_examples: Vec<String>,
    pub related_patterns: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PatternMatch {
    pub pattern: Pattern,
    pub confidence: f64,
    pub similarity_score: f64,
    pub context_alignment: f64,
    pub trigger_matches: Vec<String>,
    pub suggested_actions: Vec<PatternAction>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PatternUpdate {
    pub pattern_id: String,
    pub adjustment_type: PatternAdjustmentType,
    pub outcome: PatternOutcome,
    pub context: String,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PatternAdjustmentType {
    SuccessReinforcement,
    FailureAdjustment,
    ContextExpansion,
    TriggerRefinement,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PatternOutcome {
    Success { score: f64 },
    Failure { reason: String },
    Partial { success_rate: f64 },
}

// Core Pattern Engine Implementation
pub struct PatternEngine {
    redis_conn: Arc<RwLock<ConnectionManager>>,
    pattern_cache: Arc<RwLock<HashMap<String, Pattern>>>,
    uncertainty_threshold: f64,
    learning_rate: f64,
}

impl PatternEngine {
    pub async fn new(redis_conn: Arc<RwLock<ConnectionManager>>) -> Result<Self> {
        let engine = Self {
            redis_conn,
            pattern_cache: Arc::new(RwLock::new(HashMap::new())),
            uncertainty_threshold: 0.3,
            learning_rate: 0.1,
        };
        
        // Load patterns from Redis into cache
        engine.load_patterns_to_cache().await?;
        
        Ok(engine)
    }

    async fn load_patterns_to_cache(&self) -> Result<()> {
        let mut conn = self.redis_conn.write().await;
        let pattern_keys: Vec<String> = conn.keys("pattern:*").await?;
        
        let mut cache = self.pattern_cache.write().await;
        for key in pattern_keys {
            if let Ok(pattern_json) = conn.get::<_, String>(&key).await {
                if let Ok(pattern) = serde_json::from_str::<Pattern>(&pattern_json) {
                    cache.insert(pattern.id.clone(), pattern);
                }
            }
        }
        
        Ok(())
    }

    pub async fn find_patterns(&self, context: String, pattern_type: Option<String>) -> Result<Vec<PatternMatch>> {
        let cache = self.pattern_cache.read().await;
        let mut matches = Vec::new();
        
        // Analyze context for key indicators
        let context_lower = context.to_lowercase();
        let words: Vec<&str> = context_lower.split_whitespace().collect();
        
        for pattern in cache.values() {
            // Filter by pattern type if specified
            if let Some(ref ptype) = pattern_type {
                let pattern_type_str = match &pattern.pattern_type {
                    PatternType::ThinkingPattern { .. } => "thinking",
                    PatternType::InteractionPattern { .. } => "interaction",
                    PatternType::RetrievalPattern { .. } => "retrieval",
                    PatternType::UncertaintyPattern { .. } => "uncertainty",
                    PatternType::ProblemSolving => "problem_solving",
                    PatternType::ConceptExploration => "concept_exploration",
                    PatternType::Debugging => "debugging",
                    PatternType::SystemDesign => "system_design",
                    PatternType::Learning => "learning",
                };
                if pattern_type_str != ptype {
                    continue;
                }
            }
            
            // Calculate match scores
            let (trigger_score, trigger_matches) = self.calculate_trigger_score(&pattern, &words);
            let context_score = self.calculate_context_alignment(&pattern, &context_lower);
            let confidence_score = pattern.confidence;
            
            // Weighted scoring
            let total_score = (trigger_score * 0.4) + (context_score * 0.3) + (confidence_score * 0.3);
            
            if total_score > 0.5 {
                matches.push(PatternMatch {
                    pattern: pattern.clone(),
                    confidence: total_score,
                    similarity_score: trigger_score,
                    context_alignment: context_score,
                    trigger_matches,
                    suggested_actions: pattern.actions.clone(),
                });
            }
        }
        
        // Sort by confidence
        matches.sort_by(|a, b| b.confidence.partial_cmp(&a.confidence).unwrap());
        
        Ok(matches)
    }

    fn calculate_trigger_score(&self, pattern: &Pattern, words: &[&str]) -> (f64, Vec<String>) {
        let mut matched_triggers = Vec::new();
        let triggers = match &pattern.pattern_type {
            PatternType::ThinkingPattern { triggers, .. } => triggers,
            PatternType::InteractionPattern { .. } => return (0.0, vec![]),
            PatternType::RetrievalPattern { query_triggers, .. } => query_triggers,
            PatternType::UncertaintyPattern { uncertainty_markers, .. } => uncertainty_markers,
            PatternType::ProblemSolving | PatternType::ConceptExploration | 
            PatternType::Debugging | PatternType::SystemDesign | 
            PatternType::Learning => return (0.0, vec![]),
        };
        
        for trigger in triggers {
            if words.iter().any(|w| w.contains(&trigger.to_lowercase())) {
                matched_triggers.push(trigger.clone());
            }
        }
        
        let score = if triggers.is_empty() {
            0.0
        } else {
            matched_triggers.len() as f64 / triggers.len() as f64
        };
        
        (score, matched_triggers)
    }

    fn calculate_context_alignment(&self, pattern: &Pattern, context: &str) -> f64 {
        let mut score = 0.0;
        let mut factors = 0;
        
        // Check metadata context examples
        for example in &pattern.metadata.context_examples {
            if context.contains(&example.to_lowercase()) {
                score += 1.0;
            }
            factors += 1;
        }
        
        // Check category relevance
        if context.contains(&pattern.metadata.category.to_lowercase()) {
            score += 0.5;
            factors += 1;
        }
        
        // Check tags
        for tag in &pattern.metadata.tags {
            if context.contains(&tag.to_lowercase()) {
                score += 0.3;
            }
            factors += 1;
        }
        
        if factors == 0 {
            0.5 // Neutral score if no factors to check
        } else {
            score / factors as f64
        }
    }

    pub async fn update_patterns(&self, updates: Vec<PatternUpdate>) -> Result<()> {
        let mut cache = self.pattern_cache.write().await;
        let mut conn = self.redis_conn.write().await;
        
        for update in updates {
            if let Some(pattern) = cache.get_mut(&update.pattern_id) {
                match update.adjustment_type {
                    PatternAdjustmentType::SuccessReinforcement => {
                        if let PatternOutcome::Success { score } = update.outcome {
                            pattern.success_count += 1;
                            pattern.confidence = self.calculate_new_confidence(
                                pattern.confidence,
                                score,
                                true
                            );
                        }
                    }
                    PatternAdjustmentType::FailureAdjustment => {
                        if let PatternOutcome::Failure { .. } = update.outcome {
                            pattern.failure_count += 1;
                            pattern.confidence = self.calculate_new_confidence(
                                pattern.confidence,
                                0.0,
                                false
                            );
                        }
                    }
                    PatternAdjustmentType::ContextExpansion => {
                        pattern.metadata.context_examples.push(update.context.clone());
                        pattern.metadata.context_examples.dedup();
                    }
                    PatternAdjustmentType::TriggerRefinement => {
                        // Extract new triggers from context
                        if let PatternType::ThinkingPattern { ref mut triggers, .. } = &mut pattern.pattern_type {
                            // Simple trigger extraction - can be made more sophisticated
                            let new_triggers: Vec<String> = update.context
                                .split_whitespace()
                                .filter(|w| w.len() > 4)
                                .map(|w| w.to_string())
                                .collect();
                            triggers.extend(new_triggers);
                            triggers.dedup();
                        }
                    }
                }
                
                pattern.frequency += 1;
                pattern.last_matched = Utc::now();
                
                // Update success rate for thinking patterns
                if let PatternType::ThinkingPattern { ref mut success_rate, .. } = &mut pattern.pattern_type {
                    let total = pattern.success_count + pattern.failure_count;
                    if total > 0 {
                        *success_rate = pattern.success_count as f64 / total as f64;
                    }
                }
                
                // Save to Redis
                let key = format!("pattern:{}", pattern.id);
                let pattern_json = serde_json::to_string(&pattern)?;
                conn.set::<_, _, ()>(&key, pattern_json).await?;
            }
        }
        
        Ok(())
    }

    fn calculate_new_confidence(&self, current: f64, score: f64, success: bool) -> f64 {
        let adjustment = if success {
            self.learning_rate * (score - current)
        } else {
            -self.learning_rate * (1.0 - score)
        };
        
        (current + adjustment).clamp(0.0, 1.0)
    }

    pub async fn learn_new_pattern(&self, pattern_data: serde_json::Value) -> Result<String> {
        let pattern_id = Uuid::new_v4().to_string();
        
        // Analyze the input to determine pattern type
        let pattern_type = self.infer_pattern_type(&pattern_data)?;
        
        let pattern = Pattern {
            id: pattern_id.clone(),
            pattern_type,
            content: pattern_data["content"].as_str().unwrap_or("").to_string(),
            confidence: 0.6, // Initial confidence
            frequency: 1,
            success_count: 0,
            failure_count: 0,
            last_matched: Utc::now(),
            created_at: Utc::now(),
            actions: self.generate_initial_actions(&pattern_data),
            metadata: PatternMetadata {
                tags: self.extract_tags(&pattern_data),
                category: pattern_data["category"].as_str().unwrap_or("general").to_string(),
                learning_source: pattern_data["source"].as_str().unwrap_or("ui_think").to_string(),
                context_examples: vec![pattern_data["context"].as_str().unwrap_or("").to_string()],
                related_patterns: vec![],
            },
        };
        
        // Save to cache and Redis
        self.pattern_cache.write().await.insert(pattern_id.clone(), pattern.clone());
        
        let mut conn = self.redis_conn.write().await;
        let key = format!("pattern:{}", pattern_id);
        let pattern_json = serde_json::to_string(&pattern)?;
        conn.set::<_, _, ()>(&key, pattern_json).await?;
        
        Ok(pattern_id)
    }

    fn infer_pattern_type(&self, data: &serde_json::Value) -> Result<PatternType> {
        let content = data["content"].as_str().unwrap_or("").to_lowercase();
        let tags = data["tags"].as_array()
            .map(|arr| arr.iter()
                .filter_map(|v| v.as_str())
                .map(|s| s.to_lowercase())
                .collect::<Vec<_>>())
            .unwrap_or_default();
        
        // Detect uncertainty patterns
        let uncertainty_markers = vec!["not sure", "maybe", "possibly", "might be", "seems like", 
                                      "i think", "could be", "unclear", "confused"];
        let uncertainty_count = uncertainty_markers.iter()
            .filter(|marker| content.contains(*marker))
            .count();
        
        if uncertainty_count >= 2 {
            return Ok(PatternType::UncertaintyPattern {
                uncertainty_markers: uncertainty_markers.iter().map(|s| s.to_string()).collect(),
                confidence_threshold: self.uncertainty_threshold,
                help_indicators: vec!["need help".to_string(), "assistance".to_string()],
                clarification_needs: vec![],
            });
        }
        
        // Detect retrieval patterns
        if content.contains("remember") || content.contains("recall") || 
           content.contains("what was") || content.contains("previous") {
            return Ok(PatternType::RetrievalPattern {
                query_triggers: vec!["remember".to_string(), "recall".to_string(), 
                                   "previous".to_string(), "earlier".to_string()],
                context_depth: 5,
                time_relevance: "recent".to_string(),
                memory_types: vec!["conversation".to_string(), "decision".to_string()],
            });
        }
        
        // Detect thinking patterns
        if tags.contains(&"framework".to_string()) || content.contains("analyze") ||
           content.contains("consider") || content.contains("evaluate") {
            return Ok(PatternType::ThinkingPattern {
                triggers: vec!["analyze".to_string(), "consider".to_string(), 
                             "evaluate".to_string(), "think about".to_string()],
                frameworks: vec!["first-principles".to_string(), "OODA".to_string()],
                success_rate: 0.0,
                context_keywords: vec![],
            });
        }
        
        // Default to interaction pattern
        Ok(PatternType::InteractionPattern {
            communication_style: "conversational".to_string(),
            preferred_detail_level: "moderate".to_string(),
            response_expectations: vec![],
            emotional_indicators: vec![],
        })
    }

    fn generate_initial_actions(&self, data: &serde_json::Value) -> Vec<PatternAction> {
        let mut actions = Vec::new();
        
        // Based on pattern type inferred from content
        let content = data["content"].as_str().unwrap_or("").to_lowercase();
        
        if content.contains("remember") || content.contains("recall") {
            actions.push(PatternAction {
                action_type: "retrieve_memory".to_string(),
                parameters: json!({
                    "depth": 5,
                    "relevance_threshold": 0.7
                }),
                priority: 1,
            });
        }
        
        if content.contains("not sure") || content.contains("confused") {
            actions.push(PatternAction {
                action_type: "seek_clarification".to_string(),
                parameters: json!({
                    "method": "contextual_search",
                    "fallback": "ask_user"
                }),
                priority: 1,
            });
        }
        
        if content.contains("analyze") || content.contains("evaluate") {
            actions.push(PatternAction {
                action_type: "apply_framework".to_string(),
                parameters: json!({
                    "frameworks": ["first-principles", "OODA"],
                    "depth": "comprehensive"
                }),
                priority: 2,
            });
        }
        
        // Default action
        if actions.is_empty() {
            actions.push(PatternAction {
                action_type: "standard_response".to_string(),
                parameters: json!({}),
                priority: 3,
            });
        }
        
        actions
    }

    fn extract_tags(&self, data: &serde_json::Value) -> Vec<String> {
        if let Some(tags) = data["tags"].as_array() {
            tags.iter()
                .filter_map(|v| v.as_str())
                .map(|s| s.to_string())
                .collect()
        } else {
            vec![]
        }
    }

    // Detect uncertainty in real-time
    pub async fn detect_uncertainty(&self, content: &str) -> Option<PatternMatch> {
        let uncertainty_phrases = vec![
            "seems familiar", "not sure", "i think", "maybe", "possibly",
            "might be", "could be", "unsure", "uncertain", "vague memory",
            "rings a bell", "sounds familiar", "déjà vu"
        ];
        
        let content_lower = content.to_lowercase();
        let mut uncertainty_score = 0.0;
        let mut matched_phrases = Vec::new();
        
        for phrase in &uncertainty_phrases {
            if content_lower.contains(phrase) {
                uncertainty_score += 0.2;
                matched_phrases.push(phrase.to_string());
            }
        }
        
        if uncertainty_score > self.uncertainty_threshold {
            // Create a temporary uncertainty pattern match
            let pattern = Pattern {
                id: "temp-uncertainty".to_string(),
                pattern_type: PatternType::UncertaintyPattern {
                    uncertainty_markers: matched_phrases.clone(),
                    confidence_threshold: self.uncertainty_threshold,
                    help_indicators: vec!["detected uncertainty".to_string()],
                    clarification_needs: vec!["memory retrieval".to_string(), "context search".to_string()],
                },
                content: content.to_string(),
                confidence: uncertainty_score.min(1.0),
                frequency: 1,
                success_count: 0,
                failure_count: 0,
                last_matched: Utc::now(),
                created_at: Utc::now(),
                actions: vec![
                    PatternAction {
                        action_type: "retrieve_similar_memories".to_string(),
                        parameters: json!({
                            "similarity_threshold": 0.6,
                            "max_results": 5
                        }),
                        priority: 1,
                    },
                    PatternAction {
                        action_type: "search_context".to_string(),
                        parameters: json!({
                            "scope": "recent",
                            "keywords": matched_phrases
                        }),
                        priority: 2,
                    }
                ],
                metadata: PatternMetadata {
                    tags: vec!["uncertainty".to_string(), "detection".to_string()],
                    category: "cognitive".to_string(),
                    learning_source: "real-time".to_string(),
                    context_examples: vec![content.to_string()],
                    related_patterns: vec![],
                },
            };
            
            Some(PatternMatch {
                pattern,
                confidence: uncertainty_score,
                similarity_score: uncertainty_score,
                context_alignment: 1.0,
                trigger_matches: matched_phrases,
                suggested_actions: vec![
                    PatternAction {
                        action_type: "subconscious_assist".to_string(),
                        parameters: json!({
                            "type": "memory_retrieval",
                            "urgency": "high"
                        }),
                        priority: 1,
                    }
                ],
            })
        } else {
            None
        }
    }

    // Framework trigger detection
    pub async fn detect_framework_triggers(&self, content: &str) -> Option<String> {
        let framework_triggers = vec![
            ("why does this matter", "first-principles"),
            ("what's the root cause", "first-principles"),
            ("break this down", "first-principles"),
            ("observe orient decide act", "OODA"),
            ("what's happening here", "OODA"),
            ("rapid decision", "OODA"),
            ("question everything", "socratic"),
            ("what if", "socratic"),
            ("challenge assumption", "socratic"),
        ];
        
        let content_lower = content.to_lowercase();
        
        for (trigger, framework) in framework_triggers {
            if content_lower.contains(trigger) {
                return Some(framework.to_string());
            }
        }
        
        None
    }

    // Pattern strength decay over time
    pub async fn decay_pattern_strengths(&self) -> Result<()> {
        let mut cache = self.pattern_cache.write().await;
        let mut conn = self.redis_conn.write().await;
        let now = Utc::now();
        
        for pattern in cache.values_mut() {
            let days_since_match = (now - pattern.last_matched).num_days();
            
            if days_since_match > 7 {
                // Decay confidence based on time
                let decay_factor = 0.95_f64.powi((days_since_match / 7) as i32);
                pattern.confidence *= decay_factor;
                
                // Save updated pattern
                let key = format!("pattern:{}", pattern.id);
                let pattern_json = serde_json::to_string(&pattern)?;
                conn.set::<_, _, ()>(&key, pattern_json).await?;
            }
        }
        
        Ok(())
    }

    // Get pattern statistics for monitoring
    pub async fn get_pattern_stats(&self) -> Result<serde_json::Value> {
        let cache = self.pattern_cache.read().await;
        
        let mut stats = HashMap::new();
        let mut type_counts = HashMap::new();
        let mut total_success = 0;
        let mut total_failure = 0;
        
        for pattern in cache.values() {
            let type_name = match &pattern.pattern_type {
                PatternType::ThinkingPattern { .. } => "thinking",
                PatternType::InteractionPattern { .. } => "interaction",
                PatternType::RetrievalPattern { .. } => "retrieval",
                PatternType::UncertaintyPattern { .. } => "uncertainty",
                PatternType::ProblemSolving => "problem_solving",
                PatternType::ConceptExploration => "concept_exploration",
                PatternType::Debugging => "debugging",
                PatternType::SystemDesign => "system_design",
                PatternType::Learning => "learning",
            };
            
            *type_counts.entry(type_name).or_insert(0) += 1;
            total_success += pattern.success_count;
            total_failure += pattern.failure_count;
        }
        
        stats.insert("total_patterns", json!(cache.len()));
        stats.insert("pattern_types", json!(type_counts));
        stats.insert("total_successes", json!(total_success));
        stats.insert("total_failures", json!(total_failure));
        stats.insert("success_rate", json!(
            if total_success + total_failure > 0 {
                total_success as f64 / (total_success + total_failure) as f64
            } else {
                0.0
            }
        ));
        
        Ok(json!(stats))
    }
}

// Tests
#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_uncertainty_detection() {
        // Test implementation would go here
    }

    #[tokio::test]
    async fn test_framework_triggers() {
        // Test implementation would go here
    }
}