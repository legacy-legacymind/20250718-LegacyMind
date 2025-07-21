use crate::config::ObsidianMcpConfig;
use crate::error::ObsidianResult;
use crate::vault::VaultManager;
use rmcp::{
    handler::server::{router::tool::ToolRouter, tool::Parameters},
    model::{CallToolResult, Content, ErrorData, ServerCapabilities, ServerInfo},
    ServerHandler,
};
use rmcp_macros::{tool, tool_router, tool_handler};
use std::{future::Future, sync::Arc};

use crate::models::*;

/// The main ObsidianMCP service
#[derive(Clone)]
pub struct ObsidianMcpService {
    tool_router: ToolRouter<Self>,
    vault_manager: Arc<VaultManager>,
    config: ObsidianMcpConfig,
}

impl ObsidianMcpService {
    /// Create a new ObsidianMCP service instance
    pub async fn new() -> ObsidianResult<Self> {
        tracing::info!("Initializing ObsidianMCP service");
        
        // Load configuration
        let config = ObsidianMcpConfig::load()?;
        config.validate()?;
        
        tracing::info!("Vault root path: {}", config.vault.root_path.display());
        
        // Initialize vault manager
        let vault_manager = Arc::new(VaultManager::new(config.vault.clone())?);
        
        tracing::info!("ObsidianMCP service initialized successfully");
        
        Ok(Self {
            tool_router: Self::tool_router(),
            vault_manager,
            config,
        })
    }

    /// Get reference to vault manager
    pub fn vault_manager(&self) -> &VaultManager {
        &self.vault_manager
    }

    /// Get configuration
    pub fn config(&self) -> &ObsidianMcpConfig {
        &self.config
    }
}

/// Implementation of MCP tools using rmcp macros
#[tool_router]
impl ObsidianMcpService {
    /// Search for files and content within the vault with embedded help
    #[tool(description = "Search for files and content within the Obsidian vault. Supports file name and content search with filtering options. Use query='help' for detailed usage information.")]
    pub async fn search(
        &self,
        params: Parameters<SearchParams>,
    ) -> std::result::Result<CallToolResult, ErrorData> {
        // Check if user wants help
        if params.0.query.trim().to_lowercase() == "help" {
            let help = self.create_search_help();
            let content = Content::json(help)
                .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
            return Ok(CallToolResult::success(vec![content]));
        }
        
        tracing::info!("Searching vault: query='{}', prefix={:?}", params.0.query, params.0.path_prefix);
        
        match self.vault_manager().search_files(&params.0) {
            Ok(results) => {
                let content = Content::json(results)
                    .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            }
            Err(e) => {
                tracing::error!("Search error: {}", e);
                Err(ErrorData::from(e))
            }
        }
    }

    /// Browse and perform file operations with embedded modes and help
    #[tool(description = "Browse files/directories and perform file operations (create/update/delete/move) in the vault. Use operation='help' for detailed usage information.")]
    pub async fn browse(
        &self,
        params: Parameters<BrowseParams>,
    ) -> std::result::Result<CallToolResult, ErrorData> {
        use crate::models::BrowseOperation;
        
        match &params.0.operation {
            BrowseOperation::Help => {
                let help = self.create_browse_help();
                let content = Content::json(help)
                    .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            }
            BrowseOperation::Browse => {
                self.handle_browse_operation(&params.0).await
            }
            BrowseOperation::Create => {
                self.handle_create_operation(&params.0).await
            }
            BrowseOperation::Update => {
                self.handle_update_operation(&params.0).await
            }
            BrowseOperation::Delete => {
                self.handle_delete_operation(&params.0).await
            }
            BrowseOperation::Move => {
                self.handle_move_operation(&params.0).await
            }
        }
    }


