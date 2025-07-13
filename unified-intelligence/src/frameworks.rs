/// Thinking frameworks module for unified-intelligence
/// Provides cognitive enhancement layers on top of Sequential thinking foundation

use colored::*;
use thiserror::Error;
use tokio::time::{Duration, timeout};

/// Framework validation and processing errors
#[derive(Error, Debug)]
pub enum FrameworkError {
    #[error("Invalid framework name '{name}'. Valid frameworks: {valid_list}")]
    InvalidFramework { name: String, valid_list: String },
    
    #[error("Framework processing timeout after {timeout_ms}ms")]
    ProcessingTimeout { timeout_ms: u64 },
    
    #[error("Framework processing failed: {reason}")]
    ProcessingFailed { reason: String },
    
    #[error("Empty framework name provided")]
    EmptyFrameworkName,
}

impl FrameworkError {
    /// Create an invalid framework error with the list of valid frameworks
    pub fn invalid_framework(name: &str) -> Self {
        let valid_frameworks = "ooda, socratic, first_principles, systems, root_cause, swot, sequential";
        Self::InvalidFramework {
            name: name.to_string(),
            valid_list: valid_frameworks.to_string(),
        }
    }
}

/// Available thinking frameworks
#[derive(Debug, Clone, PartialEq)]
pub enum ThinkingFramework {
    Sequential,        // Default - just store the thought
    OODA,             // Observe, Orient, Decide, Act
    Socratic,         // Question-based analysis
    FirstPrinciples,  // Break down to fundamental truths
    Systems,          // Understand interconnections and patterns
    RootCause,        // Five Whys methodology
    SWOT,             // Strengths, Weaknesses, Opportunities, Threats
}

impl ThinkingFramework {
    /// Parse framework from string with validation
    pub fn from_string(framework: &str) -> Result<Self, FrameworkError> {
        if framework.trim().is_empty() {
            return Err(FrameworkError::EmptyFrameworkName);
        }
        
        match framework.to_lowercase().trim() {
            "ooda" => Ok(Self::OODA),
            "socratic" => Ok(Self::Socratic),
            "first_principles" => Ok(Self::FirstPrinciples),
            "systems" => Ok(Self::Systems),
            "root_cause" => Ok(Self::RootCause),
            "swot" => Ok(Self::SWOT),
            "sequential" => Ok(Self::Sequential),
            _ => Err(FrameworkError::invalid_framework(framework)),
        }
    }
    
    /// Safe parse that returns Sequential as fallback
    pub fn from_string_safe(framework: &str) -> Self {
        Self::from_string(framework).unwrap_or(Self::Sequential)
    }

    /// Get framework name for display
    pub fn name(&self) -> &'static str {
        match self {
            Self::Sequential => "Sequential",
            Self::OODA => "OODA Loop",
            Self::Socratic => "Socratic Method",
            Self::FirstPrinciples => "First Principles",
            Self::Systems => "Systems Thinking",
            Self::RootCause => "Root Cause Analysis",
            Self::SWOT => "SWOT Analysis",
        }
    }

    /// Get framework description
    pub fn description(&self) -> &'static str {
        match self {
            Self::Sequential => "Standard sequential thinking process",
            Self::OODA => "Observe, Orient, Decide, Act methodology",
            Self::Socratic => "Question-based analysis and inquiry",
            Self::FirstPrinciples => "Break down to fundamental truths",
            Self::Systems => "Understand interconnections and patterns",
            Self::RootCause => "Five Whys root cause analysis",
            Self::SWOT => "Strengths, Weaknesses, Opportunities, Threats analysis",
        }
    }

    /// Get framework color for visual output
    pub fn color(&self) -> &'static str {
        match self {
            Self::Sequential => "bright_blue",
            Self::OODA => "bright_green",
            Self::Socratic => "bright_yellow",
            Self::FirstPrinciples => "bright_magenta",
            Self::Systems => "bright_cyan",
            Self::RootCause => "bright_red",
            Self::SWOT => "bright_white",
        }
    }
}

/// Framework processing engine
pub struct FrameworkProcessor {
    framework: ThinkingFramework,
}

impl FrameworkProcessor {
    pub fn new(framework: ThinkingFramework) -> Self {
        Self { framework }
    }

    /// Process thought through the selected framework
    pub fn process_thought(&self, thought: &str, thought_number: i32) -> FrameworkResult {
        match &self.framework {
            ThinkingFramework::Sequential => self.process_sequential(thought),
            ThinkingFramework::OODA => self.process_ooda(thought, thought_number),
            ThinkingFramework::Socratic => self.process_socratic(thought),
            ThinkingFramework::FirstPrinciples => self.process_first_principles(thought),
            ThinkingFramework::Systems => self.process_systems(thought),
            ThinkingFramework::RootCause => self.process_root_cause(thought, thought_number),
            ThinkingFramework::SWOT => self.process_swot(thought),
        }
    }

    /// Sequential framework (default - no additional processing)
    fn process_sequential(&self, _thought: &str) -> FrameworkResult {
        FrameworkResult {
            framework: self.framework.clone(),
            prompts: vec![],
            insights: vec![],
            metadata: None,
        }
    }

