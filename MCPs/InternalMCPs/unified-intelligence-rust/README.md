# Unified Intelligence MCP (Rust)

**Version:** 3.0.0
**Author:** Sam Atagana <sam@samataganaphotography.com>
**License:** MIT

A high-performance cognitive enhancement MCP service, designed to augment reasoning and decision-making through structured thinking frameworks.

## 1. Overview and Purpose

The Unified Intelligence MCP is a backend service that provides a set of tools to apply structured thinking methodologies (like First Principles, SWOT, etc.) to user-provided content. It's designed to be a "cognitive co-processor," helping users analyze problems, make decisions, and generate insights with greater clarity and depth.

The core purpose is to:
- **Provide structured thinking tools:** Offer a suite of thinking frameworks as a service.
- **Analyze significance:** Automatically assess the importance of information to decide what needs to be captured.
- **Manage context:** Maintain state about the user's identity, current task, and goals.
- **Enable session management:** Support distinct sessions and instances for different users or tasks, with SSO-like capabilities via Redis.

## 2. Architecture

The service is built in Rust for performance and reliability, using the `rmcp` framework for MCP communication.

### Core Components:

- **`main.rs`**: The entry point. Initializes the `tracing` logger, reads environment configuration, creates the `UnifiedIntelligenceService`, and starts the `rmcp` server over stdio.
- **`service.rs`**: The heart of the application.
    - Defines the `UnifiedIntelligenceService` struct, which holds the application state (Redis pool, sessions).
    - Implements the `rmcp` `ServerHandler` and `ToolRouter`.
    - Exposes the three main tools: `ui_think`, `ui_context`, and `ui_bot`.
- **`tools/`**: Contains the implementation for each of the exposed tools.
    - **`think.rs`**: Implements the `ui_think` tool, which is the core engine for applying frameworks, analyzing significance, and capturing thoughts.
    - **`context.rs`**: Implements the `ui_context` tool for managing the instance's state (identity, task, goals).
    - **`bot.rs`**: Implements `ui_bot`, a high-level conversational interface (currently a simple echo).
- **`core/`**: Contains the business logic for thinking frameworks and analysis.
    - **`frameworks.rs`**: Implements the `FrameworkDetector` to automatically detect which thinking framework is most applicable to a piece of content and applies it.
    - **`significance.rs`**: Implements the `SignificanceAnalyzer` to score content on a scale of 1-10 for importance.
- **`storage.rs`**: Handles data persistence.
    - Defines the `RedisPool` for connecting to Redis.
    - Defines the data structures persisted in Redis (`Thought`, `Identity`, `Context`).
- **`utils.rs`**: Contains utility modules.
    - **`SessionResolver`**: Implements SSO-like logic to map session IDs to instance IDs, enabling persistent user contexts.

### Data Flow:

1. A client sends an `rmcp` tool call request (e.g., `ui_think`).
2. The `rmcp` server in `main.rs` receives the request and routes it via the `tool_router` in `service.rs`.
3. The appropriate tool implementation in the `tools/` directory is called.
4. The tool implementation uses `core/` components to perform analysis (e.g., `FrameworkDetector`, `SignificanceAnalyzer`).
5. If data needs to be persisted, the tool uses `storage.rs` to interact with Redis.
6. A result is returned to the client as an `rmcp` `CallToolResult`.

## 3. Installation

The project is a standard Rust binary.

### Prerequisites:

- Rust toolchain (>= 1.56)
- A running Redis instance

### Building from Source:

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd unified-intelligence-rust
    ```

2.  **Set up environment variables:**
    The service is configured via environment variables. Create a `.env` file or export them in your shell:
    ```bash
    # The connection URL for your Redis instance
    REDIS_URL="redis://127.0.0.1:6379"

    # The default significance score (1-10) required to automatically capture a thought
    DEFAULT_THRESHOLD=5

    # A unique ID for this instance of the service (e.g., "CC", "Gemini")
    INSTANCE_ID="default"
    ```

3.  **Build the project:**
    ```bash
    cargo build --release
    ```
    The binary will be located at `target/release/unified-intelligence-rust`.

## 4. Usage Examples

The service exposes three tools.

### `ui_think`

The core engine for enhanced thinking.

**Actions:**

-   `think`: Analyzes content, applies a framework, and captures it if significant.
-   `check_in`: Starts a new session.
-   `capture`: Manually captures a thought.
-   `apply_framework`: Applies a specific framework to content.

**Example: Using `think`**

This is the most common action. It automatically detects the best framework.

```json
{
  "tool": "ui_think",
  "parameters": {
    "action": "think",
    "content": "We need to decide whether to refactor our legacy module or rewrite it from scratch. A rewrite is risky but could pay off. A refactor is safer but might not fix all the underlying issues."
  }
}
```

### `ui_context`

The dashboard for managing the instance's state.

**Actions:**

-   `get`: Retrieves context information.
-   `set_identity`: Sets the name, role, and capabilities of the instance.
-   `set_task`: Sets the current task.
-   `add_goal`: Adds a goal to the current task.

**Example: Setting the identity and task**

```json
{
  "tool": "ui_context",
  "parameters": {
    "action": "set_identity",
    "data": {
      "name": "Gemini",
      "role": "Developer Assistant",
      "capabilities": ["rust", "documentation"]
    }
  }
}
```

```json
{
  "tool": "ui_context",
  "parameters": {
    "action": "set_task",
    "data": "Document the Unified Intelligence MCP"
  }
}
```

### `ui_bot`

A high-level conversational interface.

**Example: Sending a message**

```json
{
  "tool": "ui_bot",
  "parameters": {
    "message": "Hello, can you help me think through a problem?"
  }
}
```

## 5. Current Limitations and Known Issues

-   **Stateless Sessions:** In-memory session management (`sessions` in `UnifiedIntelligenceService`) is not fully integrated with the Redis-backed `SessionResolver`. A restart will clear in-memory sessions.
-   **Simple `ui_bot`:** The `ui_bot` tool is currently a placeholder and only echoes the input. It does not have any conversational intelligence yet.
-   **Framework Detection:** The `FrameworkDetector` uses simple keyword matching, which may not always be accurate.
-   **No Authentication:** The service assumes a trusted environment. There is no authentication or authorization layer.

## 6. Development Roadmap

-   **[Q3 2025] Full Conversational AI:** Integrate a proper language model with `ui_bot` to provide a rich, stateful conversational experience.
-   **[Q3 2025] Advanced Framework Detection:** Use NLP or a small ML model to improve the accuracy of `FrameworkDetector`.
-   **[Q4 2025] Pluggable Frameworks:** Allow new thinking frameworks to be added via configuration without changing the core code.
-   **[Q4 2025] Long-term Memory:** Implement a mechanism to move significant thoughts from the Redis "hot" cache to a long-term storage solution (e.g., PostgreSQL) for historical analysis.
-   **[2026] Multi-modal Input:** Allow `ui_think` to process not just text, but also images or other data types.
-   **[2026] Web Dashboard:** Create a simple web interface for visualizing thoughts, context, and session activity.
