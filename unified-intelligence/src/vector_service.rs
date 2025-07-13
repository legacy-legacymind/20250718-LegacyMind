// src/vector_service.rs - PyO3 bridge for Python vector service
use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde_json::Value;
use tokio::sync::OnceCell;
use std::env;

use crate::error::{Result, UnifiedIntelligenceError};
use crate::models::ThoughtRecord;

pub struct VectorService {
    python_service: PyObject,
}

static VECTOR_SERVICE: OnceCell<VectorService> = OnceCell::const_new();

impl VectorService {
    pub async fn get_instance() -> &'static VectorService {
        VECTOR_SERVICE.get_or_init(|| async {
            Self::new().await.expect("Failed to initialize vector service")
        }).await
    }
    
    async fn new() -> Result<Self> {
        Python::with_gil(|py| {
            // Add the python directory to sys.path
            let sys = py.import_bound("sys")?;
            let path = sys.getattr("path")?;
            path.call_method1("append", ("/Users/samuelatagana/Projects/LegacyMind/unified-intelligence/python",))?;
            
            let vector_module = py.import_bound("unified_intelligence_vector_service")?;
            let service_class = vector_module.getattr("UnifiedIntelligenceVectorService")?;
            
            let openai_key = env::var("OPENAI_API_KEY")
                .unwrap_or_else(|_| "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".to_string());
            
            let service = service_class.call1((
                "redis://localhost:6379",
                openai_key,
                "Claude"
            ))?;
            
            // Initialize the service
            let coroutine = service.call_method0("initialize")?;
            let asyncio = py.import_bound("asyncio")?;
            asyncio.call_method1("run", (coroutine,))?;
            
            Ok(VectorService {
                python_service: service.into(),
            })
        }).map_err(|e: PyErr| UnifiedIntelligenceError::Internal(format!("Failed to initialize vector service: {}", e)))
    }
    
    pub async fn semantic_search(&self, query: &str, limit: usize, threshold: f32) -> Result<Vec<ThoughtRecord>> {
        Python::with_gil(|py| {
            let coroutine = self.python_service.call_method1(
                py,
                "semantic_search",
                (query, limit, threshold)
            )?;
            
            let asyncio = py.import_bound("asyncio")?;
            let result = asyncio.call_method1("run", (coroutine,))?;
            
            // Convert Python results to Rust ThoughtRecord structs
            let mut thoughts = Vec::new();
            
            for item in result.iter()? {
                let item = item?;
                let dict = item.downcast::<PyDict>()?;
                
                let content = dict.get_item("content")?
                    .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err("Missing 'content' field"))?
                    .extract::<String>()?;
                let thought = ThoughtRecord {
                    id: dict.get_item("thought_id")?
                        .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err("Missing 'thought_id' field"))?
                        .extract::<String>()?,
                    thought: content.clone(),
                    content,
                    chain_id: dict.get_item("chain_id")?.and_then(|v| v.extract().ok()),
                    timestamp: dict.get_item("timestamp")?
                        .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err("Missing 'timestamp' field"))?
                        .extract::<String>()?,
                    similarity: Some(dict.get_item("similarity")?
                        .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err("Missing 'similarity' field"))?
                        .extract::<f32>()?),
                    instance: "Claude".to_string(),
                    thought_number: 1,
                    total_thoughts: 1,
                    next_thought_needed: false,
                };
                
                thoughts.push(thought);
            }
            
            Ok(thoughts)
        }).map_err(|e: PyErr| UnifiedIntelligenceError::Internal(format!("Vector search error: {}", e)))
    }
    
    pub async fn hybrid_search(&self, query: &str, limit: usize) -> Result<Vec<ThoughtRecord>> {
        Python::with_gil(|py| {
            let coroutine = self.python_service.call_method1(
                py,
                "hybrid_search",
                (query, limit)
            )?;
            
            let asyncio = py.import_bound("asyncio")?;
            let result = asyncio.call_method1("run", (coroutine,))?;
            
            // Convert Python results to Rust ThoughtRecord structs
            let mut thoughts = Vec::new();
            
            for item in result.iter()? {
                let item = item?;
                let dict = item.downcast::<PyDict>()?;
                
                let content = dict.get_item("content")?
                    .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err("Missing 'content' field"))?
                    .extract::<String>()?;
                let thought = ThoughtRecord {
                    id: dict.get_item("thought_id")?
                        .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err("Missing 'thought_id' field"))?
                        .extract::<String>()?,
                    thought: content.clone(),
                    content,
                    chain_id: dict.get_item("chain_id")?.and_then(|v| v.extract().ok()),
                    timestamp: dict.get_item("timestamp")?
                        .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err("Missing 'timestamp' field"))?
                        .extract::<String>()?,
                    similarity: dict.get_item("combined_score")?.and_then(|v| v.extract::<f32>().ok()),
                    instance: "Claude".to_string(),
                    thought_number: 1,
                    total_thoughts: 1,
                    next_thought_needed: false,
                };
                
                thoughts.push(thought);
            }
            
            Ok(thoughts)
        }).map_err(|e: PyErr| UnifiedIntelligenceError::Internal(format!("Hybrid search error: {}", e)))
    }
    
    pub async fn queue_for_embedding(&self, thought_id: &str, content: &str, metadata: Value) -> Result<()> {
        Python::with_gil(|py| {
            let coroutine = self.python_service.call_method1(
                py,
                "embed_thought",
                (thought_id, content, pythonize::pythonize(py, &metadata)?)
            )?;
            
            let asyncio = py.import_bound("asyncio")?;
            asyncio.call_method1("run", (coroutine,))?;
            
            Ok(())
        }).map_err(|e: PyErr| UnifiedIntelligenceError::Internal(format!("Embedding error: {}", e)))
    }
}