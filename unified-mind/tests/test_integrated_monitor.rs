#[cfg(test)]
mod tests {
    use unified_mind::monitor::{CognitiveMonitor, ConversationMessage};
    use unified_mind::patterns::PatternEngine;
    use unified_mind::retrieval::RetrievalLearner;
    use unified_mind::dialogue::DialogueManager;
    use redis::aio::ConnectionManager;
    use redis::Client;
    use std::sync::Arc;
    use tokio::sync::RwLock;
    use chrono::Utc;
    use serde_json::json;

    async fn setup_monitor() -> CognitiveMonitor {
        let redis_client = Client::open("redis://127.0.0.1/").unwrap();
        let conn_manager = ConnectionManager::new(redis_client).await.unwrap();
        let redis_conn = Arc::new(RwLock::new(conn_manager));
        
        let pattern_engine = Arc::new(PatternEngine::new(redis_conn.clone()).await.unwrap());
        let retrieval_learner = Arc::new(RetrievalLearner::new(redis_conn.clone()).await.unwrap());
        let dialogue_manager = Arc::new(DialogueManager::new(redis_conn.clone()).await.unwrap());
        
        CognitiveMonitor::new(
            redis_conn,
            pattern_engine,
            retrieval_learner,
            dialogue_manager,
        ).await.unwrap()
    }

    #[tokio::test]
    async fn test_integrated_monitoring() {
        let monitor = setup_monitor().await;
        
        // Start monitoring
        monitor.start_monitoring().await.unwrap();
        
        // Simulate conversation messages
        let messages = vec![
            ConversationMessage {
                message_id: "1".to_string(),
                instance: "CCI".to_string(),
                session_id: "test-session".to_string(),
                timestamp: Utc::now(),
                role: "user".to_string(),
                content: "I need help understanding how Redis pub/sub works with async Rust".to_string(),
                metadata: json!({}),
            },
            ConversationMessage {
                message_id: "2".to_string(),
                instance: "CCI".to_string(),
                session_id: "test-session".to_string(),
                timestamp: Utc::now(),
                role: "assistant".to_string(),
                content: "Redis pub/sub with async Rust involves using the redis-rs library with Tokio...".to_string(),
                metadata: json!({}),
            },
            ConversationMessage {
                message_id: "3".to_string(),
                instance: "CCI".to_string(),
                session_id: "test-session".to_string(),
                timestamp: Utc::now(),
                role: "user".to_string(),
                content: "I'm getting confused about connection management. How do I handle multiple subscribers?".to_string(),
                metadata: json!({}),
            },
        ];
        
        // Process messages through monitor
        for message in messages {
            monitor.process_conversation_message(message).await.unwrap();
        }
        
        // Allow time for processing
        tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;
        
        // Check monitoring status
        let status = monitor.get_monitoring_status().await.unwrap();
        
        // Verify conversation tracking
        assert!(status.contains_key("conversation_tracking"));
        let conv_tracking = status.get("conversation_tracking").unwrap();
        assert!(conv_tracking.get("total_messages").is_some());
        
        // Verify flow analysis
        assert!(status.contains_key("flow_analysis"));
        let flow_analysis = status.get("flow_analysis").unwrap();
        assert!(flow_analysis.get("current_state").is_some());
        
        // Verify entity detection
        assert!(status.contains_key("entity_detection"));
        
        // Check for interventions
        let interventions = monitor.get_intervention_queue().await.unwrap();
        println!("Generated {} interventions", interventions.len());
        
        // Get monitoring insights
        let insights = monitor.get_monitoring_insights().await.unwrap();
        assert!(insights.contains_key("monitoring_insights"));
        
        println!("Monitoring insights: {:#?}", insights);
    }

    #[tokio::test]
    async fn test_conversation_stream_monitoring() {
        let monitor = setup_monitor().await;
        let redis_conn = monitor.redis_conn.clone();
        
        // Start monitoring
        monitor.start_monitoring().await.unwrap();
        
        // Simulate conversation stream
        let stream_key = "conversation:CCI:test-session-2";
        let message = ConversationMessage {
            message_id: "stream-1".to_string(),
            instance: "CCI".to_string(),
            session_id: "test-session-2".to_string(),
            timestamp: Utc::now(),
            role: "user".to_string(),
            content: "What is the UnifiedMind architecture pattern for handling complex queries?".to_string(),
            metadata: json!({"tags": ["architecture", "patterns"]}),
        };
        
        // Add to stream
        let mut conn = redis_conn.write().await;
        let message_json = serde_json::to_string(&message).unwrap();
        conn.xadd(
            stream_key,
            "*",
            &[("message", message_json)]
        ).await.unwrap();
        
        // Allow time for processing
        tokio::time::sleep(tokio::time::Duration::from_secs(1)).await;
        
        // Check if message was processed
        let status = monitor.get_monitoring_status().await.unwrap();
        println!("Status after stream message: {:#?}", status);
        
        // Verify interventions were generated
        let interventions = monitor.get_intervention_queue().await.unwrap();
        assert!(!interventions.is_empty(), "Expected interventions for architecture query");
        
        // Check intervention types
        for intervention in &interventions {
            println!("Intervention: {:?} - {}", intervention.intervention_type, intervention.reason);
        }
    }

    #[tokio::test]
    async fn test_entity_enrichment_flow() {
        let monitor = setup_monitor().await;
        
        // Message with multiple entities
        let message = ConversationMessage {
            message_id: "entity-1".to_string(),
            instance: "CCI".to_string(),
            session_id: "entity-session".to_string(),
            timestamp: Utc::now(),
            role: "user".to_string(),
            content: "How does PatternEngine integrate with RetrievalLearner in the unified-mind codebase?".to_string(),
            metadata: json!({}),
        };
        
        // Process message
        monitor.process_conversation_message(message).await.unwrap();
        
        // Check for entity-based interventions
        let interventions = monitor.get_intervention_queue().await.unwrap();
        let entity_interventions: Vec<_> = interventions.iter()
            .filter(|i| i.context.contains_key("entity"))
            .collect();
        
        assert!(!entity_interventions.is_empty(), "Expected entity enrichment interventions");
        
        // Verify entities were detected
        for intervention in entity_interventions {
            println!("Entity intervention: {} for {}", 
                     intervention.suggested_action, 
                     intervention.context.get("entity").unwrap());
        }
    }
}