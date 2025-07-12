use std::sync::Arc;
use serde_json::json;
use tracing;

use crate::error::{Result, UnifiedThinkError};
use crate::models::{
    UiThinkParams, UiRecallParams, UiIdentityParams, ThoughtRecord, ThinkResponse, 
    RecallResponse, ChainMetadata, IdentityResponse, IdentityOperation, Identity
};
use crate::repository::ThoughtRepository;
use crate::search_optimization::SearchCache;
use crate::validation::InputValidator;

/// Handler for MCP tool operations
pub struct ToolHandlers<R: ThoughtRepository> {
    repository: Arc<R>,
    instance_id: String,
    validator: Arc<InputValidator>,
    search_cache: Arc<std::sync::Mutex<SearchCache>>,
    search_available: Arc<std::sync::atomic::AtomicBool>,
}

impl<R: ThoughtRepository> ToolHandlers<R> {
    pub fn new(
        repository: Arc<R>,
        instance_id: String,
        validator: Arc<InputValidator>,
        search_cache: Arc<std::sync::Mutex<SearchCache>>,
        search_available: Arc<std::sync::atomic::AtomicBool>,
    ) -> Self {
        Self {
            repository,
            instance_id,
            validator,
            search_cache,
            search_available,
        }
    }
    
    /// Handle ui_think tool
    pub async fn ui_think(&self, params: UiThinkParams) -> Result<ThinkResponse> {
        // Validate input
        self.validator.validate_thought_content(&params.thought)?;
        self.validator.validate_thought_numbers(params.thought_number, params.total_thoughts)?;
        if let Some(chain_id) = &params.chain_id {
            self.validator.validate_chain_id(chain_id)?;
        }
        
        tracing::info!(
            "Processing thought {} of {} for instance '{}'", 
            params.thought_number, 
            params.total_thoughts,
            self.instance_id
        );
        
        // Create thought record
        let thought = ThoughtRecord::new(
            self.instance_id.clone(),
            params.thought,
            params.thought_number,
            params.total_thoughts,
            params.chain_id.clone(),
        );
        
        let thought_id = thought.id.clone();
        
        // Save thought
        self.repository.save_thought(&thought).await?;
        
        // Handle chain metadata
        if let Some(chain_id) = params.chain_id {
            if !self.repository.chain_exists(&chain_id).await? {
                let metadata = ChainMetadata {
                    chain_id: chain_id.clone(),
                    created_at: chrono::Utc::now().to_rfc3339(),
                    thought_count: params.total_thoughts,
                    instance: self.instance_id.clone(),
                };
                self.repository.save_chain_metadata(&metadata).await?;
            }
        }
        
        Ok(ThinkResponse {
            status: "stored".to_string(),
            thought_id,
            next_thought_needed: params.next_thought_needed,
        })
    }
    
    /// Handle ui_recall tool
    pub async fn ui_recall(&self, params: UiRecallParams) -> Result<RecallResponse> {
        let action = params.action.as_deref().unwrap_or("search");
        let limit = params.limit.unwrap_or(50);
        
        tracing::info!(
            "Recall action '{}' for instance '{}' with query: {:?}, chain: {:?}",
            action, self.instance_id, params.query, params.chain_id
        );
        
        // Get thoughts based on query or chain_id
        let thoughts = if let Some(chain_id) = &params.chain_id {
            self.repository.get_chain_thoughts(&self.instance_id, chain_id).await?
        } else if let Some(query) = &params.query {
            if params.semantic_search.unwrap_or(false) {
                // Use semantic search
                self.repository.search_thoughts_semantic(&self.instance_id, query, limit).await?
            } else {
                // Use regular text search
                self.repository.search_thoughts(&self.instance_id, query, limit).await?
            }
        } else {
            self.repository.get_instance_thoughts(&self.instance_id, limit).await?
        };
        
        let total_found = thoughts.len();
        
        // Process action
        let (action_result, final_thoughts) = match action {
            "analyze" => {
                let analysis = self.analyze_thoughts(&thoughts).await?;
                (Some(analysis), thoughts)
            },
            "merge" => {
                if let Some(target_chain) = params.action_params.as_ref()
                    .and_then(|p| p.get("target_chain_id"))
                    .and_then(|v| v.as_str()) {
                    let result = self.merge_chains(&params.chain_id.unwrap_or_default(), target_chain).await?;
                    (Some(result), thoughts)
                } else {
                    return Err(UnifiedThinkError::Validation {
                        field: "action_params.target_chain_id".to_string(),
                        reason: "Required for merge action".to_string(),
                    });
                }
            },
            "branch" => {
                if let Some(thought_id) = params.action_params.as_ref()
                    .and_then(|p| p.get("thought_id"))
                    .and_then(|v| v.as_str()) {
                    let result = self.branch_from_thought(thought_id).await?;
                    (Some(result), thoughts)
                } else {
                    return Err(UnifiedThinkError::Validation {
                        field: "action_params.thought_id".to_string(),
                        reason: "Required for branch action".to_string(),
                    });
                }
            },
            "continue" => {
                if let Some(chain_id) = &params.chain_id {
                    let result = self.continue_chain(chain_id).await?;
                    (Some(result), thoughts)
                } else {
                    return Err(UnifiedThinkError::Validation {
                        field: "chain_id".to_string(),
                        reason: "Required for continue action".to_string(),
                    });
                }
            },
            _ => (None, thoughts), // Default search action
        };
        
        Ok(RecallResponse {
            thoughts: final_thoughts,
            total_found,
            search_method: if params.semantic_search.unwrap_or(false) {
                "semantic_vector_search".to_string()
            } else if self.search_available.load(std::sync::atomic::Ordering::SeqCst) {
                "redis_search".to_string()
            } else {
                "fallback_scan".to_string()
            },
            search_available: self.search_available.load(std::sync::atomic::Ordering::SeqCst),
            action: Some(action.to_string()),
            action_result,
        })
    }
    
