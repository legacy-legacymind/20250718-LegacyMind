// Test mock implementation that doesn't require mockall
#[cfg(test)]
use async_trait::async_trait;
use std::sync::Mutex;
use std::collections::HashMap;
use crate::error::Result;
use crate::models::{ThoughtRecord, ChainMetadata, Identity, ThoughtMetadata, UiRecallFeedbackParams};
use crate::identity_documents::IdentityDocument;
use super::*;

#[cfg(test)]
pub struct MockRepository {
    thoughts: Mutex<HashMap<String, ThoughtRecord>>,
    chains: Mutex<HashMap<String, ChainMetadata>>,
    identities: Mutex<HashMap<String, Identity>>,
    identity_docs: Mutex<HashMap<String, IdentityDocument>>,
    thought_metadata: Mutex<HashMap<String, ThoughtMetadata>>,
}

#[cfg(test)]
impl MockRepository {
    pub fn new() -> Self {
        Self {
            thoughts: Mutex::new(HashMap::new()),
            chains: Mutex::new(HashMap::new()),
            identities: Mutex::new(HashMap::new()),
            identity_docs: Mutex::new(HashMap::new()),
            thought_metadata: Mutex::new(HashMap::new()),
        }
    }
}

#[cfg(test)]
#[async_trait]
impl ThoughtStorage for MockRepository {
    async fn save_thought(&self, thought: &ThoughtRecord) -> Result<()> {
        let key = format!("{}:{}", thought.instance, thought.id);
        self.thoughts.lock().unwrap().insert(key, thought.clone());
        Ok(())
    }
    
    async fn get_thought(&self, instance: &str, thought_id: &str) -> Result<Option<ThoughtRecord>> {
        let key = format!("{}:{}", instance, thought_id);
        Ok(self.thoughts.lock().unwrap().get(&key).cloned())
    }
    
    async fn get_chain_thoughts(&self, instance: &str, chain_id: &str) -> Result<Vec<ThoughtRecord>> {
        Ok(self.thoughts.lock().unwrap()
            .values()
            .filter(|t| t.instance == instance && t.chain_id.as_deref() == Some(chain_id))
            .cloned()
            .collect())
    }
    
    async fn get_instance_thoughts(&self, instance: &str, limit: usize) -> Result<Vec<ThoughtRecord>> {
        Ok(self.thoughts.lock().unwrap()
            .values()
            .filter(|t| t.instance == instance)
            .take(limit)
            .cloned()
            .collect())
    }
    
    async fn get_all_thoughts(&self, limit: usize) -> Result<Vec<ThoughtRecord>> {
        Ok(self.thoughts.lock().unwrap()
            .values()
            .take(limit)
            .cloned()
            .collect())
    }
}

#[cfg(test)]
#[async_trait]
impl ThoughtSearch for MockRepository {
    async fn search_thoughts(&self, instance: &str, query: &str, limit: usize) -> Result<Vec<ThoughtRecord>> {
        Ok(self.thoughts.lock().unwrap()
            .values()
            .filter(|t| t.instance == instance && t.thought.contains(query))
            .take(limit)
            .cloned()
            .collect())
    }
    
    async fn search_thoughts_semantic(&self, instance: &str, _query: &str, limit: usize, _threshold: f32) -> Result<Vec<ThoughtRecord>> {
        // Simple mock - just return all thoughts for instance
        self.get_instance_thoughts(instance, limit).await
    }
    
    async fn search_thoughts_global(&self, query: &str, limit: usize) -> Result<Vec<ThoughtRecord>> {
        Ok(self.thoughts.lock().unwrap()
            .values()
            .filter(|t| t.thought.contains(query))
            .take(limit)
            .cloned()
            .collect())
    }
    
    async fn search_thoughts_semantic_global(&self, _query: &str, limit: usize, _threshold: f32) -> Result<Vec<ThoughtRecord>> {
        self.get_all_thoughts(limit).await
    }
    
    async fn generate_search_id(&self) -> Result<String> {
        Ok("mock_search_id".to_string())
    }
}

#[cfg(test)]
#[async_trait]
impl EnhancedSearch for MockRepository {
    async fn search_thoughts_semantic_enhanced(
        &self,
        instance: &str,
        query: &str,
        limit: usize,
        threshold: f32,
        _tags_filter: Option<Vec<String>>,
        _min_importance: Option<i32>,
        _min_relevance: Option<i32>,
        _category_filter: Option<String>,
    ) -> Result<Vec<ThoughtRecord>> {
        self.search_thoughts_semantic(instance, query, limit, threshold).await
    }
    
