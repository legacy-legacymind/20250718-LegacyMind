use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};

/// Specific dialogue type implementations for different cognitive moments
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DialogueType {
    /// Memory nudge - "remember the Redis issue yesterday"
    MemoryNudge {
        memory_ref: String,
        time_ref: Option<String>,
        relevance: f64,
        urgency: NudgeUrgency,
    },
    
    /// Framework suggestion - "this feels like a first-principles question"
    FrameworkSuggestion {
        framework: CognitiveFramework,
        trigger_pattern: String,
        application_hint: String,
        confidence: f64,
    },
    
    /// Pattern recognition - "this is similar to the Redis issue"
    PatternRecognition {
        pattern_ref: String,
        similarity_score: f64,
        key_similarities: Vec<String>,
        differences: Vec<String>,
    },
    
    /// Contextual reminder - "remember the timeout fix we used"
    ContextualReminder {
        context_type: ReminderContext,
        specific_detail: String,
        application: String,
        last_used: Option<DateTime<Utc>>,
    },
    
    /// Uncertainty detection - "something's not right here"
    UncertaintyFlag {
        uncertainty_type: UncertaintyType,
        indicators: Vec<String>,
        severity: f64,
        suggested_check: Option<String>,
    },
    
    /// Problem-solving hint - "try breaking this down"
    SolvingHint {
        approach: ProblemApproach,
        specific_action: String,
        rationale: String,
        expected_outcome: String,
    },
    
    /// Creative connection - "what if we combined X with Y"
    CreativeConnection {
        domain_a: String,
        domain_b: String,
        connection_type: ConnectionType,
        potential_insight: String,
    },
    
    /// Focus redirection - "getting off track, back to X"
    FocusRedirect {
        current_tangent: String,
        main_goal: String,
        redirect_phrase: String,
        importance: f64,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum NudgeUrgency {
    Gentle,      // "might want to remember"
    Moderate,    // "should probably recall"
    Strong,      // "definitely need to remember"
    Critical,    // "must remember this"
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CognitiveFramework {
    FirstPrinciples,
    OODA,
    Socratic,
    SystemsThinking,
    DesignThinking,
    CriticalAnalysis,
    FiveWhys,
    SWOT,
    RootCause,
    Hypothesis,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ReminderContext {
    PreviousSolution,
    LessonLearned,
    ErrorPattern,
    SuccessPattern,
    Configuration,
    Workaround,
    BestPractice,
    PersonalPreference,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum UncertaintyType {
    LogicalInconsistency,
    MissingInformation,
    ContradictoryEvidence,
    UnexpectedBehavior,
    AssumptionViolation,
    ComplexityOverload,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ProblemApproach {
    Decomposition,      // Break into smaller parts
    Simplification,     // Remove complexity
    Inversion,          // Work backwards
    Analogy,            // Find similar solved problem
    Experimentation,    // Try and observe
    Research,           // Gather more information
    Collaboration,      // Seek help
    SteppingBack,       // Take broader view
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ConnectionType {
    Structural,         // Similar structure
    Functional,         // Similar function
    Metaphorical,       // Abstract similarity
    Complementary,      // Fills gaps
    Synergistic,        // 1+1=3
    Contrasting,        // Opposites inform
}

/// Dialogue type selector based on context
pub struct DialogueTypeSelector;

impl DialogueTypeSelector {
    pub fn select_dialogue_type(
        intent: &super::pattern_detector::ThoughtIntent,
        patterns: &[super::pattern_detector::DialoguePattern],
        cognitive_state: &super::pattern_detector::CognitiveState,
    ) -> DialogueType {
        use super::pattern_detector::ThoughtIntent;
        
        // High uncertainty - flag it
        if cognitive_state.confusion_level > 0.7 {
            return Self::create_uncertainty_flag(patterns, cognitive_state);
        }
        
        // Pattern matching for different intents
        match intent {
            ThoughtIntent::Remembering => Self::create_memory_nudge(patterns),
            ThoughtIntent::Solving => Self::create_solving_hint(patterns, cognitive_state),
            ThoughtIntent::Planning => Self::create_framework_suggestion(patterns),
            ThoughtIntent::Creating => Self::create_creative_connection(patterns),
            ThoughtIntent::Analyzing => Self::create_pattern_recognition(patterns),
            ThoughtIntent::Deciding => Self::create_contextual_reminder(patterns),
            _ => Self::create_default_dialogue(patterns),
        }
    }
    
    fn create_uncertainty_flag(
        patterns: &[super::pattern_detector::DialoguePattern],
        cognitive_state: &super::pattern_detector::CognitiveState,
    ) -> DialogueType {
        let indicators: Vec<String> = patterns.iter()
            .flat_map(|p| p.evidence.clone())
            .collect();
        
        let uncertainty_type = if patterns.iter().any(|p| p.pattern_type == "contradiction") {
            UncertaintyType::ContradictoryEvidence
        } else if cognitive_state.confusion_level > 0.8 {
            UncertaintyType::ComplexityOverload
        } else {
            UncertaintyType::MissingInformation
        };
        
        DialogueType::UncertaintyFlag {
            uncertainty_type,
            indicators,
            severity: cognitive_state.confusion_level,
            suggested_check: Some("Step back and identify what's unclear".to_string()),
        }
    }
    
    fn create_memory_nudge(patterns: &[super::pattern_detector::DialoguePattern]) -> DialogueType {
        let memory_pattern = patterns.iter()
            .find(|p| p.pattern_type == "memory_search")
            .or_else(|| patterns.first());
        
        DialogueType::MemoryNudge {
            memory_ref: memory_pattern
                .map(|p| p.evidence.join(", "))
                .unwrap_or_else(|| "previous similar situation".to_string()),
            time_ref: Some("recently".to_string()),
            relevance: memory_pattern.map(|p| p.confidence).unwrap_or(0.5),
            urgency: NudgeUrgency::Moderate,
        }
    }
    
    fn create_solving_hint(
        patterns: &[super::pattern_detector::DialoguePattern],
        cognitive_state: &super::pattern_detector::CognitiveState,
    ) -> DialogueType {
        let approach = if cognitive_state.frustration_level > 0.6 {
            ProblemApproach::SteppingBack
        } else if patterns.iter().any(|p| p.pattern_type == "stuck_pattern") {
            ProblemApproach::Decomposition
        } else {
            ProblemApproach::Experimentation
        };
        
        let specific_action = match approach {
            ProblemApproach::SteppingBack => "Take a break and reconsider the approach",
            ProblemApproach::Decomposition => "List out each component separately",
            ProblemApproach::Experimentation => "Try a minimal test case",
            _ => "Try a different angle",
        };
        
        DialogueType::SolvingHint {
            approach,
            specific_action: specific_action.to_string(),
            rationale: "Current approach seems stuck".to_string(),
            expected_outcome: "Fresh perspective or clearer understanding".to_string(),
        }
    }
    
    fn create_framework_suggestion(patterns: &[super::pattern_detector::DialoguePattern]) -> DialogueType {
        let framework = if patterns.iter().any(|p| p.pattern_type == "complex_problem") {
            CognitiveFramework::FirstPrinciples
        } else if patterns.iter().any(|p| p.pattern_type == "planning") {
            CognitiveFramework::OODA
        } else {
            CognitiveFramework::SystemsThinking
        };
        
        let application_hint = match framework {
            CognitiveFramework::FirstPrinciples => "What are the fundamental truths here?",
            CognitiveFramework::OODA => "Start by observing the current state",
            CognitiveFramework::SystemsThinking => "Map out all the connections",
            _ => "Apply structured thinking",
        };
        
        DialogueType::FrameworkSuggestion {
            framework,
            trigger_pattern: patterns.first()
                .map(|p| p.pattern_type.clone())
                .unwrap_or_else(|| "general".to_string()),
            application_hint: application_hint.to_string(),
            confidence: patterns.first().map(|p| p.confidence).unwrap_or(0.6),
        }
    }
    
    fn create_creative_connection(_patterns: &[super::pattern_detector::DialoguePattern]) -> DialogueType {
        DialogueType::CreativeConnection {
            domain_a: "current approach".to_string(),
            domain_b: "alternative method".to_string(),
            connection_type: ConnectionType::Complementary,
            potential_insight: "Combining perspectives might reveal new solution".to_string(),
        }
    }
    
    fn create_pattern_recognition(patterns: &[super::pattern_detector::DialoguePattern]) -> DialogueType {
        let pattern_ref = patterns.first()
            .map(|p| p.evidence.join(" "))
            .unwrap_or_else(|| "similar pattern".to_string());
        
        DialogueType::PatternRecognition {
            pattern_ref,
            similarity_score: patterns.first().map(|p| p.confidence).unwrap_or(0.5),
            key_similarities: vec!["structure".to_string(), "approach".to_string()],
            differences: vec!["context".to_string()],
        }
    }
    
    fn create_contextual_reminder(_patterns: &[super::pattern_detector::DialoguePattern]) -> DialogueType {
        DialogueType::ContextualReminder {
            context_type: ReminderContext::PreviousSolution,
            specific_detail: "similar approach that worked".to_string(),
            application: "could apply same principle here".to_string(),
            last_used: None,
        }
    }
    
    fn create_default_dialogue(patterns: &[super::pattern_detector::DialoguePattern]) -> DialogueType {
        if patterns.is_empty() {
            DialogueType::FocusRedirect {
                current_tangent: "wandering thoughts".to_string(),
                main_goal: "original question".to_string(),
                redirect_phrase: "getting back to the point".to_string(),
                importance: 0.5,
            }
        } else {
            Self::create_pattern_recognition(patterns)
        }
    }
}

/// Natural phrase generator for each dialogue type
pub struct DialoguePhraseGenerator;

impl DialoguePhraseGenerator {
    pub fn generate_phrase(dialogue_type: &DialogueType) -> String {
        match dialogue_type {
            DialogueType::MemoryNudge { memory_ref, urgency, .. } => {
                match urgency {
                    NudgeUrgency::Gentle => format!("might want to remember {}", memory_ref),
                    NudgeUrgency::Moderate => format!("remember {}", memory_ref),
                    NudgeUrgency::Strong => format!("definitely remember {}", memory_ref),
                    NudgeUrgency::Critical => format!("must remember {}", memory_ref),
                }
            },
            
            DialogueType::FrameworkSuggestion { application_hint, .. } => {
                application_hint.clone()
            },
            
            DialogueType::PatternRecognition { pattern_ref, .. } => {
                format!("this is like {}", pattern_ref)
            },
            
            DialogueType::ContextualReminder { specific_detail, application, .. } => {
                format!("{} - {}", specific_detail, application)
            },
            
            DialogueType::UncertaintyFlag { suggested_check, .. } => {
                suggested_check.as_deref().unwrap_or("something's off").to_string()
            },
            
            DialogueType::SolvingHint { specific_action, .. } => {
                specific_action.clone()
            },
            
            DialogueType::CreativeConnection { domain_a, domain_b, .. } => {
                format!("what if {} connected with {}", domain_a, domain_b)
            },
            
            DialogueType::FocusRedirect { redirect_phrase, .. } => {
                redirect_phrase.clone()
            },
        }
    }
}