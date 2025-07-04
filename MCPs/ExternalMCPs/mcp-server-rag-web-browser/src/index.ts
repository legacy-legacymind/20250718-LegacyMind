#!/usr/bin/env node
/**
 * This script initializes and starts the MCP server for the Apify RAG Web Browser using the Stdio transport.
 *
 * Usage:
 *   node <script_name>
 *
 * Example:
 *   node index.js
 */
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';

import { RagWebBrowserServer } from './server.js';

async function main() {
    const server = new RagWebBrowserServer();
    const transport = new StdioServerTransport();
    await server.connect(transport);
}

main().catch((error) => {
    console.error('Server error:', error); // eslint-disable-line no-console
    process.exit(1);
});
