use rmcp::prelude::*;
use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::Utc;
use std::env;

#[derive(Debug, Clone, Default)]
struct UnifiedThinkServer;

#[derive(Debug, Deserialize, JsonSchema)]
struct UiThinkParams {
    thought: String,
    thought_number: i32,
    total_thoughts: i32,
    next_thought_needed: bool,
}

#[derive(Debug, Serialize)]
struct ThoughtRecord {
    id: String,
    instance: String,
    thought: String,
    thought_number: i32,
    total_thoughts: i32,
    timestamp: String,
}

impl UnifiedThinkServer {
    async fn ui_think(&self, params: UiThinkParams) -> Result<serde_json::Value, String> {
        let thought_id = Uuid::new_v4().to_string();
        let instance_id = env::var("INSTANCE_ID").unwrap_or_else(|_| "test".to_string());
        
        let thought_record = ThoughtRecord {
            id: thought_id.clone(),
            instance: instance_id,
            thought: params.thought,
            thought_number: params.thought_number,
            total_thoughts: params.total_thoughts,
            timestamp: Utc::now().to_rfc3339(),
        };
        
        // Log to stderr
        if let Ok(json) = serde_json::to_string_pretty(&thought_record) {
            eprintln!("Thought Record: {}", json);
        }
        
        Ok(serde_json::json!({
            "status": "stored",
            "thought_id": thought_id,
            "next_thought_needed": params.next_thought_needed
        }))
    }
}

#[async_trait]
impl ToolProvider for UnifiedThinkServer {
    async fn list_tools(&self) -> Result<Vec<Tool>, Error> {
        Ok(vec![
            Tool {
                name: "ui_think".into(),
                description: "Capture and process thoughts from UnifiedIntelligence instances".into(),
                input_schema: serde_json::json!({
                    "type": "object",
                    "properties": {
                        "thought": {
                            "type": "string",
                            "description": "The thought content"
                        },
                        "thought_number": {
                            "type": "integer",
                            "description": "Current thought number"
                        },
                        "total_thoughts": {
                            "type": "integer",
                            "description": "Total thoughts expected"
                        },
                        "next_thought_needed": {
                            "type": "boolean",
                            "description": "Whether more thoughts are needed"
                        }
                    },
                    "required": ["thought", "thought_number", "total_thoughts", "next_thought_needed"]
                }).into(),
            }
        ])
    }

    async fn call_tool(&self, name: &str, arguments: Option<serde_json::Value>) -> Result<serde_json::Value, Error> {
        match name {
            "ui_think" => {
                let params: UiThinkParams = if let Some(args) = arguments {
                    serde_json::from_value(args).map_err(|e| Error::InvalidParams(e.to_string()))?
                } else {
                    return Err(Error::InvalidParams("Missing arguments".into()));
                };
                
                self.ui_think(params).await.map_err(|e| Error::ToolExecution(e))
            }
            _ => Err(Error::ToolNotFound(name.to_string()))
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let server = UnifiedThinkServer::default();
    let transport = StdioTransport::new();
    
    Server::new(server)
        .with_name("unified-think")
        .with_version("0.1.0")
        .serve(transport)
        .await?;
    
    Ok(())
}