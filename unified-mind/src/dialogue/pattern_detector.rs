use anyhow::Result;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::patterns::{PatternEngine, PatternMatch};
use super::generator::{InterventionTrigger, FrameworkType};

/// Sophisticated pattern detection for internal dialogue triggers
pub struct DialoguePatternDetector {
    pattern_engine: std::sync::Arc<PatternEngine>,
    dialogue_triggers: HashMap<String, DialogueTriggerPattern>,
    context_analyzer: ContextAnalyzer,
    timing_analyzer: TimingAnalyzer,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DialogueTriggerPattern {
    pub pattern_name: String,
    pub trigger_phrases: Vec<String>,
    pub confidence_threshold: f64,
    pub intervention_type_hint: String,
    pub context_requirements: Vec<ContextRequirement>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContextRequirement {
    pub requirement_type: ContextType,
    pub value: String,
    pub weight: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ContextType {
    ProblemSolving,
    Learning,
    Planning,
    Debugging,
    Creative,
    Reflection,
    Decision,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThoughtContext {
    pub primary_intent: ThoughtIntent,
    pub cognitive_state: CognitiveState,
    pub temporal_context: TemporalContext,
    pub problem_indicators: Vec<ProblemIndicator>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ThoughtIntent {
    Questioning,        // User is asking questions
    Exploring,          // User is exploring ideas
    Solving,            // User is solving a problem
    Remembering,        // User is trying to recall
    Planning,           // User is planning actions
    Analyzing,          // User is analyzing information
    Deciding,           // User is making a decision
    Creating,           // User is creating something new
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CognitiveState {
    pub confusion_level: f64,      // 0.0 = clear, 1.0 = very confused
    pub certainty_level: f64,      // 0.0 = uncertain, 1.0 = certain
    pub engagement_level: f64,     // 0.0 = disengaged, 1.0 = highly engaged
    pub frustration_level: f64,    // 0.0 = calm, 1.0 = frustrated
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemporalContext {
    pub time_since_last_thought: u64,  // milliseconds
    pub thought_velocity: f64,         // thoughts per minute
    pub session_duration: u64,         // milliseconds
    pub pattern_recency: HashMap<String, DateTime<Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProblemIndicator {
    pub indicator_type: ProblemType,
    pub severity: f64,
    pub evidence: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ProblemType {
    StuckPattern,       // Repeating same approach
    MissingContext,     // Lacking key information
    WrongApproach,      // Using ineffective method
    OverComplexity,     // Making it too complicated
    MissingStep,        // Skipping important steps
}

impl DialoguePatternDetector {
    pub fn new(pattern_engine: std::sync::Arc<PatternEngine>) -> Self {
        let mut dialogue_triggers = HashMap::new();
        
        // Initialize key dialogue trigger patterns
        dialogue_triggers.insert(
            "uncertainty".to_string(),
            DialogueTriggerPattern {
                pattern_name: "uncertainty_detection".to_string(),
                trigger_phrases: vec![
                    "not sure".to_string(),
                    "I wonder".to_string(),
                    "maybe".to_string(),
                    "could be".to_string(),
                    "might be".to_string(),
                    "possibly".to_string(),
                    "I think".to_string(),
                    "perhaps".to_string(),
                ],
                confidence_threshold: 0.6,
                intervention_type_hint: "gut_feeling".to_string(),
                context_requirements: vec![],
            }
        );
        
        dialogue_triggers.insert(
            "stuck_pattern".to_string(),
            DialogueTriggerPattern {
                pattern_name: "stuck_detection".to_string(),
                trigger_phrases: vec![
                    "doesn't work".to_string(),
                    "still not".to_string(),
                    "same error".to_string(),
                    "tried that".to_string(),
                    "not working".to_string(),
                ],
                confidence_threshold: 0.7,
                intervention_type_hint: "pattern_break".to_string(),
                context_requirements: vec![
                    ContextRequirement {
                        requirement_type: ContextType::ProblemSolving,
                        value: "active".to_string(),
                        weight: 0.8,
                    }
                ],
            }
        );
        
        dialogue_triggers.insert(
            "memory_search".to_string(),
            DialogueTriggerPattern {
                pattern_name: "memory_trigger".to_string(),
                trigger_phrases: vec![
                    "remember when".to_string(),
                    "last time".to_string(),
                    "before".to_string(),
                    "similar to".to_string(),
                    "like when".to_string(),
                    "reminds me".to_string(),
                ],
                confidence_threshold: 0.5,
                intervention_type_hint: "memory_recall".to_string(),
                context_requirements: vec![],
            }
        );
        
        dialogue_triggers.insert(
            "framework_needed".to_string(),
            DialogueTriggerPattern {
                pattern_name: "framework_activation".to_string(),
                trigger_phrases: vec![
                    "how do I".to_string(),
                    "best way to".to_string(),
                    "approach this".to_string(),
                    "where to start".to_string(),
                    "systematic".to_string(),
                ],
                confidence_threshold: 0.6,
                intervention_type_hint: "framework_suggestion".to_string(),
                context_requirements: vec![
                    ContextRequirement {
                        requirement_type: ContextType::Planning,
                        value: "needed".to_string(),
                        weight: 0.7,
                    }
                ],
            }
        );
        
        Self {
            pattern_engine,
            dialogue_triggers,
            context_analyzer: ContextAnalyzer::new(),
            timing_analyzer: TimingAnalyzer::new(),
        }
    }
    
    /// Detect dialogue patterns that might trigger internal voice
    pub async fn detect_dialogue_patterns(
        &self,
        user_input: &str,
        recent_history: &[String],
    ) -> Result<Vec<DialoguePattern>> {
        let mut detected_patterns = Vec::new();
        
        // 1. Check for direct trigger phrases
        for (pattern_type, trigger_pattern) in &self.dialogue_triggers {
            let confidence = self.calculate_trigger_confidence(user_input, trigger_pattern);
            if confidence > trigger_pattern.confidence_threshold {
                detected_patterns.push(DialoguePattern {
                    pattern_type: pattern_type.clone(),
                    confidence,
                    evidence: trigger_pattern.trigger_phrases
                        .iter()
                        .filter(|phrase| user_input.to_lowercase().contains(&phrase.to_lowercase()))
                        .cloned()
                        .collect(),
                    context_match: self.check_context_requirements(
                        &trigger_pattern.context_requirements,
                        user_input,
                        recent_history,
                    ),
                    suggested_intervention: trigger_pattern.intervention_type_hint.clone(),
                });
            }
        }
        
        // 2. Detect cognitive patterns
        let cognitive_patterns = self.detect_cognitive_patterns(user_input, recent_history)?;
        detected_patterns.extend(cognitive_patterns);
        
        // 3. Detect temporal patterns
        let temporal_patterns = self.timing_analyzer.detect_temporal_patterns(recent_history)?;
        detected_patterns.extend(temporal_patterns);
        
        // 4. Sort by confidence
        detected_patterns.sort_by(|a, b| b.confidence.partial_cmp(&a.confidence).unwrap());
        
        Ok(detected_patterns)
    }
    
    /// Analyze thought context for intervention decisions
    pub fn analyze_thought_context(
        &self,
        user_input: &str,
        recent_history: &[String],
    ) -> Result<ThoughtContext> {
        let primary_intent = self.detect_thought_intent(user_input, recent_history)?;
        let cognitive_state = self.assess_cognitive_state(user_input, recent_history)?;
        let temporal_context = self.timing_analyzer.build_temporal_context(recent_history)?;
        let problem_indicators = self.detect_problem_indicators(user_input, recent_history)?;
        
        Ok(ThoughtContext {
            primary_intent,
            cognitive_state,
            temporal_context,
            problem_indicators,
        })
    }
    
    /// Build comprehensive intervention trigger
    pub async fn build_intervention_trigger(
        &self,
        patterns: Vec<DialoguePattern>,
        thought_context: ThoughtContext,
        pattern_matches: Vec<PatternMatch>,
    ) -> Result<InterventionTrigger> {
        // Calculate aggregate confidence
        let confidence = if patterns.is_empty() {
            0.0
        } else {
            patterns.iter().map(|p| p.confidence).sum::<f64>() / patterns.len() as f64
        };
        
        // Determine if uncertainty is present
        let uncertainty_detected = patterns.iter()
            .any(|p| p.pattern_type == "uncertainty" || 
                    thought_context.cognitive_state.confusion_level > 0.6);
        
        // Extract concern areas from problem indicators
        let concern_areas: Vec<String> = thought_context.problem_indicators
            .iter()
            .map(|pi| format!("{:?}: {}", pi.indicator_type, pi.evidence.join(", ")))
            .collect();
        
        // Calculate relevance based on context match
        let relevance = patterns.iter()
            .map(|p| p.context_match)
            .fold(0.0f64, |a, b| a.max(b));
        
        // Estimate novelty based on pattern recency
        let novelty = self.estimate_novelty(&patterns, &thought_context.temporal_context);
        
        Ok(InterventionTrigger {
            patterns: patterns.iter()
                .map(|p| p.pattern_type.clone())
                .collect(),
            confidence,
            relevance,
            novelty,
            uncertainty_detected,
            uncertainty_level: thought_context.cognitive_state.confusion_level,
            concern_areas,
            pattern_match_strength: pattern_matches.first()
                .map(|p| p.similarity_score)
                .unwrap_or(0.0),
            memory_relevance: self.calculate_memory_relevance(&patterns),
        })
    }
    
    fn calculate_trigger_confidence(
        &self,
        input: &str,
        trigger_pattern: &DialogueTriggerPattern,
    ) -> f64 {
        let input_lower = input.to_lowercase();
        let matches = trigger_pattern.trigger_phrases
            .iter()
            .filter(|phrase| input_lower.contains(&phrase.to_lowercase()))
            .count();
        
        if matches == 0 {
            return 0.0;
        }
        
        // Base confidence on number of matches
        let base_confidence = matches as f64 / trigger_pattern.trigger_phrases.len() as f64;
        
        // Boost confidence if multiple phrases match
        if matches > 1 {
            (base_confidence * 1.2).min(1.0)
        } else {
            base_confidence
        }
    }
    
    fn check_context_requirements(
        &self,
        requirements: &[ContextRequirement],
        _input: &str,
        _history: &[String],
    ) -> f64 {
        if requirements.is_empty() {
            return 1.0;
        }
        
        // Simplified context matching - would be more sophisticated in practice
        requirements.iter()
            .map(|req| req.weight)
            .sum::<f64>() / requirements.len() as f64
    }
    
    fn detect_cognitive_patterns(
        &self,
        input: &str,
        history: &[String],
    ) -> Result<Vec<DialoguePattern>> {
        let mut patterns = Vec::new();
        
        // Detect question patterns
        if input.contains('?') || input.starts_with("how") || input.starts_with("why") || 
           input.starts_with("what") || input.starts_with("when") {
            patterns.push(DialoguePattern {
                pattern_type: "questioning".to_string(),
                confidence: 0.8,
                evidence: vec!["question detected".to_string()],
                context_match: 0.9,
                suggested_intervention: "socratic_response".to_string(),
            });
        }
        
        // Detect repetition (stuck pattern)
        if history.len() > 2 {
            let similar_count = history.iter()
                .filter(|h| self.calculate_similarity(input, h) > 0.7)
                .count();
            
            if similar_count > 1 {
                patterns.push(DialoguePattern {
                    pattern_type: "repetition".to_string(),
                    confidence: 0.7,
                    evidence: vec!["similar thoughts detected".to_string()],
                    context_match: 0.8,
                    suggested_intervention: "pattern_break".to_string(),
                });
            }
        }
        
        Ok(patterns)
    }
    
    fn detect_thought_intent(
        &self,
        input: &str,
        _history: &[String],
    ) -> Result<ThoughtIntent> {
        let input_lower = input.to_lowercase();
        
        if input_lower.contains('?') || input_lower.starts_with("what") || 
           input_lower.starts_with("how") || input_lower.starts_with("why") {
            Ok(ThoughtIntent::Questioning)
        } else if input_lower.contains("plan") || input_lower.contains("steps") ||
                  input_lower.contains("first") || input_lower.contains("then") {
            Ok(ThoughtIntent::Planning)
        } else if input_lower.contains("remember") || input_lower.contains("recall") ||
                  input_lower.contains("last time") {
            Ok(ThoughtIntent::Remembering)
        } else if input_lower.contains("analyze") || input_lower.contains("examine") ||
                  input_lower.contains("look at") {
            Ok(ThoughtIntent::Analyzing)
        } else if input_lower.contains("create") || input_lower.contains("build") ||
                  input_lower.contains("make") {
            Ok(ThoughtIntent::Creating)
        } else if input_lower.contains("should") || input_lower.contains("better") ||
                  input_lower.contains("choose") {
            Ok(ThoughtIntent::Deciding)
        } else if input_lower.contains("solve") || input_lower.contains("fix") ||
                  input_lower.contains("debug") {
            Ok(ThoughtIntent::Solving)
        } else {
            Ok(ThoughtIntent::Exploring)
        }
    }
    
    fn assess_cognitive_state(
        &self,
        input: &str,
        history: &[String],
    ) -> Result<CognitiveState> {
        let input_lower = input.to_lowercase();
        
        // Assess confusion level
        let confusion_markers = ["confused", "not sure", "don't understand", "unclear", "lost"];
        let confusion_count = confusion_markers.iter()
            .filter(|&marker| input_lower.contains(marker))
            .count();
        let confusion_level = (confusion_count as f64 * 0.2).min(1.0);
        
        // Assess certainty level
        let certainty_markers = ["definitely", "certainly", "obviously", "clearly", "sure"];
        let uncertainty_markers = ["maybe", "perhaps", "might", "possibly", "could be"];
        let certainty_count = certainty_markers.iter()
            .filter(|&marker| input_lower.contains(marker))
            .count();
        let uncertainty_count = uncertainty_markers.iter()
            .filter(|&marker| input_lower.contains(marker))
            .count();
        let certainty_level = if uncertainty_count > certainty_count {
            0.3
        } else if certainty_count > 0 {
            0.8
        } else {
            0.5
        };
        
        // Assess engagement (based on thought length and complexity)
        let engagement_level = (input.len() as f64 / 200.0).min(1.0).max(0.3);
        
        // Assess frustration
        let frustration_markers = ["frustrated", "annoying", "stuck", "doesn't work", "damn", "ugh"];
        let frustration_count = frustration_markers.iter()
            .filter(|&marker| input_lower.contains(marker))
            .count();
        let repetition_frustration = if history.len() > 2 {
            history.windows(2)
                .filter(|w| self.calculate_similarity(&w[0], &w[1]) > 0.8)
                .count() as f64 * 0.1
        } else {
            0.0
        };
        let frustration_level = ((frustration_count as f64 * 0.2) + repetition_frustration).min(1.0);
        
        Ok(CognitiveState {
            confusion_level,
            certainty_level,
            engagement_level,
            frustration_level,
        })
    }
    
    fn detect_problem_indicators(
        &self,
        input: &str,
        history: &[String],
    ) -> Result<Vec<ProblemIndicator>> {
        let mut indicators = Vec::new();
        
        // Check for stuck pattern
        if history.len() > 2 {
            let similar_thoughts = history.windows(2)
                .filter(|w| self.calculate_similarity(&w[0], &w[1]) > 0.7)
                .count();
            
            if similar_thoughts > 1 {
                indicators.push(ProblemIndicator {
                    indicator_type: ProblemType::StuckPattern,
                    severity: (similar_thoughts as f64 * 0.3).min(1.0),
                    evidence: vec!["Repeating similar thoughts".to_string()],
                });
            }
        }
        
        // Check for missing context
        let context_markers = ["don't know", "not sure about", "what is", "where is"];
        let missing_context = context_markers.iter()
            .any(|&marker| input.to_lowercase().contains(marker));
        
        if missing_context {
            indicators.push(ProblemIndicator {
                indicator_type: ProblemType::MissingContext,
                severity: 0.6,
                evidence: vec!["Missing information detected".to_string()],
            });
        }
        
        Ok(indicators)
    }
    
    fn calculate_similarity(&self, text1: &str, text2: &str) -> f64 {
        // Simplified similarity calculation
        let words1: std::collections::HashSet<_> = text1.split_whitespace().collect();
        let words2: std::collections::HashSet<_> = text2.split_whitespace().collect();
        
        if words1.is_empty() || words2.is_empty() {
            return 0.0;
        }
        
        let intersection = words1.intersection(&words2).count();
        let union = words1.union(&words2).count();
        
        intersection as f64 / union as f64
    }
    
    fn estimate_novelty(
        &self,
        patterns: &[DialoguePattern],
        temporal_context: &TemporalContext,
    ) -> f64 {
        // Check how recently similar patterns were seen
        let mut total_recency = 0.0;
        let mut count = 0;
        
        for pattern in patterns {
            if let Some(last_seen) = temporal_context.pattern_recency.get(&pattern.pattern_type) {
                let elapsed = Utc::now() - *last_seen;
                let hours = elapsed.num_hours() as f64;
                // More hours = more novel
                total_recency += (hours / 24.0).min(1.0);
                count += 1;
            } else {
                // Never seen before = very novel
                total_recency += 1.0;
                count += 1;
            }
        }
        
        if count > 0 {
            total_recency / count as f64
        } else {
            0.5
        }
    }
    
    fn calculate_memory_relevance(&self, patterns: &[DialoguePattern]) -> f64 {
        patterns.iter()
            .filter(|p| p.pattern_type == "memory_search" || 
                       p.suggested_intervention == "memory_recall")
            .map(|p| p.confidence)
            .fold(0.0, |a, b| a.max(b))
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DialoguePattern {
    pub pattern_type: String,
    pub confidence: f64,
    pub evidence: Vec<String>,
    pub context_match: f64,
    pub suggested_intervention: String,
}

struct ContextAnalyzer;

impl ContextAnalyzer {
    fn new() -> Self {
        Self
    }
}

struct TimingAnalyzer;

impl TimingAnalyzer {
    fn new() -> Self {
        Self
    }
    
    fn detect_temporal_patterns(&self, _history: &[String]) -> Result<Vec<DialoguePattern>> {
        // Simplified implementation
        Ok(vec![])
    }
    
    fn build_temporal_context(&self, _history: &[String]) -> Result<TemporalContext> {
        Ok(TemporalContext {
            time_since_last_thought: 1000,
            thought_velocity: 10.0,
            session_duration: 60000,
            pattern_recency: HashMap::new(),
        })
    }
}

/// Map detected patterns to framework suggestions
pub fn suggest_framework(intent: &ThoughtIntent, patterns: &[DialoguePattern]) -> Option<FrameworkType> {
    match intent {
        ThoughtIntent::Questioning => Some(FrameworkType::Socratic),
        ThoughtIntent::Planning => Some(FrameworkType::OODA),
        ThoughtIntent::Analyzing => Some(FrameworkType::CriticalAnalysis),
        ThoughtIntent::Creating => Some(FrameworkType::DesignThinking),
        ThoughtIntent::Solving => {
            if patterns.iter().any(|p| p.pattern_type == "stuck_pattern") {
                Some(FrameworkType::FirstPrinciples)
            } else {
                Some(FrameworkType::SystemsThinking)
            }
        },
        _ => None,
    }
}