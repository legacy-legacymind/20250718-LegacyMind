use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use uuid::Uuid;

/// Represents a single identity document field, following the same pattern as thoughts
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IdentityDocument {
    /// Unique identifier for this document
    pub id: String,
    
    /// The field type (e.g., "basics", "work_style", "preferences", "relationships")
    pub field_type: String,
    
    /// The actual content of this identity field
    pub content: Value,
    
    /// The instance this identity belongs to (CC, CCI, CCD, etc.)
    pub instance: String,
    
    /// When this field was first created
    pub created_at: DateTime<Utc>,
    
    /// When this field was last updated
    pub updated_at: DateTime<Utc>,
    
    /// Version number for this field (increments on each update)
    pub version: u32,
    
    /// Optional embedding for semantic search on identity fields
    pub embedding: Option<Vec<f32>>,
    
    /// Metadata for tracking and search
    pub metadata: IdentityMetadata,
}

/// Metadata for identity documents
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IdentityMetadata {
    /// Tags for categorization
    pub tags: Vec<String>,
    
    /// Importance score (1-10)
    pub importance: Option<i32>,
    
    /// Whether this field contains sensitive information
    pub is_sensitive: bool,
    
    /// Last accessed timestamp
    pub last_accessed: Option<DateTime<Utc>>,
    
    /// Access count
    pub access_count: u32,
}

/// Identity field types enum for type safety
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum IdentityFieldType {
    Basics,
    WorkStyle,
    Communication,
    KnowledgeDomains,
    Preferences,
    Relationships,
    Context,
    Metadata,
    Custom(String),
}


/// Index structure for tracking all identity documents
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IdentityIndex {
    /// Map of field type to document IDs
    pub fields: HashMap<String, Vec<String>>,
    
    /// Total document count
    pub document_count: u32,
    
    /// Last updated timestamp
    pub last_updated: DateTime<Utc>,
    
    /// Instance this index belongs to
    pub instance: String,
}


impl IdentityDocument {
    /// Create a new identity document
    pub fn new(
        field_type: String,
        content: Value,
        instance: String,
    ) -> Self {
        let now = Utc::now();
        Self {
            id: Uuid::new_v4().to_string(),
            field_type,
            content,
            instance,
            created_at: now,
            updated_at: now,
            version: 1,
            embedding: None,
            metadata: IdentityMetadata {
                tags: Vec::new(),
                importance: None,
                is_sensitive: false,
                last_accessed: None,
                access_count: 0,
            },
        }
    }
    
    
    /// Mark as accessed
    pub fn mark_accessed(&mut self) {
        self.metadata.last_accessed = Some(Utc::now());
        self.metadata.access_count += 1;
    }
    
    /// Get Redis key for this document
    pub fn redis_key(&self) -> String {
        format!("{}:identity:{}:{}", self.instance, self.field_type, self.id)
    }
}

/// Conversion utilities for migrating between formats
pub mod conversion {
    use super::*;
    
    
    /// Convert monolithic identity JSON to document-based format
    pub fn monolithic_to_documents(
        monolithic: Value,
        instance: String,
    ) -> Result<Vec<IdentityDocument>, Box<dyn std::error::Error + Send + Sync>> {
        let obj = monolithic.as_object()
            .ok_or_else(|| "Identity must be an object".to_string())?;
        
        let mut documents = Vec::new();
        
        for (field_name, field_value) in obj {
            // Skip internal fields
            if field_name.starts_with('_') {
                continue;
            }
            
            // Handle relationships specially
            if field_name == "relationships" {
                if let Some(relationships) = field_value.as_object() {
                    for (person, relationship_data) in relationships {
                        let mut doc = IdentityDocument::new(
                            format!("relationships:{}", person),
                            relationship_data.clone(),
                            instance.to_string(),
                        );
                        doc.metadata.tags.push("relationship".to_string());
                        doc.metadata.tags.push(person.to_string());
                        documents.push(doc);
                    }
                }
            } else {
                let mut doc = IdentityDocument::new(
                    field_name.to_string(),
                    field_value.clone(),
                    instance.to_string(),
                );
                
                // Add default tags based on field type
                match field_name.as_str() {
                    "basics" => doc.metadata.tags.push("core".to_string()),
                    "work_style" => doc.metadata.tags.push("preferences".to_string()),
                    "communication" => doc.metadata.tags.push("interaction".to_string()),
                    _ => {}
                }
                
                documents.push(doc);
            }
        }
        
        Ok(documents)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    
    #[test]
    fn test_identity_document_creation() {
        let doc = IdentityDocument::new(
            "basics".to_string(),
            json!({"name": "Claude", "role": "AI Assistant"}),
            "CCI".to_string(),
        );
        
        assert_eq!(doc.field_type, "basics");
        assert_eq!(doc.instance, "CCI");
        assert_eq!(doc.version, 1);
        assert!(doc.id.len() > 0);
    }
    
    #[test]
    fn test_redis_key_generation() {
        let doc = IdentityDocument::new(
            "preferences".to_string(),
            json!({"theme": "dark"}),
            "CC".to_string(),
        );
        
        let key = doc.redis_key();
        assert!(key.starts_with("CC:identity:preferences:"));
    }
    
    #[test]
    fn test_monolithic_to_documents_conversion() {
        let monolithic = json!({
            "basics": {"name": "Claude", "role": "AI"},
            "preferences": {"theme": "dark"},
            "relationships": {
                "Sam": {"type": "user", "trust": "high"}
            }
        });
        
        let docs = conversion::monolithic_to_documents(monolithic, "CCI".to_string())
            .expect("Conversion should succeed");
        
        assert_eq!(docs.len(), 3);
        
        // Check that relationships are properly namespaced
        let relationship_doc = docs.iter()
            .find(|d| d.field_type == "relationships:Sam")
            .expect("Should have Sam relationship");
        
        assert_eq!(relationship_doc.content["type"], "user");
    }
    
}