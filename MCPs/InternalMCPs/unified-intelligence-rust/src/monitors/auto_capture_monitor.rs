use anyhow::Result;
use chrono::{DateTime, Utc};
use redis::AsyncCommands;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;
use tokio::time::interval;
use tracing::{debug, error, info, warn};

use crate::storage::redis_pool::RedisPool;

// ... (structs remain the same) ...

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MonitorState {
    pub instance_id: String,
    pub session_id: String,
    pub start_time: DateTime<Utc>,
    pub thoughts_captured: u32,
    pub last_activity: DateTime<Utc>,
    pub significance_threshold: u8,
    pub enabled: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AutoThinkEvent {
    pub event_type: String,
    pub instance_id: String,
    pub content: Option<String>,
    pub significance: Option<u8>,
    pub timestamp: DateTime<Utc>,
    pub metadata: serde_json::Value,
}


pub struct AutoCaptureMonitor {
    redis_pool: Arc<RedisPool>,
    active_monitors: Arc<RwLock<HashMap<String, MonitorState>>>,
}

impl AutoCaptureMonitor {
    pub fn new(redis_pool: Arc<RedisPool>) -> Self {
        Self {
            redis_pool,
            active_monitors: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub async fn initialize(&self) -> Result<()> {
        info!("Initializing AutoCaptureMonitor");
        self.start_background_loop().await;
        info!("AutoCaptureMonitor initialized successfully");
        Ok(())
    }

    pub async fn start_monitoring(&self, instance_id: String, session_id: String, threshold: u8) -> Result<()> {
        info!("Starting auto-capture monitoring for instance: {}", instance_id);
        
        let monitor_state = MonitorState {
            instance_id: instance_id.clone(),
            session_id: session_id.clone(),
            start_time: Utc::now(),
            thoughts_captured: 0,
            last_activity: Utc::now(),
            significance_threshold: threshold,
            enabled: true,
        };

        self.active_monitors.write().await.insert(instance_id.clone(), monitor_state.clone());
        self.persist_monitor_state(&instance_id, &monitor_state).await?;

        self.publish_event(&instance_id, AutoThinkEvent {
            event_type: "monitor_started".to_string(),
            instance_id: instance_id.clone(),
            content: None, significance: None, timestamp: Utc::now(),
            metadata: serde_json::json!({ "sessionId": session_id, "threshold": threshold }),
        }).await?;

        info!("Auto-capture monitoring started for instance: {}", instance_id);
        Ok(())
    }

    pub async fn stop_monitoring(&self, instance_id: &str) -> Result<()> {
        info!("Stopping auto-capture monitoring for instance: {}", instance_id);
        self.active_monitors.write().await.remove(instance_id);

        let monitor_key = format!("{}:auto_think", instance_id);
        let mut conn = self.redis_pool.get().await?;
        let _: () = conn.del(&monitor_key).await?;

        self.publish_event(instance_id, AutoThinkEvent {
            event_type: "monitor_stopped".to_string(),
            instance_id: instance_id.to_string(),
            content: None, significance: None, timestamp: Utc::now(),
            metadata: serde_json::json!({}),
        }).await?;

        info!("Auto-capture monitoring stopped for instance: {}", instance_id);
        Ok(())
    }

    async fn publish_event(&self, instance_id: &str, event: AutoThinkEvent) -> Result<()> {
        let channel = format!("{}:auto_think:events", instance_id);
        let event_json = serde_json::to_string(&event)?;
        let mut conn = self.redis_pool.get().await?;
        let _: () = conn.publish(&channel, &event_json).await?;
        debug!("Published event: {} to channel: {}", event.event_type, channel);
        Ok(())
    }

    pub async fn process_thought_capture(&self, instance_id: &str, content: &str, significance: u8) -> Result<bool> {
        let should_capture = self.active_monitors.read().await
            .get(instance_id)
            .map_or(false, |m| m.enabled && significance >= m.significance_threshold);

        if should_capture {
            if let Some(monitor) = self.active_monitors.write().await.get_mut(instance_id) {
                monitor.thoughts_captured += 1;
                monitor.last_activity = Utc::now();
            }

            self.publish_event(instance_id, AutoThinkEvent {
                event_type: "thought_captured".to_string(),
                instance_id: instance_id.to_string(),
                content: Some(content.to_string()),
                significance: Some(significance),
                timestamp: Utc::now(),
                metadata: serde_json::json!({ "auto_captured": true }),
            }).await?;
            info!("Auto-captured thought for instance: {} (significance: {})", instance_id, significance);
        }
        Ok(should_capture)
    }

    async fn persist_monitor_state(&self, instance_id: &str, state: &MonitorState) -> Result<()> {
        let monitor_key = format!("{}:auto_think", instance_id);
        let state_json = serde_json::to_string(state)?;
        let mut conn = self.redis_pool.get().await?;
        let _: () = conn.set(&monitor_key, &state_json).await?;
        Ok(())
    }

    async fn start_background_loop(&self) {
        let monitors = Arc::clone(&self.active_monitors);
        let redis_pool = Arc::clone(&self.redis_pool);

        tokio::spawn(async move {
            let mut interval = interval(Duration::from_secs(30));
            loop {
                interval.tick().await;
                if let Err(e) = Self::background_tasks(&monitors, &redis_pool).await {
                    error!("AutoCaptureMonitor background task failed: {}", e);
                }
            }
        });
    }

    async fn background_tasks(monitors: &Arc<RwLock<HashMap<String, MonitorState>>>, redis_pool: &Arc<RedisPool>) -> Result<()> {
        Self::cleanup_inactive_monitors(monitors, redis_pool).await?;
        Self::sync_monitor_state(monitors, redis_pool).await?;
        Ok(())
    }

    async fn cleanup_inactive_monitors(monitors: &Arc<RwLock<HashMap<String, MonitorState>>>, redis_pool: &Arc<RedisPool>) -> Result<()> {
        let now = Utc::now();
        let inactivity_threshold = Duration::from_secs(600);
        let mut to_remove = Vec::new();

        for (id, state) in monitors.read().await.iter() {
            if now.signed_duration_since(state.last_activity).to_std()? > inactivity_threshold {
                to_remove.push(id.clone());
            }
        }

        for id in to_remove {
            monitors.write().await.remove(&id);
            let monitor_key = format!("{}:auto_think", &id);
            let mut conn = redis_pool.get().await?;
            let _: () = conn.del(&monitor_key).await?;
            info!("Cleaned up inactive monitor for instance: {}", id);
        }
        Ok(())
    }

    async fn sync_monitor_state(monitors: &Arc<RwLock<HashMap<String, MonitorState>>>, redis_pool: &Arc<RedisPool>) -> Result<()> {
        for (id, state) in monitors.read().await.iter() {
            let monitor_key = format!("{}:auto_think", id);
            let state_json = serde_json::to_string(state)?;
            let mut conn = redis_pool.get().await?;
            if let Err(e) = conn.set::<_, _, ()>(&monitor_key, &state_json).await {
                 warn!("Failed to sync state for instance {}: {}", id, e);
            }
        }
        Ok(())
    }
}