    // Action implementations
    
    async fn analyze_thoughts(&self, thoughts: &[ThoughtRecord]) -> Result<serde_json::Value> {
        if thoughts.is_empty() {
            return Ok(json!({
                "error": "No thoughts to analyze"
            }));
        }
        
        let total_thoughts = thoughts.len();
        let instances: std::collections::HashSet<_> = thoughts.iter()
            .map(|t| t.instance.as_str())
            .collect();
        let chains: std::collections::HashSet<_> = thoughts.iter()
            .filter_map(|t| t.chain_id.as_deref())
            .collect();
        
        // Identify patterns
        let mut word_freq = std::collections::HashMap::new();
        for thought in thoughts {
            for word in thought.thought.split_whitespace() {
                *word_freq.entry(word.to_lowercase()).or_insert(0) += 1;
            }
        }
        
        let mut patterns: Vec<_> = word_freq.into_iter()
            .filter(|(_, count)| *count > 1)
            .collect();
        patterns.sort_by(|a, b| b.1.cmp(&a.1));
        
        let top_patterns: Vec<_> = patterns.into_iter()
            .take(10)
            .map(|(word, count)| json!({
                "word": word,
                "count": count
            }))
            .collect();
        
        Ok(json!({
            "total_thoughts": total_thoughts,
            "unique_instances": instances.len(),
            "unique_chains": chains.len(),
            "date_range": {
                "earliest": thoughts.first().map(|t| &t.timestamp),
                "latest": thoughts.last().map(|t| &t.timestamp)
            },
            "patterns": top_patterns,
            "thought_progression": thoughts.iter()
                .filter(|t| t.chain_id.is_some())
                .take(5)
                .map(|t| json!({
                    "number": t.thought_number,
                    "preview": t.thought.chars().take(100).collect::<String>()
                }))
                .collect::<Vec<_>>()
        }))
    }
    
    async fn merge_chains(&self, source_chain: &str, target_chain: &str) -> Result<serde_json::Value> {
        // Get thoughts from both chains
        let source_thoughts = self.repository.get_chain_thoughts(&self.instance_id, source_chain).await?;
        let target_thoughts = self.repository.get_chain_thoughts(&self.instance_id, target_chain).await?;
        
        if source_thoughts.is_empty() || target_thoughts.is_empty() {
            return Ok(json!({
                "error": "One or both chains have no thoughts"
            }));
        }
        
        let new_chain_id = uuid::Uuid::new_v4().to_string();
        let total_thoughts = source_thoughts.len() + target_thoughts.len();
        
        // Create new chain with merged thoughts
        let mut thought_number = 1;
        for thought in source_thoughts.iter().chain(target_thoughts.iter()) {
            let mut merged_thought = thought.clone();
            merged_thought.id = uuid::Uuid::new_v4().to_string();
            merged_thought.chain_id = Some(new_chain_id.clone());
            merged_thought.thought_number = thought_number;
            merged_thought.total_thoughts = total_thoughts as i32;
            
            self.repository.save_thought(&merged_thought).await?;
            thought_number += 1;
        }
        
        // Create metadata for new chain
        let metadata = ChainMetadata {
            chain_id: new_chain_id.clone(),
            created_at: chrono::Utc::now().to_rfc3339(),
            thought_count: total_thoughts as i32,
            instance: self.instance_id.clone(),
        };
        self.repository.save_chain_metadata(&metadata).await?;
        
        Ok(json!({
            "new_chain_id": new_chain_id,
            "total_thoughts": total_thoughts,
            "source_count": source_thoughts.len(),
            "target_count": target_thoughts.len()
        }))
    }
    