    async fn search_thoughts_semantic_global_enhanced(
        &self,
        query: &str,
        limit: usize,
        threshold: f32,
        _tags_filter: Option<Vec<String>>,
        _min_importance: Option<i32>,
        _min_relevance: Option<i32>,
        _category_filter: Option<String>,
    ) -> Result<Vec<ThoughtRecord>> {
        self.search_thoughts_semantic_global(query, limit, threshold).await
    }
    
    async fn get_thoughts_by_tags(&self, _instance: &str, _tags: &[String]) -> Result<Vec<String>> {
        Ok(Vec::new())
    }
}

#[cfg(test)]
#[async_trait]
impl ChainOperations for MockRepository {
    async fn save_chain_metadata(&self, metadata: &ChainMetadata) -> Result<()> {
        self.chains.lock().unwrap().insert(metadata.chain_id.clone(), metadata.clone());
        Ok(())
    }
    
    async fn chain_exists(&self, chain_id: &str) -> Result<bool> {
        Ok(self.chains.lock().unwrap().contains_key(chain_id))
    }
}

#[cfg(test)]
#[async_trait]
impl FeedbackOperations for MockRepository {
    async fn save_thought_metadata(&self, metadata: &ThoughtMetadata) -> Result<()> {
        let key = format!("{}:{}", metadata.instance, metadata.thought_id);
        self.thought_metadata.lock().unwrap().insert(key, metadata.clone());
        Ok(())
    }
    
    async fn get_thought_metadata(&self, instance: &str, thought_id: &str) -> Result<Option<ThoughtMetadata>> {
        let key = format!("{}:{}", instance, thought_id);
        Ok(self.thought_metadata.lock().unwrap().get(&key).cloned())
    }
    
    async fn record_feedback(&self, _feedback: &UiRecallFeedbackParams, _instance: &str) -> Result<()> {
        Ok(())
    }
    
    async fn update_boost_score(&self, _instance: &str, _thought_id: &str, _feedback_action: &str, _relevance_rating: Option<i32>, _dwell_time: Option<i32>) -> Result<f64> {
        Ok(1.0)
    }
    
    async fn apply_boost_scores(&self, _instance: &str, _thoughts: &mut Vec<ThoughtRecord>) -> Result<()> {
        Ok(())
    }
}

#[cfg(test)]
#[async_trait]
impl IdentityOperations for MockRepository {
    async fn get_identity(&self, identity_key: &str) -> Result<Option<Identity>> {
        Ok(self.identities.lock().unwrap().get(identity_key).cloned())
    }
}

#[cfg(test)]
#[async_trait]
impl IdentityDocumentOperations for MockRepository {
    async fn get_identity_documents_by_field(&self, instance_id: &str, field_type: &str) -> Result<Vec<IdentityDocument>> {
        Ok(self.identity_docs.lock().unwrap()
            .values()
            .filter(|d| d.instance == instance_id && d.field_type == field_type)
            .cloned()
            .collect())
    }
    
    async fn save_identity_document(&self, document: &IdentityDocument) -> Result<()> {
        self.identity_docs.lock().unwrap().insert(document.id.clone(), document.clone());
        Ok(())
    }
    
    async fn delete_identity_document(&self, _instance_id: &str, _field_type: &str, document_id: &str) -> Result<()> {
        self.identity_docs.lock().unwrap().remove(document_id);
        Ok(())
    }
    
    async fn get_all_identity_documents(&self, instance_id: &str) -> Result<Vec<IdentityDocument>> {
        Ok(self.identity_docs.lock().unwrap()
            .values()
            .filter(|d| d.instance == instance_id)
            .cloned()
            .collect())
    }
    
    async fn get_identity_document_by_id(&self, _instance_id: &str, document_id: &str) -> Result<Option<IdentityDocument>> {
        Ok(self.identity_docs.lock().unwrap().get(document_id).cloned())
    }
}

#[cfg(test)]
#[async_trait]
impl EventOperations for MockRepository {
    async fn log_event(&self, _instance: &str, _event_type: &str, _fields: Vec<(&str, &str)>) -> Result<()> {
        Ok(())
    }
    
    async fn publish_feedback_event(&self, _event: &serde_json::Value) -> Result<()> {
        Ok(())
    }
}

