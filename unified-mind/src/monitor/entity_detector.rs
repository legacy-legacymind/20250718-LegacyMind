use anyhow::Result;
use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{debug, info};

/// Types of entities we can detect
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum EntityType {
    System,          // UnifiedVault, Redis, etc.
    Instance,        // CC, CCI, CCD, DT
    FilePath,        // /Users/sam/...
    Function,        // function names
    Error,           // error messages
    Configuration,   // config keys
    Command,         // CLI commands
    Concept,         // abstract concepts
    Tool,            // MCP tools
}

/// Detected entity with metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DetectedEntity {
    pub text: String,
    pub entity_type: EntityType,
    pub confidence: f64,
    pub context: String,
    pub enrichment_needed: bool,
    pub metadata: HashMap<String, Value>,
}

/// Strategy for enriching detected entities
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EnrichmentStrategy {
    pub entity_type: EntityType,
    pub actions: Vec<EnrichmentAction>,
    pub priority: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum EnrichmentAction {
    FetchStatus,              // Get current status
    RetrieveDocumentation,    // Get docs
    QueryRecentIssues,        // Check for problems
    GetConfiguration,         // Fetch config
    AnalyzeUsagePatterns,     // Usage statistics
    CheckDependencies,        // Dependency status
}

/// Entity detector for conversation intelligence
pub struct EntityDetector {
    // Known entities database
    known_entities: Arc<RwLock<HashMap<String, EntityMetadata>>>,
    
    // Detection patterns
    system_patterns: Vec<CompiledPattern>,
    path_patterns: Vec<CompiledPattern>,
    error_patterns: Vec<CompiledPattern>,
    function_patterns: Vec<CompiledPattern>,
    
    // Enrichment rules
    enrichment_rules: Arc<RwLock<HashMap<EntityType, Vec<EnrichmentStrategy>>>>,
    
    // Learning cache
    detection_cache: Arc<RwLock<HashMap<String, Vec<DetectedEntity>>>>,
}

#[derive(Debug, Clone)]
struct CompiledPattern {
    regex: Regex,
    entity_type: EntityType,
    confidence_boost: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct EntityMetadata {
    name: String,
    entity_type: EntityType,
    aliases: Vec<String>,
    description: String,
    importance: f64,
}

impl EntityDetector {
    /// Minimal constructor for testing MCP initialization
    pub fn new_minimal() -> Self {
        Self {
            known_entities: Arc::new(RwLock::new(HashMap::new())),
            system_patterns: Vec::new(),
            path_patterns: Vec::new(),
            error_patterns: Vec::new(),
            function_patterns: Vec::new(),
            enrichment_rules: Arc::new(RwLock::new(HashMap::new())),
            detection_cache: Arc::new(RwLock::new(HashMap::new())),
        }
    }
    
    pub async fn new() -> Result<Self> {
        let mut detector = Self {
            known_entities: Arc::new(RwLock::new(HashMap::new())),
            system_patterns: Vec::new(),
            path_patterns: Vec::new(),
            error_patterns: Vec::new(),
            function_patterns: Vec::new(),
            enrichment_rules: Arc::new(RwLock::new(HashMap::new())),
            detection_cache: Arc::new(RwLock::new(HashMap::new())),
        };
        
        detector.initialize_patterns()?;
        detector.initialize_known_entities().await?;
        detector.initialize_enrichment_rules().await?;
        
        Ok(detector)
    }
    
    /// Initialize detection patterns
    fn initialize_patterns(&mut self) -> Result<()> {
        // System/component patterns
        self.system_patterns = vec![
            CompiledPattern {
                regex: Regex::new(r"\b(UnifiedVault|UnifiedIntelligence|UnifiedMind|UnifiedBot)\b")?,
                entity_type: EntityType::System,
                confidence_boost: 0.9,
            },
            CompiledPattern {
                regex: Regex::new(r"\b(Redis|Qdrant|PostgreSQL|Docker|Kubernetes)\b")?,
                entity_type: EntityType::System,
                confidence_boost: 0.8,
            },
        ];
        
        // File path patterns
        self.path_patterns = vec![
            CompiledPattern {
                regex: Regex::new(r"(/[\w/.-]+\.[\w]+)")?,
                entity_type: EntityType::FilePath,
                confidence_boost: 0.7,
            },
            CompiledPattern {
                regex: Regex::new(r"(~/[\w/.-]+)")?,
                entity_type: EntityType::FilePath,
                confidence_boost: 0.7,
            },
        ];
        
        // Error patterns
        self.error_patterns = vec![
            CompiledPattern {
                regex: Regex::new(r"(?i)(error|exception|failed|failure):\s*(.+)")?,
                entity_type: EntityType::Error,
                confidence_boost: 0.9,
            },
            CompiledPattern {
                regex: Regex::new(r"(?i)(connection refused|timeout|permission denied)")?,
                entity_type: EntityType::Error,
                confidence_boost: 0.85,
            },
        ];
        
        // Function/method patterns
        self.function_patterns = vec![
            CompiledPattern {
                regex: Regex::new(r"\b(\w+)\(\)")?,
                entity_type: EntityType::Function,
                confidence_boost: 0.6,
            },
            CompiledPattern {
                regex: Regex::new(r"fn\s+(\w+)")?,
                entity_type: EntityType::Function,
                confidence_boost: 0.8,
            },
        ];
        
        Ok(())
    }
    
    /// Initialize known entities database
    async fn initialize_known_entities(&self) -> Result<()> {
        let mut entities = self.known_entities.write().await;
        
        // Core systems
        entities.insert("UnifiedIntelligence".to_string(), EntityMetadata {
            name: "UnifiedIntelligence".to_string(),
            entity_type: EntityType::System,
            aliases: vec!["UI".to_string(), "unified-intelligence".to_string()],
            description: "Core memory and thinking MCP".to_string(),
            importance: 1.0,
        });
        
        entities.insert("UnifiedMind".to_string(), EntityMetadata {
            name: "UnifiedMind".to_string(),
            entity_type: EntityType::System,
            aliases: vec!["UM".to_string(), "unified-mind".to_string()],
            description: "Cognitive subconscious platform".to_string(),
            importance: 1.0,
        });
        
        entities.insert("Redis".to_string(), EntityMetadata {
            name: "Redis".to_string(),
            entity_type: EntityType::System,
            aliases: vec!["redis-server".to_string()],
            description: "In-memory data store".to_string(),
            importance: 0.9,
        });
        
        // Federation instances
        entities.insert("CC".to_string(), EntityMetadata {
            name: "CC".to_string(),
            entity_type: EntityType::Instance,
            aliases: vec!["Claude Code".to_string()],
            description: "Primary Claude Code instance".to_string(),
            importance: 0.8,
        });
        
        entities.insert("CCI".to_string(), EntityMetadata {
            name: "CCI".to_string(),
            entity_type: EntityType::Instance,
            aliases: vec!["UnifiedIntelligence Specialist".to_string()],
            description: "UnifiedIntelligence development instance".to_string(),
            importance: 0.8,
        });
        
        // MCP tools
        entities.insert("ui_think".to_string(), EntityMetadata {
            name: "ui_think".to_string(),
            entity_type: EntityType::Tool,
            aliases: vec!["think tool".to_string()],
            description: "Thinking and framework application tool".to_string(),
            importance: 0.7,
        });
        
        Ok(())
    }
    
    /// Initialize enrichment rules
    async fn initialize_enrichment_rules(&self) -> Result<()> {
        let mut rules = self.enrichment_rules.write().await;
        
        // System entity enrichment
        rules.insert(EntityType::System, vec![
            EnrichmentStrategy {
                entity_type: EntityType::System,
                actions: vec![
                    EnrichmentAction::FetchStatus,
                    EnrichmentAction::QueryRecentIssues,
                    EnrichmentAction::CheckDependencies,
                ],
                priority: 0.9,
            },
        ]);
        
        // Error entity enrichment
        rules.insert(EntityType::Error, vec![
            EnrichmentStrategy {
                entity_type: EntityType::Error,
                actions: vec![
                    EnrichmentAction::QueryRecentIssues,
                    EnrichmentAction::RetrieveDocumentation,
                ],
                priority: 0.95,
            },
        ]);
        
        // FilePath entity enrichment
        rules.insert(EntityType::FilePath, vec![
            EnrichmentStrategy {
                entity_type: EntityType::FilePath,
                actions: vec![
                    EnrichmentAction::FetchStatus,
                    EnrichmentAction::GetConfiguration,
                ],
                priority: 0.7,
            },
        ]);
        
        Ok(())
    }
    
    /// Detect entities in text
    pub async fn detect_entities(&self, text: &str) -> Result<Vec<DetectedEntity>> {
        let mut detected = Vec::new();
        let text_lower = text.to_lowercase();
        
        // Check cache first
        if let Some(cached) = self.detection_cache.read().await.get(text) {
            return Ok(cached.clone());
        }
        
        // Apply pattern matching
        for pattern in &self.system_patterns {
            if let Some(captures) = pattern.regex.captures(text) {
                for cap in captures.iter().skip(1).flatten() {
                    detected.push(DetectedEntity {
                        text: cap.as_str().to_string(),
                        entity_type: pattern.entity_type.clone(),
                        confidence: pattern.confidence_boost,
                        context: self.extract_context(text, cap.start(), cap.end()),
                        enrichment_needed: true,
                        metadata: HashMap::new(),
                    });
                }
            }
        }
        
        // Check for file paths
        for pattern in &self.path_patterns {
            if let Some(captures) = pattern.regex.captures(text) {
                for cap in captures.iter().skip(1).flatten() {
                    detected.push(DetectedEntity {
                        text: cap.as_str().to_string(),
                        entity_type: EntityType::FilePath,
                        confidence: pattern.confidence_boost,
                        context: self.extract_context(text, cap.start(), cap.end()),
                        enrichment_needed: self.should_enrich_path(cap.as_str()),
                        metadata: HashMap::new(),
                    });
                }
            }
        }
        
        // Check for errors
        for pattern in &self.error_patterns {
            if let Some(captures) = pattern.regex.captures(text) {
                if let Some(cap) = captures.get(0) {
                    detected.push(DetectedEntity {
                        text: cap.as_str().to_string(),
                        entity_type: EntityType::Error,
                        confidence: pattern.confidence_boost,
                        context: self.extract_context(text, cap.start(), cap.end()),
                        enrichment_needed: true,
                        metadata: HashMap::new(),
                    });
                }
            }
        }
        
        // Check known entities
        let entities = self.known_entities.read().await;
        for (name, metadata) in entities.iter() {
            if text_lower.contains(&name.to_lowercase()) {
                detected.push(DetectedEntity {
                    text: name.clone(),
                    entity_type: metadata.entity_type.clone(),
                    confidence: metadata.importance,
                    context: text.to_string(),
                    enrichment_needed: true,
                    metadata: HashMap::from([
                        ("description".to_string(), json!(metadata.description)),
                        ("aliases".to_string(), json!(metadata.aliases)),
                    ]),
                });
            }
        }
        
        // Deduplicate
        detected = self.deduplicate_entities(detected);
        
        // Cache results
        self.detection_cache.write().await.insert(text.to_string(), detected.clone());
        
        Ok(detected)
    }
    
    /// Get enrichment strategy for an entity
    pub async fn get_enrichment_strategy(&self, entity: &DetectedEntity) -> Option<EnrichmentStrategy> {
        let rules = self.enrichment_rules.read().await;
        
        rules.get(&entity.entity_type)
            .and_then(|strategies| strategies.first())
            .cloned()
    }
    
    /// Check if entity needs immediate enrichment
    pub fn needs_immediate_enrichment(&self, entity: &DetectedEntity) -> bool {
        match entity.entity_type {
            EntityType::Error => true,
            EntityType::System => entity.confidence > 0.8,
            _ => false,
        }
    }
    
    /// Extract context around detected entity
    fn extract_context(&self, text: &str, start: usize, end: usize) -> String {
        let context_size = 50;
        let context_start = start.saturating_sub(context_size);
        let context_end = (end + context_size).min(text.len());
        
        text[context_start..context_end].to_string()
    }
    
    /// Check if file path should be enriched
    fn should_enrich_path(&self, path: &str) -> bool {
        // Enrich paths that look like project files
        path.contains("LegacyMind") || 
        path.ends_with(".rs") || 
        path.ends_with(".toml") ||
        path.ends_with(".md")
    }
    
    /// Deduplicate detected entities
    fn deduplicate_entities(&self, entities: Vec<DetectedEntity>) -> Vec<DetectedEntity> {
        let mut seen = HashSet::new();
        let mut unique = Vec::new();
        
        for entity in entities {
            let key = format!("{}:{}", entity.text, entity.entity_type.clone() as u8);
            if seen.insert(key) {
                unique.push(entity);
            }
        }
        
        unique
    }
    
    /// Learn new entity from user interaction
    pub async fn learn_entity(&self, name: String, entity_type: EntityType, metadata: EntityMetadata) -> Result<()> {
        info!("Learning new entity: {} of type {:?}", name, entity_type);
        
        let mut entities = self.known_entities.write().await;
        entities.insert(name, metadata);
        
        Ok(())
    }
    
    /// Update entity importance based on usage
    pub async fn update_entity_importance(&self, name: &str, delta: f64) -> Result<()> {
        let mut entities = self.known_entities.write().await;
        
        if let Some(metadata) = entities.get_mut(name) {
            metadata.importance = (metadata.importance + delta).clamp(0.0, 1.0);
            debug!("Updated {} importance to {}", name, metadata.importance);
        }
        
        Ok(())
    }
    
    /// Get all known entities of a specific type
    pub async fn get_entities_by_type(&self, entity_type: EntityType) -> Vec<EntityMetadata> {
        let entities = self.known_entities.read().await;
        
        entities.values()
            .filter(|e| e.entity_type == entity_type)
            .cloned()
            .collect()
    }
}