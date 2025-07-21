use async_trait::async_trait;
use crate::error::Result;
use crate::models::{
    ThoughtRecord, ChainMetadata, Identity, ThoughtMetadata, 
    UiRecallFeedbackParams
};
use crate::identity_documents::IdentityDocument;

/// Core trait for thought storage and retrieval operations
#[async_trait]
#[cfg_attr(test, mockall::automock)]
pub trait ThoughtStorage: Send + Sync {
    /// Store a thought record
    async fn save_thought(&self, thought: &ThoughtRecord) -> Result<()>;
    
    /// Get a thought by ID
    async fn get_thought(&self, instance: &str, thought_id: &str) -> Result<Option<ThoughtRecord>>;
    
    /// Get thoughts by chain ID
    async fn get_chain_thoughts(&self, instance: &str, chain_id: &str) -> Result<Vec<ThoughtRecord>>;
    
    /// Get all thoughts for an instance
    async fn get_instance_thoughts(&self, instance: &str, limit: usize) -> Result<Vec<ThoughtRecord>>;
    
    /// Get thoughts from all instances
    async fn get_all_thoughts(&self, limit: usize) -> Result<Vec<ThoughtRecord>>;
}

/// Trait for thought search operations
#[async_trait]
#[cfg_attr(test, mockall::automock)]
pub trait ThoughtSearch: Send + Sync {
    /// Search thoughts by query
    async fn search_thoughts(
        &self,
        instance: &str,
        query: &str,
        limit: usize,
    ) -> Result<Vec<ThoughtRecord>>;
    
    /// Search thoughts using semantic similarity
    async fn search_thoughts_semantic(
        &self,
        instance: &str,
        query: &str,
        limit: usize,
        threshold: f32,
    ) -> Result<Vec<ThoughtRecord>>;
    
    /// Search thoughts across all instances by query
    async fn search_thoughts_global(
        &self,
        query: &str,
        limit: usize,
    ) -> Result<Vec<ThoughtRecord>>;
    
    /// Search thoughts across all instances using semantic similarity
    async fn search_thoughts_semantic_global(
        &self,
        query: &str,
        limit: usize,
        threshold: f32,
    ) -> Result<Vec<ThoughtRecord>>;
    
    /// Generate unique search ID for tracking
    async fn generate_search_id(&self) -> Result<String>;
}

/// Enhanced search operations with metadata filtering
#[async_trait]
#[cfg_attr(test, mockall::automock)]
pub trait EnhancedSearch: Send + Sync {
    /// Enhanced semantic search with tag filtering and metadata scoring
    async fn search_thoughts_semantic_enhanced(
        &self,
        instance: &str,
        query: &str,
        limit: usize,
        threshold: f32,
        tags_filter: Option<Vec<String>>,
        min_importance: Option<i32>,
        min_relevance: Option<i32>,
        category_filter: Option<String>,
    ) -> Result<Vec<ThoughtRecord>>;
    
    /// Enhanced global semantic search with metadata filtering
    async fn search_thoughts_semantic_global_enhanced(
        &self,
        query: &str,
        limit: usize,
        threshold: f32,
        tags_filter: Option<Vec<String>>,
        min_importance: Option<i32>,
        min_relevance: Option<i32>,
        category_filter: Option<String>,
    ) -> Result<Vec<ThoughtRecord>>;
    
    /// Get thought IDs by tag intersection
    async fn get_thoughts_by_tags(&self, instance: &str, tags: &[String]) -> Result<Vec<String>>;
}

/// Trait for chain metadata operations
#[async_trait]
#[cfg_attr(test, mockall::automock)]
pub trait ChainOperations: Send + Sync {
    /// Create or update chain metadata
    async fn save_chain_metadata(&self, metadata: &ChainMetadata) -> Result<()>;
    
    
    /// Check if chain exists
    async fn chain_exists(&self, chain_id: &str) -> Result<bool>;
}

/// Trait for feedback and boost score operations
#[async_trait]
#[cfg_attr(test, mockall::automock)]
pub trait FeedbackOperations: Send + Sync {
    /// Save thought metadata for feedback loop system
    async fn save_thought_metadata(&self, metadata: &ThoughtMetadata) -> Result<()>;
    
    /// Get thought metadata by thought ID
    async fn get_thought_metadata(&self, instance: &str, thought_id: &str) -> Result<Option<ThoughtMetadata>>;
    
    /// Record feedback for search result
    async fn record_feedback(&self, feedback: &UiRecallFeedbackParams, instance: &str) -> Result<()>;
    
    /// Set/increment boost score for a thought based on feedback
    async fn update_boost_score(&self, instance: &str, thought_id: &str, feedback_action: &str, relevance_rating: Option<i32>, dwell_time: Option<i32>) -> Result<f64>;
    
    
    /// Apply boost scores to search results for ranking
    async fn apply_boost_scores(&self, instance: &str, thoughts: &mut Vec<ThoughtRecord>) -> Result<()>;
}

/// Trait for identity management operations
#[async_trait]
#[cfg_attr(test, mockall::automock)]
pub trait IdentityOperations: Send + Sync {
    /// Get identity for instance
    async fn get_identity(&self, identity_key: &str) -> Result<Option<Identity>>;
    
}

/// Trait for document-based identity operations
#[async_trait]
#[cfg_attr(test, mockall::automock)]
pub trait IdentityDocumentOperations: Send + Sync {
    /// Get identity documents by field type
    async fn get_identity_documents_by_field(&self, instance_id: &str, field_type: &str) -> Result<Vec<IdentityDocument>>;
    
    /// Save an identity document
    async fn save_identity_document(&self, document: &IdentityDocument) -> Result<()>;
    
    /// Delete an identity document
    async fn delete_identity_document(&self, instance_id: &str, field_type: &str, document_id: &str) -> Result<()>;
    
    /// Get all identity documents for instance
    async fn get_all_identity_documents(&self, instance_id: &str) -> Result<Vec<IdentityDocument>>;
    
    /// Get identity document by ID
    async fn get_identity_document_by_id(&self, instance_id: &str, document_id: &str) -> Result<Option<IdentityDocument>>;
}

/// Trait for event streaming operations
#[async_trait]
#[cfg_attr(test, mockall::automock)]
pub trait EventOperations: Send + Sync {
    /// Log event to instance stream
    async fn log_event(&self, instance: &str, event_type: &str, fields: Vec<(&str, &str)>) -> Result<()>;
    
    /// Publish event to feedback stream for background processing
    async fn publish_feedback_event(&self, event: &serde_json::Value) -> Result<()>;
}


/// Combined repository trait that includes all operations
/// This can be used for backwards compatibility or when all operations are needed
#[async_trait]
pub trait Repository: 
    ThoughtStorage + 
    ThoughtSearch + 
    EnhancedSearch + 
    ChainOperations + 
    FeedbackOperations + 
    IdentityOperations + 
    IdentityDocumentOperations + 
    EventOperations + 
    Send + 
    Sync 
{}

// Automatically implement Repository for any type that implements all sub-traits
impl<T> Repository for T 
where 
    T: ThoughtStorage + 
       ThoughtSearch + 
       EnhancedSearch + 
       ChainOperations + 
       FeedbackOperations + 
       IdentityOperations + 
       IdentityDocumentOperations + 
       EventOperations + 
       Send + 
       Sync 
{}