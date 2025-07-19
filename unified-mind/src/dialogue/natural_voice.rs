use anyhow::Result;
use rand::Rng;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use super::voice_patterns::{VoicePattern, ProcessingSpeed, SelfReferenceStyle};
use super::generator::{VoiceStyle, InterventionType};

/// Natural voice generator that creates authentic internal dialogue
pub struct NaturalVoiceGenerator {
    phrase_library: PhraseLibrary,
    voice_templates: HashMap<VoiceStyle, Vec<VoiceTemplate>>,
    contraction_map: HashMap<String, String>,
}

#[derive(Debug, Clone)]
struct PhraseLibrary {
    // Starter phrases organized by intervention type
    memory_starters: Vec<String>,
    pattern_starters: Vec<String>,
    uncertainty_starters: Vec<String>,
    suggestion_starters: Vec<String>,
    framework_starters: Vec<String>,
    creative_starters: Vec<String>,
    
    // Connective tissue
    thought_bridges: Vec<String>,
    
    // Natural fillers that match internal voice
    cognitive_fillers: Vec<String>,
}

#[derive(Debug, Clone)]
struct VoiceTemplate {
    template: String,
    variables: Vec<String>,
    emotional_range: (f64, f64), // min, max valence
}

impl NaturalVoiceGenerator {
    pub fn new() -> Self {
        let mut voice_templates = HashMap::new();
        
        // Questioning voice templates
        voice_templates.insert(VoiceStyle::Questioning, vec![
            VoiceTemplate {
                template: "{starter}... {content}?".to_string(),
                variables: vec!["starter".to_string(), "content".to_string()],
                emotional_range: (-0.2, 0.5),
            },
            VoiceTemplate {
                template: "{content}... {filler}?".to_string(),
                variables: vec!["content".to_string(), "filler".to_string()],
                emotional_range: (-0.3, 0.3),
            },
        ]);
        
        // Suggestive voice templates
        voice_templates.insert(VoiceStyle::Suggestive, vec![
            VoiceTemplate {
                template: "{starter} {content}".to_string(),
                variables: vec!["starter".to_string(), "content".to_string()],
                emotional_range: (0.0, 0.6),
            },
            VoiceTemplate {
                template: "{content}... {continuation}".to_string(),
                variables: vec!["content".to_string(), "continuation".to_string()],
                emotional_range: (0.1, 0.7),
            },
        ]);
        
        // Connective voice templates
        voice_templates.insert(VoiceStyle::Connective, vec![
            VoiceTemplate {
                template: "{connector} {reference}".to_string(),
                variables: vec!["connector".to_string(), "reference".to_string()],
                emotional_range: (-0.1, 0.5),
            },
            VoiceTemplate {
                template: "{reference}, {elaboration}".to_string(),
                variables: vec!["reference".to_string(), "elaboration".to_string()],
                emotional_range: (0.0, 0.6),
            },
        ]);
        
        // Cautionary voice templates
        voice_templates.insert(VoiceStyle::Cautionary, vec![
            VoiceTemplate {
                template: "{warning}... {concern}".to_string(),
                variables: vec!["warning".to_string(), "concern".to_string()],
                emotional_range: (-0.4, 0.1),
            },
            VoiceTemplate {
                template: "{concern} {advice}".to_string(),
                variables: vec!["concern".to_string(), "advice".to_string()],
                emotional_range: (-0.3, 0.2),
            },
        ]);
        
        let contraction_map = Self::build_contraction_map();
        
        Self {
            phrase_library: Self::build_phrase_library(),
            voice_templates,
            contraction_map,
        }
    }
    
    /// Generate natural internal voice based on intervention type and voice pattern
    pub fn generate_natural_voice(
        &self,
        intervention_type: &InterventionType,
        voice_pattern: &VoicePattern,
        context: &GenerationContext,
    ) -> Result<String> {
        // 1. Get base content for the intervention type
        let base_content = self.get_intervention_content(intervention_type, context)?;
        
        // 2. Apply voice pattern transformations
        let personalized = self.apply_voice_pattern(base_content, voice_pattern)?;
        
        // 3. Add natural variations
        let natural = self.add_natural_variations(personalized, voice_pattern)?;
        
        // 4. Apply emotional coloring
        let emotionally_colored = self.apply_emotional_coloring(
            natural,
            &voice_pattern.emotional_baseline.baseline_mood,
        )?;
        
        Ok(emotionally_colored)
    }
    
