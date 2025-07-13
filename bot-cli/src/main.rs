use clap::{Parser, Subcommand};
use colored::*;
use redis::Commands;
use rustyline::DefaultEditor;
use serde::{Deserialize, Serialize};
use std::error::Error;

#[derive(Parser)]
#[command(name = "bot")]
#[command(about = "CLI for local Ollama LLM with memory", long_about = None)]
struct Cli {
    /// Model to use
    #[arg(short, long, default_value = "qwen2.5-coder:1.5b")]
    model: String,

    /// Session ID for memory continuity
    #[arg(short, long, default_value = "default")]
    session: String,

    /// Single prompt mode
    #[arg(short, long)]
    prompt: Option<String>,

    /// File to use as context
    #[arg(short, long)]
    file: Option<String>,

    /// Disable session context
    #[arg(long)]
    no_context: bool,

    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand)]
enum Commands {
    /// Interactive chat mode
    Chat,
    /// List all sessions
    Sessions,
    /// Clear current session
    Clear,
    /// Show session context
    Context,
}

#[derive(Serialize)]
struct OllamaRequest {
    model: String,
    prompt: String,
    stream: bool,
    options: OllamaOptions,
}

#[derive(Serialize)]
struct OllamaOptions {
    temperature: f32,
    top_p: f32,
}

#[derive(Deserialize)]
struct OllamaResponse {
    response: String,
}

struct Bot {
    model: String,
    session: String,
    redis: redis::Client,
    ollama_url: String,
    redis_prefix: String,
}

impl Bot {
    fn new(model: String, session: String) -> Result<Self, Box<dyn Error>> {
        let redis = redis::Client::open("redis://127.0.0.1/")?;
        
        Ok(Bot {
            model,
            session,
            redis,
            ollama_url: "http://localhost:11434/api/generate".to_string(),
            redis_prefix: "Bot/cli".to_string(),
        })
    }

    fn get_session_context(&self, max_chars: usize) -> Result<String, Box<dyn Error>> {
        let mut conn = self.redis.get_connection()?;
        let key = format!("{}/sessions/{}", self.redis_prefix, self.session);
        let context: Option<String> = conn.get(&key)?;
        
        match context {
            Some(ctx) if ctx.len() > max_chars => {
                // Return last N characters of context
                Ok(format!("...{}", &ctx[ctx.len() - max_chars..]))
            }
            Some(ctx) => Ok(ctx),
            None => Ok(String::new()),
        }
    }

    fn save_interaction(&self, prompt: &str, response: &str) -> Result<(), Box<dyn Error>> {
        let mut conn = self.redis.get_connection()?;
        
        // Append to session
        let session_key = format!("{}/sessions/{}", self.redis_prefix, self.session);
        let interaction = format!("\nUSER: {}\nBOT: {}\n---", prompt, response);
        let _: () = conn.append(&session_key, &interaction)?;
        
        // Log interaction
        let timestamp = chrono::Utc::now().timestamp();
        let log_key = format!("{}/logs/{}", self.redis_prefix, timestamp);
        let log_data = serde_json::json!({
            "session": self.session,
            "model": self.model,
            "prompt": prompt,
            "response": response,
            "timestamp": chrono::Utc::now().to_rfc3339()
        });
        let _: () = conn.set(&log_key, log_data.to_string())?;
        
        Ok(())
    }

    fn generate(&self, prompt: &str, include_context: bool) -> Result<String, Box<dyn Error>> {
        let full_prompt = if include_context {
            let context = self.get_session_context(2000)?;
            if !context.is_empty() {
                format!("Previous conversation:\n{}\n\nUser: {}", context, prompt)
            } else {
                prompt.to_string()
            }
        } else {
            prompt.to_string()
        };

        let request = OllamaRequest {
            model: self.model.clone(),
            prompt: full_prompt,
            stream: false,
            options: OllamaOptions {
                temperature: 0.7,
                top_p: 0.9,
            },
        };

        let client = reqwest::blocking::Client::new();
        let response = client
            .post(&self.ollama_url)
            .json(&request)
            .send()?;

        if response.status().is_success() {
            let ollama_response: OllamaResponse = response.json()?;
            Ok(ollama_response.response)
        } else {
            Err(format!("Ollama error: {}", response.status()).into())
        }
    }

