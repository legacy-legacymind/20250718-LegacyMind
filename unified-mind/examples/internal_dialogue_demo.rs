use anyhow::Result;
use unified_mind::service::UnifiedMindService;
use rmcp::{
    handler::server::tool::Parameters,
    model::CallToolResult,
};
use unified_mind::models::{MindDialogueParams, MindInternalVoiceParams};
use serde_json::json;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize the service
    let service = UnifiedMindService::new().await?;
    
    println!("=== UnifiedMind Internal Dialogue Demo ===\n");
    
    // Demo 1: Uncertainty detection
    println!("Demo 1: Detecting uncertainty and providing internal voice");
    let uncertain_thought = "I'm not sure if this approach will work... maybe I should try something different?";
    
    let response = service.mind_internal_voice(Parameters(MindInternalVoiceParams {
        current_thought: uncertain_thought.to_string(),
        recent_context: Some(vec![
            "Tried the direct approach but it failed".to_string(),
            "Getting the same error again".to_string(),
        ]),
        cognitive_state: Some(json!("problem_solving")),
    })).await?;
    
    if let CallToolResult::Content { content, .. } = response {
        if let Some(json_content) = content.first() {
            println!("Internal Voice Response: {}", serde_json::to_string_pretty(&json_content)?);
        }
    }
    
    println!("\n---\n");
    
    // Demo 2: Pattern recognition
    println!("Demo 2: Pattern recognition with memory nudge");
    let pattern_thought = "This Redis connection error looks familiar...";
    
    let response = service.mind_dialogue(Parameters(MindDialogueParams {
        thought: pattern_thought.to_string(),
        context: Some("debugging Redis timeout issues".to_string()),
    })).await?;
    
    if let CallToolResult::Content { content, .. } = response {
        if let Some(json_content) = content.first() {
            println!("Dialogue Response: {}", serde_json::to_string_pretty(&json_content)?);
        }
    }
    
    println!("\n---\n");
    
    // Demo 3: Framework suggestion
    println!("Demo 3: Framework activation for complex problem");
    let framework_thought = "How do I approach this system design problem? Where should I even start?";
    
    let response = service.mind_internal_voice(Parameters(MindInternalVoiceParams {
        current_thought: framework_thought.to_string(),
        recent_context: Some(vec![
            "Need to design a distributed system".to_string(),
            "Multiple components need to communicate".to_string(),
            "Performance is critical".to_string(),
        ]),
        cognitive_state: Some(json!("planning")),
    })).await?;
    
    if let CallToolResult::Content { content, .. } = response {
        if let Some(json_content) = content.first() {
            println!("Internal Voice Response: {}", serde_json::to_string_pretty(&json_content)?);
        }
    }
    
    println!("\n---\n");
    
    // Demo 4: Stuck pattern detection
    println!("Demo 4: Detecting stuck pattern and suggesting alternative");
    let stuck_thought = "Still getting the same error... I've tried this three times now";
    
    let response = service.mind_internal_voice(Parameters(MindInternalVoiceParams {
        current_thought: stuck_thought.to_string(),
        recent_context: Some(vec![
            "Attempted fix #1 - failed".to_string(),
            "Attempted fix #2 - failed".to_string(),
            "Attempted fix #3 - failed".to_string(),
        ]),
        cognitive_state: Some(json!("debugging")),
    })).await?;
    
    if let CallToolResult::Content { content, .. } = response {
        if let Some(json_content) = content.first() {
            println!("Internal Voice Response: {}", serde_json::to_string_pretty(&json_content)?);
        }
    }
    
    println!("\n---\n");
    
    // Demo 5: Creative connection
    println!("Demo 5: Making creative connections");
    let creative_thought = "What if we combined the caching approach with the event-driven pattern?";
    
    let response = service.mind_dialogue(Parameters(MindDialogueParams {
        thought: creative_thought.to_string(),
        context: Some("exploring architecture solutions".to_string()),
    })).await?;
    
    if let CallToolResult::Content { content, .. } = response {
        if let Some(json_content) = content.first() {
            println!("Dialogue Response: {}", serde_json::to_string_pretty(&json_content)?);
        }
    }
    
    println!("\n=== Demo Complete ===");
    
    Ok(())
}