    async fn branch_from_thought(&self, thought_id: &str) -> Result<serde_json::Value> {
        let thought = self.repository.get_thought(&self.instance_id, thought_id).await?
            .ok_or_else(|| UnifiedThinkError::NotFound(format!("Thought {} not found", thought_id)))?;
        
        let new_chain_id = uuid::Uuid::new_v4().to_string();
        
        // Create new thought as first in new chain
        let branch_thought = ThoughtRecord::new(
            self.instance_id.clone(),
            format!("Branching from: {}", thought.thought),
            1,
            1,
            Some(new_chain_id.clone()),
        );
        
        self.repository.save_thought(&branch_thought).await?;
        
        // Create metadata for new chain
        let metadata = ChainMetadata {
            chain_id: new_chain_id.clone(),
            created_at: chrono::Utc::now().to_rfc3339(),
            thought_count: 1,
            instance: self.instance_id.clone(),
        };
        self.repository.save_chain_metadata(&metadata).await?;
        
        Ok(json!({
            "new_chain_id": new_chain_id,
            "branched_from": thought_id,
            "new_thought_id": branch_thought.id
        }))
    }
    
    async fn continue_chain(&self, chain_id: &str) -> Result<serde_json::Value> {
        let thoughts = self.repository.get_chain_thoughts(&self.instance_id, chain_id).await?;
        
        if thoughts.is_empty() {
            return Ok(json!({
                "error": "Chain has no thoughts"
            }));
        }
        
        let last_thought = thoughts.iter()
            .max_by_key(|t| t.thought_number)
            .unwrap();
        
        Ok(json!({
            "chain_id": chain_id,
            "last_thought_number": last_thought.thought_number,
            "total_thoughts": last_thought.total_thoughts,
            "ready_for_next": true,
            "next_thought_number": last_thought.thought_number + 1
        }))
    }
    
    /// Handle ui_identity tool
    pub async fn ui_identity(&self, params: UiIdentityParams) -> Result<IdentityResponse> {
        let operation = params.operation.unwrap_or(IdentityOperation::View);
        
        tracing::info!(
            "Identity operation '{:?}' for instance '{}' - category: {:?}, field: {:?}",
            operation, self.instance_id, params.category, params.field
        );
        
        match operation {
            IdentityOperation::View => {
                let identity = self.get_or_create_identity().await?;
                Ok(IdentityResponse::View {
                    identity,
                    available_categories: vec![
                        "core_info", "communication", "relationships", 
                        "work_preferences", "behavioral_patterns", 
                        "technical_profile", "context_awareness", "memory_preferences"
                    ],
                })
            }
            
            IdentityOperation::Add => {
                let category = params.category.ok_or_else(|| UnifiedThinkError::Validation {
                    field: "category".to_string(),
                    reason: "category required for add operation".to_string(),
                })?;
                let field = params.field.ok_or_else(|| UnifiedThinkError::Validation {
                    field: "field".to_string(),
                    reason: "field required for add operation".to_string(),
                })?;
                let value = params.value.ok_or_else(|| UnifiedThinkError::Validation {
                    field: "value".to_string(),
                    reason: "value required for add operation".to_string(),
                })?;
                
                self.add_to_identity_field(&category, &field, value).await?;
                Ok(IdentityResponse::Updated { 
                    operation: "add".to_string(),
                    category, 
                    field: Some(field),
                    success: true,
                })
            }
            
            IdentityOperation::Modify => {
                let category = params.category.ok_or_else(|| UnifiedThinkError::Validation {
                    field: "category".to_string(),
                    reason: "category required for modify operation".to_string(),
                })?;
                let field = params.field.ok_or_else(|| UnifiedThinkError::Validation {
                    field: "field".to_string(),
                    reason: "field required for modify operation".to_string(),
                })?;
                let value = params.value.ok_or_else(|| UnifiedThinkError::Validation {
                    field: "value".to_string(),
                    reason: "value required for modify operation".to_string(),
                })?;
                
                self.modify_identity_field(&category, &field, value).await?;
                Ok(IdentityResponse::Updated { 
                    operation: "modify".to_string(),
                    category,
                    field: Some(field),
                    success: true,
                })
            }
            
            IdentityOperation::Delete => {
                let category = params.category.ok_or_else(|| UnifiedThinkError::Validation {
                    field: "category".to_string(),
                    reason: "category required for delete operation".to_string(),
                })?;
                let field = params.field.ok_or_else(|| UnifiedThinkError::Validation {
                    field: "field".to_string(),
                    reason: "field required for delete operation".to_string(),
                })?;
                
                self.delete_from_identity_field(&category, &field, params.value).await?;
                Ok(IdentityResponse::Updated { 
                    operation: "delete".to_string(),
                    category,
                    field: Some(field),
                    success: true,
                })
            }
        }
    }
    