    fn get_intervention_content(
        &self,
        intervention_type: &InterventionType,
        context: &GenerationContext,
    ) -> Result<String> {
        let content = match intervention_type {
            InterventionType::SubconsciousRecall { memory_type, .. } => {
                self.generate_memory_content(memory_type, context)
            },
            InterventionType::PatternRecognition { familiarity_type, pattern_strength, .. } => {
                self.generate_pattern_content(familiarity_type, *pattern_strength, context)
            },
            InterventionType::GutFeeling { concern_areas, uncertainty_level, .. } => {
                self.generate_gut_feeling_content(concern_areas, *uncertainty_level, context)
            },
            InterventionType::IntuitiveSuggestion { voice_style, .. } => {
                self.generate_suggestion_content(voice_style, context)
            },
            InterventionType::CognitiveFramework { framework_type, .. } => {
                self.generate_framework_content(framework_type, context)
            },
            InterventionType::CreativeLeap { domains_connected, .. } => {
                self.generate_creative_content(domains_connected, context)
            },
        }?;
        
        Ok(content)
    }
    
    fn generate_memory_content(
        &self,
        memory_type: &super::generator::MemoryType,
        context: &GenerationContext,
    ) -> Result<String> {
        let starter = self.phrase_library.memory_starters
            .get(rand::thread_rng().gen_range(0..self.phrase_library.memory_starters.len()))
            .unwrap();
        
        let content = match memory_type {
            super::generator::MemoryType::Experiential => {
                if let Some(similar) = &context.similar_experience {
                    format!("{} {}", starter, similar)
                } else {
                    format!("{} something similar", starter)
                }
            },
            super::generator::MemoryType::Conceptual => {
                format!("{} that principle about", starter)
            },
            super::generator::MemoryType::Emotional => {
                format!("{} this feeling", starter)
            },
            super::generator::MemoryType::Procedural => {
                format!("{} the steps", starter)
            },
        };
        
        Ok(content)
    }
    
    fn generate_pattern_content(
        &self,
        familiarity_type: &super::generator::FamiliarityType,
        strength: f64,
        _context: &GenerationContext,
    ) -> Result<String> {
        let starter = self.phrase_library.pattern_starters
            .get(rand::thread_rng().gen_range(0..self.phrase_library.pattern_starters.len()))
            .unwrap();
        
        let confidence_modifier = if strength > 0.8 {
            "definitely"
        } else if strength > 0.6 {
            "probably"
        } else {
            "might be"
        };
        
        let content = match familiarity_type {
            super::generator::FamiliarityType::Exact => {
                format!("{} {} the same thing", starter, confidence_modifier)
            },
            super::generator::FamiliarityType::Similar => {
                format!("{} {} similar", starter, confidence_modifier)
            },
            super::generator::FamiliarityType::Structural => {
                format!("{} the pattern", starter)
            },
            super::generator::FamiliarityType::Emotional => {
                format!("{} feeling", starter)
            },
        };
        
        Ok(content)
    }
    
    fn generate_gut_feeling_content(
        &self,
        concern_areas: &[String],
        uncertainty_level: f64,
        _context: &GenerationContext,
    ) -> Result<String> {
        let starter = self.phrase_library.uncertainty_starters
            .get(rand::thread_rng().gen_range(0..self.phrase_library.uncertainty_starters.len()))
            .unwrap();
        
        let intensity = if uncertainty_level > 0.8 {
            "really"
        } else if uncertainty_level > 0.6 {
            "kinda"
        } else {
            "slightly"
        };
        
        if concern_areas.is_empty() {
            Ok(format!("{} {} off", starter, intensity))
        } else {
            Ok(format!("{} {} off about the {}", starter, intensity, concern_areas[0]))
        }
    }
    
    fn generate_suggestion_content(
        &self,
        voice_style: &VoiceStyle,
        context: &GenerationContext,
    ) -> Result<String> {
        let templates = self.voice_templates.get(voice_style)
            .ok_or_else(|| anyhow::anyhow!("No templates for voice style"))?;
        
        let template = &templates[rand::thread_rng().gen_range(0..templates.len())];
        let mut result = template.template.clone();
        
        // Fill in template variables
        if result.contains("{starter}") {
            let starter = self.phrase_library.suggestion_starters
                .get(rand::thread_rng().gen_range(0..self.phrase_library.suggestion_starters.len()))
                .unwrap();
            result = result.replace("{starter}", starter);
        }
        
        if result.contains("{content}") {
            let content = context.suggestion_content.as_deref().unwrap_or("try something different");
            result = result.replace("{content}", content);
        }
        
        if result.contains("{filler}") {
            let filler = self.phrase_library.cognitive_fillers
                .get(rand::thread_rng().gen_range(0..self.phrase_library.cognitive_fillers.len()))
                .unwrap();
            result = result.replace("{filler}", filler);
        }
        
        Ok(result)
    }
    