    /// Handle browse (read) operations
    async fn handle_browse_operation(&self, params: &BrowseParams) -> std::result::Result<CallToolResult, ErrorData> {
        tracing::info!("Browsing vault path: {}", params.path);
        
        // First check if it's a file or directory
        let file_result = self.vault_manager().read_file(&params.path, false);
        
        match file_result {
            Ok(vault_file) if vault_file.is_directory => {
                // It's a directory, list contents
                match self.vault_manager().list_directory(Some(&params.path)) {
                    Ok(files) => {
                        let browse_result = BrowseResult {
                            path: params.path.clone(),
                            is_directory: true,
                            files: Some(files),
                            content: None,
                        };
                        let content = Content::json(browse_result)
                            .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                        Ok(CallToolResult::success(vec![content]))
                    }
                    Err(e) => {
                        tracing::error!("Browse directory error: {}", e);
                        Err(ErrorData::from(e))
                    }
                }
            }
            Ok(_) => {
                // It's a file, read content
                match self.vault_manager().read_file(&params.path, params.include_content) {
                    Ok(vault_file) => {
                        let browse_result = BrowseResult {
                            path: params.path.clone(),
                            is_directory: false,
                            files: None,
                            content: Some(vault_file),
                        };
                        let content = Content::json(browse_result)
                            .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                        Ok(CallToolResult::success(vec![content]))
                    }
                    Err(e) => {
                        tracing::error!("Browse file error: {}", e);
                        Err(ErrorData::from(e))
                    }
                }
            }
            Err(e) => {
                tracing::error!("Browse error: {}", e);
                Err(ErrorData::from(e))
            }
        }
    }

    /// Handle create operations
    async fn handle_create_operation(&self, params: &BrowseParams) -> std::result::Result<CallToolResult, ErrorData> {
        tracing::info!("Creating file: {}", params.path);
        
        let content = params.content.as_ref()
            .ok_or_else(|| ErrorData::invalid_params("content is required for create operation".to_string(), None))?;
        
        let create_params = CreateFileParams {
            path: params.path.clone(),
            content: content.clone(),
            frontmatter: params.frontmatter.clone(),
            tags: params.tags.clone(),
            create_dirs: params.create_dirs,
            overwrite: params.overwrite,
        };
        
        match self.vault_manager().create_file(&create_params) {
            Ok(vault_file) => {
                let content = Content::json(vault_file)
                    .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            }
            Err(e) => {
                tracing::error!("Create file error: {}", e);
                Err(ErrorData::from(e))
            }
        }
    }

    /// Handle update operations
    async fn handle_update_operation(&self, params: &BrowseParams) -> std::result::Result<CallToolResult, ErrorData> {
        tracing::info!("Updating file: {}", params.path);
        
        let content = params.content.as_ref()
            .ok_or_else(|| ErrorData::invalid_params("content is required for update operation".to_string(), None))?;
        
        let update_params = UpdateFileParams {
            path: params.path.clone(),
            content: content.clone(),
            frontmatter: params.frontmatter.clone(),
            tags: params.tags.clone(),
            create_if_missing: params.create_if_missing,
        };
        
        match self.vault_manager().update_file(&update_params) {
            Ok(vault_file) => {
                let content = Content::json(vault_file)
                    .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            }
            Err(e) => {
                tracing::error!("Update file error: {}", e);
                Err(ErrorData::from(e))
            }
        }
    }

    /// Handle delete operations
    async fn handle_delete_operation(&self, params: &BrowseParams) -> std::result::Result<CallToolResult, ErrorData> {
        tracing::info!("Deleting file: {}", params.path);
        
        let delete_params = DeleteFileParams {
            path: params.path.clone(),
            recursive: params.recursive,
        };
        
        match self.vault_manager().delete_file(&delete_params) {
            Ok(()) => {
                let result = serde_json::json!({
                    "success": true,
                    "message": format!("Successfully deleted: {}", params.path)
                });
                let content = Content::json(result)
                    .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            }
            Err(e) => {
                tracing::error!("Delete file error: {}", e);
                Err(ErrorData::from(e))
            }
        }
    }

