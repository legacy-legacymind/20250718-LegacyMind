use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use schemars::JsonSchema;

/// Represents a file or note in the Obsidian vault
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct VaultFile {
    /// Relative path from vault root
    pub path: String,
    /// File content (for text files)
    pub content: Option<String>,
    /// File metadata
    pub metadata: FileMetadata,
    /// Whether this is a directory
    pub is_directory: bool,
}

/// File metadata information
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct FileMetadata {
    /// File size in bytes
    pub size: u64,
    /// Creation timestamp
    pub created: DateTime<Utc>,
    /// Last modified timestamp
    pub modified: DateTime<Utc>,
    /// File extension
    pub extension: Option<String>,
}

/// Search parameters for vault operations with embedded help
#[derive(Debug, Deserialize, JsonSchema)]
pub struct SearchParams {
    /// Search query string (use "help" to show search help)
    pub query: String,
    /// Optional path prefix to limit search scope
    pub path_prefix: Option<String>,
    /// Include file content in results
    #[serde(default)]
    pub include_content: bool,
    /// Maximum number of results
    #[serde(default = "default_limit")]
    pub limit: usize,
    /// File extensions to include (e.g., ["md", "txt"])
    pub extensions: Option<Vec<String>>,
}

fn default_limit() -> usize {
    50
}

/// Parameters for creating a new file
#[derive(Debug, Deserialize, JsonSchema)]
pub struct CreateFileParams {
    /// Relative path where to create the file
    pub path: String,
    /// File content
    pub content: String,
    /// Whether to create parent directories if they don't exist
    #[serde(default = "default_true")]
    pub create_dirs: bool,
    /// Whether to overwrite if file exists
    #[serde(default)]
    pub overwrite: bool,
}

/// Parameters for updating an existing file
#[derive(Debug, Deserialize, JsonSchema)]
pub struct UpdateFileParams {
    /// Relative path of the file to update
    pub path: String,
    /// New content for the file
    pub content: String,
    /// Whether to create the file if it doesn't exist
    #[serde(default)]
    pub create_if_missing: bool,
}

/// Parameters for moving/renaming files
#[derive(Debug, Deserialize, JsonSchema)]
pub struct MoveFileParams {
    /// Source path
    pub from_path: String,
    /// Destination path
    pub to_path: String,
    /// Whether to overwrite destination if it exists
    #[serde(default)]
    pub overwrite: bool,
}

/// Parameters for deleting files
#[derive(Debug, Deserialize, JsonSchema)]
pub struct DeleteFileParams {
    /// Path of the file to delete
    pub path: String,
    /// Whether to delete directories recursively
    #[serde(default)]
    pub recursive: bool,
}

/// Search results container
#[derive(Debug, Serialize, JsonSchema)]
pub struct SearchResults {
    /// List of matching files
    pub files: Vec<VaultFile>,
    /// Total number of matches (may be higher than files.len() due to limit)
    pub total_matches: usize,
    /// Search query used
    pub query: String,
}

/// Vault configuration and status
#[derive(Debug, Serialize, JsonSchema)]
pub struct VaultInfo {
    /// Vault root path
    pub root_path: String,
    /// Total number of files
    pub file_count: usize,
    /// Total vault size in bytes
    pub total_size: u64,
    /// Vault configuration status
    pub is_valid: bool,
}

fn default_true() -> bool {
    true
}

/// Operation modes for the browse tool
#[derive(Debug, Deserialize, JsonSchema)]
#[serde(rename_all = "lowercase")]
pub enum BrowseOperation {
    /// Browse/read files or directories (default)
    Browse,
    /// Create a new file
    Create,
    /// Update an existing file
    Update,
    /// Delete a file or directory
    Delete,
    /// Move or rename a file/directory
    Move,
    /// Show help for browse operations
    Help,
}

impl Default for BrowseOperation {
    fn default() -> Self {
        BrowseOperation::Browse
    }
}

/// Parameters for browsing and file operations with embedded modes
#[derive(Debug, Deserialize, JsonSchema)]
pub struct BrowseParams {
    /// Path to operate on (file or directory)
    pub path: String,
    /// Operation to perform
    #[serde(default)]
    pub operation: BrowseOperation,
    /// Include file content for files (browse mode)
    #[serde(default = "default_true")]
    pub include_content: bool,
    /// File content for create/update operations
    pub content: Option<String>,
    /// Destination path for move operations
    pub to_path: Option<String>,
    /// Whether to create parent directories if they don't exist (create mode)
    #[serde(default = "default_true")]
    pub create_dirs: bool,
    /// Whether to overwrite if file exists (create/move modes)
    #[serde(default)]
    pub overwrite: bool,
    /// Whether to create file if it doesn't exist (update mode)
    #[serde(default)]
    pub create_if_missing: bool,
    /// Whether to delete directories recursively (delete mode)
    #[serde(default)]
    pub recursive: bool,
}

/// Result of a browse operation
#[derive(Debug, Serialize, JsonSchema)]
pub struct BrowseResult {
    /// The path that was browsed
    pub path: String,
    /// Whether the path is a directory
    pub is_directory: bool,
    /// Directory contents (if directory)
    pub files: Option<Vec<VaultFile>>,
    /// File content (if file)
    pub content: Option<VaultFile>,
}

/// Help information for search operations
#[derive(Debug, Serialize, JsonSchema)]
pub struct SearchHelp {
    pub tool_name: String,
    pub description: String,
    pub parameters: Vec<ParameterHelp>,
    pub examples: Vec<SearchExample>,
    pub tips: Vec<String>,
}

/// Help information for browse operations
#[derive(Debug, Serialize, JsonSchema)]
pub struct BrowseHelp {
    pub tool_name: String,
    pub description: String,
    pub operations: Vec<OperationHelp>,
    pub examples: Vec<BrowseExample>,
    pub tips: Vec<String>,
}

/// Parameter help information
#[derive(Debug, Serialize, JsonSchema)]
pub struct ParameterHelp {
    pub name: String,
    pub description: String,
    pub required: bool,
    pub example: Option<String>,
}

/// Operation help information
#[derive(Debug, Serialize, JsonSchema)]
pub struct OperationHelp {
    pub operation: String,
    pub description: String,
    pub required_params: Vec<String>,
    pub optional_params: Vec<String>,
}

/// Search usage examples
#[derive(Debug, Serialize, JsonSchema)]
pub struct SearchExample {
    pub description: String,
    pub query: String,
    pub additional_params: Option<serde_json::Value>,
}

/// Browse usage examples
#[derive(Debug, Serialize, JsonSchema)]
pub struct BrowseExample {
    pub description: String,
    pub operation: String,
    pub params: serde_json::Value,
}