    fn generate_framework_content(
        &self,
        framework_type: &super::generator::FrameworkType,
        _context: &GenerationContext,
    ) -> Result<String> {
        let starter = self.phrase_library.framework_starters
            .get(rand::thread_rng().gen_range(0..self.phrase_library.framework_starters.len()))
            .unwrap();
        
        let framework_hint = match framework_type {
            super::generator::FrameworkType::FirstPrinciples => "break this down to basics",
            super::generator::FrameworkType::OODA => "observe first",
            super::generator::FrameworkType::Socratic => "question the assumption",
            super::generator::FrameworkType::SystemsThinking => "see the connections",
            super::generator::FrameworkType::DesignThinking => "think user-first",
            super::generator::FrameworkType::CriticalAnalysis => "check the evidence",
        };
        
        Ok(format!("{} {}", starter, framework_hint))
    }
    
    fn generate_creative_content(
        &self,
        domains: &[String],
        _context: &GenerationContext,
    ) -> Result<String> {
        let starter = self.phrase_library.creative_starters
            .get(rand::thread_rng().gen_range(0..self.phrase_library.creative_starters.len()))
            .unwrap();
        
        if domains.len() >= 2 {
            Ok(format!("{} {} and {}", starter, domains[0], domains[1]))
        } else {
            Ok(format!("{} this differently", starter))
        }
    }
    
    fn apply_voice_pattern(&self, content: String, voice_pattern: &VoicePattern) -> Result<String> {
        let mut result = content;
        
        // Apply contraction preference
        if voice_pattern.linguistic_markers.contraction_preference > 0.6 {
            result = self.apply_contractions(result);
        }
        
        // Apply self-reference style
        result = self.apply_self_reference_style(result, &voice_pattern.linguistic_markers.self_reference_style);
        
        // Apply processing speed variations
        result = self.apply_processing_speed_variations(result, &voice_pattern.cognitive_style.processing_speed);
        
        Ok(result)
    }
    
    fn apply_contractions(&self, text: String) -> String {
        let mut result = text;
        for (formal, casual) in &self.contraction_map {
            result = result.replace(formal, casual);
        }
        result
    }
    
    fn apply_self_reference_style(&self, text: String, style: &SelfReferenceStyle) -> String {
        match style {
            SelfReferenceStyle::Direct => {
                // Keep or add direct references
                if !text.contains("I ") && rand::thread_rng().gen_bool(0.3) {
                    format!("I think {}", text)
                } else {
                    text
                }
            },
            SelfReferenceStyle::Indirect => {
                // Remove direct references
                text.replace("I think ", "")
                    .replace("I believe ", "")
                    .replace("I feel ", "seems ")
            },
            SelfReferenceStyle::Minimal => {
                // Remove most self-references
                text.replace("I think ", "")
                    .replace("I believe ", "")
                    .replace("I feel ", "")
                    .replace("I wonder ", "")
            },
            _ => text,
        }
    }
    
    fn apply_processing_speed_variations(&self, text: String, speed: &ProcessingSpeed) -> String {
        match speed {
            ProcessingSpeed::Deliberate => {
                // Add pauses and careful phrasing
                text.replace(". ", "... ")
                    .replace(", ", "... ")
            },
            ProcessingSpeed::Rapid => {
                // Remove unnecessary words, make more direct
                text.replace("might be", "is")
                    .replace("could be", "is")
                    .replace("perhaps", "")
            },
            _ => text,
        }
    }
    
    fn add_natural_variations(&self, text: String, voice_pattern: &VoicePattern) -> Result<String> {
        let mut result = text;
        
        // Add uncertainty markers based on cognitive style
        if voice_pattern.cognitive_style.analytical_vs_intuitive < -0.3 {
            // Analytical thinkers use more hedging
            if rand::thread_rng().gen_bool(0.3) && !result.contains("maybe") && !result.contains("perhaps") {
                let markers = &voice_pattern.linguistic_markers.uncertainty_markers;
                if !markers.is_empty() {
                    let marker = &markers[rand::thread_rng().gen_range(0..markers.len())];
                    result = format!("{} {}", marker, result);
                }
            }
        }
        
        // Add thought connectors for complex thinkers
        if voice_pattern.cognitive_style.abstraction_level > 0.6 {
            if rand::thread_rng().gen_bool(0.2) {
                let connectors = &voice_pattern.linguistic_markers.thought_connectors;
                if !connectors.is_empty() {
                    let connector = &connectors[rand::thread_rng().gen_range(0..connectors.len())];
                    result = format!("{}... {}", connector, result);
                }
            }
        }
        
        // Add trailing thoughts for meandering thinkers
        if matches!(voice_pattern.thought_rhythm.base_tempo, super::voice_patterns::ThinkingTempo::Meandering) {
            if rand::thread_rng().gen_bool(0.4) {
                result.push_str("...");
            }
        }
        
        Ok(result)
    }
    