    /// Handle move operations
    async fn handle_move_operation(&self, params: &BrowseParams) -> std::result::Result<CallToolResult, ErrorData> {
        tracing::info!("Moving file: {} -> {:?}", params.path, params.to_path);
        
        let to_path = params.to_path.as_ref()
            .ok_or_else(|| ErrorData::invalid_params("to_path is required for move operation".to_string(), None))?;
        
        let move_params = MoveFileParams {
            from_path: params.path.clone(),
            to_path: to_path.clone(),
            overwrite: params.overwrite,
        };
        
        match self.vault_manager().move_file(&move_params) {
            Ok(vault_file) => {
                let content = Content::json(vault_file)
                    .map_err(|e| ErrorData::internal_error(format!("Failed to create JSON content: {}", e), None))?;
                Ok(CallToolResult::success(vec![content]))
            }
            Err(e) => {
                tracing::error!("Move file error: {}", e);
                Err(ErrorData::from(e))
            }
        }
    }

    /// Create help information for search operations
    fn create_search_help(&self) -> SearchHelp {
        use crate::models::{SearchHelp, ParameterHelp, SearchExample};
        
        SearchHelp {
            tool_name: "search".to_string(),
            description: "Search for files and content within the Obsidian vault with filtering options. Includes wikilink parsing when content is included.".to_string(),
            parameters: vec![
                ParameterHelp {
                    name: "query".to_string(),
                    description: "Search query string (use 'help' to show this help)".to_string(),
                    required: true,
                    example: Some("meeting notes".to_string()),
                },
                ParameterHelp {
                    name: "path_prefix".to_string(),
                    description: "Optional path prefix to limit search scope".to_string(),
                    required: false,
                    example: Some("Projects/".to_string()),
                },
                ParameterHelp {
                    name: "include_content".to_string(),
                    description: "Include file content in results".to_string(),
                    required: false,
                    example: Some("true".to_string()),
                },
                ParameterHelp {
                    name: "limit".to_string(),
                    description: "Maximum number of results (default: 50)".to_string(),
                    required: false,
                    example: Some("20".to_string()),
                },
                ParameterHelp {
                    name: "extensions".to_string(),
                    description: "File extensions to include".to_string(),
                    required: false,
                    example: Some("[\"md\", \"txt\"]".to_string()),
                },
            ],
            examples: vec![
                SearchExample {
                    description: "Basic text search".to_string(),
                    query: "project planning".to_string(),
                    additional_params: None,
                },
                SearchExample {
                    description: "Search in specific directory".to_string(),
                    query: "meeting".to_string(),
                    additional_params: Some(serde_json::json!({"path_prefix": "Work/"})),
                },
                SearchExample {
                    description: "Search with content included".to_string(),
                    query: "todo".to_string(),
                    additional_params: Some(serde_json::json!({"include_content": true, "limit": 10})),
                },
            ],
            tips: vec![
                "Use specific keywords for better results".to_string(),
                "path_prefix helps narrow down search scope".to_string(),
                "include_content shows file contents and parses wikilinks in results".to_string(),
                "extensions filter limits to specific file types".to_string(),
                "Wikilinks are automatically parsed when include_content=true".to_string(),
                "Search also looks inside wikilink targets for matches".to_string(),
            ],
        }
    }

