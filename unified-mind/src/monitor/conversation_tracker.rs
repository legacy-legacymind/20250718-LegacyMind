use anyhow::Result;
use chrono::{DateTime, Utc, Duration};
use redis::aio::ConnectionManager;
use redis::{AsyncCommands, streams::{StreamReadOptions, StreamReadReply}};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{HashMap, VecDeque};
use std::sync::Arc;
use tokio::sync::RwLock;
use tokio::time::sleep;
use tracing::{info, warn, error, debug};

/// Represents a single message in a conversation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConversationMessage {
    pub id: String,
    pub timestamp: DateTime<Utc>,
    pub instance: String,
    pub session: String,
    pub role: MessageRole,
    pub content: String,
    pub entities: Vec<String>,
    pub topics: Vec<String>,
    pub confidence: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum MessageRole {
    User,
    Assistant, 
    System,
    Thought,
}

/// Tracks the state of an active conversation stream
#[derive(Debug, Clone)]
pub struct StreamState {
    pub stream_key: String,
    pub last_id: String,
    pub last_activity: DateTime<Utc>,
    pub message_count: usize,
    pub current_topic: Option<String>,
    pub context_depth: usize,
}

/// Manages conversation tracking across multiple streams
pub struct ConversationTracker {
    redis_conn: Arc<RwLock<ConnectionManager>>,
    active_streams: Arc<RwLock<HashMap<String, StreamState>>>,
    message_buffer: Arc<RwLock<VecDeque<ConversationMessage>>>,
    buffer_capacity: usize,
    context_window: Duration,
}

impl ConversationTracker {
    pub fn new(redis_conn: Arc<RwLock<ConnectionManager>>) -> Self {
        Self {
            redis_conn,
            active_streams: Arc::new(RwLock::new(HashMap::new())),
            message_buffer: Arc::new(RwLock::new(VecDeque::with_capacity(1000))),
            buffer_capacity: 1000,
            context_window: Duration::minutes(30),
        }
    }
    
    /// Start monitoring conversation streams
    pub async fn start_monitoring(&self) -> Result<()> {
        info!("Starting conversation stream monitoring");
        
        // Monitor for new conversation streams
        let discovery_handle = self.clone();
        tokio::spawn(async move {
            if let Err(e) = discovery_handle.discover_streams().await {
                error!("Stream discovery error: {}", e);
            }
        });
        
        // Monitor active conversation streams
        let monitor_handle = self.clone();
        tokio::spawn(async move {
            if let Err(e) = monitor_handle.monitor_active_streams().await {
                error!("Stream monitoring error: {}", e);
            }
        });
        
        Ok(())
    }
    
    /// Discover new conversation streams
    async fn discover_streams(&self) -> Result<()> {
        let mut interval = tokio::time::interval(std::time::Duration::from_secs(10));
        
        loop {
            interval.tick().await;
            
            let mut conn = self.redis_conn.write().await;
            
            // Scan for conversation stream keys
            let pattern = "conversation:*:*";
            let keys: Vec<String> = match conn.scan_match(pattern).await {
                Ok(mut iter) => {
                    let mut keys = Vec::new();
                    while let Some(key) = iter.next_item().await {
                        keys.push(key);
                    }
                    keys
                },
                Err(e) => {
                    warn!("Error scanning for conversation streams: {}", e);
                    continue;
                }
            };
            
            let mut streams = self.active_streams.write().await;
            
            for key in keys {
                if !streams.contains_key(&key) {
                    info!("Discovered new conversation stream: {}", key);
                    streams.insert(key.clone(), StreamState {
                        stream_key: key,
                        last_id: "0".to_string(),
                        last_activity: Utc::now(),
                        message_count: 0,
                        current_topic: None,
                        context_depth: 0,
                    });
                }
            }
            
            // Clean up inactive streams
            let cutoff = Utc::now() - Duration::hours(1);
            streams.retain(|_, state| state.last_activity > cutoff);
        }
    }
    
