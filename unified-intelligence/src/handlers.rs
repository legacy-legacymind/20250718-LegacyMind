use std::sync::Arc;
use serde_json::json;
use tracing;

use crate::error::{Result, UnifiedIntelligenceError};
use crate::models::{
    UiThinkParams, UiRecallParams, UiIdentityParams, UiDebugEnvParams, ThoughtRecord, ThinkResponse, 
    RecallResponse, ChainMetadata, IdentityResponse, IdentityOperation, Identity, DebugEnvResponse,
    OperationHelp, CategoryHelp, FieldTypeHelp, ExampleUsage, ThoughtMetadata, UiRecallFeedbackParams,
    FeedbackResponse
};
use crate::repository::ThoughtRepository;
use crate::search_optimization::SearchCache;
use crate::validation::InputValidator;
use crate::visual::VisualOutput;
use crate::frameworks::{ThinkingFramework, FrameworkProcessor, FrameworkVisual, FrameworkError};

/// Handler for MCP tool operations
pub struct ToolHandlers<R: ThoughtRepository> {
    repository: Arc<R>,
    instance_id: String,
    validator: Arc<InputValidator>,
    search_cache: Arc<std::sync::Mutex<SearchCache>>,
    search_available: Arc<std::sync::atomic::AtomicBool>,
    visual: VisualOutput,
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
            visual: VisualOutput::new(),
        }
    }
    
    /// Handle ui_think tool
    pub async fn ui_think(&self, params: UiThinkParams) -> Result<ThinkResponse> {
        // Determine framework with validation
        let framework = if let Some(ref framework_str) = params.framework {
            match ThinkingFramework::from_string(framework_str) {
                Ok(f) => f,
                Err(e) => {
                    self.visual.error(&format!("Framework error: {}", e));
                    return Err(UnifiedIntelligenceError::Validation {
                        field: "framework".to_string(),
                        reason: e.to_string(),
                    });
                }
            }
        } else {
            ThinkingFramework::Sequential
        };

        // Display visual start with framework
        self.visual.thought_start(params.thought_number, params.total_thoughts);
        FrameworkVisual::display_framework_start(&framework);
        self.visual.thought_content(&params.thought);
        
        // Process through framework
        if framework != ThinkingFramework::Sequential {
            let processor = FrameworkProcessor::new(framework.clone());
            let result = processor.process_thought(&params.thought, params.thought_number);
            
            FrameworkVisual::display_insights(&result.insights);
            FrameworkVisual::display_prompts(&result.prompts);
        }
        
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
            params.next_thought_needed,
        );
        
        let thought_id = thought.id.clone();
        
        // Handle chain metadata and visual display
        let _is_new_chain = if let Some(ref chain_id) = params.chain_id {
            let chain_exists = self.repository.chain_exists(chain_id).await?;
            if !chain_exists {
                let metadata = ChainMetadata {
                    chain_id: chain_id.clone(),
                    created_at: chrono::Utc::now().to_rfc3339(),
                    thought_count: params.total_thoughts,
                    instance: self.instance_id.clone(),
                };
                self.repository.save_chain_metadata(&metadata).await?;
            }
            self.visual.chain_info(chain_id, !chain_exists);
            !chain_exists
        } else {
            false
        };
        
        // Save thought
        self.repository.save_thought(&thought).await?;
        
        // Save metadata if any new fields are provided (Phase 1 feedback loop implementation)
        if params.importance.is_some() || params.relevance.is_some() || 
           params.tags.is_some() || params.category.is_some() {
            let metadata = ThoughtMetadata::new(
                thought_id.clone(),
                self.instance_id.clone(),
                params.importance,
                params.relevance,
                params.tags.clone(),
                params.category.clone(),
            );
            
            // Store metadata in Redis using pattern: {instance}:thought_meta:{id}
            self.repository.save_thought_metadata(&metadata).await?;
            
            // Publish metadata event to feedback stream for background processing
            self.repository.publish_feedback_event(&json!({
                "event_type": "thought_created",
                "thought_id": thought_id,
                "instance": self.instance_id,
                "metadata": {
                    "importance": params.importance,
                    "relevance": params.relevance,
                    "tags": params.tags,
                    "category": params.category,
                },
                "timestamp": metadata.created_at,
            })).await?;
            
            tracing::info!("Saved metadata for thought {} with importance: {:?}, relevance: {:?}, tags: {:?}, category: {:?}", 
                thought_id, params.importance, params.relevance, params.tags, params.category);
        }
        
        // Display success and completion status
        self.visual.thought_stored(&thought_id);
        
        if !params.next_thought_needed {
            self.visual.thinking_complete();
        } else {
            self.visual.next_thought_indicator(true);
        }
        
        // Progress bar
        self.visual.progress_bar(params.thought_number, params.total_thoughts);
        
        Ok(ThinkResponse {
            status: "stored".to_string(),
            thought_id,
            next_thought_needed: params.next_thought_needed,
        })
    }
    
    /// Handle ui_recall tool (Phase 2 Enhanced)
    pub async fn ui_recall(&self, params: UiRecallParams) -> Result<RecallResponse> {
        let action = params.action.as_deref().unwrap_or("search");
        let limit = params.limit.unwrap_or(50);
        
        // Generate search ID for tracking (Phase 2 feature)
        let search_id = self.repository.generate_search_id().await?;
        
        tracing::info!(
            "Recall action '{}' for instance '{}' with query: {:?}, chain: {:?}, search_id: {}",
            action, self.instance_id, params.query, params.chain_id, search_id
        );
        
        // Check if any Phase 2 metadata filters are applied
        let has_metadata_filters = params.tags_filter.is_some() || 
            params.min_importance.is_some() || 
            params.min_relevance.is_some() || 
            params.category_filter.is_some();
        
        // Get thoughts based on query or chain_id
        let thoughts = if let Some(chain_id) = &params.chain_id {
            self.repository.get_chain_thoughts(&self.instance_id, chain_id).await?
        } else if let Some(query) = &params.query {
            let search_all_instances = params.search_all_instances.unwrap_or(false);
            
            if params.semantic_search.unwrap_or(false) {
                // Use semantic search via repository with configurable threshold
                let threshold = params.threshold.unwrap_or(0.5); // Standardized threshold for improved embedding quality
                tracing::info!("Handler semantic search - threshold: {}, global: {}, enhanced: {}", 
                    threshold, search_all_instances, has_metadata_filters);
                
                // Use enhanced search methods if metadata filters are provided (Phase 2)
                if has_metadata_filters {
                    if search_all_instances {
                        self.repository.search_thoughts_semantic_global_enhanced(
                            query, 
                            limit, 
                            threshold,
                            params.tags_filter.clone(),
                            params.min_importance,
                            params.min_relevance,
                            params.category_filter.clone(),
                        ).await?
                    } else {
                        self.repository.search_thoughts_semantic_enhanced(
                            &self.instance_id,
                            query, 
                            limit, 
                            threshold,
                            params.tags_filter.clone(),
                            params.min_importance,
                            params.min_relevance,
                            params.category_filter.clone(),
                        ).await?
                    }
                } else {
                    // Use standard semantic search
                    let mut thoughts = if search_all_instances {
                        self.repository.search_thoughts_semantic_global(query, limit, threshold).await?
                    } else {
                        self.repository.search_thoughts_semantic(&self.instance_id, query, limit, threshold).await?
                    };
                    
                    // Apply boost scores to improve ranking (Phase 3)
                    if !search_all_instances {
                        self.repository.apply_boost_scores(&self.instance_id, &mut thoughts).await?;
                    }
                    
                    thoughts
                }
            } else {
                // Use regular text search (Phase 2 filters not supported for text search yet)
                tracing::info!("Handler text search - global: {}", search_all_instances);
                
                let mut thoughts = if search_all_instances {
                    self.repository.search_thoughts_global(query, limit).await?
                } else {
                    self.repository.search_thoughts(&self.instance_id, query, limit).await?
                };
                
                // Apply boost scores to text search results too (Phase 3)
                if !search_all_instances {
                    self.repository.apply_boost_scores(&self.instance_id, &mut thoughts).await?;
                }
                
                thoughts
            }
        } else {
            let search_all_instances = params.search_all_instances.unwrap_or(false);
            
            if search_all_instances {
                self.repository.get_all_thoughts(limit).await?
            } else {
                self.repository.get_instance_thoughts(&self.instance_id, limit).await?
            }
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
                    return Err(UnifiedIntelligenceError::Validation {
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
                    return Err(UnifiedIntelligenceError::Validation {
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
                    return Err(UnifiedIntelligenceError::Validation {
                        field: "chain_id".to_string(),
                        reason: "Required for continue action".to_string(),
                    });
                }
            },
            _ => (None, thoughts), // Default search action
        };
        
        // Publish search performed event for background analysis (Phase 2)
        if params.query.is_some() {
            let search_event = json!({
                "event_type": "search_performed",
                "search_id": search_id,
                "instance": self.instance_id,
                "query": params.query,
                "semantic_search": params.semantic_search.unwrap_or(false),
                "enhanced_filters": has_metadata_filters,
                "tags_filter": params.tags_filter,
                "min_importance": params.min_importance,
                "min_relevance": params.min_relevance,
                "category_filter": params.category_filter,
                "results_count": final_thoughts.len(),
                "total_found": total_found,
                "timestamp": chrono::Utc::now().to_rfc3339(),
            });
            
            if let Err(e) = self.repository.publish_feedback_event(&search_event).await {
                tracing::warn!("Failed to publish search event: {}", e);
            }
        }

        Ok(RecallResponse {
            thoughts: final_thoughts,
            total_found,
            search_method: if params.semantic_search.unwrap_or(false) {
                if has_metadata_filters {
                    "enhanced_semantic_search".to_string()
                } else {
                    "semantic_vector_search".to_string()
                }
            } else if self.search_available.load(std::sync::atomic::Ordering::SeqCst) {
                "redis_search".to_string()
            } else {
                "fallback_scan".to_string()
            },
            search_available: self.search_available.load(std::sync::atomic::Ordering::SeqCst),
            action: Some(action.to_string()),
            action_result,
            search_id, // Phase 2 enhancement
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
            .ok_or_else(|| UnifiedIntelligenceError::NotFound(format!("Thought {} not found", thought_id)))?;
        
        let new_chain_id = uuid::Uuid::new_v4().to_string();
        
        // Create new thought as first in new chain
        let branch_thought = ThoughtRecord::new(
            self.instance_id.clone(),
            format!("Branching from: {}", thought.thought),
            1,
            1,
            Some(new_chain_id.clone()),
            false, // Branch complete, no next thought needed
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
                let category = params.category.ok_or_else(|| UnifiedIntelligenceError::Validation {
                    field: "category".to_string(),
                    reason: "category required for add operation".to_string(),
                })?;
                let field = params.field.ok_or_else(|| UnifiedIntelligenceError::Validation {
                    field: "field".to_string(),
                    reason: "field required for add operation".to_string(),
                })?;
                let value = params.value.ok_or_else(|| UnifiedIntelligenceError::Validation {
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
                let category = params.category.ok_or_else(|| UnifiedIntelligenceError::Validation {
                    field: "category".to_string(),
                    reason: "category required for modify operation".to_string(),
                })?;
                let field = params.field.ok_or_else(|| UnifiedIntelligenceError::Validation {
                    field: "field".to_string(),
                    reason: "field required for modify operation".to_string(),
                })?;
                let value = params.value.ok_or_else(|| UnifiedIntelligenceError::Validation {
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
                let category = params.category.ok_or_else(|| UnifiedIntelligenceError::Validation {
                    field: "category".to_string(),
                    reason: "category required for delete operation".to_string(),
                })?;
                let field = params.field.ok_or_else(|| UnifiedIntelligenceError::Validation {
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
            
            IdentityOperation::Help => {
                Ok(self.generate_help_response())
            }
        }
    }
    
    // Helper methods for identity operations
    
    async fn get_or_create_identity(&self) -> Result<Identity> {
        let identity_key = format!("{}:identity", self.instance_id);
        
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
        // Validate category
        self.validate_category(category)?;
        
        let identity_key = format!("{}:identity", self.instance_id);
        
        // Process value to ensure correct type
        let processed_value = self.process_identity_value(category, field, value)?;
        
        // Add to array fields using Redis JSON operations
        match field {
            // Array fields that support appending
            "common_mistakes" | "strengths" | "triggers" | "improvement_areas" 
            | "preferred_languages" | "frameworks" | "tools" | "expertise_areas" 
            | "learning_interests" | "active_goals" | "core_values" 
            | "boundaries" | "shared_history" | "priority_topics" => {
                let path = format!("$.{}.{}", category, field);
                self.repository.json_array_append(&identity_key, &path, &processed_value).await?;
            }
            
            // Object fields (like relationships map) or scalar fields
            _ => {
                let path = format!("$.{}.{}", category, field);
                self.repository.json_set(&identity_key, &path, &processed_value).await?;
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
        // Validate category
        self.validate_category(category)?;
        
        let identity_key = format!("{}:identity", self.instance_id);
        let path = format!("$.{}.{}", category, field);
        
        // Convert string values to numbers for known numeric fields
        let processed_value = self.process_identity_value(category, field, value)?;
        
        // Use Redis JSON.SET for direct field modification
        self.repository.json_set(&identity_key, &path, &processed_value).await?;
        
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
        // Validate category
        self.validate_category(category)?;
        
        let identity_key = format!("{}:identity", self.instance_id);
        
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
    
    /// Validate category names against the known schema
    fn validate_category(&self, category: &str) -> Result<()> {
        const VALID_CATEGORIES: &[&str] = &[
            "core_info",
            "communication",
            "relationships", 
            "work_preferences",
            "behavioral_patterns",
            "technical_profile",
            "context_awareness",
            "memory_preferences",
        ];
        
        if !VALID_CATEGORIES.contains(&category) {
            return Err(UnifiedIntelligenceError::Validation {
                field: "category".to_string(),
                reason: format!("Invalid category '{}'. Valid categories are: {}", 
                    category, 
                    VALID_CATEGORIES.join(", ")
                )
            });
        }
        
        Ok(())
    }
    
    /// Process identity values to ensure correct types for known numeric and array fields
    fn process_identity_value(&self, category: &str, field: &str, value: serde_json::Value) -> Result<serde_json::Value> {
        // Define numeric fields that should be f32
        let numeric_fields = [
            ("communication", "humor_level"),
            ("communication", "directness"),
            ("work_preferences", "challenge_level"),
            ("work_preferences", "autonomy_level"),
            ("relationships", "trust_level"), // For any relationship.trust_level
        ];
        
        // Define array fields that should be Vec<String>
        let array_fields = [
            ("behavioral_patterns", "common_mistakes"),
            ("behavioral_patterns", "strengths"),
            ("behavioral_patterns", "triggers"),
            ("behavioral_patterns", "improvement_areas"),
            ("technical_profile", "preferred_languages"),
            ("technical_profile", "frameworks"),
            ("technical_profile", "tools"),
            ("technical_profile", "expertise_areas"),
            ("technical_profile", "learning_interests"),
            ("context_awareness", "active_goals"),
            ("memory_preferences", "priority_topics"),
            ("core_info", "core_values"),
        ];
        
        // Check if this is a numeric field
        let is_numeric_field = numeric_fields.iter().any(|(cat, fld)| {
            category == *cat && (field == *fld || field.ends_with(&format!(".{}", fld)))
        });
        
        // Check if this is an array field
        let is_array_field = array_fields.iter().any(|(cat, fld)| {
            category == *cat && field == *fld
        });
        
        if is_numeric_field {
            // Try to convert to number if it's a string
            match &value {
                serde_json::Value::String(s) => {
                    if let Ok(num) = s.parse::<f32>() {
                        return Ok(serde_json::Value::Number(
                            serde_json::Number::from_f64(num as f64)
                                .ok_or_else(|| UnifiedIntelligenceError::Validation {
                                    field: field.to_string(),
                                    reason: "Invalid numeric value".to_string()
                                })?
                        ));
                    }
                }
                serde_json::Value::Number(_) => return Ok(value), // Already a number
                _ => {}
            }
        }
        
        if is_array_field {
            // Try to convert string to array if it's a JSON string
            match &value {
                serde_json::Value::String(s) => {
                    // Check if it looks like a JSON array
                    if s.starts_with('[') && s.ends_with(']') {
                        // Try to parse as JSON array
                        if let Ok(parsed) = serde_json::from_str::<serde_json::Value>(s) {
                            if parsed.is_array() {
                                return Ok(parsed);
                            }
                        }
                    }
                    // If not a JSON array, split by comma (for comma-separated values)
                    else if s.contains(',') {
                        let items: Vec<String> = s.split(',')
                            .map(|item| item.trim().to_string())
                            .filter(|item| !item.is_empty())
                            .collect();
                        return Ok(serde_json::Value::Array(
                            items.into_iter().map(serde_json::Value::String).collect()
                        ));
                    }
                }
                serde_json::Value::Array(_) => return Ok(value), // Already an array
                _ => {}
            }
        }
        
        Ok(value)
    }
    
    /// Generate comprehensive help response for ui_identity
    fn generate_help_response(&self) -> IdentityResponse {
        let operations = vec![
            OperationHelp {
                name: "view".to_string(),
                description: "Display the current identity structure with all categories and fields".to_string(),
                required_params: vec![],
                optional_params: vec!["category".to_string(), "field".to_string()],
            },
            OperationHelp {
                name: "add".to_string(),
                description: "Add a value to an array field or set a new field value".to_string(),
                required_params: vec!["category".to_string(), "field".to_string(), "value".to_string()],
                optional_params: vec![],
            },
            OperationHelp {
                name: "modify".to_string(),
                description: "Update an existing field's value in the specified category".to_string(),
                required_params: vec!["category".to_string(), "field".to_string(), "value".to_string()],
                optional_params: vec![],
            },
            OperationHelp {
                name: "delete".to_string(),
                description: "Remove a specific value from an array field or delete the entire field".to_string(),
                required_params: vec!["category".to_string(), "field".to_string()],
                optional_params: vec!["value".to_string()],
            },
            OperationHelp {
                name: "help".to_string(),
                description: "Show this comprehensive help documentation".to_string(),
                required_params: vec![],
                optional_params: vec![],
            },
        ];

        let categories = vec![
            CategoryHelp {
                name: "core_info".to_string(),
                description: "Basic identity information like name, instance type, and core values".to_string(),
                common_fields: vec!["name".to_string(), "instance_id".to_string(), "primary_purpose".to_string(), "core_values".to_string()],
            },
            CategoryHelp {
                name: "communication".to_string(),
                description: "Communication style and preferences including tone, verbosity, and humor".to_string(),
                common_fields: vec!["tone".to_string(), "verbosity".to_string(), "humor_level".to_string(), "directness".to_string(), "formality".to_string()],
            },
            CategoryHelp {
                name: "relationships".to_string(),
                description: "Information about relationships with users, trust levels, and social connections".to_string(),
                common_fields: vec!["trust_level".to_string(), "shared_history".to_string(), "boundaries".to_string()],
            },
            CategoryHelp {
                name: "work_preferences".to_string(),
                description: "Preferences for work style, planning, pace, and collaboration approaches".to_string(),
                common_fields: vec!["planning_style".to_string(), "pace".to_string(), "autonomy_level".to_string(), "challenge_level".to_string()],
            },
            CategoryHelp {
                name: "behavioral_patterns".to_string(),
                description: "Common behaviors, strengths, weaknesses, and triggers".to_string(),
                common_fields: vec!["common_mistakes".to_string(), "strengths".to_string(), "triggers".to_string(), "improvement_areas".to_string()],
            },
            CategoryHelp {
                name: "technical_profile".to_string(),
                description: "Technical skills, preferred languages, frameworks, and expertise areas".to_string(),
                common_fields: vec!["preferred_languages".to_string(), "frameworks".to_string(), "tools".to_string(), "expertise_areas".to_string()],
            },
            CategoryHelp {
                name: "context_awareness".to_string(),
                description: "Current context including project, environment, role, and active goals".to_string(),
                common_fields: vec!["current_project".to_string(), "environment".to_string(), "instance_role".to_string(), "active_goals".to_string()],
            },
            CategoryHelp {
                name: "memory_preferences".to_string(),
                description: "Preferences for memory management, recall style, and priority topics".to_string(),
                common_fields: vec!["recall_style".to_string(), "priority_topics".to_string(), "context_depth".to_string()],
            },
        ];

        let field_types = vec![
            FieldTypeHelp {
                field_type: "text".to_string(),
                description: "String values for names, descriptions, and text content".to_string(),
                examples: vec!["Claude".to_string(), "sarcastic".to_string(), "structured".to_string()],
            },
            FieldTypeHelp {
                field_type: "numeric".to_string(),
                description: "Floating-point numbers typically ranging from 0.0 to 1.0 for levels/scores".to_string(),
                examples: vec!["0.8".to_string(), "0.5".to_string(), "0.9".to_string()],
            },
            FieldTypeHelp {
                field_type: "array".to_string(),
                description: "Lists of strings or objects for multiple values like skills, goals, or mistakes".to_string(),
                examples: vec!["[\"Rust\", \"TypeScript\"]".to_string(), "[\"planning\", \"execution\"]".to_string()],
            },
            FieldTypeHelp {
                field_type: "object".to_string(),
                description: "Complex nested structures for relationships or detailed configurations".to_string(),
                examples: vec!["{\"Sam\": {\"trust_level\": 0.9}}".to_string()],
            },
        ];

        let examples = vec![
            ExampleUsage {
                operation: "view".to_string(),
                description: "View complete identity structure".to_string(),
                example: json!({"operation": "view"}),
            },
            ExampleUsage {
                operation: "modify".to_string(),
                description: "Update humor level in communication preferences".to_string(),
                example: json!({
                    "operation": "modify",
                    "category": "communication", 
                    "field": "humor_level",
                    "value": 0.7
                }),
            },
            ExampleUsage {
                operation: "add".to_string(),
                description: "Add a new programming language to technical profile".to_string(),
                example: json!({
                    "operation": "add",
                    "category": "technical_profile",
                    "field": "preferred_languages", 
                    "value": "Python"
                }),
            },
            ExampleUsage {
                operation: "delete".to_string(),
                description: "Remove a specific goal from active goals".to_string(),
                example: json!({
                    "operation": "delete",
                    "category": "context_awareness",
                    "field": "active_goals",
                    "value": "old goal"
                }),
            },
            ExampleUsage {
                operation: "modify".to_string(),
                description: "Set trust level for a specific relationship".to_string(),
                example: json!({
                    "operation": "modify",
                    "category": "relationships",
                    "field": "Sam.trust_level",
                    "value": 0.9
                }),
            },
        ];

        IdentityResponse::Help {
            operations,
            categories,
            field_types,
            examples,
        }
    }
    
    /// Handle ui_debug_env tool - returns masked environment variables
    pub async fn ui_debug_env(&self, _params: UiDebugEnvParams) -> Result<DebugEnvResponse> {
        tracing::info!("Debug environment request for instance '{}'", self.instance_id);
        
        // Get environment variables
        let openai_api_key = std::env::var("OPENAI_API_KEY").unwrap_or_else(|_| "NOT_SET".to_string());
        let redis_password = std::env::var("REDIS_PASSWORD").unwrap_or_else(|_| "NOT_SET".to_string());
        let instance_id = std::env::var("INSTANCE_ID").ok();
        
        // Mask sensitive values
        let masked_openai_key = if openai_api_key != "NOT_SET" && openai_api_key.len() > 8 {
            format!("{}...{}", &openai_api_key[..4], &openai_api_key[openai_api_key.len()-4..])
        } else {
            openai_api_key
        };
        
        let masked_redis_password = if redis_password != "NOT_SET" && redis_password.len() > 6 {
            format!("{}...{}", &redis_password[..3], &redis_password[redis_password.len()-3..])
        } else {
            redis_password
        };
        
        Ok(DebugEnvResponse {
            openai_api_key: masked_openai_key,
            redis_password: masked_redis_password,
            instance_id,
        })
    }
    
    /// Handle ui_recall_feedback tool - record feedback on search results (Phase 2)
    pub async fn ui_recall_feedback(&self, params: UiRecallFeedbackParams) -> Result<FeedbackResponse> {
        tracing::info!(
            "Recording feedback for search '{}', thought '{}', action '{}' for instance '{}'",
            params.search_id, params.thought_id, params.action, self.instance_id
        );
        
        // Validate action parameter
        match params.action.as_str() {
            "viewed" | "used" | "irrelevant" | "helpful" => {},
            _ => {
                return Err(UnifiedIntelligenceError::Validation {
                    field: "action".to_string(),
                    reason: "Action must be one of: 'viewed', 'used', 'irrelevant', 'helpful'".to_string(),
                });
            }
        }
        
        // Validate dwell_time if provided
        if let Some(dwell_time) = params.dwell_time {
            if dwell_time < 0 {
                return Err(UnifiedIntelligenceError::Validation {
                    field: "dwell_time".to_string(),
                    reason: "Dwell time must be positive".to_string(),
                });
            }
        }
        
        // Validate relevance_rating if provided
        if let Some(rating) = params.relevance_rating {
            if rating < 1 || rating > 10 {
                return Err(UnifiedIntelligenceError::Validation {
                    field: "relevance_rating".to_string(),
                    reason: "Relevance rating must be between 1 and 10".to_string(),
                });
            }
        }
        
        // Record feedback via repository
        self.repository.record_feedback(&params, &self.instance_id).await?;
        
        let recorded_at = chrono::Utc::now().to_rfc3339();
        
        tracing::info!("Successfully recorded feedback for search {} thought {}", 
            params.search_id, params.thought_id);
        
        Ok(FeedbackResponse {
            status: "recorded".to_string(),
            search_id: params.search_id,
            thought_id: params.thought_id,
            recorded_at,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::repository::MockThoughtRepository;
    
    fn create_test_handler() -> ToolHandlers<MockThoughtRepository> {
        let repository = Arc::new(MockThoughtRepository::new());
        let validator = Arc::new(InputValidator::new());
        let search_cache = Arc::new(std::sync::Mutex::new(SearchCache::new(300))); // 5 minute TTL
        let search_available = Arc::new(std::sync::atomic::AtomicBool::new(true));
        
        ToolHandlers::new(
            repository,
            "test".to_string(),
            validator,
            search_cache,
            search_available,
        )
    }
    
    #[test]
    fn test_process_identity_value_numeric_fields() {
        let handler = create_test_handler();
        
        // Test numeric field conversion from string to f32
        let test_cases = vec![
            ("communication", "humor_level", "0.75"),
            ("communication", "directness", "0.9"),
            ("work_preferences", "challenge_level", "0.8"),
            ("work_preferences", "autonomy_level", "0.85"),
            ("relationships", "trust_level", "0.95"),
        ];
        
        for (category, field, value_str) in test_cases {
            let input = json!(value_str);
            let result = handler.process_identity_value(category, field, input).unwrap();
            
            // Verify it's a number
            assert!(result.is_f64() || result.is_u64() || result.is_i64(), 
                    "Result should be numeric for {}.{}", category, field);
            
            // Compare with epsilon for floating point
            let result_f64 = result.as_f64().unwrap();
            let expected_f64 = value_str.parse::<f64>().unwrap();
            assert!((result_f64 - expected_f64).abs() < 0.0001, 
                    "Value mismatch for {}.{}: {} vs {}", 
                    category, field, result_f64, expected_f64);
        }
    }
    
    #[test]
    fn test_process_identity_value_numeric_already_correct() {
        let handler = create_test_handler();
        
        // Test that already-correct numeric values are preserved
        let test_cases = vec![
            ("communication", "humor_level", json!(0.75)),
            ("communication", "directness", json!(0.9)),
            ("work_preferences", "challenge_level", json!(0.8)),
        ];
        
        for (category, field, value) in test_cases {
            let result = handler.process_identity_value(category, field, value.clone()).unwrap();
            assert_eq!(result, value, "Value should be unchanged for {}.{}", category, field);
        }
    }
    
    #[test]
    fn test_process_identity_value_array_fields() {
        let handler = create_test_handler();
        
        // Test array field conversion from JSON string to array
        let test_cases = vec![
            (
                "behavioral_patterns",
                "strengths",
                json!("[\"fast execution\", \"creative solutions\"]"),
                json!(["fast execution", "creative solutions"])
            ),
            (
                "technical_profile",
                "preferred_languages",
                json!("[\"Rust\", \"TypeScript\"]"),
                json!(["Rust", "TypeScript"])
            ),
            (
                "technical_profile",
                "expertise_areas",
                json!("[\"MCP development\", \"Redis\"]"),
                json!(["MCP development", "Redis"])
            ),
        ];
        
        for (category, field, input, expected) in test_cases {
            let result = handler.process_identity_value(category, field, input).unwrap();
            assert_eq!(result, expected, "Failed for {}.{}", category, field);
        }
    }
    
    #[test]
    fn test_process_identity_value_array_comma_separated() {
        let handler = create_test_handler();
        
        // Test comma-separated string conversion to array
        let result = handler.process_identity_value(
            "behavioral_patterns",
            "strengths",
            json!("fast execution, creative solutions, systematic debugging")
        ).unwrap();
        
        assert_eq!(
            result,
            json!(["fast execution", "creative solutions", "systematic debugging"])
        );
    }
    
    #[test]
    fn test_process_identity_value_array_already_correct() {
        let handler = create_test_handler();
        
        // Test that already-correct arrays are preserved
        let value = json!(["Rust", "TypeScript", "Python"]);
        let result = handler.process_identity_value(
            "technical_profile",
            "preferred_languages",
            value.clone()
        ).unwrap();
        
        assert_eq!(result, value);
    }
    
    #[test]
    fn test_process_identity_value_non_special_fields() {
        let handler = create_test_handler();
        
        // Test that non-special fields are passed through unchanged
        let test_cases = vec![
            ("core_info", "name", json!("Claude")),
            ("communication", "tone", json!("friendly")),
            ("work_preferences", "planning_style", json!("structured")),
            ("some_category", "some_field", json!("some value")),
        ];
        
        for (category, field, value) in test_cases {
            let result = handler.process_identity_value(category, field, value.clone()).unwrap();
            assert_eq!(result, value, "Value should be unchanged for {}.{}", category, field);
        }
    }
    
    #[test]
    fn test_process_identity_value_invalid_numeric_string() {
        let handler = create_test_handler();
        
        // Test that invalid numeric strings are passed through unchanged
        let result = handler.process_identity_value(
            "communication",
            "humor_level",
            json!("not a number")
        ).unwrap();
        
        assert_eq!(result, json!("not a number"));
    }
    
    #[test]
    fn test_process_identity_value_invalid_json_array_string() {
        let handler = create_test_handler();
        
        // Test that invalid JSON array strings are passed through unchanged
        let result = handler.process_identity_value(
            "behavioral_patterns",
            "strengths",
            json!("[invalid json")
        ).unwrap();
        
        assert_eq!(result, json!("[invalid json"));
    }
}