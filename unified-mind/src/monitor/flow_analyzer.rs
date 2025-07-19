use anyhow::Result;
use chrono::{DateTime, Utc, Duration};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{HashMap, VecDeque};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{debug, info, warn};

use super::conversation_tracker::ConversationMessage;

/// Represents the current state of a conversation
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum ConversationState {
    Exploring,      // Open-ended discussion, discovery mode
    Debugging,      // Problem-solving, issue investigation
    Learning,       // Knowledge building, understanding concepts
    Implementing,   // Active development, writing code
    Planning,       // Architecture, design discussions
    Stuck,          // Circular discussion, no progress
    Transitioning,  // Moving between states
}

/// Tracks conversation momentum and engagement
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConversationMomentum {
    pub velocity: f64,              // Messages per minute
    pub acceleration: f64,          // Change in velocity
    pub engagement_score: f64,      // How engaged participants are
    pub clarity_score: f64,         // How clear the discussion is
    pub progress_score: f64,        // Forward movement vs circles
    pub confusion_indicators: u32,   // Count of confusion signals
}

/// Represents a topic transition in conversation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TopicTransition {
    pub from_topic: String,
    pub to_topic: String,
    pub timestamp: DateTime<Utc>,
    pub transition_type: TransitionType,
    pub smoothness: f64,  // How natural the transition was
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TransitionType {
    Natural,       // Organic flow
    Abrupt,        // Sudden shift
    Return,        // Coming back to previous topic
    Tangent,       // Side discussion
    Correction,    // Error-driven shift
}

/// Analyzes conversation flow patterns
pub struct FlowAnalyzer {
    // State tracking
    current_state: Arc<RwLock<ConversationState>>,
    state_history: Arc<RwLock<VecDeque<(DateTime<Utc>, ConversationState)>>>,
    
    // Momentum tracking
    momentum: Arc<RwLock<ConversationMomentum>>,
    message_timestamps: Arc<RwLock<VecDeque<DateTime<Utc>>>>,
    
    // Topic tracking
    current_topics: Arc<RwLock<Vec<String>>>,
    topic_history: Arc<RwLock<Vec<TopicTransition>>>,
    
    // Pattern detection
    confusion_patterns: Vec<String>,
    progress_patterns: Vec<String>,
    stuck_patterns: Vec<String>,
    
    // Analysis window
    analysis_window: Duration,
}

impl FlowAnalyzer {
    pub fn new() -> Self {
        Self {
            current_state: Arc::new(RwLock::new(ConversationState::Exploring)),
            state_history: Arc::new(RwLock::new(VecDeque::with_capacity(100))),
            momentum: Arc::new(RwLock::new(ConversationMomentum {
                velocity: 0.0,
                acceleration: 0.0,
                engagement_score: 1.0,
                clarity_score: 1.0,
                progress_score: 1.0,
                confusion_indicators: 0,
            })),
            message_timestamps: Arc::new(RwLock::new(VecDeque::with_capacity(1000))),
            current_topics: Arc::new(RwLock::new(Vec::new())),
            topic_history: Arc::new(RwLock::new(Vec::new())),
            confusion_patterns: Self::init_confusion_patterns(),
            progress_patterns: Self::init_progress_patterns(),
            stuck_patterns: Self::init_stuck_patterns(),
            analysis_window: Duration::minutes(5),
        }
    }
    
    /// Initialize confusion detection patterns
    fn init_confusion_patterns() -> Vec<String> {
        vec![
            "i don't understand".to_string(),
            "confused".to_string(),
            "not sure".to_string(),
            "what do you mean".to_string(),
            "can you explain".to_string(),
            "i'm lost".to_string(),
            "doesn't make sense".to_string(),
            "wait, what".to_string(),
        ]
    }
    
    /// Initialize progress detection patterns
    fn init_progress_patterns() -> Vec<String> {
        vec![
            "i see".to_string(),
            "that makes sense".to_string(),
            "got it".to_string(),
            "understood".to_string(),
            "ah, right".to_string(),
            "now i understand".to_string(),
            "perfect".to_string(),
            "exactly".to_string(),
        ]
    }
    
    /// Initialize stuck detection patterns
    fn init_stuck_patterns() -> Vec<String> {
        vec![
            "we already tried".to_string(),
            "back to square one".to_string(),
            "going in circles".to_string(),
            "same issue".to_string(),
            "still not working".to_string(),
            "tried that before".to_string(),
            "no progress".to_string(),
        ]
    }
    
