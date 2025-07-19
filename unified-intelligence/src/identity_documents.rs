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

impl IdentityFieldType {
    pub fn as_str(&self) -> &str {
        match self {
            Self::Basics => "basics",
            Self::WorkStyle => "work_style",
            Self::Communication => "communication",
            Self::KnowledgeDomains => "knowledge_domains",
            Self::Preferences => "preferences",
            Self::Relationships => "relationships",
            Self::Context => "context",
            Self::Metadata => "metadata",
            Self::Custom(s) => s,
        }
    }
    
    pub fn from_str(s: &str) -> Self {
        match s {
            "basics" => Self::Basics,
            "work_style" => Self::WorkStyle,
            "communication" => Self::Communication,
            "knowledge_domains" => Self::KnowledgeDomains,
            "preferences" => Self::Preferences,
            "relationships" => Self::Relationships,
            "context" => Self::Context,
            "metadata" => Self::Metadata,
            other => Self::Custom(other.to_string()),
        }
    }
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

impl IdentityIndex {
    pub fn new(instance: String) -> Self {
        Self {
            fields: HashMap::new(),
            document_count: 0,
            last_updated: Utc::now(),
            instance,
        }
    }
    
    /// Add a document ID to the index
    pub fn add_document(&mut self, field_type: &str, doc_id: String) {
        self.fields
            .entry(field_type.to_string())
            .or_insert_with(Vec::new)
            .push(doc_id);
        self.document_count += 1;
        self.last_updated = Utc::now();
    }
    
    /// Remove a document ID from the index
    pub fn remove_document(&mut self, field_type: &str, doc_id: &str) {
        if let Some(docs) = self.fields.get_mut(field_type) {
            docs.retain(|id| id != doc_id);
            if docs.is_empty() {
                self.fields.remove(field_type);
            }
            self.document_count = self.document_count.saturating_sub(1);
            self.last_updated = Utc::now();
        }
    }
    
    /// Get all document IDs for a field type
    pub fn get_field_documents(&self, field_type: &str) -> Option<&Vec<String>> {
        self.fields.get(field_type)
    }
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
    
    /// Update the content and increment version
    pub fn update_content(&mut self, new_content: Value) {
        self.content = new_content;
        self.updated_at = Utc::now();
        self.version += 1;
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
    use std::collections::HashMap;
    
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
                            instance.clone(),
                        );
                        doc.metadata.tags.push("relationship".to_string());
                        doc.metadata.tags.push(person.to_string());
                        documents.push(doc);
                    }
                }
            } else {
                let mut doc = IdentityDocument::new(
                    field_name.clone(),
                    field_value.clone(),
                    instance.clone(),
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
    
    /// Convert document-based format back to monolithic JSON
    pub fn documents_to_monolithic(documents: Vec<IdentityDocument>) -> Value {
        let mut result = serde_json::Map::new();
        let mut relationships = serde_json::Map::new();
        
        for doc in documents {
            if doc.field_type.starts_with("relationships:") {
                // Extract person name from relationships:person format
                let person = doc.field_type.strip_prefix("relationships:")
                    .unwrap_or(&doc.field_type);
                relationships.insert(person.to_string(), doc.content);
            } else {
                result.insert(doc.field_type.clone(), doc.content);
            }
        }
        
        if !relationships.is_empty() {
            result.insert("relationships".to_string(), Value::Object(relationships));
        }
        
        Value::Object(result)
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
    
    #[test]
    fn test_documents_to_monolithic_conversion() {
        let docs = vec![
            IdentityDocument::new(
                "basics".to_string(),
                json!({"name": "Claude"}),
                "CCI".to_string(),
            ),
            IdentityDocument::new(
                "relationships:Sam".to_string(),
                json!({"type": "user", "trust": "high"}),
                "CCI".to_string(),
            ),
        ];
        
        let monolithic = conversion::documents_to_monolithic(docs);
        
        assert_eq!(monolithic["basics"]["name"], "Claude");
        assert_eq!(monolithic["relationships"]["Sam"]["type"], "user");
    }
    
    #[test]
    fn test_identity_index_operations() {
        let mut index = IdentityIndex::new("CCI".to_string());
        
        index.add_document("basics", "doc1".to_string());
        index.add_document("basics", "doc2".to_string());
        index.add_document("preferences", "doc3".to_string());
        
        assert_eq!(index.document_count, 3);
        assert_eq!(index.get_field_documents("basics").unwrap().len(), 2);
        
        index.remove_document("basics", "doc1");
        assert_eq!(index.document_count, 2);
        assert_eq!(index.get_field_documents("basics").unwrap().len(), 1);
    }
}