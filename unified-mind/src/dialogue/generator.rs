use anyhow::Result;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;

use super::voice_patterns::{VoicePattern, EmotionalState, ProcessingSpeed};

/// Types of internal dialogue interventions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum InterventionType {
    /// Subtle nudges that feel like natural realizations
    IntuitiveSuggestion {
        trigger: PatternTrigger,
        voice_style: VoiceStyle,
        confidence: f64,
    },
    
    /// Memory-like flashes of relevant information
    SubconsciousRecall {
        memory_type: MemoryType,
        relevance_score: f64,
        presentation_style: RecallStyle,
    },
    
    /// Pattern recognition moments - "this feels familiar"
    PatternRecognition {
        pattern_strength: f64,
        familiarity_type: FamiliarityType,
        associated_feelings: Vec<EmotionalMarker>,
    },
    
    /// Uncertainty detection - "something's not right here"
    GutFeeling {
        uncertainty_level: f64,
        concern_areas: Vec<String>,
        resolution_hints: Vec<SubtleHint>,
    },
    
    /// Framework activation - natural problem-solving approaches
    CognitiveFramework {
        framework_type: FrameworkType,
        activation_strength: f64,
        natural_triggers: Vec<String>,
    },
    
    /// Creative connections - unexpected associations
    CreativeLeap {
        connection_strength: f64,
        domains_connected: Vec<String>,
        insight_type: InsightType,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PatternTrigger {
    pub context_matches: Vec<String>,
    pub timing_criteria: TimingCriteria,
    pub relevance_threshold: f64,
    pub user_state_requirements: UserStateRequirements,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum VoiceStyle {
    Questioning,     // "What if...?", "Could it be...?"
    Suggestive,      // "Perhaps...", "Maybe..."
    Connective,      // "This reminds me of...", "Like when..."
    Cautionary,      // "Careful...", "Watch out for..."
    Encouraging,     // "Yes, and...", "That's it..."
    Reflective,      // "Thinking about it...", "On second thought..."
    Curious,         // "I wonder...", "Interesting..."
    Decisive,        // "Actually...", "No, wait..."
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum MemoryType {
    Experiential,    // Past experiences
    Conceptual,      // Learned concepts
    Emotional,       // Emotional memories
    Procedural,      // How-to knowledge
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum RecallStyle {
    Flash,           // Sudden, complete recall
    Gradual,         // Slowly emerging memory
    Fragmented,      // Bits and pieces
    Associative,     // Connected memories
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum FamiliarityType {
    Exact,           // "I've seen this exact thing"
    Similar,         // "This is like..."
    Structural,      // "Same pattern as..."
    Emotional,       // "Same feeling as..."
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmotionalMarker {
    pub emotion: String,
    pub intensity: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubtleHint {
    pub hint_content: String,
    pub delivery_style: HintDelivery,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HintDelivery {
    Whisper,         // Very subtle
    Nudge,           // Gentle push
    Highlight,       // Draw attention
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum FrameworkType {
    FirstPrinciples,
    OODA,
    Socratic,
    SystemsThinking,
    DesignThinking,
    CriticalAnalysis,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum InsightType {
    Analogy,
    Synthesis,
    Inversion,
    Lateral,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimingCriteria {
    pub min_pause_ms: u64,
    pub max_cognitive_load: f64,
    pub preferred_moments: Vec<PreferredMoment>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PreferredMoment {
    AfterQuestion,
    DuringPause,
    AtTransition,
    WhenStuck,
    DuringReflection,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserStateRequirements {
    pub min_receptivity: f64,
    pub max_stress_level: f64,
    pub required_focus_level: Option<(f64, f64)>, // min, max
}

/// Generated internal dialogue
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InternalDialogue {
    pub id: String,
    pub content: String,
    pub voice_style: VoiceStyle,
    pub emotional_tone: EmotionalState,
    pub delivery: DeliveryStyle,
    pub confidence: f64,
    pub timing: DialogueTiming,
    pub metadata: DialogueMetadata,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeliveryStyle {
    pub pacing: Pacing,
    pub emphasis: Vec<EmphasisPoint>,
    pub volume: Volume, // Metaphorical "volume" of internal voice
    pub persistence: f64, // How long it lingers
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Pacing {
    Rushed,          // Quick, urgent thoughts
    Measured,        // Normal pace
    Slow,            // Deliberate, careful
    Halting,         // Uncertain, with pauses
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmphasisPoint {
    pub word_index: usize,
    pub emphasis_type: EmphasisType,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum EmphasisType {
    Stress,          // Emphasized word
    Pause,           // Pause before/after
    Elongation,      // Drawn out
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Volume {
    Whisper,         // Barely there
    Quiet,           // Subdued
    Normal,          // Regular internal voice
    Prominent,       // Clear and present
    Insistent,       // Hard to ignore
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DialogueTiming {
    pub delay_ms: u64,
    pub duration_ms: u64,
    pub fade_pattern: FadePattern,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum FadePattern {
    Immediate,       // Appears and disappears quickly
    Gradual,         // Fades in and out
    Lingering,       // Stays present
    Recurring,       // Comes back periodically
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DialogueMetadata {
    pub intervention_type: InterventionType,
    pub triggered_by: Vec<String>,
    pub expected_impact: f64,
    pub learning_opportunity: bool,
}

/// The main dialogue generator
pub struct DialogueGenerator {
    thought_patterns: ThoughtPatternLibrary,
    voice_adaptor: VoiceAdaptor,
    timing_controller: TimingController,
    context_buffer: ContextBuffer,
}

impl DialogueGenerator {
    pub fn new() -> Self {
        Self {
            thought_patterns: ThoughtPatternLibrary::new(),
            voice_adaptor: VoiceAdaptor::new(),
            timing_controller: TimingController::new(),
            context_buffer: ContextBuffer::new(100), // Keep last 100 thoughts
        }
    }
    
    /// Generate internal dialogue based on current context
    pub async fn generate_internal_thought(
        &self,
        trigger: InterventionTrigger,
        user_context: &UserContext,
        voice_pattern: &VoicePattern,
    ) -> Result<Option<InternalDialogue>> {
        // 1. Check if intervention is appropriate
        if !self.should_intervene(&trigger, user_context, voice_pattern) {
            return Ok(None);
        }
        
        // 2. Select intervention type based on trigger and context
        let intervention_type = self.select_intervention_type(&trigger, user_context)?;
        
        // 3. Generate base thought content
        let base_content = self.generate_base_content(&intervention_type, user_context)?;
        
        // 4. Adapt to user's voice pattern
        let adapted_content = self.voice_adaptor.adapt_to_voice(
            base_content,
            voice_pattern,
            &intervention_type,
        )?;
        
        // 5. Determine delivery style
        let delivery = self.determine_delivery_style(
            &intervention_type,
            voice_pattern,
            user_context,
        )?;
        
        // 6. Calculate timing
        let timing = self.timing_controller.calculate_timing(
            &intervention_type,
            user_context,
            voice_pattern,
        )?;
        
        // 7. Create the internal dialogue
        let dialogue = InternalDialogue {
            id: uuid::Uuid::new_v4().to_string(),
            content: adapted_content,
            voice_style: self.extract_voice_style(&intervention_type),
            emotional_tone: self.calculate_emotional_tone(user_context, voice_pattern),
            delivery,
            confidence: trigger.confidence,
            timing,
            metadata: DialogueMetadata {
                intervention_type,
                triggered_by: trigger.patterns.clone(),
                expected_impact: self.estimate_impact(&trigger, user_context),
                learning_opportunity: self.is_learning_opportunity(&trigger),
            },
        };
        
        Ok(Some(dialogue))
    }
    
    fn should_intervene(
        &self,
        trigger: &InterventionTrigger,
        context: &UserContext,
        voice_pattern: &VoicePattern,
    ) -> bool {
        // Check cognitive load
        if context.cognitive_load > 0.8 {
            return false;
        }
        
        // Check if user is in deep focus
        if context.focus_level > 0.9 {
            return false;
        }
        
        // Check intervention cooldown
        if !self.timing_controller.check_cooldown(&context.last_intervention) {
            return false;
        }
        
        // Check confidence threshold
        if trigger.confidence < 0.4 {
            return false;
        }
        
        // Check user's receptivity based on their pattern
        match voice_pattern.cognitive_style.processing_speed {
            ProcessingSpeed::Deliberate => {
                // More selective for deliberate thinkers
                trigger.confidence > 0.6
            },
            ProcessingSpeed::Rapid => {
                // More frequent for rapid thinkers
                trigger.confidence > 0.3
            },
            _ => trigger.confidence > 0.5,
        }
    }
    
    fn select_intervention_type(
        &self,
        trigger: &InterventionTrigger,
        _context: &UserContext,
    ) -> Result<InterventionType> {
        // Analyze trigger patterns to determine best intervention type
        if trigger.uncertainty_detected {
            Ok(InterventionType::GutFeeling {
                uncertainty_level: trigger.uncertainty_level,
                concern_areas: trigger.concern_areas.clone(),
                resolution_hints: self.generate_hints(&trigger.concern_areas),
            })
        } else if trigger.pattern_match_strength > 0.7 {
            Ok(InterventionType::PatternRecognition {
                pattern_strength: trigger.pattern_match_strength,
                familiarity_type: self.determine_familiarity_type(&trigger.patterns),
                associated_feelings: vec![],
            })
        } else if trigger.memory_relevance > 0.6 {
            Ok(InterventionType::SubconsciousRecall {
                memory_type: MemoryType::Experiential,
                relevance_score: trigger.memory_relevance,
                presentation_style: RecallStyle::Flash,
            })
        } else {
            Ok(InterventionType::IntuitiveSuggestion {
                trigger: PatternTrigger {
                    context_matches: trigger.patterns.clone(),
                    timing_criteria: TimingCriteria {
                        min_pause_ms: 500,
                        max_cognitive_load: 0.7,
                        preferred_moments: vec![PreferredMoment::DuringPause],
                    },
                    relevance_threshold: 0.5,
                    user_state_requirements: UserStateRequirements {
                        min_receptivity: 0.4,
                        max_stress_level: 0.8,
                        required_focus_level: Some((0.3, 0.8)),
                    },
                },
                voice_style: VoiceStyle::Suggestive,
                confidence: trigger.confidence,
            })
        }
    }
    
    fn generate_base_content(
        &self,
        intervention_type: &InterventionType,
        context: &UserContext,
    ) -> Result<String> {
        match intervention_type {
            InterventionType::IntuitiveSuggestion { voice_style, .. } => {
                self.generate_suggestion_content(voice_style, context)
            },
            InterventionType::SubconsciousRecall { memory_type, .. } => {
                self.generate_recall_content(memory_type, context)
            },
            InterventionType::PatternRecognition { familiarity_type, .. } => {
                self.generate_pattern_content(familiarity_type, context)
            },
            InterventionType::GutFeeling { concern_areas, .. } => {
                self.generate_gut_feeling_content(concern_areas, context)
            },
            InterventionType::CognitiveFramework { framework_type, .. } => {
                self.generate_framework_content(framework_type, context)
            },
            InterventionType::CreativeLeap { domains_connected, .. } => {
                self.generate_creative_content(domains_connected, context)
            },
        }
    }
    
    fn generate_suggestion_content(
        &self,
        voice_style: &VoiceStyle,
        _context: &UserContext,
    ) -> Result<String> {
        let content = match voice_style {
            VoiceStyle::Questioning => {
                self.thought_patterns.get_questioning_starter()
            },
            VoiceStyle::Suggestive => {
                self.thought_patterns.get_suggestive_starter()
            },
            VoiceStyle::Encouraging => {
                self.thought_patterns.get_encouraging_starter()
            },
            _ => "Maybe...".to_string(),
        };
        
        Ok(content)
    }
    
    fn generate_recall_content(
        &self,
        memory_type: &MemoryType,
        _context: &UserContext,
    ) -> Result<String> {
        let content = match memory_type {
            MemoryType::Experiential => "This reminds me of when",
            MemoryType::Conceptual => "Like that concept about",
            MemoryType::Emotional => "Same feeling as",
            MemoryType::Procedural => "The way to do this",
        };
        
        Ok(content.to_string())
    }
    
    fn generate_pattern_content(
        &self,
        familiarity_type: &FamiliarityType,
        _context: &UserContext,
    ) -> Result<String> {
        let content = match familiarity_type {
            FamiliarityType::Exact => "I've seen this exact pattern",
            FamiliarityType::Similar => "This is similar to",
            FamiliarityType::Structural => "Same structure as",
            FamiliarityType::Emotional => "This feels like",
        };
        
        Ok(content.to_string())
    }
    
    fn generate_gut_feeling_content(
        &self,
        concern_areas: &[String],
        _context: &UserContext,
    ) -> Result<String> {
        if concern_areas.is_empty() {
            Ok("Something feels off...".to_string())
        } else {
            Ok(format!("Not sure about the {}...", concern_areas[0]))
        }
    }
    
    fn generate_framework_content(
        &self,
        framework_type: &FrameworkType,
        _context: &UserContext,
    ) -> Result<String> {
        let content = match framework_type {
            FrameworkType::FirstPrinciples => "What's the fundamental truth here",
            FrameworkType::OODA => "Observe... what's actually happening",
            FrameworkType::Socratic => "But why is that true",
            FrameworkType::SystemsThinking => "How does this connect to the whole",
            FrameworkType::DesignThinking => "What does the user really need",
            FrameworkType::CriticalAnalysis => "What's the evidence for this",
        };
        
        Ok(content.to_string())
    }
    
    fn generate_creative_content(
        &self,
        domains: &[String],
        _context: &UserContext,
    ) -> Result<String> {
        if domains.len() >= 2 {
            Ok(format!("What if {} connected to {}", domains[0], domains[1]))
        } else {
            Ok("What if we looked at this differently".to_string())
        }
    }
    
    fn determine_delivery_style(
        &self,
        intervention_type: &InterventionType,
        voice_pattern: &VoicePattern,
        _context: &UserContext,
    ) -> Result<DeliveryStyle> {
        let (pacing, volume, persistence) = match intervention_type {
            InterventionType::GutFeeling { uncertainty_level, .. } => {
                (Pacing::Halting, Volume::Whisper, *uncertainty_level)
            },
            InterventionType::SubconsciousRecall { .. } => {
                (Pacing::Rushed, Volume::Normal, 0.7)
            },
            InterventionType::PatternRecognition { pattern_strength, .. } => {
                (Pacing::Measured, Volume::Prominent, *pattern_strength)
            },
            _ => (Pacing::Measured, Volume::Quiet, 0.5),
        };
        
        // Adjust based on voice pattern
        let adjusted_volume = match voice_pattern.emotional_baseline.baseline_mood.arousal {
            x if x > 0.7 => self.increase_volume(volume),
            x if x < 0.3 => self.decrease_volume(volume),
            _ => volume,
        };
        
        Ok(DeliveryStyle {
            pacing,
            emphasis: vec![],
            volume: adjusted_volume,
            persistence,
        })
    }
    
    fn increase_volume(&self, volume: Volume) -> Volume {
        match volume {
            Volume::Whisper => Volume::Quiet,
            Volume::Quiet => Volume::Normal,
            Volume::Normal => Volume::Prominent,
            _ => volume,
        }
    }
    
    fn decrease_volume(&self, volume: Volume) -> Volume {
        match volume {
            Volume::Insistent => Volume::Prominent,
            Volume::Prominent => Volume::Normal,
            Volume::Normal => Volume::Quiet,
            _ => volume,
        }
    }
    
    fn extract_voice_style(&self, intervention_type: &InterventionType) -> VoiceStyle {
        match intervention_type {
            InterventionType::IntuitiveSuggestion { voice_style, .. } => voice_style.clone(),
            InterventionType::GutFeeling { .. } => VoiceStyle::Cautionary,
            InterventionType::PatternRecognition { .. } => VoiceStyle::Connective,
            InterventionType::SubconsciousRecall { .. } => VoiceStyle::Reflective,
            InterventionType::CognitiveFramework { .. } => VoiceStyle::Questioning,
            InterventionType::CreativeLeap { .. } => VoiceStyle::Curious,
        }
    }
    
    fn calculate_emotional_tone(
        &self,
        context: &UserContext,
        voice_pattern: &VoicePattern,
    ) -> EmotionalState {
        // Start with baseline
        let mut tone = voice_pattern.emotional_baseline.baseline_mood.clone();
        
        // Adjust based on context
        if context.stress_level > 0.7 {
            tone.arousal += 0.2;
            tone.valence -= 0.1;
        }
        
        if context.recent_success {
            tone.valence += 0.2;
            tone.dominance += 0.1;
        }
        
        // Clamp values
        tone.valence = tone.valence.clamp(-1.0, 1.0);
        tone.arousal = tone.arousal.clamp(0.0, 1.0);
        tone.dominance = tone.dominance.clamp(0.0, 1.0);
        
        tone
    }
    
    fn generate_hints(&self, concern_areas: &[String]) -> Vec<SubtleHint> {
        concern_areas.iter().map(|area| {
            SubtleHint {
                hint_content: format!("Check the {}", area),
                delivery_style: HintDelivery::Whisper,
            }
        }).collect()
    }
    
    fn determine_familiarity_type(&self, patterns: &[String]) -> FamiliarityType {
        // Simple heuristic - would be more sophisticated in practice
        if patterns.iter().any(|p| p.contains("exact")) {
            FamiliarityType::Exact
        } else if patterns.iter().any(|p| p.contains("similar")) {
            FamiliarityType::Similar
        } else {
            FamiliarityType::Structural
        }
    }
    
    fn estimate_impact(&self, trigger: &InterventionTrigger, _context: &UserContext) -> f64 {
        trigger.confidence * trigger.relevance
    }
    
    fn is_learning_opportunity(&self, trigger: &InterventionTrigger) -> bool {
        trigger.confidence > 0.6 && trigger.novelty > 0.5
    }
}

// Supporting structures

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InterventionTrigger {
    pub patterns: Vec<String>,
    pub confidence: f64,
    pub relevance: f64,
    pub novelty: f64,
    pub uncertainty_detected: bool,
    pub uncertainty_level: f64,
    pub concern_areas: Vec<String>,
    pub pattern_match_strength: f64,
    pub memory_relevance: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserContext {
    pub recent_thoughts: Vec<String>,
    pub cognitive_load: f64,
    pub focus_level: f64,
    pub stress_level: f64,
    pub last_intervention: Option<DateTime<Utc>>,
    pub recent_success: bool,
    pub current_task: Option<String>,
    pub environmental_factors: EnvironmentalFactors,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EnvironmentalFactors {
    pub time_of_day: String,
    pub interruption_count: u32,
    pub session_duration: u64,
}

struct ThoughtPatternLibrary {
    questioning_starters: Vec<String>,
    suggestive_starters: Vec<String>,
    encouraging_starters: Vec<String>,
}

impl ThoughtPatternLibrary {
    fn new() -> Self {
        Self {
            questioning_starters: vec![
                "What if".to_string(),
                "Could it be".to_string(),
                "Wonder if".to_string(),
                "Why not".to_string(),
            ],
            suggestive_starters: vec![
                "Maybe".to_string(),
                "Perhaps".to_string(),
                "Might try".to_string(),
                "Could be".to_string(),
            ],
            encouraging_starters: vec![
                "Yes, and".to_string(),
                "That's it".to_string(),
                "Keep going".to_string(),
                "Almost there".to_string(),
            ],
        }
    }
    
    fn get_questioning_starter(&self) -> String {
        self.questioning_starters[0].clone() // Would be random in practice
    }
    
    fn get_suggestive_starter(&self) -> String {
        self.suggestive_starters[0].clone()
    }
    
    fn get_encouraging_starter(&self) -> String {
        self.encouraging_starters[0].clone()
    }
}

struct VoiceAdaptor;

impl VoiceAdaptor {
    fn new() -> Self {
        Self
    }
    
    fn adapt_to_voice(
        &self,
        base_content: String,
        voice_pattern: &VoicePattern,
        _intervention_type: &InterventionType,
    ) -> Result<String> {
        let mut adapted = base_content;
        
        // Apply contraction preferences
        if voice_pattern.linguistic_markers.contraction_preference > 0.7 {
            adapted = adapted.replace("do not", "don't")
                .replace("cannot", "can't")
                .replace("will not", "won't");
        }
        
        // Add uncertainty markers if appropriate
        if voice_pattern.cognitive_style.analytical_vs_intuitive > 0.5 {
            if !adapted.contains("maybe") && !adapted.contains("perhaps") {
                adapted = format!("Maybe {}",
                    adapted.chars().next().unwrap().to_lowercase().collect::<String>() 
                    + &adapted[1..]);
            }
        }
        
        Ok(adapted)
    }
}

struct TimingController {
    min_intervention_gap: std::time::Duration,
}

impl TimingController {
    fn new() -> Self {
        Self {
            min_intervention_gap: std::time::Duration::from_secs(30),
        }
    }
    
    fn check_cooldown(&self, last_intervention: &Option<DateTime<Utc>>) -> bool {
        match last_intervention {
            Some(last) => {
                let elapsed = Utc::now() - *last;
                elapsed.to_std().unwrap_or_default() > self.min_intervention_gap
            },
            None => true,
        }
    }
    
    fn calculate_timing(
        &self,
        intervention_type: &InterventionType,
        _context: &UserContext,
        _voice_pattern: &VoicePattern,
    ) -> Result<DialogueTiming> {
        let (delay_ms, duration_ms, fade_pattern) = match intervention_type {
            InterventionType::GutFeeling { .. } => {
                (100, 3000, FadePattern::Lingering)
            },
            InterventionType::SubconsciousRecall { .. } => {
                (0, 2000, FadePattern::Immediate)
            },
            InterventionType::PatternRecognition { .. } => {
                (200, 2500, FadePattern::Gradual)
            },
            _ => (300, 2000, FadePattern::Gradual),
        };
        
        Ok(DialogueTiming {
            delay_ms,
            duration_ms,
            fade_pattern,
        })
    }
}

struct ContextBuffer {
    thoughts: VecDeque<String>,
    capacity: usize,
}

impl ContextBuffer {
    fn new(capacity: usize) -> Self {
        Self {
            thoughts: VecDeque::with_capacity(capacity),
            capacity,
        }
    }
    
    fn add_thought(&mut self, thought: String) {
        if self.thoughts.len() >= self.capacity {
            self.thoughts.pop_front();
        }
        self.thoughts.push_back(thought);
    }
}