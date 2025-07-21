use crate::error::ObsidianResult;
use config::{Config, Environment, File};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

/// ObsidianMCP service configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ObsidianMcpConfig {
    /// Vault configuration
    pub vault: VaultConfig,
    /// Redis configuration for Federation integration
    pub redis: Option<RedisConfig>,
    /// Server configuration
    pub server: ServerConfig,
}

/// Vault-specific configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VaultConfig {
    /// Root path of the Obsidian vault
    pub root_path: PathBuf,
    /// Name of the vault for generating obsidian:// URLs
    pub vault_name: String,
    /// Allowed file extensions for operations
    pub allowed_extensions: Vec<String>,
    /// Maximum file size in bytes for operations
    pub max_file_size: u64,
    /// Whether to enable file watching for changes
    pub enable_watching: bool,
    /// Whether to parse and include wikilinks in search results
    pub enable_wikilinks: bool,
}

/// Redis configuration for Federation integration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RedisConfig {
    /// Redis connection URL
    pub url: String,
    /// Connection pool size
    pub pool_size: u32,
    /// Key prefix for this MCP instance
    pub key_prefix: String,
}

/// Server configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerConfig {
    /// Server name/identifier
    pub name: String,
    /// Server version
    pub version: String,
}

impl Default for ObsidianMcpConfig {
    fn default() -> Self {
        Self {
            vault: VaultConfig::default(),
            redis: None,
            server: ServerConfig::default(),
        }
    }
}

impl Default for VaultConfig {
    fn default() -> Self {
        Self {
            root_path: PathBuf::from("./vault"),
            vault_name: "ObsidianVault".to_string(),
            allowed_extensions: vec![
                "md".to_string(),
                "txt".to_string(),
                "json".to_string(),
                "yaml".to_string(),
                "yml".to_string(),
            ],
            max_file_size: 10 * 1024 * 1024, // 10MB
            enable_watching: false,
            enable_wikilinks: true,
        }
    }
}

impl Default for ServerConfig {
    fn default() -> Self {
        Self {
            name: "ObsidianMCP".to_string(),
            version: env!("CARGO_PKG_VERSION").to_string(),
        }
    }
}

impl ObsidianMcpConfig {
    /// Load configuration from various sources
    pub fn load() -> ObsidianResult<Self> {
        // Check for OBSIDIAN_VAULT_PATH environment variable first (Claude Desktop standard)
        let default_vault_path = if let Ok(vault_path) = std::env::var("OBSIDIAN_VAULT_PATH") {
            tracing::info!("Using OBSIDIAN_VAULT_PATH: {}", vault_path);
            vault_path
        } else {
            tracing::warn!("OBSIDIAN_VAULT_PATH not set, using default: ./vault");
            "./vault".to_string()
        };

        let mut config = Config::builder()
            // Start with defaults
            .set_default("vault.root_path", default_vault_path)?
            .set_default("vault.vault_name", "LegacyMind_Vault")?
            .set_default("vault.allowed_extensions", vec!["md", "txt", "json", "yaml", "yml"])?
            .set_default("vault.max_file_size", 10 * 1024 * 1024)?
            .set_default("vault.enable_watching", false)?
            .set_default("vault.enable_wikilinks", true)?
            .set_default("server.name", "ObsidianMCP")?
            .set_default("server.version", env!("CARGO_PKG_VERSION"))?;

        // Add configuration file if it exists
        if let Ok(config_file) = std::env::var("OBSIDIAN_MCP_CONFIG") {
            config = config.add_source(File::with_name(&config_file).required(false));
        } else {
            config = config.add_source(File::with_name("obsidian-mcp.toml").required(false));
        }

        // Add environment variables (with OBSIDIAN_MCP_ prefix)
        config = config.add_source(Environment::with_prefix("OBSIDIAN_MCP").separator("_"));

        let config = config.build()?;
        Ok(config.try_deserialize()?)
    }

    /// Validate configuration
    pub fn validate(&self) -> ObsidianResult<()> {
        // Check if vault path exists
        if !self.vault.root_path.exists() {
            return Err(crate::error::ObsidianMcpError::InvalidVaultPath {
                path: format!("Vault path does not exist: {}", self.vault.root_path.display()),
            });
        }

        // Validate that the path is actually a directory
        if !self.vault.root_path.is_dir() {
            return Err(crate::error::ObsidianMcpError::InvalidVaultPath {
                path: format!("Vault path is not a directory: {}", self.vault.root_path.display()),
            });
        }

        // Check if we have read access to the vault
        if let Err(e) = std::fs::read_dir(&self.vault.root_path) {
            return Err(crate::error::ObsidianMcpError::InvalidVaultPath {
                path: format!("Cannot read vault directory {}: {}", self.vault.root_path.display(), e),
            });
        }

        tracing::info!("Vault configuration validated successfully: {}", self.vault.root_path.display());
        Ok(())
    }
}