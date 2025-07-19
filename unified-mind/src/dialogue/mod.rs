pub mod generator;
pub mod voice_patterns;
pub mod pattern_detector;
pub mod natural_voice;
pub mod dialogue_types;

use anyhow::Result;
use chrono::{DateTime, Utc};
use redis::aio::ConnectionManager;
use redis::AsyncCommands;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;

use crate::patterns::PatternEngine;
use generator::{
    DialogueGenerator, UserContext,
    EnvironmentalFactors
};
use voice_patterns::{VoicePattern, UserObservation};
use pattern_detector::DialoguePatternDetector;
use natural_voice::{NaturalVoiceGenerator, GenerationContext, EmotionalContext};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DialogueResponse {
    pub id: String,
    pub content: String,
    pub timestamp: DateTime<Utc>,
    pub patterns: Vec<String>,
    pub explorations: Vec<String>,
    pub emotional_tone: String,
    pub cognitive_load: f64,
    pub internal_voice: Option<InternalVoice>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InternalVoice {
    pub content: String,
    pub delivery: String, // whisper, normal, prominent
    pub timing: String,   // immediate, delayed, recurring
    pub confidence: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThoughtThread {
    pub id: String,
    pub thoughts: Vec<Thought>,
    pub patterns_emerged: Vec<String>,
    pub insights: Vec<String>,
    pub unresolved_questions: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Thought {
    pub id: String,
    pub content: String,
    pub timestamp: DateTime<Utc>,
    pub associations: Vec<String>,
    pub emotional_valence: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubconsciousResponse {
    pub internal_voice: Option<InternalVoice>,
    pub cognitive_load: f64,
    pub intervention_confidence: f64,
}

pub struct DialogueManager {
    redis_conn: Arc<RwLock<ConnectionManager>>,
    pattern_engine: Arc<PatternEngine>,
    dialogue_generator: DialogueGenerator,
    voice_patterns: Arc<RwLock<HashMap<String, VoicePattern>>>,
    pattern_detector: DialoguePatternDetector,
    natural_voice_gen: NaturalVoiceGenerator,
    thought_history: Arc<RwLock<Vec<String>>>,
}

use std::collections::HashMap;

impl DialogueManager {
    pub async fn new(
        redis_conn: Arc<RwLock<ConnectionManager>>,
        pattern_engine: Arc<PatternEngine>,
    ) -> Result<Self> {
        let voice_patterns = Self::load_voice_patterns(&redis_conn).await?;
        let pattern_detector = DialoguePatternDetector::new(Arc::clone(&pattern_engine));
        
        Ok(Self {
            redis_conn,
            pattern_engine,
            dialogue_generator: DialogueGenerator::new(),
            voice_patterns: Arc::new(RwLock::new(voice_patterns)),
            pattern_detector,
            natural_voice_gen: NaturalVoiceGenerator::new(),
            thought_history: Arc::new(RwLock::new(Vec::with_capacity(100))),
        })
    }
    
    async fn load_voice_patterns(
        redis_conn: &Arc<RwLock<ConnectionManager>>
    ) -> Result<HashMap<String, VoicePattern>> {
        let mut conn = redis_conn.write().await;
        let pattern_keys: Vec<String> = conn.keys("voice_pattern:*").await?;
        
        let mut patterns = HashMap::new();
        for key in pattern_keys {
            if let Ok(pattern_json) = conn.get::<_, String>(&key).await {
                if let Ok(pattern) = serde_json::from_str::<VoicePattern>(&pattern_json) {
                    patterns.insert(pattern.user_id.clone(), pattern);
                }
            }
        }
        
        Ok(patterns)
    }

    pub async fn process_thought(
        &self,
        thought: String,
        context: Option<String>,
    ) -> Result<DialogueResponse> {
        let user_id = "default"; // Would come from session context
        
        // Update thought history
        {
            let mut history = self.thought_history.write().await;
            history.push(thought.clone());
            if history.len() > 100 {
                history.remove(0);
            }
        }
        
        // Get or create voice pattern for user
        let voice_pattern = self.get_or_create_voice_pattern(user_id).await?;
        
        // Process through subconscious stream
        let subconscious_response = self.process_subconscious_stream(
            thought.clone(),
            context.clone(),
            &voice_pattern,
        ).await?;
        
        // Extract patterns for response
        let patterns = if let Some(ref voice) = subconscious_response.internal_voice {
            vec![format!("Internal: {}", voice.content)]
        } else {
            vec![]
        };
        
        // Determine emotional tone based on voice pattern
        let emotional_tone = self.determine_emotional_tone(&voice_pattern);
        
        Ok(DialogueResponse {
            id: Uuid::new_v4().to_string(),
            content: thought,
            timestamp: Utc::now(),
            patterns,
            explorations: vec![],
            emotional_tone,
            cognitive_load: subconscious_response.cognitive_load,
            internal_voice: subconscious_response.internal_voice,
        })
    }
    
    pub async fn process_subconscious_stream(
        &self,
        user_input: String,
        context: Option<String>,
        voice_pattern: &VoicePattern,
    ) -> Result<SubconsciousResponse> {
        // Get thought history
        let history = self.thought_history.read().await;
        let recent_history: Vec<String> = history.iter()
            .rev()
            .take(10)
            .cloned()
            .collect();
        drop(history);
        
        // 1. Detect dialogue patterns using enhanced pattern detector
        let dialogue_patterns = self.pattern_detector
            .detect_dialogue_patterns(&user_input, &recent_history)
            .await?;
        
        // 2. Analyze thought context
        let thought_context = self.pattern_detector
            .analyze_thought_context(&user_input, &recent_history)?;
        
        // 3. Pattern matching against learned behaviors
        let pattern_matches = self.pattern_engine.find_patterns(
            user_input.clone(),
            None
        ).await?;
        
        // 4. Build comprehensive intervention trigger
        let trigger = self.pattern_detector
            .build_intervention_trigger(
                dialogue_patterns,
                thought_context.clone(),
                pattern_matches.clone(),
            ).await?;
        
        // 5. Build user context with enhanced information
        let user_context = UserContext {
            recent_thoughts: recent_history.clone(),
            cognitive_load: thought_context.cognitive_state.confusion_level * 0.5 + 
                           self.calculate_cognitive_load(&pattern_matches) * 0.5,
            focus_level: 1.0 - thought_context.cognitive_state.confusion_level,
            stress_level: thought_context.cognitive_state.frustration_level,
            last_intervention: None, // Would track this
            recent_success: false, // Would track outcomes
            current_task: context.clone(),
            environmental_factors: EnvironmentalFactors {
                time_of_day: chrono::Local::now().format("%H:%M").to_string(),
                interruption_count: 0,
                session_duration: thought_context.temporal_context.session_duration,
            },
        };
        
        // 6. Generate internal dialogue if appropriate
        let internal_dialogue = self.dialogue_generator
            .generate_internal_thought(trigger.clone(), &user_context, voice_pattern)
            .await?;
        
        // 7. Use natural voice generator for more authentic internal voice
        let internal_voice = if let Some(dialogue) = internal_dialogue {
            let generation_context = GenerationContext {
                similar_experience: pattern_matches.first()
                    .map(|p| p.pattern.content.clone()),
                suggestion_content: context,
                current_focus: Some(user_input.clone()),
                recent_success: user_context.recent_success,
                emotional_context: EmotionalContext {
                    current_mood: self.determine_emotional_tone(voice_pattern),
                    stress_level: user_context.stress_level,
                    energy_level: voice_pattern.emotional_baseline.baseline_mood.arousal,
                },
            };
            
            let natural_content = self.natural_voice_gen
                .generate_natural_voice(
                    &dialogue.metadata.intervention_type,
                    voice_pattern,
                    &generation_context,
                )?;
            
            Some(InternalVoice {
                content: natural_content,
                delivery: format!("{:?}", dialogue.delivery.volume).to_lowercase(),
                timing: format!("{:?}", dialogue.timing.fade_pattern).to_lowercase(),
                confidence: dialogue.confidence,
            })
        } else {
            None
        };
        
        Ok(SubconsciousResponse {
            internal_voice,
            cognitive_load: user_context.cognitive_load,
            intervention_confidence: trigger.confidence,
        })
    }
    
    pub async fn get_or_create_voice_pattern(&self, user_id: &str) -> Result<VoicePattern> {
        let mut patterns = self.voice_patterns.write().await;
        
        if let Some(pattern) = patterns.get(user_id) {
            Ok(pattern.clone())
        } else {
            let new_pattern = VoicePattern::new(user_id.to_string());
            patterns.insert(user_id.to_string(), new_pattern.clone());
            
            // Save to Redis
            let mut conn = self.redis_conn.write().await;
            let key = format!("voice_pattern:{}", user_id);
            let pattern_json = serde_json::to_string(&new_pattern)?;
            conn.set::<_, _, ()>(&key, pattern_json).await?;
            
            Ok(new_pattern)
        }
    }
    
    pub async fn learn_from_interaction(
        &self,
        user_id: &str,
        observation: UserObservation,
    ) -> Result<()> {
        let mut patterns = self.voice_patterns.write().await;
        
        if let Some(pattern) = patterns.get_mut(user_id) {
            pattern.learn_from_observation(&observation)?;
            
            // Save updated pattern to Redis
            let mut conn = self.redis_conn.write().await;
            let key = format!("voice_pattern:{}", user_id);
            let pattern_json = serde_json::to_string(&pattern)?;
            conn.set::<_, _, ()>(&key, pattern_json).await?;
        }
        
        Ok(())
    }
    
    fn calculate_cognitive_load(&self, patterns: &[crate::patterns::PatternMatch]) -> f64 {
        if patterns.is_empty() {
            return 0.3; // Base cognitive load
        }
        
        // Higher pattern complexity = higher cognitive load
        let avg_confidence: f64 = patterns.iter()
            .map(|p| p.confidence)
            .sum::<f64>() / patterns.len() as f64;
        
        // Inverse relationship - low confidence patterns increase cognitive load
        0.3 + (1.0 - avg_confidence) * 0.4
    }

    pub async fn create_thought_thread(&self, _initial_thought: String) -> Result<ThoughtThread> {
        // TODO: Implement thought thread creation
        Ok(ThoughtThread {
            id: Uuid::new_v4().to_string(),
            thoughts: vec![],
            patterns_emerged: vec![],
            insights: vec![],
            unresolved_questions: vec![],
        })
    }
    
    fn determine_emotional_tone(&self, voice_pattern: &VoicePattern) -> String {
        let mood = &voice_pattern.emotional_baseline.baseline_mood;
        
        if mood.valence > 0.5 {
            if mood.arousal > 0.5 {
                "excited".to_string()
            } else {
                "content".to_string()
            }
        } else if mood.valence < -0.5 {
            if mood.arousal > 0.5 {
                "anxious".to_string()
            } else {
                "melancholic".to_string()
            }
        } else {
            if mood.arousal > 0.5 {
                "alert".to_string()
            } else {
                "neutral".to_string()
            }
        }
    }
}