    fn interactive_mode(&self) -> Result<(), Box<dyn Error>> {
        println!("{}", "Bot CLI - Interactive Mode".green());
        println!("{}: {}", "Model".blue(), self.model);
        println!("{}: {}", "Session".blue(), self.session);
        println!("Type 'help' for commands, 'exit' to quit\n");

        let mut rl = DefaultEditor::new()?;
        
        loop {
            let readline = rl.readline(&format!("{}: ", "You".yellow()));
            
            match readline {
                Ok(line) => {
                    if line.trim().is_empty() {
                        continue;
                    }
                    
                    // Handle commands
                    match line.trim() {
                        "exit" | "quit" => break,
                        "help" => {
                            self.print_help();
                            continue;
                        }
                        "clear" => {
                            print!("\x1B[2J\x1B[1;1H");
                            continue;
                        }
                        "context" => {
                            let context = self.get_session_context(1000)?;
                            if !context.is_empty() {
                                println!("{}", "Session context:".blue());
                                println!("{}", context);
                            } else {
                                println!("No context in current session");
                            }
                            continue;
                        }
                        _ => {}
                    }
                    
                    // Generate response
                    print!("{}: ", "Bot".green());
                    match self.generate(&line, true) {
                        Ok(response) => {
                            println!("{}\n", response);
                            self.save_interaction(&line, &response)?;
                        }
                        Err(e) => {
                            println!("{}: {}\n", "Error".red(), e);
                        }
                    }
                    
                    // Add to history
                    rl.add_history_entry(&line)?;
                }
                Err(rustyline::error::ReadlineError::Interrupted) => {
                    println!("Use 'exit' to quit");
                    continue;
                }
                Err(rustyline::error::ReadlineError::Eof) => break,
                Err(err) => {
                    println!("Error: {:?}", err);
                    break;
                }
            }
        }
        
        println!("Goodbye!");
        Ok(())
    }

    fn print_help(&self) {
        println!("Commands:");
        println!("  help     - Show this help");
        println!("  exit     - Exit the program");
        println!("  clear    - Clear screen");
        println!("  context  - Show session context");
    }

    fn list_sessions(&self) -> Result<(), Box<dyn Error>> {
        let mut conn = self.redis.get_connection()?;
        let pattern = format!("{}/sessions/*", self.redis_prefix);
        let keys: Vec<String> = conn.keys(pattern)?;
        
        println!("{}", "Active sessions:".blue());
        for key in keys {
            let session_id = key.split('/').last().unwrap_or(&key);
            println!("  - {}", session_id);
        }
        
        Ok(())
    }

    fn clear_session(&self) -> Result<(), Box<dyn Error>> {
        let mut conn = self.redis.get_connection()?;
        let key = format!("{}/sessions/{}", self.redis_prefix, self.session);
        let _: () = conn.del(&key)?;
        println!("Session '{}' cleared", self.session);
        Ok(())
    }
}

fn main() -> Result<(), Box<dyn Error>> {
    let cli = Cli::parse();
    let bot = Bot::new(cli.model, cli.session)?;

    // Handle single prompt mode
    if let Some(prompt) = cli.prompt {
        let response = bot.generate(&prompt, !cli.no_context)?;
        println!("{}", response);
        if !cli.no_context {
            bot.save_interaction(&prompt, &response)?;
        }
        return Ok(());
    }

    // Handle file mode
    if let Some(file_path) = cli.file {
        let content = std::fs::read_to_string(&file_path)?;
        let prompt = format!("File: {}\n\n{}\n\nAnalyze this file.", file_path, content);
        let response = bot.generate(&prompt, false)?;
        println!("{}", response);
        return Ok(());
    }

    // Handle subcommands
    match cli.command {
        Some(Commands::Chat) | None => {
            bot.interactive_mode()?;
        }
        Some(Commands::Sessions) => {
            bot.list_sessions()?;
        }
        Some(Commands::Clear) => {
            bot.clear_session()?;
        }
        Some(Commands::Context) => {
            let context = bot.get_session_context(2000)?;
            if !context.is_empty() {
                println!("{}", context);
            } else {
                println!("No context in current session");
            }
        }
    }

    Ok(())
}