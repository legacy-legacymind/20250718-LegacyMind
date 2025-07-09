use anyhow::Result;
use crate::storage::FrameworkAnalysis;

pub struct FrameworkDetector;

impl FrameworkDetector {
    pub async fn detect(content: &str) -> String {
        let lower = content.to_lowercase();
        
        // OODA Loop detection - decision making and task execution
        if lower.contains("next step") || lower.contains("execute") || 
           lower.contains("decide") || lower.contains("action") {
            return "ooda".to_string();
        }
        
        // Socratic method - learning and conversation
        if lower.contains("understand") || lower.contains("learn") || 
           lower.contains("question") || lower.contains("why") {
            return "socratic".to_string();
        }
        
        // First principles - breaking down complex problems
        if lower.contains("fundamental") || lower.contains("basic") || 
           lower.contains("core") || lower.contains("essence") {
            return "first-principles".to_string();
        }
        
        // 5 Whys - root cause analysis
        if lower.contains("root cause") || lower.contains("debug") || 
           lower.contains("problem") || lower.contains("issue") {
            return "5whys".to_string();
        }
        
        // SWOT analysis - strategic evaluation
        if lower.contains("pros and cons") || lower.contains("evaluate") || 
           lower.contains("strengths") || lower.contains("weaknesses") ||
           lower.contains("opportunities") || lower.contains("threats") {
            return "swot".to_string();
        }
        
        // Devil's advocate - challenging assumptions
        if lower.contains("challenge") || lower.contains("assume") || 
           lower.contains("opposite") || lower.contains("wrong") {
            return "devils-advocate".to_string();
        }
        
        // Lateral thinking - creative problem solving
        if lower.contains("creative") || lower.contains("innovative") || 
           lower.contains("different approach") || lower.contains("think outside") {
            return "lateral".to_string();
        }
        
        // Systems thinking - holistic analysis
        if lower.contains("system") || lower.contains("holistic") || 
           lower.contains("interconnected") || lower.contains("feedback") {
            return "systems".to_string();
        }
        
        // Six hats - multiple perspectives
        if lower.contains("different angles") || lower.contains("perspectives") || 
           lower.contains("viewpoints") || lower.contains("multiple views") {
            return "six-hats".to_string();
        }
        
        "general".to_string()
    }
    
    pub async fn apply(content: &str, framework: &str) -> Result<FrameworkAnalysis> {
        match framework {
            "ooda" => Self::apply_ooda(content).await,
            "socratic" => Self::apply_socratic(content).await,
            "first-principles" => Self::apply_first_principles(content).await,
            "5whys" => Self::apply_5whys(content).await,
            "swot" => Self::apply_swot(content).await,
            "devils-advocate" => Self::apply_devils_advocate(content).await,
            "lateral" => Self::apply_lateral(content).await,
            "systems" => Self::apply_systems(content).await,
            "six-hats" => Self::apply_six_hats(content).await,
            _ => Self::apply_general(content).await,
        }
    }
    
    async fn apply_ooda(content: &str) -> Result<FrameworkAnalysis> {
        let insights = vec![
            "🔍 OBSERVE: What data do you have about this situation?".to_string(),
            "🧭 ORIENT: How does this fit with your current understanding?".to_string(),
            "🎯 DECIDE: What are your options and what's the best course?".to_string(),
            "⚡ ACT: What's your next concrete step?".to_string(),
            format!("Applied to: {}", content),
        ];
        
        Ok(FrameworkAnalysis {
            framework: "ooda".to_string(),
            insights,
            confidence: 0.85,
            metadata: serde_json::json!({
                "tags": ["decision", "action", "execution"],
                "steps": ["Observe", "Orient", "Decide", "Act"],
                "best_for": ["task", "decision"]
            }),
        })
    }

    async fn apply_socratic(content: &str) -> Result<FrameworkAnalysis> {
        let insights = vec![
            "❓ QUESTION: What are you trying to understand? What's unclear?".to_string(),
            "🔍 EXAMINE: What assumptions are you making? Are they valid?".to_string(),
            "⚔️ CHALLENGE: What if the opposite were true? What evidence exists?".to_string(),
            "✨ REFINE: What's the clearest way to state this? What did you learn?".to_string(),
            format!("Applied to: {}", content),
        ];
        
        Ok(FrameworkAnalysis {
            framework: "socratic".to_string(),
            insights,
            confidence: 0.82,
            metadata: serde_json::json!({
                "tags": ["learning", "questioning", "understanding"],
                "steps": ["Question", "Examine", "Challenge", "Refine"],
                "best_for": ["learn", "conversation"]
            }),
        })
    }

    async fn apply_first_principles(content: &str) -> Result<FrameworkAnalysis> {
        let insights = vec![
            "🧩 BREAK DOWN: What are the components? How can you decompose this?".to_string(),
            "⚛️ FUNDAMENTALS: What are the basic truths? What can't be reduced further?".to_string(),
            "🔨 REBUILD: How do these pieces fit together? What new solution emerges?".to_string(),
            format!("Applied to: {}", content),
        ];
        
        Ok(FrameworkAnalysis {
            framework: "first-principles".to_string(),
            insights,
            confidence: 0.88,
            metadata: serde_json::json!({
                "tags": ["fundamental", "decomposition", "rebuild"],
                "steps": ["Break Down", "Identify Fundamentals", "Rebuild"],
                "best_for": ["design", "debug"]
            }),
        })
    }

