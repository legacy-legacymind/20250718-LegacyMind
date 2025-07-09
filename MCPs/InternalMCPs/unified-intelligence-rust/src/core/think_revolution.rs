use anyhow::Result;
use crate::storage::FrameworkAnalysis;
use crate::core::FrameworkDetector;
use tracing::{info, debug};

pub struct ThinkRevolution;

impl ThinkRevolution {
    /// Determines if content should trigger automatic framework application
    pub async fn should_auto_apply(content: &str, significance: u8) -> bool {
        // High significance thoughts always trigger auto-framework
        if significance >= 8 {
            return true;
        }
        
        // Medium significance with decision/problem indicators
        if significance >= 6 {
            let lower = content.to_lowercase();
            if lower.contains("decision") || lower.contains("problem") || 
               lower.contains("stuck") || lower.contains("help") ||
               lower.contains("issue") || lower.contains("challenge") {
                return true;
            }
        }
        
        // Pattern-based triggers
        Self::has_thinking_trigger(content).await
    }
    
    /// Checks for specific thinking pattern triggers
    async fn has_thinking_trigger(content: &str) -> bool {
        let lower = content.to_lowercase();
        
        // Cognitive load indicators
        let cognitive_triggers = [
            "how do i", "what if", "i need to", "should i",
            "trying to figure out", "confused about", "wondering",
            "not sure", "let me think", "considering", "analyzing"
        ];
        
        cognitive_triggers.iter().any(|trigger| lower.contains(trigger))
    }
    
    /// Performs automatic thinking enhancement
    pub async fn auto_enhance_thinking(
        content: &str, 
        significance: u8
    ) -> Result<ThinkingEnhancement> {
        info!("Think Revolution: Auto-enhancing thought with significance {}", significance);
        
        // Detect best framework
        let framework = FrameworkDetector::detect(content).await;
        debug!("Auto-detected framework: {}", framework);
        
        // Apply framework
        let analysis = FrameworkDetector::apply(content, &framework).await?;
        
        // Generate proactive insights
        let proactive_insights = Self::generate_proactive_insights(
            content, 
            &framework, 
            significance
        ).await;
        
        // Suggest next steps
        let next_steps = Self::suggest_next_steps(&analysis, significance).await;
        
        Ok(ThinkingEnhancement {
            original_content: content.to_string(),
            framework_applied: framework,
            analysis,
            significance,
            proactive_insights,
            next_steps,
            auto_applied: true,
        })
    }
    
    /// Generates proactive insights based on content and framework
    async fn generate_proactive_insights(
        content: &str, 
        framework: &str, 
        significance: u8
    ) -> Vec<String> {
        let mut insights = Vec::new();
        
        // High significance insights
        if significance >= 8 {
            insights.push("🚨 High significance detected - this seems critical".to_string());
            insights.push("Consider documenting this insight for future reference".to_string());
        }
        
        // Framework-specific insights
        match framework {
            "ooda" => {
                insights.push("💡 Action-oriented thinking detected".to_string());
                insights.push("Remember: Speed of decision often beats perfection".to_string());
            },
            "5whys" => {
                insights.push("🔍 Root cause analysis in progress".to_string());
                insights.push("Keep drilling down - the real issue may be deeper".to_string());
            },
            "first-principles" => {
                insights.push("🧩 Breaking down to fundamentals".to_string());
                insights.push("Question every assumption - what's truly essential?".to_string());
            },
            "swot" => {
                insights.push("📊 Strategic evaluation mode".to_string());
                insights.push("Balance internal factors (SW) with external (OT)".to_string());
            },
            _ => {
                insights.push("🧠 Enhanced thinking pattern activated".to_string());
            }
        }
        
        // Content-based insights
        if content.len() > 200 {
            insights.push("📝 Complex thought detected - consider breaking into smaller parts".to_string());
        }
        
        insights
    }
    
    /// Suggests next cognitive steps based on analysis
    async fn suggest_next_steps(
        analysis: &FrameworkAnalysis, 
        significance: u8
    ) -> Vec<String> {
        let mut steps = Vec::new();
        
        // Always suggest the next insight from the framework
        if let Some(next_insight) = analysis.insights.get(0) {
            steps.push(format!("Next: {}", next_insight));
        }
        
        // Significance-based suggestions
        if significance >= 7 {
            steps.push("📌 Consider capturing related thoughts while this is fresh".to_string());
            steps.push("🔗 Look for connections to previous high-significance thoughts".to_string());
        }
        
        // Framework-specific next steps
        if let Some(tags) = analysis.metadata.get("tags").and_then(|v| v.as_array()) {
            if tags.iter().any(|t| t.as_str() == Some("decision")) {
                steps.push("📋 List concrete action items from this decision".to_string());
            }
            if tags.iter().any(|t| t.as_str() == Some("problem-solving")) {
                steps.push("🎯 Define success criteria for the solution".to_string());
            }
        }
        
        steps
    }
    