    /// Analyze a new message in the conversation flow
    pub async fn analyze_message(&self, message: &ConversationMessage) -> Result<()> {
        // Update message timestamps
        {
            let mut timestamps = self.message_timestamps.write().await;
            timestamps.push_back(message.timestamp);
            
            // Keep only recent timestamps
            let cutoff = Utc::now() - self.analysis_window;
            while let Some(front) = timestamps.front() {
                if *front < cutoff {
                    timestamps.pop_front();
                } else {
                    break;
                }
            }
        }
        
        // Update momentum
        self.update_momentum().await?;
        
        // Detect state changes
        self.detect_state_change(message).await?;
        
        // Track topic transitions
        self.track_topic_transition(message).await?;
        
        // Update confusion indicators
        self.update_confusion_indicators(message).await?;
        
        Ok(())
    }
    
    /// Update conversation momentum metrics
    async fn update_momentum(&self) -> Result<()> {
        let timestamps = self.message_timestamps.read().await;
        let mut momentum = self.momentum.write().await;
        
        if timestamps.len() < 2 {
            return Ok(());
        }
        
        // Calculate velocity (messages per minute)
        let time_span = *timestamps.back().unwrap() - *timestamps.front().unwrap();
        let minutes = time_span.num_seconds() as f64 / 60.0;
        let new_velocity = if minutes > 0.0 {
            timestamps.len() as f64 / minutes
        } else {
            0.0
        };
        
        // Calculate acceleration
        let old_velocity = momentum.velocity;
        momentum.acceleration = new_velocity - old_velocity;
        momentum.velocity = new_velocity;
        
        // Update engagement score based on velocity
        momentum.engagement_score = match new_velocity {
            v if v > 10.0 => 1.0,      // Very engaged
            v if v > 5.0 => 0.8,        // Engaged
            v if v > 2.0 => 0.6,        // Moderate
            v if v > 0.5 => 0.4,        // Low engagement
            _ => 0.2,                   // Very low
        };
        
        Ok(())
    }
    
    /// Detect conversation state changes
    async fn detect_state_change(&self, message: &ConversationMessage) -> Result<()> {
        let content_lower = message.content.to_lowercase();
        let current = self.current_state.read().await.clone();
        let mut new_state = current.clone();
        
        // Check for debugging indicators
        if content_lower.contains("error") || 
           content_lower.contains("bug") || 
           content_lower.contains("issue") ||
           content_lower.contains("problem") {
            new_state = ConversationState::Debugging;
        }
        
        // Check for learning indicators
        else if content_lower.contains("how does") || 
                content_lower.contains("what is") || 
                content_lower.contains("explain") ||
                content_lower.contains("understand") {
            new_state = ConversationState::Learning;
        }
        
        // Check for implementation indicators
        else if content_lower.contains("implement") || 
                content_lower.contains("build") || 
                content_lower.contains("create") ||
                content_lower.contains("code") {
            new_state = ConversationState::Implementing;
        }
        
        // Check for planning indicators
        else if content_lower.contains("design") || 
                content_lower.contains("architecture") || 
                content_lower.contains("plan") ||
                content_lower.contains("structure") {
            new_state = ConversationState::Planning;
        }
        
        // Check if stuck
        let momentum = self.momentum.read().await;
        if momentum.progress_score < 0.3 && momentum.confusion_indicators > 3 {
            new_state = ConversationState::Stuck;
        }
        
        // Update state if changed
        if new_state != current {
            info!("Conversation state transition: {:?} -> {:?}", current, new_state);
            
            let mut state = self.current_state.write().await;
            *state = new_state.clone();
            
            let mut history = self.state_history.write().await;
            history.push_back((Utc::now(), new_state));
            
            // Keep history size manageable
            if history.len() > 100 {
                history.pop_front();
            }
        }
        
        Ok(())
    }
    
    /// Track topic transitions
    async fn track_topic_transition(&self, message: &ConversationMessage) -> Result<()> {
        let new_topics = &message.topics;
        let mut current_topics = self.current_topics.write().await;
        
        if !new_topics.is_empty() && new_topics != &*current_topics {
            // Determine transition type
            let transition_type = if current_topics.is_empty() {
                TransitionType::Natural
            } else if new_topics.iter().any(|t| current_topics.contains(t)) {
                TransitionType::Natural  // Some overlap
            } else if message.content.contains("actually") || 
                      message.content.contains("wait") {
                TransitionType::Correction
            } else {
                TransitionType::Abrupt
            };
            
            // Calculate smoothness
            let smoothness = match transition_type {
                TransitionType::Natural => 0.9,
                TransitionType::Return => 0.8,
                TransitionType::Tangent => 0.6,
                TransitionType::Correction => 0.5,
                TransitionType::Abrupt => 0.3,
            };
            
            // Record transition
            let transition = TopicTransition {
                from_topic: current_topics.join(", "),
                to_topic: new_topics.join(", "),
                timestamp: message.timestamp,
                transition_type,
                smoothness,
            };
            
            let mut history = self.topic_history.write().await;
            history.push(transition);
            
            // Update current topics
            *current_topics = new_topics.clone();
        }
        
        Ok(())
    }
    
