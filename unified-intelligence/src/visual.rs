use colored::*;

/// Visual output module for unified-intelligence MCP
/// Provides colored console output similar to Sequential Thinking
pub struct VisualOutput;

impl VisualOutput {
    /// Initialize visual output system
    pub fn new() -> Self {
        Self
    }

    /// Display thought storage beginning with instance
    pub fn thought_start(&self, thought_number: i32, total_thoughts: i32, instance_id: &str) {
        eprintln!("DEBUG: thought_start called with instance_id: '{}'", instance_id);
        println!("{} {} {}{}{}", 
            "🧠".blue(),
            format!("[{}]", instance_id).bright_magenta(),
            "Thought ".bright_blue(),
            format!("{}/{}", thought_number, total_thoughts).bright_white(),
            ":".bright_blue()
        );
    }

    /// Display thought content with indentation
    pub fn thought_content(&self, content: &str) {
        // Wrap long content lines
        let max_width = 80;
        for line in content.lines() {
            if line.len() <= max_width {
                println!("   {}", line.white());
            } else {
                // Simple word wrap
                let words: Vec<&str> = line.split_whitespace().collect();
                let mut current_line = String::new();
                
                for word in words {
                    if current_line.len() + word.len() + 1 <= max_width {
                        if !current_line.is_empty() {
                            current_line.push(' ');
                        }
                        current_line.push_str(word);
                    } else {
                        if !current_line.is_empty() {
                            println!("   {}", current_line.white());
                            current_line = word.to_string();
                        } else {
                            println!("   {}", word.white());
                        }
                    }
                }
                if !current_line.is_empty() {
                    println!("   {}", current_line.white());
                }
            }
        }
    }

    /// Display chain information
    pub fn chain_info(&self, chain_id: &str, is_new: bool) {
        if is_new {
            println!("   {} {}", 
                "⛓️".green(),
                format!("New chain: {}", Self::truncate_uuid(chain_id)).bright_green()
            );
        } else {
            println!("   {} {}", 
                "⛓️".green(),
                format!("Chain: {}", Self::truncate_uuid(chain_id)).green()
            );
        }
    }

    /// Display thought storage success with instance
    pub fn thought_stored(&self, thought_id: &str, instance_id: &str) {
        eprintln!("DEBUG: thought_stored called with instance_id: '{}'", instance_id);
        println!("   {} {} {}", 
            "✅".bright_green(),
            format!("[{}]", instance_id).bright_magenta(),
            format!("Stored: {}", Self::truncate_uuid(thought_id)).green()
        );
    }

    /// Display error messages
    pub fn error(&self, message: &str) {
        println!("   {} {}", 
            "❌".red(),
            message.red()
        );
    }

    /// Display search results count
    #[allow(dead_code)]
    pub fn search_results(&self, count: usize, query: &str) {
        if count > 0 {
            println!("{} {} {}", 
                "🔍".yellow(),
                format!("Found {} thoughts", count).bright_yellow(),
                format!("for: {}", query).yellow()
            );
        } else {
            println!("{} {}", 
                "🔍".yellow(),
                format!("No thoughts found for: {}", query).yellow()
            );
        }
    }

    /// Display thinking completion
    pub fn thinking_complete(&self) {
        println!("   {} {}", 
            "🎯".bright_blue(),
            "Thinking complete".bright_blue()
        );
    }

    /// Display next thought needed indicator
    pub fn next_thought_indicator(&self, next_needed: bool) {
        if next_needed {
            println!("   {} {}", 
                "➡️".bright_cyan(),
                "Next thought needed...".bright_cyan()
            );
        }
    }

    /// Truncate UUID for display (show first 8 characters)
    fn truncate_uuid(uuid: &str) -> String {
        if uuid.len() > 8 {
            format!("{}...", &uuid[..8])
        } else {
            uuid.to_string()
        }
    }

    /// Progress bar for sequential thinking
    pub fn progress_bar(&self, current: i32, total: i32) {
        let progress = (current as f32 / total as f32 * 20.0) as usize;
        let filled = "█".repeat(progress);
        let empty = "░".repeat(20 - progress);
        
        println!("   {} [{}{}] {}/{}", 
            "📊".bright_blue(),
            filled.bright_blue(),
            empty.dimmed(),
            current,
            total
        );
    }
}