    /// Monitor active conversation streams
    async fn monitor_active_streams(&self) -> Result<()> {
        loop {
            let streams_snapshot = {
                let streams = self.active_streams.read().await;
                streams.clone()
            };
            
            if streams_snapshot.is_empty() {
                sleep(std::time::Duration::from_secs(1)).await;
                continue;
            }
            
            let mut conn = self.redis_conn.write().await;
            
            // Prepare stream keys and IDs for XREAD
            let stream_keys: Vec<&str> = streams_snapshot.keys()
                .map(|k| k.as_str())
                .collect();
            let last_ids: Vec<&str> = streams_snapshot.values()
                .map(|s| s.last_id.as_str())
                .collect();
            
            let options = StreamReadOptions::default()
                .block(1000)
                .count(10);
            
            match conn.xread_options::<&str, &str, StreamReadReply>(
                &stream_keys,
                &last_ids,
                &options
            ).await {
                Ok(results) => {
                    for stream_key_result in results.keys {
                        for stream_id in &stream_key_result.ids {
                            // Convert HashMap<String, redis::Value> to HashMap<String, String>
                            let mut string_map = HashMap::new();
                            for (k, v) in stream_id.map.iter() {
                                if let redis::Value::Data(bytes) = v {
                                    if let Ok(s) = String::from_utf8(bytes.clone()) {
                                        string_map.insert(k.clone(), s);
                                    }
                                }
                            }
                            
                            if let Ok(message) = self.parse_message(&stream_key_result.key, &stream_id.id, string_map).await {
                                self.process_message(message).await?;
                                
                                // Update stream state
                                let mut streams = self.active_streams.write().await;
                                if let Some(state) = streams.get_mut(&stream_key_result.key) {
                                    state.last_id = stream_id.id.clone();
                                    state.last_activity = Utc::now();
                                    state.message_count += 1;
                                }
                            }
                        }
                    }
                }
                Err(e) => {
                    warn!("Error reading conversation streams: {}", e);
                    sleep(std::time::Duration::from_millis(500)).await;
                }
            }
        }
    }
    
    /// Parse a raw message from Redis stream
    async fn parse_message(
        &self,
        stream_key: &str,
        id: &str,
        data: HashMap<String, String>
    ) -> Result<ConversationMessage> {
        // Extract instance and session from stream key
        let parts: Vec<&str> = stream_key.split(':').collect();
        let instance = parts.get(1).unwrap_or(&"unknown").to_string();
        let session = parts.get(2).unwrap_or(&"unknown").to_string();
        
        // Parse message data
        let content = data.get("content").cloned().unwrap_or_default();
        let role = match data.get("role").map(|s| s.as_str()) {
            Some("user") => MessageRole::User,
            Some("assistant") => MessageRole::Assistant,
            Some("system") => MessageRole::System,
            Some("thought") => MessageRole::Thought,
            _ => MessageRole::Assistant,
        };
        
        // Extract entities and topics (would be enhanced by entity_detector)
        let entities = self.extract_entities(&content).await;
        let topics = self.extract_topics(&content).await;
        
        let confidence = data.get("confidence")
            .and_then(|s| s.parse::<f64>().ok())
            .unwrap_or(1.0);
        
        Ok(ConversationMessage {
            id: id.to_string(),
            timestamp: Utc::now(),
            instance,
            session,
            role,
            content,
            entities,
            topics,
            confidence,
        })
    }
    