    /// OODA Loop framework
    fn process_ooda(&self, thought: &str, thought_number: i32) -> FrameworkResult {
        let stage = match thought_number % 4 {
            1 => "Observe",
            2 => "Orient", 
            3 => "Decide",
            0 => "Act",
            _ => "Observe",
        };

        let prompts = match stage {
            "Observe" => vec![
                "What data and observations are relevant to this situation?".to_string(),
                "What patterns or changes do you notice?".to_string(),
            ],
            "Orient" => vec![
                "How do these observations fit with your existing understanding?".to_string(),
                "What mental models or frameworks apply here?".to_string(),
            ],
            "Decide" => vec![
                "What are the available options based on your analysis?".to_string(),
                "Which course of action best addresses the situation?".to_string(),
            ],
            "Act" => vec![
                "What concrete steps will you take?".to_string(),
                "How will you monitor the results of your actions?".to_string(),
            ],
            _ => vec![],
        };

        FrameworkResult {
            framework: self.framework.clone(),
            prompts,
            insights: vec![format!("OODA Stage: {}", stage)],
            metadata: Some(serde_json::json!({
                "ooda_stage": stage,
                "stage_number": thought_number % 4,
            })),
        }
    }

    /// Socratic Method framework
    fn process_socratic(&self, thought: &str) -> FrameworkResult {
        let prompts = vec![
            "What assumptions are you making in this thought?".to_string(),
            "What evidence supports or challenges this idea?".to_string(),
            "What would someone who disagrees with this think?".to_string(),
            "What are the implications if this thought is true?".to_string(),
        ];

        FrameworkResult {
            framework: self.framework.clone(),
            prompts,
            insights: vec!["Question your assumptions and examine evidence".to_string()],
            metadata: Some(serde_json::json!({
                "method": "questioning",
                "focus": "assumptions_and_evidence"
            })),
        }
    }

    /// First Principles framework
    fn process_first_principles(&self, thought: &str) -> FrameworkResult {
        let prompts = vec![
            "What are the fundamental facts that are certainly true?".to_string(),
            "What am I assuming that might not be true?".to_string(),
            "Can I break this down into more basic components?".to_string(),
            "What would I conclude if I reasoned from these fundamentals?".to_string(),
        ];

        FrameworkResult {
            framework: self.framework.clone(),
            prompts,
            insights: vec!["Break down to fundamental truths and reason upward".to_string()],
            metadata: Some(serde_json::json!({
                "approach": "deconstruction",
                "goal": "fundamental_understanding"
            })),
        }
    }

    /// Systems Thinking framework
    fn process_systems(&self, thought: &str) -> FrameworkResult {
        let prompts = vec![
            "What other elements or systems does this connect to?".to_string(),
            "What are the feedback loops and interconnections?".to_string(),
            "How might changes here affect other parts of the system?".to_string(),
            "What emergent properties arise from these relationships?".to_string(),
        ];

        FrameworkResult {
            framework: self.framework.clone(),
            prompts,
            insights: vec!["Consider interconnections and system-wide effects".to_string()],
            metadata: Some(serde_json::json!({
                "perspective": "holistic",
                "focus": "interconnections"
            })),
        }
    }

    /// Root Cause Analysis (Five Whys) framework
    fn process_root_cause(&self, thought: &str, thought_number: i32) -> FrameworkResult {
        let why_number = std::cmp::min(thought_number, 5);
        let prompt = format!("Why #{}: Why is this happening? (Dig deeper into the root cause)", why_number);

        let prompts = vec![
            prompt,
            "What evidence supports this cause?".to_string(),
        ];

        FrameworkResult {
            framework: self.framework.clone(),
            prompts,
            insights: vec![format!("Root cause analysis - Why #{}", why_number)],
            metadata: Some(serde_json::json!({
                "why_number": why_number,
                "method": "five_whys"
            })),
        }
    }

    /// SWOT Analysis framework
    fn process_swot(&self, thought: &str) -> FrameworkResult {
        let prompts = vec![
            "Strengths: What advantages or positive aspects are present?".to_string(),
            "Weaknesses: What limitations or negative aspects exist?".to_string(),
            "Opportunities: What external factors could be beneficial?".to_string(),
            "Threats: What external factors could be harmful?".to_string(),
        ];

        FrameworkResult {
            framework: self.framework.clone(),
            prompts,
            insights: vec!["Analyze internal and external factors systematically".to_string()],
            metadata: Some(serde_json::json!({
                "quadrants": ["strengths", "weaknesses", "opportunities", "threats"],
                "perspective": "strategic"
            })),
        }
    }
}

/// Result of framework processing
#[derive(Debug)]
pub struct FrameworkResult {
    pub framework: ThinkingFramework,
    pub prompts: Vec<String>,
    pub insights: Vec<String>,
    pub metadata: Option<serde_json::Value>,
}

/// Visual display for frameworks
pub struct FrameworkVisual;

impl FrameworkVisual {
    /// Display framework information with colored output
    pub fn display_framework_start(framework: &ThinkingFramework) {
        let icon = match framework {
            ThinkingFramework::Sequential => "🧠",
            ThinkingFramework::OODA => "🎯",
            ThinkingFramework::Socratic => "❓",
            ThinkingFramework::FirstPrinciples => "🔬",
            ThinkingFramework::Systems => "🌐",
            ThinkingFramework::RootCause => "🔍",
            ThinkingFramework::SWOT => "📊",
        };

        if framework != &ThinkingFramework::Sequential {
            println!("   {} {}", 
                icon.bright_purple(),
                format!("[{}]", framework.name()).bright_purple()
            );
        }
    }

    /// Display framework prompts
    pub fn display_prompts(prompts: &[String]) {
        if !prompts.is_empty() {
            println!("   {} {}", 
                "💭".bright_cyan(),
                "Framework prompts:".bright_cyan()
            );
            for (i, prompt) in prompts.iter().enumerate() {
                println!("      {}. {}", 
                    (i + 1).to_string().cyan(),
                    prompt.white()
                );
            }
        }
    }

    /// Display framework insights
    pub fn display_insights(insights: &[String]) {
        if !insights.is_empty() {
            for insight in insights {
                println!("   {} {}", 
                    "💡".bright_yellow(),
                    insight.yellow()
                );
            }
        }
    }
}