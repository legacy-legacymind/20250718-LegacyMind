use anyhow::Result;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Represents the linguistic profile of a user's internal voice
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LinguisticProfile {
    /// Average complexity of vocabulary (0.0 = simple, 1.0 = complex)
    pub vocabulary_complexity: f64,
    
    /// Common sentence patterns used by the user
    pub sentence_patterns: Vec<SentencePattern>,
    
    /// Frequently used phrases with their frequency scores
    pub common_phrases: HashMap<String, f64>,
    
    /// Words used to connect thoughts ("but", "however", "although")
    pub thought_connectors: Vec<String>,
    
    /// Markers of uncertainty ("maybe", "perhaps", "might")
    pub uncertainty_markers: Vec<String>,
    
    /// Markers of confidence ("definitely", "certainly", "obviously")
    pub confidence_markers: Vec<String>,
    
    /// Preferred contraction usage (0.0 = formal, 1.0 = casual)
    pub contraction_preference: f64,
    
    /// Use of self-referential language ("I think", "my view")
    pub self_reference_style: SelfReferenceStyle,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SentencePattern {
    pub pattern_type: SentenceType,
    pub frequency: f64,
    pub typical_length: usize,
    pub complexity_score: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SentenceType {
    Declarative,      // Statements
    Interrogative,    // Questions
    Exclamatory,      // Exclamations
    Conditional,      // If-then structures
    Comparative,      // Comparisons
    FragmentedThought, // Incomplete thoughts, trailing off...
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SelfReferenceStyle {
    Direct,           // "I think", "I believe"
    Indirect,         // "It seems", "One might say"
    Mixed,            // Varies by context
    Minimal,          // Rarely self-references
}

/// Represents the cognitive style of the user
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CognitiveStyle {
    /// Speed of mental processing
    pub processing_speed: ProcessingSpeed,
    
    /// Preference for abstract vs concrete thinking (0.0 = concrete, 1.0 = abstract)
    pub abstraction_level: f64,
    
    /// Analytical vs intuitive thinking (-1.0 = analytical, 1.0 = intuitive)
    pub analytical_vs_intuitive: f64,
    
    /// Attention to detail (0.0 = big picture, 1.0 = detail-oriented)
    pub detail_orientation: f64,
    
    /// Frequency of metaphor usage
    pub metaphor_usage: f64,
    
    /// Preference for linear vs associative thinking
    pub thinking_linearity: f64,
    
    /// Tendency to question vs accept
    pub questioning_tendency: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ProcessingSpeed {
    Deliberate,   // Slow, careful consideration
    Moderate,     // Balanced pace
    Rapid,        // Quick, intuitive leaps
    Variable,     // Depends on context
}

/// Represents the rhythm and flow of thoughts
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThoughtRhythm {
    /// Patterns of pauses in thinking
    pub pause_patterns: Vec<PausePattern>,
    
    /// How thoughts group together (0.0 = scattered, 1.0 = clustered)
    pub thought_clustering: f64,
    
    /// How often thoughts diverge from main topic
    pub tangent_frequency: f64,
    
    /// Patterns of returning to previous thoughts
    pub return_patterns: Vec<ReturnPattern>,
    
    /// Natural thinking tempo
    pub base_tempo: ThinkingTempo,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PausePattern {
    pub trigger_context: String,
    pub typical_duration_ms: u64,
    pub frequency: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReturnPattern {
    pub return_phrase: String, // "As I was saying", "Getting back to"
    pub frequency: f64,
    pub typical_delay: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ThinkingTempo {
    Staccato,     // Short, rapid thoughts
    Flowing,      // Smooth, connected thoughts
    Meandering,   // Long, wandering thoughts
    Rhythmic,     // Regular, patterned thoughts
}

/// Emotional baseline and patterns
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmotionalProfile {
    /// Default emotional state
    pub baseline_mood: EmotionalState,
    
    /// Emotional volatility (0.0 = stable, 1.0 = highly variable)
    pub emotional_volatility: f64,
    
    /// Common emotional patterns
    pub emotional_patterns: Vec<EmotionalPattern>,
    
    /// Emotional expression style
    pub expression_style: EmotionalExpressionStyle,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmotionalState {
    pub valence: f64,  // -1.0 (negative) to 1.0 (positive)
    pub arousal: f64,  // 0.0 (calm) to 1.0 (excited)
    pub dominance: f64, // 0.0 (submissive) to 1.0 (dominant)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmotionalPattern {
    pub trigger_type: String,
    pub emotional_response: EmotionalState,
    pub typical_duration: u64,
    pub frequency: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum EmotionalExpressionStyle {
    Subdued,      // Minimal emotional expression
    Moderate,     // Balanced expression
    Expressive,   // Strong emotional expression
    Variable,     // Context-dependent
}

/// Complete voice pattern for a user
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VoicePattern {
    pub id: String,
    pub user_id: String,
    pub linguistic_markers: LinguisticProfile,
    pub cognitive_style: CognitiveStyle,
    pub emotional_baseline: EmotionalProfile,
    pub thought_rhythm: ThoughtRhythm,
    pub created_at: DateTime<Utc>,
    pub last_updated: DateTime<Utc>,
    pub learning_iterations: u64,
}

impl VoicePattern {
    /// Create a new voice pattern with default values
    pub fn new(user_id: String) -> Self {
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            user_id,
            linguistic_markers: LinguisticProfile::default(),
            cognitive_style: CognitiveStyle::default(),
            emotional_baseline: EmotionalProfile::default(),
            thought_rhythm: ThoughtRhythm::default(),
            created_at: Utc::now(),
            last_updated: Utc::now(),
            learning_iterations: 0,
        }
    }
    
    /// Update pattern based on observed user behavior
    pub fn learn_from_observation(&mut self, observation: &UserObservation) -> Result<()> {
        // Update linguistic markers
        self.update_linguistic_profile(&observation.language_samples)?;
        
        // Update cognitive style
        self.update_cognitive_style(&observation.thinking_patterns)?;
        
        // Update emotional baseline
        self.update_emotional_profile(&observation.emotional_indicators)?;
        
        // Update thought rhythm
        self.update_thought_rhythm(&observation.timing_patterns)?;
        
        self.last_updated = Utc::now();
        self.learning_iterations += 1;
        
        Ok(())
    }
    
    fn update_linguistic_profile(&mut self, samples: &[String]) -> Result<()> {
        // Analyze vocabulary complexity
        let complexity = self.calculate_vocabulary_complexity(samples);
        self.linguistic_markers.vocabulary_complexity = 
            self.weighted_average(
                self.linguistic_markers.vocabulary_complexity,
                complexity,
                self.learning_iterations as f64
            );
        
        // Extract common phrases
        self.extract_common_phrases(samples);
        
        // Identify thought connectors
        self.identify_thought_connectors(samples);
        
        Ok(())
    }
    
    fn update_cognitive_style(&mut self, patterns: &[ThinkingPattern]) -> Result<()> {
        // Analyze thinking patterns to update cognitive style
        for pattern in patterns {
            match pattern {
                ThinkingPattern::Analytical(score) => {
                    self.cognitive_style.analytical_vs_intuitive = 
                        self.weighted_average(
                            self.cognitive_style.analytical_vs_intuitive,
                            -*score,
                            self.learning_iterations as f64
                        );
                },
                ThinkingPattern::Intuitive(score) => {
                    self.cognitive_style.analytical_vs_intuitive = 
                        self.weighted_average(
                            self.cognitive_style.analytical_vs_intuitive,
                            *score,
                            self.learning_iterations as f64
                        );
                },
                ThinkingPattern::Abstract(score) => {
                    self.cognitive_style.abstraction_level = 
                        self.weighted_average(
                            self.cognitive_style.abstraction_level,
                            *score,
                            self.learning_iterations as f64
                        );
                },
                ThinkingPattern::DetailFocused(score) => {
                    self.cognitive_style.detail_orientation = 
                        self.weighted_average(
                            self.cognitive_style.detail_orientation,
                            *score,
                            self.learning_iterations as f64
                        );
                },
            }
        }
        
        Ok(())
    }
    
    fn update_emotional_profile(&mut self, indicators: &[EmotionalIndicator]) -> Result<()> {
        // Update emotional baseline based on observations
        let mut total_valence = 0.0;
        let mut total_arousal = 0.0;
        let mut count = 0.0;
        
        for indicator in indicators {
            total_valence += indicator.valence;
            total_arousal += indicator.arousal;
            count += 1.0;
        }
        
        if count > 0.0 {
            let new_valence = total_valence / count;
            let new_arousal = total_arousal / count;
            
            self.emotional_baseline.baseline_mood.valence = 
                self.weighted_average(
                    self.emotional_baseline.baseline_mood.valence,
                    new_valence,
                    self.learning_iterations as f64
                );
            
            self.emotional_baseline.baseline_mood.arousal = 
                self.weighted_average(
                    self.emotional_baseline.baseline_mood.arousal,
                    new_arousal,
                    self.learning_iterations as f64
                );
        }
        
        Ok(())
    }
    
    fn update_thought_rhythm(&mut self, timing: &[TimingObservation]) -> Result<()> {
        // Analyze pause patterns
        self.analyze_pause_patterns(timing);
        
        // Calculate thought clustering
        let clustering = self.calculate_thought_clustering(timing);
        self.thought_rhythm.thought_clustering = 
            self.weighted_average(
                self.thought_rhythm.thought_clustering,
                clustering,
                self.learning_iterations as f64
            );
        
        Ok(())
    }
    
    /// Helper function for weighted averaging during learning
    fn weighted_average(&self, old_value: f64, new_value: f64, iterations: f64) -> f64 {
        let weight = 1.0 / (iterations + 1.0);
        old_value * (1.0 - weight) + new_value * weight
    }
    
    fn calculate_vocabulary_complexity(&self, samples: &[String]) -> f64 {
        // Simplified complexity calculation
        // In practice, this would use more sophisticated NLP
        let total_words: usize = samples.iter().map(|s| s.split_whitespace().count()).sum();
        let unique_words: std::collections::HashSet<_> = 
            samples.iter()
                .flat_map(|s| s.split_whitespace())
                .collect();
        
        if total_words == 0 {
            return 0.5;
        }
        
        (unique_words.len() as f64 / total_words as f64).min(1.0)
    }
    
    fn extract_common_phrases(&mut self, samples: &[String]) {
        // Extract 2-3 word phrases that appear frequently
        // Simplified implementation
        for sample in samples {
            let words: Vec<&str> = sample.split_whitespace().collect();
            for window in words.windows(2) {
                let phrase = window.join(" ");
                *self.linguistic_markers.common_phrases.entry(phrase).or_insert(0.0) += 1.0;
            }
            for window in words.windows(3) {
                let phrase = window.join(" ");
                *self.linguistic_markers.common_phrases.entry(phrase).or_insert(0.0) += 1.0;
            }
        }
    }
    
    fn identify_thought_connectors(&mut self, samples: &[String]) {
        let connectors = vec![
            "but", "however", "although", "though", "yet",
            "furthermore", "moreover", "additionally", "also",
            "therefore", "thus", "hence", "so", "because",
            "meanwhile", "nevertheless", "nonetheless",
        ];
        
        for sample in samples {
            let lower = sample.to_lowercase();
            for connector in &connectors {
                if lower.contains(connector) && 
                   !self.linguistic_markers.thought_connectors.contains(&connector.to_string()) {
                    self.linguistic_markers.thought_connectors.push(connector.to_string());
                }
            }
        }
    }
    
    fn analyze_pause_patterns(&mut self, _timing: &[TimingObservation]) {
        // Analyze timing between thoughts to identify pause patterns
        // This would be implemented based on actual timing data
    }
    
    fn calculate_thought_clustering(&self, _timing: &[TimingObservation]) -> f64 {
        // Calculate how closely related consecutive thoughts are
        // Placeholder implementation
        0.5
    }
}

// Supporting types for learning
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserObservation {
    pub language_samples: Vec<String>,
    pub thinking_patterns: Vec<ThinkingPattern>,
    pub emotional_indicators: Vec<EmotionalIndicator>,
    pub timing_patterns: Vec<TimingObservation>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ThinkingPattern {
    Analytical(f64),
    Intuitive(f64),
    Abstract(f64),
    DetailFocused(f64),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmotionalIndicator {
    pub valence: f64,
    pub arousal: f64,
    pub context: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimingObservation {
    pub thought_duration: u64,
    pub pause_after: u64,
    pub thought_type: String,
}

// Default implementations
impl Default for LinguisticProfile {
    fn default() -> Self {
        Self {
            vocabulary_complexity: 0.5,
            sentence_patterns: vec![],
            common_phrases: HashMap::new(),
            thought_connectors: vec![
                "but".to_string(),
                "and".to_string(),
                "so".to_string(),
            ],
            uncertainty_markers: vec![
                "maybe".to_string(),
                "perhaps".to_string(),
                "might".to_string(),
            ],
            confidence_markers: vec![
                "definitely".to_string(),
                "certainly".to_string(),
                "clearly".to_string(),
            ],
            contraction_preference: 0.7,
            self_reference_style: SelfReferenceStyle::Mixed,
        }
    }
}

impl Default for CognitiveStyle {
    fn default() -> Self {
        Self {
            processing_speed: ProcessingSpeed::Moderate,
            abstraction_level: 0.5,
            analytical_vs_intuitive: 0.0,
            detail_orientation: 0.5,
            metaphor_usage: 0.3,
            thinking_linearity: 0.6,
            questioning_tendency: 0.5,
        }
    }
}

impl Default for EmotionalProfile {
    fn default() -> Self {
        Self {
            baseline_mood: EmotionalState {
                valence: 0.0,
                arousal: 0.3,
                dominance: 0.5,
            },
            emotional_volatility: 0.3,
            emotional_patterns: vec![],
            expression_style: EmotionalExpressionStyle::Moderate,
        }
    }
}

impl Default for ThoughtRhythm {
    fn default() -> Self {
        Self {
            pause_patterns: vec![],
            thought_clustering: 0.5,
            tangent_frequency: 0.3,
            return_patterns: vec![],
            base_tempo: ThinkingTempo::Flowing,
        }
    }
}