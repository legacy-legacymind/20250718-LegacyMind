mod conversation_tracker;
mod entity_detector;
mod flow_analyzer;

use anyhow::Result;
use chrono::{DateTime, Utc, Duration};
use redis::aio::{ConnectionManager, PubSub};
use redis::{AsyncCommands, streams::{StreamReadOptions, StreamReadReply}};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{HashMap, VecDeque};
use std::sync::Arc;
use tokio::sync::{RwLock, mpsc};
use tokio::time::{sleep, timeout};
use tracing::{info, warn, error, debug};
use uuid::Uuid;

use crate::patterns::{PatternUpdate, PatternEngine, PatternType};
use crate::retrieval::{RetrievalLearner, ConversationPattern};
use crate::dialogue::DialogueManager;

use self::conversation_tracker::{ConversationTracker, ConversationMessage};
use self::entity_detector::{EntityDetector, DetectedEntity};
use self::flow_analyzer::{FlowAnalyzer, ConversationState};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CognitiveState {
    pub timestamp: DateTime<Utc>,
    pub cognitive_load: f64,
    pub pattern_recognition_rate: f64,
    pub learning_velocity: f64,
    pub active_patterns: Vec<String>,
    pub attention_focus: Vec<String>,
    // Enhanced tracking
    pub focus_level: f64,
    pub confidence: f64,
    pub thinking_velocity: f64,
    pub uncertainty_level: f64,
    pub cognitive_fatigue: f64,
    pub context_switches: u32,
    pub working_memory_usage: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThoughtStream {
    pub thought_id: String,
    pub chain_id: String,
    pub content: String,
    pub timestamp: DateTime<Utc>,
    pub thinking_type: String,
    pub confidence: f64,
    pub cognitive_load: f64,
    pub tags: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Intervention {
    pub id: String,
    pub timestamp: DateTime<Utc>,
    pub intervention_type: InterventionType,
    pub priority: InterventionPriority,
    pub context: HashMap<String, Value>,
    pub suggested_action: String,
    pub reason: String,
    pub confidence: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum InterventionType {
    MemoryRetrieval,
    FrameworkSuggestion,
    UncertaintyAssistance,
    CognitiveFatigueWarning,
    PatternRecognition,
    ContextSwitchHelp,
    FocusRedirection,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub enum InterventionPriority {
    Low,
    Normal,
    High,
    Urgent,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LearningResult {
    pub task_id: String,
    pub outcome: String,
    pub should_update_patterns: bool,
    pub pattern_updates: Vec<PatternUpdate>,
    pub patterns_updated_count: u32,
    pub strategies_refined: Vec<String>,
    pub improvement_score: f64,
    pub insights: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceMetrics {
    pub task_completion_rate: f64,
    pub pattern_accuracy: f64,
    pub retrieval_efficiency: f64,
    pub adaptation_speed: f64,
    pub error_recovery_rate: f64,
}

pub struct CognitiveMonitor {
    redis_conn: Arc<RwLock<ConnectionManager>>,
    pattern_engine: Arc<PatternEngine>,
    retrieval_learner: Arc<RetrievalLearner>,
    dialogue_manager: Arc<DialogueManager>,
    
    // Conversational intelligence components
    conversation_tracker: Arc<ConversationTracker>,
    entity_detector: Arc<EntityDetector>,
    flow_analyzer: Arc<FlowAnalyzer>,
    
    // Monitoring state
    cognitive_state: Arc<RwLock<CognitiveState>>,
    thought_buffer: Arc<RwLock<VecDeque<ThoughtStream>>>,
    intervention_queue: Arc<RwLock<VecDeque<Intervention>>>,
    
    // Performance tracking
    metrics: Arc<RwLock<PerformanceMetrics>>,
    intervention_history: Arc<RwLock<Vec<Intervention>>>,
}

impl CognitiveMonitor {
    pub async fn new(
        redis_conn: Arc<RwLock<ConnectionManager>>,
        pattern_engine: Arc<PatternEngine>,
        retrieval_learner: Arc<RetrievalLearner>,
        dialogue_manager: Arc<DialogueManager>,
    ) -> Result<Self> {
        // Initialize conversational intelligence components
        let conversation_tracker = Arc::new(ConversationTracker::new(redis_conn.clone()));
        // TODO: Fix entity detector initialization blocking MCP protocol
        // let entity_detector = Arc::new(EntityDetector::new().await?);
        let entity_detector = Arc::new(EntityDetector::new_minimal());
        let flow_analyzer = Arc::new(FlowAnalyzer::new());
        
        let monitor = Self {
            redis_conn,
            pattern_engine,
            retrieval_learner,
            dialogue_manager,
            conversation_tracker,
            entity_detector,
            flow_analyzer,
            cognitive_state: Arc::new(RwLock::new(CognitiveState {
                timestamp: Utc::now(),
                cognitive_load: 0.0,
                pattern_recognition_rate: 0.0,
                learning_velocity: 0.0,
                active_patterns: vec![],
                attention_focus: vec![],
                focus_level: 1.0,
                confidence: 1.0,
                thinking_velocity: 0.0,
                uncertainty_level: 0.0,
                cognitive_fatigue: 0.0,
                context_switches: 0,
                working_memory_usage: 0.0,
            })),
            thought_buffer: Arc::new(RwLock::new(VecDeque::with_capacity(1000))),
            intervention_queue: Arc::new(RwLock::new(VecDeque::new())),
            metrics: Arc::new(RwLock::new(PerformanceMetrics {
                task_completion_rate: 0.0,
                pattern_accuracy: 0.0,
                retrieval_efficiency: 0.0,
                adaptation_speed: 0.0,
                error_recovery_rate: 0.0,
            })),
            intervention_history: Arc::new(RwLock::new(Vec::new())),
        };
        
        Ok(monitor)
    }
    
    /// Start the background monitoring process
    pub async fn start_monitoring(&self) -> Result<()> {
        info!("Starting cognitive monitoring system with conversational intelligence");
        
        // Initialize all components
        self.initialize_monitoring_components().await?;
        
        // Start conversation stream monitoring
        self.conversation_tracker.start_monitoring().await?;
        
        // Start conversation event processor
        let event_processor = self.clone();
        tokio::spawn(async move {
            if let Err(e) = event_processor.process_conversation_events().await {
                error!("Conversation event processing error: {}", e);
            }
        });
        
        // Keep existing thought stream monitoring for backward compatibility
        let thought_monitor = self.clone();
        tokio::spawn(async move {
            if let Err(e) = thought_monitor.monitor_thought_streams().await {
                error!("Thought stream monitoring error: {}", e);
            }
        });
        
        // Start intervention processing
        let intervention_processor = self.clone();
        tokio::spawn(async move {
            if let Err(e) = intervention_processor.process_interventions().await {
                error!("Intervention processing error: {}", e);
            }
        });
        
        // Start cognitive state analysis
        let state_analyzer = self.clone();
        tokio::spawn(async move {
            if let Err(e) = state_analyzer.analyze_cognitive_state().await {
                error!("Cognitive state analysis error: {}", e);
            }
        });
        
        // Start monitoring health checker
        let health_monitor = self.clone();
        tokio::spawn(async move {
            if let Err(e) = health_monitor.monitor_health().await {
                error!("Health monitoring error: {}", e);
            }
        });
        
        Ok(())
    }
    
    /// Initialize all monitoring components
    async fn initialize_monitoring_components(&self) -> Result<()> {
        info!("Initializing monitoring components");
        
        // Entity detector and flow analyzer initialization happens in their constructors
        
        // Initialize conversation tracker
        info!("Monitoring components initialized successfully");
        
        Ok(())
    }
    
    /// Monitor health of all components
    async fn monitor_health(&self) -> Result<()> {
        let mut interval = tokio::time::interval(std::time::Duration::from_secs(30));
        
        loop {
            interval.tick().await;
            
            // Check component health
            let mut health_status = HashMap::new();
            
            // Check conversation tracker
            let flow_state = self.conversation_tracker.get_flow_state().await;
            health_status.insert("conversation_tracker", json!({
                "active_streams": flow_state.len(),
                "total_messages": flow_state.values().map(|s| s.message_count as u64).sum::<u64>(),
            }));
            
            // Check flow analyzer
            let flow_state = self.flow_analyzer.get_state().await;
            health_status.insert("flow_analyzer", json!({
                "current_state": flow_state,
                "needs_intervention": self.flow_analyzer.needs_intervention().await,
            }));
            
            // Check intervention queue
            let queue_size = self.intervention_queue.read().await.len();
            health_status.insert("intervention_queue", json!({
                "size": queue_size,
                "backlogged": queue_size > 100,
            }));
            
            // Store health status
            let mut conn = self.redis_conn.write().await;
            let key = "unified_mind:monitor:health";
            conn.set_ex::<_, _, ()>(&key, json!(health_status).to_string(), 60).await?;
            
            debug!("Health check completed: {:?}", health_status);
        }
    }
    
    /// Monitor Redis streams for ui_think thoughts
    async fn monitor_thought_streams(&self) -> Result<()> {
        info!("Starting thought stream monitoring");
        
        let mut last_id = "$".to_string();
        
        loop {
            let mut conn = self.redis_conn.write().await;
            
            // Read from ui_think stream
            let stream_key = "unified_mind:thought_stream";
            let options = StreamReadOptions::default()
                .block(1000)
                .count(10);
            
            match conn.xread_options::<&str, &str, StreamReadReply>(
                &[stream_key],
                &[&last_id],
                &options
            ).await {
                Ok(results) => {
                    for stream_key_result in results.keys {
                        for stream_id in &stream_key_result.ids {
                            last_id = stream_id.id.clone();
                            
                            if let Some(thought_json) = stream_id.map.get("thought") {
                                if let redis::Value::Data(bytes) = thought_json {
                                    if let Ok(thought_str) = String::from_utf8(bytes.clone()) {
                                        if let Ok(thought) = serde_json::from_str::<ThoughtStream>(&thought_str) {
                                            self.process_thought(thought).await?;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                Err(e) => {
                    warn!("Error reading thought stream: {}", e);
                    sleep(std::time::Duration::from_millis(500)).await;
                }
            }
        }
    }
    
    /// Process individual thoughts and detect intervention needs
    async fn process_thought(&self, thought: ThoughtStream) -> Result<()> {
        debug!("Processing thought: {}", thought.thought_id);
        
        // Update thought buffer
        {
            let mut buffer = self.thought_buffer.write().await;
            buffer.push_back(thought.clone());
            if buffer.len() > 1000 {
                buffer.pop_front();
            }
        }
        
        // Update cognitive state
        self.update_cognitive_state(&thought).await?;
        
        // Check for intervention triggers
        self.check_intervention_triggers(&thought).await?;
        
        Ok(())
    }
    
    /// Update cognitive state based on thought stream
    async fn update_cognitive_state(&self, thought: &ThoughtStream) -> Result<()> {
        let mut state = self.cognitive_state.write().await;
        
        // Update basic metrics
        state.timestamp = Utc::now();
        state.confidence = thought.confidence;
        state.cognitive_load = thought.cognitive_load;
        
        // Calculate thinking velocity (thoughts per minute)
        let buffer = self.thought_buffer.read().await;
        let recent_thoughts: Vec<_> = buffer.iter()
            .filter(|t| t.timestamp > Utc::now() - Duration::minutes(1))
            .collect();
        state.thinking_velocity = recent_thoughts.len() as f64;
        
        // Calculate uncertainty level
        let uncertainty_count = recent_thoughts.iter()
            .filter(|t| t.confidence < 0.7)
            .count();
        state.uncertainty_level = uncertainty_count as f64 / recent_thoughts.len().max(1) as f64;
        
        // Update cognitive fatigue based on sustained high load
        if state.cognitive_load > 0.8 {
            state.cognitive_fatigue = (state.cognitive_fatigue + 0.01).min(1.0);
        } else {
            state.cognitive_fatigue = (state.cognitive_fatigue - 0.005).max(0.0);
        }
        
        // Track context switches
        if !state.attention_focus.is_empty() && 
           !thought.tags.iter().any(|t| state.attention_focus.contains(t)) {
            state.context_switches += 1;
        }
        state.attention_focus = thought.tags.clone();
        
        Ok(())
    }
    
    /// Check if current thought requires intervention
    async fn check_intervention_triggers(&self, thought: &ThoughtStream) -> Result<()> {
        let state = self.cognitive_state.read().await;
        
        // Check for high uncertainty
        if thought.confidence < 0.5 {
            self.queue_intervention(Intervention {
                id: Uuid::new_v4().to_string(),
                timestamp: Utc::now(),
                intervention_type: InterventionType::UncertaintyAssistance,
                priority: InterventionPriority::High,
                context: HashMap::from([
                    ("thought_id".to_string(), json!(thought.thought_id)),
                    ("confidence".to_string(), json!(thought.confidence)),
                    ("content".to_string(), json!(thought.content)),
                ]),
                suggested_action: "Provide clarification or additional context".to_string(),
                reason: format!("Low confidence detected: {:.2}", thought.confidence),
                confidence: 0.9,
            }).await?;
        }
        
        // Check for cognitive fatigue
        if state.cognitive_fatigue > 0.8 {
            self.queue_intervention(Intervention {
                id: Uuid::new_v4().to_string(),
                timestamp: Utc::now(),
                intervention_type: InterventionType::CognitiveFatigueWarning,
                priority: InterventionPriority::Normal,
                context: HashMap::from([
                    ("fatigue_level".to_string(), json!(state.cognitive_fatigue)),
                    ("cognitive_load".to_string(), json!(state.cognitive_load)),
                ]),
                suggested_action: "Consider taking a break or simplifying approach".to_string(),
                reason: "High cognitive fatigue detected".to_string(),
                confidence: 0.85,
            }).await?;
        }
        
        // Check for pattern recognition opportunities
        // Check for patterns in the thought
        if let Ok(patterns) = self.pattern_engine.find_patterns(
            thought.content.clone(),
            Some(thought.thinking_type.clone())
        ).await {
            if !patterns.is_empty() {
                self.queue_intervention(Intervention {
                    id: Uuid::new_v4().to_string(),
                    timestamp: Utc::now(),
                    intervention_type: InterventionType::PatternRecognition,
                    priority: InterventionPriority::Normal,
                    context: HashMap::from([
                        ("patterns".to_string(), json!(patterns)),
                        ("thought_id".to_string(), json!(thought.thought_id)),
                    ]),
                    suggested_action: "Apply recognized patterns".to_string(),
                    reason: "Relevant patterns detected".to_string(),
                    confidence: 0.8,
                }).await?;
            }
        }
        
        // Check for memory retrieval needs
        if thought.content.contains("remember") || 
           thought.content.contains("recall") || 
           thought.content.contains("what was") {
            self.queue_intervention(Intervention {
                id: Uuid::new_v4().to_string(),
                timestamp: Utc::now(),
                intervention_type: InterventionType::MemoryRetrieval,
                priority: InterventionPriority::High,
                context: HashMap::from([
                    ("query".to_string(), json!(thought.content)),
                    ("chain_id".to_string(), json!(thought.chain_id)),
                ]),
                suggested_action: "Retrieve relevant memories".to_string(),
                reason: "Memory retrieval trigger detected".to_string(),
                confidence: 0.9,
            }).await?;
        }
        
        Ok(())
    }
    
    /// Queue an intervention for processing
    async fn queue_intervention(&self, intervention: Intervention) -> Result<()> {
        let mut queue = self.intervention_queue.write().await;
        
        // Insert based on priority
        let position = queue.iter().position(|i| i.priority < intervention.priority)
            .unwrap_or(queue.len());
        
        queue.insert(position, intervention);
        
        Ok(())
    }
    
    /// Process queued interventions
    async fn process_interventions(&self) -> Result<()> {
        info!("Starting intervention processor");
        
        loop {
            // Get next intervention
            let intervention = {
                let mut queue = self.intervention_queue.write().await;
                queue.pop_front()
            };
            
            if let Some(intervention) = intervention {
                // Process based on cognitive load
                let state = self.cognitive_state.read().await;
                if state.cognitive_load < 0.9 || intervention.priority >= InterventionPriority::High {
                    self.execute_intervention(intervention).await?;
                } else {
                    // Re-queue if load is too high
                    let mut queue = self.intervention_queue.write().await;
                    queue.push_back(intervention);
                }
            } else {
                // No interventions, sleep briefly
                sleep(std::time::Duration::from_millis(100)).await;
            }
        }
    }
    
    /// Execute a specific intervention
    async fn execute_intervention(&self, intervention: Intervention) -> Result<()> {
        info!("Executing intervention: {:?} with confidence {}", 
              intervention.intervention_type, intervention.confidence);
        
        // Get conversation context if available
        let conversation_context = Some(
            self.conversation_tracker.get_recent_messages(Some(5)).await
        );
        
        let mut result = json!({
            "intervention_id": intervention.id,
            "type": intervention.intervention_type,
            "timestamp": intervention.timestamp,
        });
        
        match intervention.intervention_type {
            InterventionType::MemoryRetrieval => {
                let mut enriched_results = Vec::new();
                
                // Get query and entities
                if let Some(query) = intervention.context.get("query") {
                    if let Some(query_str) = query.as_str() {
                        // Basic retrieval
                        let query_pattern = ConversationPattern {
                            pattern_type: PatternType::ProblemSolving,
                            context: query_str.to_string(),
                            confidence: 0.8,
                            timestamp: Utc::now(),
                            metadata: HashMap::new(),
                        };
                        let mut results = self.retrieval_learner.retrieve_context(&query_pattern).await?;
                        
                        // Enhance with entity context
                        if let Some(entity) = intervention.context.get("entity") {
                            let entity_str = entity.as_str().unwrap_or("");
                            let entity_pattern = ConversationPattern {
                                pattern_type: PatternType::ProblemSolving,
                                context: format!("{} {}", query_str, entity_str),
                                confidence: 0.8,
                                timestamp: Utc::now(),
                                metadata: HashMap::new(),
                            };
                            let entity_results = self.retrieval_learner.retrieve_context(&entity_pattern).await?;
                            results.extend(entity_results);
                        }
                        
                        // Add conversation context if available
                        if let Some(conv_ctx) = &conversation_context {
                            enriched_results.push(json!({
                                "source": "conversation_context",
                                "relevance": 0.9,
                                "content": conv_ctx,
                            }));
                        }
                        
                        enriched_results.extend(results.into_iter().map(|r| json!(r)));
                        result["results"] = json!(enriched_results);
                    }
                }
            }
            
            InterventionType::PatternRecognition => {
                if let Some(patterns) = intervention.context.get("patterns") {
                    // Pattern suggestions will be handled in the result
                    
                    // Analyze pattern relevance based on entities
                    if let Some(entities) = intervention.context.get("entities") {
                        let pattern_analysis = json!({
                            "patterns": patterns,
                            "entities": entities,
                            "relevance_score": 0.85,
                            "suggested_applications": [
                                "Apply pattern to current context",
                                "Use pattern for similar entity types",
                            ],
                        });
                        result["pattern_analysis"] = pattern_analysis;
                    }
                }
            }
            
            InterventionType::UncertaintyAssistance => {
                let mut assistance_items = Vec::new();
                
                // Generate base assistance
                if let Some(content) = intervention.context.get("content") {
                    let assistance = json!({
                        "type": "uncertainty",
                        "content": content.as_str().unwrap_or(""),
                        "suggestions": ["Break down the problem", "Review similar patterns", "Check documentation"]
                    });
                    assistance_items.push(assistance);
                }
                
                // Add flow-based suggestions
                if let Some(flow_state) = intervention.context.get("conversation_state") {
                    let flow_suggestions = match flow_state.as_str() {
                        Some("Stuck") => vec![
                            "Try rephrasing the question",
                            "Break down the problem into smaller parts",
                            "Look for similar solved problems",
                        ],
                        Some("Exploring") => vec![
                            "Define clear objectives",
                            "Identify key constraints",
                            "List what you know vs what you need to know",
                        ],
                        _ => vec!["Continue with current approach"],
                    };
                    assistance_items.extend(flow_suggestions.into_iter().map(|s| json!(s)));
                }
                
                result["assistance"] = json!(assistance_items);
            }
            
            InterventionType::CognitiveFatigueWarning => {
                // Generate context-aware fatigue management
                let mut suggestions = vec![
                    "Consider taking a 5-minute break",
                    "Try breaking down the problem into smaller parts",
                ];
                
                // Add specific suggestions based on conversation state
                if let Some(conv_ctx) = &conversation_context {
                    if conv_ctx.len() > 20 {
                        suggestions.push("This conversation has been long - consider summarizing progress");
                    }
                }
                
                result["suggestions"] = json!(suggestions);
            }
            
            InterventionType::ContextSwitchHelp => {
                // Help with context switching
                let switch_assistance = json!({
                    "previous_context": intervention.context.get("previous_focus"),
                    "new_context": intervention.context.get("attention_focus"),
                    "suggestions": [
                        "Save current state before switching",
                        "Note any unfinished tasks",
                        "Set a reminder to return to previous context if needed",
                    ],
                });
                result["context_switch_help"] = switch_assistance;
            }
            
            InterventionType::FocusRedirection => {
                // Provide focus guidance
                if let Some(suggestion) = intervention.context.get("suggestion") {
                    let focus_guidance = json!({
                        "current_focus": intervention.context.get("attention_focus"),
                        "suggested_focus": suggestion,
                        "reason": intervention.reason,
                        "priority_actions": [
                            "Complete current thought if critical",
                            "Transition to suggested focus area",
                            "Set clear objectives for new focus",
                        ],
                    });
                    result["focus_guidance"] = focus_guidance;
                }
            }
            
            InterventionType::FrameworkSuggestion => {
                // Suggest relevant frameworks
                let complexity = intervention.context.get("complexity_indicators")
                    .and_then(|v| v.as_object())
                    .map(|obj| {
                        let has_questions = obj.get("has_questions").and_then(|v| v.as_bool()).unwrap_or(false);
                        let has_tech = obj.get("has_technical_terms").and_then(|v| v.as_bool()).unwrap_or(false);
                        let has_code = obj.get("has_code").and_then(|v| v.as_bool()).unwrap_or(false);
                        (has_questions, has_tech, has_code)
                    })
                    .unwrap_or((false, false, false));
                
                let frameworks = match complexity {
                    (true, _, _) => vec!["5 Whys", "Socratic Method", "Question Decomposition"],
                    (_, true, true) => vec!["Technical Design Review", "Code Review Checklist", "Architecture Decision Record"],
                    (_, true, false) => vec!["Concept Mapping", "Technical Documentation Template", "Domain Modeling"],
                    _ => vec!["SMART Goals", "Problem-Solution Fit", "User Story Mapping"],
                };
                
                result["suggested_frameworks"] = json!(frameworks);
            }
        }
        
        // Store intervention result
        let mut conn = self.redis_conn.write().await;
        let key = format!("unified_mind:intervention_results:{}", intervention.id);
        conn.set_ex::<_, _, ()>(&key, result.to_string(), 300).await?;
        
        // Publish intervention event for other components
        let event = json!({
            "type": "intervention_executed",
            "intervention": intervention.clone(),
            "result_summary": result.get("results").map(|r| r.as_array().map(|a| a.len())).flatten().unwrap_or(0),
        });
        conn.publish("unified_mind:intervention_events", event.to_string()).await?;
        
        // Record intervention in history
        let mut history = self.intervention_history.write().await;
        history.push(intervention);
        if history.len() > 1000 {
            history.remove(0);
        }
        
        Ok(())
    }
    
    /// Continuously analyze cognitive state and update metrics
    async fn analyze_cognitive_state(&self) -> Result<()> {
        info!("Starting cognitive state analyzer");
        
        let mut interval = tokio::time::interval(std::time::Duration::from_secs(5));
        
        loop {
            interval.tick().await;
            
            // Analyze recent thoughts
            let buffer = self.thought_buffer.read().await;
            let recent_thoughts: Vec<_> = buffer.iter()
                .filter(|t| t.timestamp > Utc::now() - Duration::minutes(5))
                .collect();
            
            if !recent_thoughts.is_empty() {
                // Calculate pattern recognition rate
                let pattern_count = recent_thoughts.iter()
                    .filter(|t| t.tags.contains(&"pattern_matched".to_string()))
                    .count();
                let pattern_rate = pattern_count as f64 / recent_thoughts.len() as f64;
                
                // Calculate learning velocity
                let learning_indicators = recent_thoughts.iter()
                    .filter(|t| t.tags.iter().any(|tag| 
                        tag.contains("insight") || 
                        tag.contains("learned") || 
                        tag.contains("understood")
                    ))
                    .count();
                let learning_velocity = learning_indicators as f64 / recent_thoughts.len() as f64;
                
                // Update state
                let mut state = self.cognitive_state.write().await;
                state.pattern_recognition_rate = pattern_rate;
                state.learning_velocity = learning_velocity;
                
                // Update metrics
                let mut metrics = self.metrics.write().await;
                metrics.pattern_accuracy = pattern_rate;
                metrics.adaptation_speed = learning_velocity;
            }
            
            // Store state snapshot
            let state = self.cognitive_state.read().await;
            let mut conn = self.redis_conn.write().await;
            let key = "unified_mind:cognitive_state:current";
            conn.set(&key, json!(state.clone()).to_string()).await?;
            
            // Store in time series
            let ts_key = format!("unified_mind:cognitive_state:history:{}", 
                                 state.timestamp.timestamp());
            conn.set_ex::<_, _, ()>(&ts_key, json!(state.clone()).to_string(), 86400).await?;
        }
    }

    pub async fn record_outcome(
        &self,
        task_id: String,
        outcome: String,
        _metrics: Option<Value>,
    ) -> Result<LearningResult> {
        // TODO: Implement outcome recording and learning logic
        // For now, return a basic learning result
        Ok(LearningResult {
            task_id,
            outcome,
            should_update_patterns: false,
            pattern_updates: vec![],
            patterns_updated_count: 0,
            strategies_refined: vec![],
            improvement_score: 0.0,
            insights: vec!["Learning from this experience".to_string()],
        })
    }

    pub async fn get_cognitive_state(&self) -> Result<CognitiveState> {
        Ok(self.cognitive_state.read().await.clone())
    }
    
    /// Get current monitoring status
    pub async fn get_monitoring_status(&self) -> Result<HashMap<String, Value>> {
        let state = self.cognitive_state.read().await;
        let queue_size = self.intervention_queue.read().await.len();
        let buffer_size = self.thought_buffer.read().await.len();
        let metrics = self.metrics.read().await;
        
        // Get conversation intelligence status
        // Get conversation tracker stats from flow state
        let flow_state_tracker = self.conversation_tracker.get_flow_state().await;
        let tracker_stats = json!({
            "active_sessions": flow_state_tracker.len(),
            "total_messages": flow_state_tracker.values().map(|s| s.message_count as u64).sum::<u64>(),
            "messages_per_minute": 0.0
        });
        let flow_state = self.flow_analyzer.get_state().await;
        // Entity detector stats
        let entity_stats = json!({
            "total_entities": 0,
            "enrichments_queued": 0,
            "entity_types": Vec::<String>::new()
        });
        
        // Get health status if available
        let health_status = {
            let mut conn = self.redis_conn.write().await;
            let key = "unified_mind:monitor:health";
            match conn.get::<_, String>(&key).await {
                Ok(health_json) => serde_json::from_str::<Value>(&health_json).ok(),
                Err(_) => None,
            }
        };
        
        Ok(HashMap::from([
            ("status".to_string(), json!("active")),
            ("cognitive_load".to_string(), json!(state.cognitive_load)),
            ("cognitive_fatigue".to_string(), json!(state.cognitive_fatigue)),
            ("uncertainty_level".to_string(), json!(state.uncertainty_level)),
            ("thinking_velocity".to_string(), json!(state.thinking_velocity)),
            ("focus_level".to_string(), json!(state.focus_level)),
            ("context_switches".to_string(), json!(state.context_switches)),
            ("intervention_queue_size".to_string(), json!(queue_size)),
            ("thought_buffer_size".to_string(), json!(buffer_size)),
            ("pattern_accuracy".to_string(), json!(metrics.pattern_accuracy)),
            ("last_update".to_string(), json!(state.timestamp)),
            
            // Conversation intelligence metrics
            ("conversation_tracking".to_string(), json!({
                "active_sessions": tracker_stats.get("active_sessions"),
                "total_messages": tracker_stats.get("total_messages"),
                "messages_per_minute": tracker_stats.get("messages_per_minute"),
            })),
            ("flow_analysis".to_string(), json!({
                "current_state": flow_state,
                "needs_intervention": self.flow_analyzer.needs_intervention().await,
            })),
            ("entity_detection".to_string(), json!({
                "entities_detected": entity_stats.get("total_entities"),
                "enrichments_queued": entity_stats.get("enrichments_queued"),
                "entity_types": entity_stats.get("entity_types"),
            })),
            
            // Component health
            ("component_health".to_string(), health_status.unwrap_or(json!("unavailable"))),
        ]))
    }
    
    /// Get queued interventions
    pub async fn get_intervention_queue(&self) -> Result<Vec<Intervention>> {
        Ok(self.intervention_queue.read().await.iter().cloned().collect())
    }
    
    /// Get cognitive metrics
    pub async fn get_cognitive_metrics(&self) -> Result<HashMap<String, Value>> {
        let state = self.cognitive_state.read().await;
        let metrics = self.metrics.read().await;
        let history = self.intervention_history.read().await;
        
        // Calculate intervention effectiveness
        let recent_interventions: Vec<_> = history.iter()
            .filter(|i| i.timestamp > Utc::now() - Duration::hours(1))
            .collect();
        
        let intervention_stats = HashMap::from([
            ("total_interventions".to_string(), json!(history.len())),
            ("recent_interventions".to_string(), json!(recent_interventions.len())),
            ("high_priority_rate".to_string(), json!(
                recent_interventions.iter()
                    .filter(|i| i.priority >= InterventionPriority::High)
                    .count() as f64 / recent_interventions.len().max(1) as f64
            )),
        ]);
        
        Ok(HashMap::from([
            ("cognitive_state".to_string(), json!(state.clone())),
            ("performance_metrics".to_string(), json!(metrics.clone())),
            ("intervention_stats".to_string(), json!(intervention_stats)),
            ("monitoring_uptime".to_string(), json!(Utc::now() - state.timestamp)),
        ]))
    }
    
    /// Get comprehensive monitoring insights
    pub async fn get_monitoring_insights(&self) -> Result<HashMap<String, Value>> {
        let state = self.cognitive_state.read().await;
        let history = self.intervention_history.read().await;
        
        // Analyze intervention patterns
        let recent_interventions: Vec<_> = history.iter()
            .filter(|i| i.timestamp > Utc::now() - Duration::hours(1))
            .collect();
        
        let mut intervention_type_counts = HashMap::new();
        for intervention in &recent_interventions {
            *intervention_type_counts.entry(format!("{:?}", intervention.intervention_type))
                .or_insert(0) += 1;
        }
        
        // Get conversation insights from recent messages
        let recent_messages = self.conversation_tracker.get_recent_messages(Some(10)).await;
        let conversation_insights = json!({
            "recent_message_count": recent_messages.len(),
            "active_topics": recent_messages.iter().flat_map(|m| &m.topics).collect::<Vec<_>>(),
        });
        
        // Flow patterns analysis
        let flow_patterns = json!({
            "current_state": self.flow_analyzer.get_state().await,
            "momentum": self.flow_analyzer.get_momentum().await,
        });
        
        // Entity trends placeholder
        let entity_trends = json!({
            "trending_entities": Vec::<String>::new(),
            "entity_frequency": HashMap::<String, u32>::new(),
        });
        
        // Calculate effectiveness metrics
        let avg_confidence = recent_interventions.iter()
            .map(|i| i.confidence)
            .sum::<f64>() / recent_interventions.len().max(1) as f64;
        
        let high_priority_ratio = recent_interventions.iter()
            .filter(|i| i.priority >= InterventionPriority::High)
            .count() as f64 / recent_interventions.len().max(1) as f64;
        
        Ok(HashMap::from([
            ("monitoring_insights".to_string(), json!({
                "cognitive_patterns": {
                    "average_load": state.cognitive_load,
                    "fatigue_trend": state.cognitive_fatigue,
                    "context_switch_frequency": state.context_switches,
                    "uncertainty_periods": state.uncertainty_level,
                },
                "intervention_analysis": {
                    "total_recent": recent_interventions.len(),
                    "type_distribution": intervention_type_counts,
                    "average_confidence": avg_confidence,
                    "high_priority_ratio": high_priority_ratio,
                },
                "conversation_intelligence": {
                    "insights": conversation_insights,
                    "flow_patterns": flow_patterns,
                    "entity_trends": entity_trends,
                },
                "recommendations": self.generate_monitoring_recommendations(&state, &recent_interventions),
            })),
        ]))
    }
    
    /// Generate monitoring recommendations based on current state
    fn generate_monitoring_recommendations(
        &self,
        state: &CognitiveState,
        recent_interventions: &[&Intervention],
    ) -> Vec<String> {
        let mut recommendations = Vec::new();
        
        // Check cognitive load
        if state.cognitive_load > 0.8 {
            recommendations.push("High cognitive load detected - consider task prioritization".to_string());
        }
        
        // Check fatigue
        if state.cognitive_fatigue > 0.7 {
            recommendations.push("Cognitive fatigue is high - schedule breaks or simpler tasks".to_string());
        }
        
        // Check context switching
        if state.context_switches > 10 {
            recommendations.push("Frequent context switches detected - try to batch similar tasks".to_string());
        }
        
        // Check intervention patterns
        let uncertainty_count = recent_interventions.iter()
            .filter(|i| i.intervention_type == InterventionType::UncertaintyAssistance)
            .count();
        
        if uncertainty_count > 5 {
            recommendations.push("High uncertainty detected - consider clearer problem definition".to_string());
        }
        
        // Check focus level
        if state.focus_level < 0.5 {
            recommendations.push("Low focus detected - minimize distractions and set clear goals".to_string());
        }
        
        recommendations
    }
    
    /// Shutdown monitoring gracefully
    pub async fn shutdown(&self) -> Result<()> {
        info!("Shutting down cognitive monitor");
        
        // Save final state
        let state = self.cognitive_state.read().await;
        let mut conn = self.redis_conn.write().await;
        let key = format!("unified_mind:monitor:final_state:{}", Utc::now().timestamp());
        conn.set_ex::<_, _, ()>(&key, json!(state.clone()).to_string(), 86400 * 7).await?;
        
        // Note: Proper shutdown would require a shared shutdown flag
        // For now, tasks will continue running until the process exits
        Ok(())
    }

    pub async fn analyze_performance(&self, _time_window: chrono::Duration) -> Result<PerformanceMetrics> {
        // TODO: Implement performance analysis
        Ok(PerformanceMetrics {
            task_completion_rate: 0.8,
            pattern_accuracy: 0.75,
            retrieval_efficiency: 0.7,
            adaptation_speed: 0.6,
            error_recovery_rate: 0.85,
        })
    }
    
    /// Process conversation events from the event stream
    async fn process_conversation_events(&self) -> Result<()> {
        info!("Starting conversation event processor");
        
        // Monitor conversation streams directly
        let mut last_ids: HashMap<String, String> = HashMap::new();
        
        loop {
            let mut conn = self.redis_conn.write().await;
            
            // Get list of active conversation streams
            let pattern = "conversation:*:*";
            let streams: Vec<String> = conn.keys(pattern).await?;
            
            if streams.is_empty() {
                sleep(std::time::Duration::from_secs(1)).await;
                continue;
            }
            
            // Prepare stream keys and last IDs
            let mut stream_keys = Vec::new();
            let mut stream_ids = Vec::new();
            
            let default_id = "$".to_string();
            for stream in &streams {
                stream_keys.push(stream.as_str());
                let last_id = last_ids.get(stream).unwrap_or(&default_id);
                stream_ids.push(last_id.as_str());
            }
            
            // Read from multiple conversation streams
            let options = StreamReadOptions::default()
                .block(1000)
                .count(10);
            
            match conn.xread_options::<&str, &str, StreamReadReply>(
                &stream_keys,
                &stream_ids,
                &options
            ).await {
                Ok(results) => {
                    for stream_key in results.keys {
                        for stream_id in &stream_key.ids {
                            // Update last ID for this stream
                            last_ids.insert(stream_key.key.clone(), stream_id.id.clone());
                            
                            // Parse conversation message
                            if let Some(msg_json) = stream_id.map.get("message") {
                                if let redis::Value::Data(bytes) = msg_json {
                                    if let Ok(msg_str) = String::from_utf8(bytes.clone()) {
                                        if let Ok(message) = serde_json::from_str::<ConversationMessage>(&msg_str) {
                                            // Process through all analyzers
                                            self.process_conversation_message(message).await?;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                Err(e) => {
                    if !e.to_string().contains("timeout") {
                        warn!("Error reading conversation streams: {}", e);
                    }
                    sleep(std::time::Duration::from_millis(500)).await;
                }
            }
        }
    }
    
    /// Process a conversation message with full intelligence
    async fn process_conversation_message(&self, message: ConversationMessage) -> Result<()> {
        debug!("Processing conversation message from {}: {}", message.instance, &message.content[..50.min(message.content.len())]);
        
        // Message is already tracked by conversation_tracker's stream monitoring
        
        // Analyze conversation flow
        self.flow_analyzer.analyze_message(&message).await?;
        
        // Detect entities for enrichment
        let entities = self.entity_detector.detect_entities(&message.content).await?;
        
        // Get current conversation state
        let flow_state = self.flow_analyzer.get_state().await;
        
        // Update cognitive state based on conversation
        self.update_cognitive_state_from_conversation(&message, &flow_state).await?;
        
        // Check for flow-based interventions
        if self.flow_analyzer.needs_intervention().await {
            if let Some(recommendation) = self.flow_analyzer.get_intervention_recommendation().await {
                self.queue_intervention(Intervention {
                    id: Uuid::new_v4().to_string(),
                    timestamp: Utc::now(),
                    intervention_type: match recommendation.reason.as_str() {
                        r if r.contains("stuck") => InterventionType::UncertaintyAssistance,
                        r if r.contains("context") => InterventionType::ContextSwitchHelp,
                        r if r.contains("pattern") => InterventionType::PatternRecognition,
                        _ => InterventionType::FocusRedirection,
                    },
                    priority: if recommendation.priority > 0.8 {
                        InterventionPriority::Urgent
                    } else if recommendation.priority > 0.6 {
                        InterventionPriority::High
                    } else if recommendation.priority > 0.4 {
                        InterventionPriority::Normal
                    } else {
                        InterventionPriority::Low
                    },
                    context: HashMap::from([
                        ("reason".to_string(), json!(recommendation.reason)),
                        ("suggestion".to_string(), json!(recommendation.suggestion)),
                        ("conversation_state".to_string(), json!(flow_state)),
                        ("instance".to_string(), json!(message.instance)),
                        ("session".to_string(), json!(message.session)),
                    ]),
                    suggested_action: recommendation.suggestion,
                    reason: recommendation.reason,
                    confidence: recommendation.priority,
                }).await?;
            }
        }
        
        // Process entities for enrichment
        let mut entity_context = Vec::new();
        for entity in &entities {
            // Check if entity needs immediate enrichment based on confidence
            if entity.confidence < 0.7 {
                self.queue_entity_enrichment(entity.clone()).await?;
            }
            
            // Collect entity context for pattern analysis
            entity_context.push(json!({
                "text": entity.text,
                "type": entity.entity_type,
                "confidence": entity.confidence,
                "context": entity.context,
            }));
        }
        
        // Analyze for pattern-based interventions
        if !entity_context.is_empty() {
            let pattern_input = json!({
                "message": message.content,
                "entities": entity_context,
                "flow_state": flow_state,
                "instance": message.instance,
            });
            
            // Look for patterns based on the message content and context
            if let Ok(patterns) = self.pattern_engine.find_patterns(
                format!("{} {}", message.content, serde_json::to_string(&entity_context).unwrap_or_default()),
                None
            ).await {
                if !patterns.is_empty() {
                    self.queue_intervention(Intervention {
                        id: Uuid::new_v4().to_string(),
                        timestamp: Utc::now(),
                        intervention_type: InterventionType::PatternRecognition,
                        priority: InterventionPriority::Normal,
                        context: HashMap::from([
                            ("patterns".to_string(), json!(patterns)),
                            ("entities".to_string(), json!(entities)),
                            ("message".to_string(), json!(message.content)),
                        ]),
                        suggested_action: "Apply recognized patterns to enhance understanding".to_string(),
                        reason: format!("Detected {} relevant patterns in conversation", patterns.len()),
                        confidence: 0.85,
                    }).await?;
                }
            }
        }
        
        // Check for cognitive assistance needs based on message analysis
        if message.content.len() > 500 || entities.len() > 5 {
            // Complex message, might need assistance
            self.queue_intervention(Intervention {
                id: Uuid::new_v4().to_string(),
                timestamp: Utc::now(),
                intervention_type: InterventionType::FrameworkSuggestion,
                priority: InterventionPriority::Low,
                context: HashMap::from([
                    ("message_length".to_string(), json!(message.content.len())),
                    ("entity_count".to_string(), json!(entities.len())),
                    ("complexity_indicators".to_string(), json!({
                        "has_questions": message.content.contains('?'),
                        "has_technical_terms": entities.iter().any(|e| matches!(e.entity_type, entity_detector::EntityType::Function | entity_detector::EntityType::Tool)),
                        "has_code": message.content.contains("```"),
                    })),
                ]),
                suggested_action: "Consider breaking down complex concepts or using frameworks".to_string(),
                reason: "Complex message detected that may benefit from structured thinking".to_string(),
                confidence: 0.7,
            }).await?;
        }
        
        Ok(())
    }
    
    /// Update cognitive state based on conversation analysis
    async fn update_cognitive_state_from_conversation(
        &self,
        message: &ConversationMessage,
        flow_state: &ConversationState,
    ) -> Result<()> {
        let mut state = self.cognitive_state.write().await;
        
        // Update based on flow state
        match flow_state {
            ConversationState::Exploring => {
                state.cognitive_load = (state.cognitive_load * 0.9 + 0.3).min(1.0);
                state.uncertainty_level = (state.uncertainty_level * 0.8 + 0.2).min(1.0);
            }
            ConversationState::Implementing => {
                state.cognitive_load = (state.cognitive_load * 0.9 + 0.5).min(1.0);
                state.focus_level = (state.focus_level * 0.9 + 0.8).min(1.0);
            }
            ConversationState::Stuck => {
                state.cognitive_load = (state.cognitive_load * 0.9 + 0.8).min(1.0);
                state.uncertainty_level = (state.uncertainty_level * 0.8 + 0.7).min(1.0);
                state.cognitive_fatigue = (state.cognitive_fatigue + 0.05).min(1.0);
            }
            ConversationState::Transitioning => {
                state.context_switches += 1;
                state.cognitive_load = (state.cognitive_load * 0.9 + 0.6).min(1.0);
            }
            ConversationState::Debugging => {
                state.cognitive_load = (state.cognitive_load * 0.9 + 0.7).min(1.0);
                state.focus_level = (state.focus_level * 0.9 + 0.7).min(1.0);
            }
            ConversationState::Learning => {
                state.cognitive_load = (state.cognitive_load * 0.9 + 0.4).min(1.0);
                state.learning_velocity = (state.learning_velocity * 0.9 + 0.1).min(1.0);
            }
            ConversationState::Planning => {
                state.cognitive_load = (state.cognitive_load * 0.9 + 0.5).min(1.0);
                state.focus_level = (state.focus_level * 0.9 + 0.6).min(1.0);
            }
        }
        
        // Track conversation velocity
        state.thinking_velocity = state.thinking_velocity * 0.95 + 0.05;
        
        Ok(())
    }
    
    /// Queue entity enrichment intervention
    async fn queue_entity_enrichment(&self, entity: DetectedEntity) -> Result<()> {
        let enrichment_strategy = self.entity_detector.get_enrichment_strategy(&entity).await;
        
        if let Some(strategy) = enrichment_strategy {
            self.queue_intervention(Intervention {
                id: Uuid::new_v4().to_string(),
                timestamp: Utc::now(),
                intervention_type: InterventionType::MemoryRetrieval,
                priority: if entity.confidence > 0.8 { 
                    InterventionPriority::High 
                } else { 
                    InterventionPriority::Normal 
                },
                context: HashMap::from([
                    ("entity".to_string(), json!(entity.text)),
                    ("entity_type".to_string(), json!(entity.entity_type)),
                    ("enrichment_actions".to_string(), json!(strategy.actions)),
                ]),
                suggested_action: format!("Enrich context for {}", entity.text),
                reason: format!("Entity '{}' detected requiring enrichment", entity.text),
                confidence: entity.confidence,
            }).await?;
        }
        
        Ok(())
    }
}

impl Clone for CognitiveMonitor {
    fn clone(&self) -> Self {
        Self {
            redis_conn: self.redis_conn.clone(),
            pattern_engine: self.pattern_engine.clone(),
            retrieval_learner: self.retrieval_learner.clone(),
            dialogue_manager: self.dialogue_manager.clone(),
            conversation_tracker: self.conversation_tracker.clone(),
            entity_detector: self.entity_detector.clone(),
            flow_analyzer: self.flow_analyzer.clone(),
            cognitive_state: self.cognitive_state.clone(),
            thought_buffer: self.thought_buffer.clone(),
            intervention_queue: self.intervention_queue.clone(),
            metrics: self.metrics.clone(),
            intervention_history: self.intervention_history.clone(),
        }
    }
}