    /// Monitors thinking patterns for continuous improvement
    pub async fn monitor_thinking_patterns(
        instance_id: &str,
        recent_thoughts: &[ThoughtPattern]
    ) -> CognitiveReport {
        let total_thoughts = recent_thoughts.len();
        let high_sig_thoughts = recent_thoughts.iter()
            .filter(|t| t.significance >= 7)
            .count();
        
        let framework_usage = Self::analyze_framework_usage(recent_thoughts);
        let cognitive_velocity = Self::calculate_cognitive_velocity(recent_thoughts);
        let patterns = Self::identify_patterns(recent_thoughts);
        
        let recommendations = Self::generate_recommendations(&patterns);
        
        CognitiveReport {
            instance_id: instance_id.to_string(),
            period: "recent".to_string(),
            total_thoughts,
            high_significance_ratio: high_sig_thoughts as f64 / total_thoughts.max(1) as f64,
            framework_usage,
            cognitive_velocity,
            patterns,
            recommendations,
        }
    }
    
    fn analyze_framework_usage(thoughts: &[ThoughtPattern]) -> std::collections::HashMap<String, usize> {
        use std::collections::HashMap;
        
        let mut usage = HashMap::new();
        for thought in thoughts {
            if let Some(framework) = &thought.framework {
                *usage.entry(framework.clone()).or_insert(0) += 1;
            }
        }
        usage
    }
    
    fn calculate_cognitive_velocity(thoughts: &[ThoughtPattern]) -> f64 {
        if thoughts.len() < 2 {
            return 0.0;
        }
        
        // Calculate thoughts per hour based on timestamp differences
        let time_span = thoughts.last().unwrap().timestamp - thoughts.first().unwrap().timestamp;
        let hours = time_span.num_seconds() as f64 / 3600.0;
        
        if hours > 0.0 {
            thoughts.len() as f64 / hours
        } else {
            0.0
        }
    }
    
    fn identify_patterns(thoughts: &[ThoughtPattern]) -> Vec<String> {
        let mut patterns = Vec::new();
        
        // Check for thinking momentum
        let recent_high_sig = thoughts.iter()
            .rev()
            .take(5)
            .filter(|t| t.significance >= 7)
            .count();
            
        if recent_high_sig >= 3 {
            patterns.push("🔥 High cognitive momentum detected".to_string());
        }
        
        // Check for framework preferences
        let framework_counts = Self::analyze_framework_usage(thoughts);
        if let Some((dominant, count)) = framework_counts.iter().max_by_key(|(_, v)| *v) {
            if *count > thoughts.len() / 3 {
                patterns.push(format!("📊 Preference for {} framework", dominant));
            }
        }
        
        patterns
    }
    
    fn generate_recommendations(patterns: &[String]) -> Vec<String> {
        let mut recommendations = Vec::new();
        
        for pattern in patterns {
            if pattern.contains("High cognitive momentum") {
                recommendations.push("🚀 Maintain momentum - keep exploring these insights".to_string());
                recommendations.push("📝 Document key breakthroughs before context is lost".to_string());
            }
            
            if pattern.contains("Preference for") {
                recommendations.push("🔄 Try different frameworks for fresh perspectives".to_string());
            }
        }
        
        if recommendations.is_empty() {
            recommendations.push("💡 Experiment with different thinking frameworks".to_string());
            recommendations.push("🎯 Focus on high-significance thoughts for breakthroughs".to_string());
        }
        
        recommendations
    }
}

#[derive(Debug, Clone)]
pub struct ThinkingEnhancement {
    pub original_content: String,
    pub framework_applied: String,
    pub analysis: FrameworkAnalysis,
    pub significance: u8,
    pub proactive_insights: Vec<String>,
    pub next_steps: Vec<String>,
    pub auto_applied: bool,
}

#[derive(Debug, Clone)]
pub struct ThoughtPattern {
    pub content: String,
    pub significance: u8,
    pub framework: Option<String>,
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

#[derive(Debug, Clone)]
pub struct CognitiveReport {
    pub instance_id: String,
    pub period: String,
    pub total_thoughts: usize,
    pub high_significance_ratio: f64,
    pub framework_usage: std::collections::HashMap<String, usize>,
    pub cognitive_velocity: f64,
    pub patterns: Vec<String>,
    pub recommendations: Vec<String>,
}