    // Helper methods for identity operations
    
    async fn get_or_create_identity(&self) -> Result<Identity> {
        let identity_key = format!("{}/identity", self.instance_id);
        
        // Try to get existing identity using Redis JSON.GET
        if let Some(identity) = self.repository.get_identity(&identity_key).await? {
            Ok(identity)
        } else {
            // Create default identity for this instance
            let identity = Identity::default_for_instance(&self.instance_id);
            self.repository.save_identity(&identity_key, &identity).await?;
            Ok(identity)
        }
    }
    
    async fn add_to_identity_field(&self, category: &str, field: &str, value: serde_json::Value) -> Result<()> {
        let identity_key = format!("{}/identity", self.instance_id);
        
        // Add to array fields using Redis JSON operations
        match field {
            // Array fields that support appending
            "common_mistakes" | "strengths" | "triggers" | "improvement_areas" 
            | "preferred_languages" | "frameworks" | "tools" | "expertise_areas" 
            | "learning_interests" | "active_goals" | "core_values" 
            | "boundaries" | "shared_history" | "priority_topics" => {
                let path = format!("$.{}.{}", category, field);
                self.repository.json_array_append(&identity_key, &path, &value).await?;
            }
            
            // Object fields (like relationships map) or scalar fields
            _ => {
                let path = format!("$.{}.{}", category, field);
                self.repository.json_set(&identity_key, &path, &value).await?;
            }
        }
        
        // Update metadata
        self.update_identity_metadata(&identity_key).await?;
        
        // Log the change
        self.repository.log_event(
            &self.instance_id,
            "identity_updated",
            vec![
                ("operation", "add"),
                ("category", category),
                ("field", field),
            ]
        ).await?;
        
        Ok(())
    }
    
    async fn modify_identity_field(&self, category: &str, field: &str, value: serde_json::Value) -> Result<()> {
        let identity_key = format!("{}/identity", self.instance_id);
        let path = format!("$.{}.{}", category, field);
        
        // Use Redis JSON.SET for direct field modification
        self.repository.json_set(&identity_key, &path, &value).await?;
        
        // Update metadata and log
        self.update_identity_metadata(&identity_key).await?;
        self.repository.log_event(
            &self.instance_id,
            "identity_updated",
            vec![
                ("operation", "modify"),
                ("category", category),
                ("field", field),
            ]
        ).await?;
        
        Ok(())
    }
    
    async fn delete_from_identity_field(&self, category: &str, field: &str, value: Option<serde_json::Value>) -> Result<()> {
        let identity_key = format!("{}/identity", self.instance_id);
        
        if let Some(target_value) = value {
            // Remove specific value from array - requires getting array, filtering, setting back
            let path = format!("$.{}.{}", category, field);
            if let Some(current_array) = self.repository.json_get_array(&identity_key, &path).await? {
                let filtered: Vec<serde_json::Value> = current_array
                    .into_iter()
                    .filter(|v| v != &target_value)
                    .collect();
                self.repository.json_set(&identity_key, &path, &serde_json::Value::Array(filtered)).await?;
            }
        } else {
            // Delete entire field using JSON.DEL
            let path = format!("$.{}.{}", category, field);
            self.repository.json_delete(&identity_key, &path).await?;
        }
        
        // Update metadata and log
        self.update_identity_metadata(&identity_key).await?;
        self.repository.log_event(
            &self.instance_id,
            "identity_updated",
            vec![
                ("operation", "delete"),
                ("category", category),
                ("field", field),
            ]
        ).await?;
        
        Ok(())
    }
    
    async fn update_identity_metadata(&self, identity_key: &str) -> Result<()> {
        let now = chrono::Utc::now();
        
        // Update metadata fields using JSON.SET
        self.repository.json_set(
            identity_key, 
            "$.metadata.last_updated", 
            &serde_json::Value::String(now.to_rfc3339())
        ).await?;
        
        // Increment update count using JSON.NUMINCRBY
        self.repository.json_increment(identity_key, "$.metadata.update_count", 1).await?;
        
        Ok(())
    }
}