    async fn apply_5whys(content: &str) -> Result<FrameworkAnalysis> {
        let insights = vec![
            "❓ WHY 1: Why did this happen?".to_string(),
            "❓ WHY 2: Why did that cause occur?".to_string(),
            "❓ WHY 3: Why did that underlying issue exist?".to_string(),
            "❓ WHY 4: Why wasn't that prevented?".to_string(),
            "❓ WHY 5: What's the root cause?".to_string(),
            format!("Applied to: {}", content),
        ];
        
        Ok(FrameworkAnalysis {
            framework: "5whys".to_string(),
            insights,
            confidence: 0.9,
            metadata: serde_json::json!({
                "tags": ["root-cause", "debugging", "analysis"],
                "steps": ["Why 1", "Why 2", "Why 3", "Why 4", "Why 5"],
                "best_for": ["debug", "problem-solving"]
            }),
        })
    }

    async fn apply_devils_advocate(content: &str) -> Result<FrameworkAnalysis> {
        let insights = vec![
            "📝 STATE POSITION: What's your current position or belief?".to_string(),
            "⚔️ CHALLENGE: What if you're wrong? What's the opposite view?".to_string(),
            "🛡️ COUNTER-ARGUE: How would you defend against these challenges?".to_string(),
            "⚖️ SYNTHESIZE: What truth emerges from both perspectives?".to_string(),
            format!("Applied to: {}", content),
        ];
        
        Ok(FrameworkAnalysis {
            framework: "devils-advocate".to_string(),
            insights,
            confidence: 0.8,
            metadata: serde_json::json!({
                "tags": ["challenge", "assumptions", "perspective"],
                "steps": ["State Position", "Challenge", "Counter-argue", "Synthesize"],
                "best_for": ["decision", "design"]
            }),
        })
    }

    async fn apply_lateral(content: &str) -> Result<FrameworkAnalysis> {
        let insights = vec![
            "🎯 DEFINE PROBLEM: What problem are you trying to solve?".to_string(),
            "🎲 RANDOM INPUT: Pick a random concept. How might it relate?".to_string(),
            "🔗 CONNECT: What unexpected connections can you make?".to_string(),
            "🚀 DEVELOP: How can this new perspective solve the problem?".to_string(),
            format!("Applied to: {}", content),
        ];
        
        Ok(FrameworkAnalysis {
            framework: "lateral".to_string(),
            insights,
            confidence: 0.75,
            metadata: serde_json::json!({
                "tags": ["creative", "innovative", "indirect"],
                "steps": ["Define Problem", "Random Input", "Connect", "Develop"],
                "best_for": ["design", "creative-problem-solving"]
            }),
        })
    }

    async fn apply_systems(content: &str) -> Result<FrameworkAnalysis> {
        let insights = vec![
            "🧩 COMPONENTS: What are the key parts of this system?".to_string(),
            "🔗 CONNECTIONS: How do these parts interact? What are the relationships?".to_string(),
            "⚡ DYNAMICS: What feedback loops exist? What drives change?".to_string(),
            "✨ EMERGENCE: What behaviors emerge from the whole system?".to_string(),
            format!("Applied to: {}", content),
        ];
        
        Ok(FrameworkAnalysis {
            framework: "systems".to_string(),
            insights,
            confidence: 0.87,
            metadata: serde_json::json!({
                "tags": ["holistic", "interconnected", "emergence"],
                "steps": ["Identify Components", "Map Connections", "Understand Dynamics", "See Emergence"],
                "best_for": ["complex-systems", "strategy"]
            }),
        })
    }
    
    async fn apply_swot(content: &str) -> Result<FrameworkAnalysis> {
        let insights = vec![
            "💪 STRENGTHS: What are the strong points? What works well?".to_string(),
            "⚠️ WEAKNESSES: What are the limitations? Where are the gaps?".to_string(),
            "🚀 OPPORTUNITIES: What possibilities exist? What could be leveraged?".to_string(),
            "⚡ THREATS: What risks exist? What could go wrong?".to_string(),
            format!("Applied to: {}", content),
        ];
        
        Ok(FrameworkAnalysis {
            framework: "swot".to_string(),
            insights,
            confidence: 0.85,
            metadata: serde_json::json!({
                "tags": ["strategic", "evaluation", "comprehensive"],
                "steps": ["Strengths", "Weaknesses", "Opportunities", "Threats"],
                "best_for": ["strategy", "decision-making"]
            }),
        })
    }
    
    async fn apply_six_hats(content: &str) -> Result<FrameworkAnalysis> {
        let insights = vec![
            "🤍 WHITE HAT: Facts and information - What do we know?".to_string(),
            "❤️ RED HAT: Emotions and intuition - What do we feel?".to_string(),
            "🖤 BLACK HAT: Critical judgment - What could go wrong?".to_string(),
            "💛 YELLOW HAT: Positive assessment - What are the benefits?".to_string(),
            "💚 GREEN HAT: Creative alternatives - What are new ideas?".to_string(),
            "💙 BLUE HAT: Process control - How do we manage this thinking?".to_string(),
            format!("Applied to: {}", content),
        ];
        
        Ok(FrameworkAnalysis {
            framework: "six-hats".to_string(),
            insights,
            confidence: 0.9,
            metadata: serde_json::json!({
                "tags": ["perspective", "comprehensive", "multi-angle"],
                "steps": ["White Hat", "Red Hat", "Black Hat", "Yellow Hat", "Green Hat", "Blue Hat"],
                "best_for": ["group-thinking", "comprehensive-analysis"]
            }),
        })
    }
    
    async fn apply_general(content: &str) -> Result<FrameworkAnalysis> {
        let insights = vec![
            format!("Analyzing: {}", content),
            "General cognitive processing applied".to_string(),
        ];
        
        Ok(FrameworkAnalysis {
            framework: "general".to_string(),
            insights,
            confidence: 0.5,
            metadata: serde_json::json!({
                "tags": ["general", "analysis"]
            }),
        })
    }
}