    /// Create help information for browse operations
    fn create_browse_help(&self) -> BrowseHelp {
        use crate::models::{BrowseHelp, OperationHelp, BrowseExample};
        
        BrowseHelp {
            tool_name: "browse".to_string(),
            description: "Browse files/directories and perform file operations in the vault".to_string(),
            operations: vec![
                OperationHelp {
                    operation: "browse".to_string(),
                    description: "Browse/read files or directories (default)".to_string(),
                    required_params: vec!["path".to_string()],
                    optional_params: vec!["include_content".to_string()],
                },
                OperationHelp {
                    operation: "create".to_string(),
                    description: "Create a new file".to_string(),
                    required_params: vec!["path".to_string(), "content".to_string()],
                    optional_params: vec!["create_dirs".to_string(), "overwrite".to_string(), "frontmatter".to_string(), "tags".to_string()],
                },
                OperationHelp {
                    operation: "update".to_string(),
                    description: "Update an existing file".to_string(),
                    required_params: vec!["path".to_string(), "content".to_string()],
                    optional_params: vec!["create_if_missing".to_string(), "frontmatter".to_string(), "tags".to_string()],
                },
                OperationHelp {
                    operation: "delete".to_string(),
                    description: "Delete a file or directory".to_string(),
                    required_params: vec!["path".to_string()],
                    optional_params: vec!["recursive".to_string()],
                },
                OperationHelp {
                    operation: "move".to_string(),
                    description: "Move or rename a file/directory".to_string(),
                    required_params: vec!["path".to_string(), "to_path".to_string()],
                    optional_params: vec!["overwrite".to_string()],
                },
            ],
            examples: vec![
                BrowseExample {
                    description: "Browse a directory".to_string(),
                    operation: "browse".to_string(),
                    params: serde_json::json!({"path": "Projects/", "include_content": false}),
                },
                BrowseExample {
                    description: "Read a file with content".to_string(),
                    operation: "browse".to_string(),
                    params: serde_json::json!({"path": "notes.md", "include_content": true}),
                },
                BrowseExample {
                    description: "Create a new note".to_string(),
                    operation: "create".to_string(),
                    params: serde_json::json!({"path": "daily-notes/2024-01-15.md", "content": "# Daily Note\n\nToday's tasks:", "create_dirs": true}),
                },
                BrowseExample {
                    description: "Create a note with frontmatter and tags".to_string(),
                    operation: "create".to_string(),
                    params: serde_json::json!({"path": "project-notes.md", "content": "# Project Planning\n\nKey objectives...", "frontmatter": {"type": "planning-doc", "importance": 8}, "tags": ["project", "planning"]}),
                },
                BrowseExample {
                    description: "Update existing file".to_string(),
                    operation: "update".to_string(),
                    params: serde_json::json!({"path": "todo.md", "content": "# Updated Todo List\n\n- [x] Task 1\n- [ ] Task 2"}),
                },
                BrowseExample {
                    description: "Update file with new metadata (preserves existing frontmatter if not overridden)".to_string(),
                    operation: "update".to_string(),
                    params: serde_json::json!({"path": "notes.md", "content": "Updated content...", "frontmatter": {"status": "completed"}, "tags": ["finished"]}),
                },
                BrowseExample {
                    description: "Delete a file".to_string(),
                    operation: "delete".to_string(),
                    params: serde_json::json!({"path": "old-notes.md"}),
                },
                BrowseExample {
                    description: "Move/rename a file".to_string(),
                    operation: "move".to_string(),
                    params: serde_json::json!({"path": "draft.md", "to_path": "archive/old-draft.md"}),
                },
            ],
            tips: vec![
                "Default operation is 'browse' if not specified".to_string(),
                "Use create_dirs=true when creating files in new directories".to_string(),
                "Set recursive=true when deleting directories".to_string(),
                "Move operation can rename files and move between directories".to_string(),
                "Always specify required parameters for each operation".to_string(),
                "Frontmatter is optional - files work normally without it".to_string(),
                "Update operations preserve existing frontmatter unless explicitly overridden".to_string(),
                "Tags can be specified in frontmatter or as inline #tags in content".to_string(),
            ],
        }
    }
}

#[tool_handler]
impl ServerHandler for ObsidianMcpService {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            protocol_version: rmcp::model::ProtocolVersion::V_2024_11_05,
            server_info: rmcp::model::Implementation {
                name: "obsidian-mcp".into(),
                version: env!("CARGO_PKG_VERSION").into(),
            },
            capabilities: ServerCapabilities {
                tools: Some(Default::default()),
                ..Default::default()
            },
            instructions: Some("ObsidianMCP Server for secure Obsidian vault operations".into()),
        }
    }
}