    /// Process a conversation message
    async fn process_message(&self, message: ConversationMessage) -> Result<()> {
        debug!("Processing conversation message: {} from {}", 
               message.id, message.instance);
        
        // Add to message buffer
        {
            let mut buffer = self.message_buffer.write().await;
            buffer.push_back(message.clone());
            
            // Maintain buffer capacity
            while buffer.len() > self.buffer_capacity {
                buffer.pop_front();
            }
        }
        
        // Store processed message for other components
        let mut conn = self.redis_conn.write().await;
        let key = format!("unified_mind:processed_messages:{}", message.id);
        conn.set_ex(&key, json!(message).to_string(), 3600).await?;
        
        // Publish to internal event stream for other components
        let event = json!({
            "type": "conversation_message",
            "message": message,
            "timestamp": Utc::now(),
        });
        conn.publish("unified_mind:events", event.to_string()).await?;
        
        Ok(())
    }
    
    /// Extract entities from message content (basic implementation)
    async fn extract_entities(&self, content: &str) -> Vec<String> {
        let mut entities = Vec::new();
        
        // Look for common system/component names
        let known_entities = [
            "UnifiedVault", "UnifiedIntelligence", "UnifiedMind",
            "Redis", "Qdrant", "PostgreSQL", "Docker",
            "CCI", "CCD", "CC", "DT",
        ];
        
        for entity in known_entities {
            if content.contains(entity) {
                entities.push(entity.to_string());
            }
        }
        
        // Look for file paths
        let path_regex = regex::Regex::new(r"(/[\w/.-]+)").unwrap();
        for cap in path_regex.captures_iter(content) {
            if let Some(path) = cap.get(1) {
                entities.push(format!("path:{}", path.as_str()));
            }
        }
        
        entities
    }
    
    /// Extract topics from message content (basic implementation)
    async fn extract_topics(&self, content: &str) -> Vec<String> {
        let mut topics = Vec::new();
        
        // Topic keywords
        let topic_patterns = [
            ("error", vec!["error", "exception", "failed", "failure"]),
            ("debugging", vec!["debug", "trace", "investigate", "issue"]),
            ("architecture", vec!["design", "architecture", "structure", "pattern"]),
            ("performance", vec!["slow", "performance", "optimize", "speed"]),
            ("memory", vec!["remember", "recall", "memory", "forgot"]),
            ("implementation", vec!["implement", "build", "create", "develop"]),
        ];
        
        let content_lower = content.to_lowercase();
        for (topic, keywords) in topic_patterns {
            if keywords.iter().any(|kw| content_lower.contains(kw)) {
                topics.push(topic.to_string());
            }
        }
        
        topics
    }
    
    /// Get recent messages within context window
    pub async fn get_recent_messages(&self, limit: Option<usize>) -> Vec<ConversationMessage> {
        let buffer = self.message_buffer.read().await;
        let cutoff = Utc::now() - self.context_window;
        
        buffer.iter()
            .filter(|msg| msg.timestamp > cutoff)
            .take(limit.unwrap_or(100))
            .cloned()
            .collect()
    }
    
    /// Get conversation context for a specific session
    pub async fn get_session_context(
        &self, 
        instance: &str, 
        session: &str
    ) -> Vec<ConversationMessage> {
        let buffer = self.message_buffer.read().await;
        
        buffer.iter()
            .filter(|msg| msg.instance == instance && msg.session == session)
            .cloned()
            .collect()
    }
    
    /// Get messages containing specific entities
    pub async fn get_entity_messages(&self, entity: &str) -> Vec<ConversationMessage> {
        let buffer = self.message_buffer.read().await;
        
        buffer.iter()
            .filter(|msg| msg.entities.contains(&entity.to_string()))
            .cloned()
            .collect()
    }
    
    /// Get conversation flow state
    pub async fn get_flow_state(&self) -> HashMap<String, StreamState> {
        self.active_streams.read().await.clone()
    }
}

impl Clone for ConversationTracker {
    fn clone(&self) -> Self {
        Self {
            redis_conn: self.redis_conn.clone(),
            active_streams: self.active_streams.clone(),
            message_buffer: self.message_buffer.clone(),
            buffer_capacity: self.buffer_capacity,
            context_window: self.context_window,
        }
    }
}