    fn apply_emotional_coloring(
        &self,
        text: String,
        emotional_state: &super::voice_patterns::EmotionalState,
    ) -> Result<String> {
        let mut result = text;
        
        // High arousal = more exclamation, shorter sentences
        if emotional_state.arousal > 0.7 {
            if rand::thread_rng().gen_bool(0.3) {
                result = result.replace(".", "!");
            }
        }
        
        // Low valence = more negative framing
        if emotional_state.valence < -0.3 {
            result = result.replace("might work", "probably won't work")
                          .replace("could be", "doubt it's");
        }
        
        // High valence = more positive framing
        if emotional_state.valence > 0.3 {
            result = result.replace("might", "will probably")
                          .replace("could", "should");
        }
        
        Ok(result)
    }
    
    fn build_phrase_library() -> PhraseLibrary {
        PhraseLibrary {
            memory_starters: vec![
                "this reminds me of".to_string(),
                "like that time".to_string(),
                "remember when".to_string(),
                "oh yeah".to_string(),
                "similar to when".to_string(),
                "just like".to_string(),
            ],
            pattern_starters: vec![
                "this feels like".to_string(),
                "seeing".to_string(),
                "wait, this is".to_string(),
                "oh, it's".to_string(),
                "recognizing".to_string(),
            ],
            uncertainty_starters: vec![
                "something feels".to_string(),
                "not sure this is".to_string(),
                "hmm, seems".to_string(),
                "this doesn't feel".to_string(),
                "getting a sense that".to_string(),
            ],
            suggestion_starters: vec![
                "what if".to_string(),
                "maybe try".to_string(),
                "could".to_string(),
                "might work to".to_string(),
                "how about".to_string(),
            ],
            framework_starters: vec![
                "need to".to_string(),
                "should probably".to_string(),
                "time to".to_string(),
                "better".to_string(),
                "gotta".to_string(),
            ],
            creative_starters: vec![
                "what if we connected".to_string(),
                "imagine combining".to_string(),
                "could merge".to_string(),
                "link between".to_string(),
                "bridge".to_string(),
            ],
            thought_bridges: vec![
                "actually".to_string(),
                "wait".to_string(),
                "oh".to_string(),
                "hmm".to_string(),
                "so".to_string(),
            ],
            cognitive_fillers: vec![
                "right".to_string(),
                "exactly".to_string(),
                "yeah".to_string(),
                "okay".to_string(),
                "interesting".to_string(),
            ],
        }
    }
    
    fn build_contraction_map() -> HashMap<String, String> {
        let mut map = HashMap::new();
        map.insert("do not".to_string(), "don't".to_string());
        map.insert("cannot".to_string(), "can't".to_string());
        map.insert("will not".to_string(), "won't".to_string());
        map.insert("should not".to_string(), "shouldn't".to_string());
        map.insert("could not".to_string(), "couldn't".to_string());
        map.insert("would not".to_string(), "wouldn't".to_string());
        map.insert("it is".to_string(), "it's".to_string());
        map.insert("that is".to_string(), "that's".to_string());
        map.insert("what is".to_string(), "what's".to_string());
        map.insert("there is".to_string(), "there's".to_string());
        map.insert("I am".to_string(), "I'm".to_string());
        map.insert("you are".to_string(), "you're".to_string());
        map.insert("we are".to_string(), "we're".to_string());
        map.insert("they are".to_string(), "they're".to_string());
        map.insert("I have".to_string(), "I've".to_string());
        map.insert("you have".to_string(), "you've".to_string());
        map.insert("we have".to_string(), "we've".to_string());
        map.insert("I would".to_string(), "I'd".to_string());
        map.insert("you would".to_string(), "you'd".to_string());
        map.insert("I will".to_string(), "I'll".to_string());
        map.insert("you will".to_string(), "you'll".to_string());
        map
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GenerationContext {
    pub similar_experience: Option<String>,
    pub suggestion_content: Option<String>,
    pub current_focus: Option<String>,
    pub recent_success: bool,
    pub emotional_context: EmotionalContext,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmotionalContext {
    pub current_mood: String,
    pub stress_level: f64,
    pub energy_level: f64,
}