    /// Update confusion indicators
    async fn update_confusion_indicators(&self, message: &ConversationMessage) -> Result<()> {
        let content_lower = message.content.to_lowercase();
        let mut momentum = self.momentum.write().await;
        
        // Check for confusion patterns
        let has_confusion = self.confusion_patterns.iter()
            .any(|pattern| content_lower.contains(pattern));
        
        if has_confusion {
            momentum.confusion_indicators += 1;
            momentum.clarity_score = (momentum.clarity_score - 0.1).max(0.0);
        }
        
        // Check for progress patterns
        let has_progress = self.progress_patterns.iter()
            .any(|pattern| content_lower.contains(pattern));
        
        if has_progress {
            momentum.confusion_indicators = momentum.confusion_indicators.saturating_sub(1);
            momentum.clarity_score = (momentum.clarity_score + 0.1).min(1.0);
            momentum.progress_score = (momentum.progress_score + 0.05).min(1.0);
        }
        
        // Check for stuck patterns
        let is_stuck = self.stuck_patterns.iter()
            .any(|pattern| content_lower.contains(pattern));
        
        if is_stuck {
            momentum.progress_score = (momentum.progress_score - 0.2).max(0.0);
        }
        
        Ok(())
    }
    
    /// Get current conversation state
    pub async fn get_state(&self) -> ConversationState {
        self.current_state.read().await.clone()
    }
    
    /// Get conversation momentum
    pub async fn get_momentum(&self) -> ConversationMomentum {
        self.momentum.read().await.clone()
    }
    
    /// Check if conversation needs intervention
    pub async fn needs_intervention(&self) -> bool {
        let state = self.current_state.read().await;
        let momentum = self.momentum.read().await;
        
        matches!(*state, ConversationState::Stuck) ||
        momentum.confusion_indicators > 5 ||
        momentum.progress_score < 0.3 ||
        momentum.clarity_score < 0.4
    }
    
    /// Get intervention recommendation
    pub async fn get_intervention_recommendation(&self) -> Option<InterventionRecommendation> {
        let state = self.current_state.read().await;
        let momentum = self.momentum.read().await;
        
        if matches!(*state, ConversationState::Stuck) {
            Some(InterventionRecommendation {
                reason: "Conversation appears stuck".to_string(),
                suggestion: "Try a different approach or break down the problem".to_string(),
                priority: 0.9,
            })
        } else if momentum.confusion_indicators > 5 {
            Some(InterventionRecommendation {
                reason: "High confusion detected".to_string(),
                suggestion: "Provide clarification or examples".to_string(),
                priority: 0.8,
            })
        } else if momentum.progress_score < 0.3 {
            Some(InterventionRecommendation {
                reason: "Low progress detected".to_string(),
                suggestion: "Suggest concrete next steps".to_string(),
                priority: 0.7,
            })
        } else {
            None
        }
    }
    
    /// Get conversation analytics
    pub async fn get_analytics(&self) -> HashMap<String, Value> {
        let state = self.current_state.read().await;
        let momentum = self.momentum.read().await;
        let state_history = self.state_history.read().await;
        let topic_history = self.topic_history.read().await;
        
        // Calculate time in each state
        let mut state_durations: HashMap<String, Duration> = HashMap::new();
        let mut last_time = Utc::now();
        
        for (timestamp, state) in state_history.iter().rev() {
            let duration = last_time - timestamp;
            let state_str = format!("{:?}", state);
            *state_durations.entry(state_str).or_insert(Duration::zero()) += duration;
            last_time = *timestamp;
        }
        
        HashMap::from([
            ("current_state".to_string(), json!(format!("{:?}", *state))),
            ("momentum".to_string(), json!(*momentum)),
            ("state_durations".to_string(), json!(state_durations)),
            ("topic_transitions".to_string(), json!(topic_history.len())),
            ("needs_intervention".to_string(), json!(self.needs_intervention().await)),
        ])
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InterventionRecommendation {
    pub reason: String,
    pub suggestion: String,
    pub priority: f64,
}