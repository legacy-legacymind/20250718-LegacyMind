#!/bin/bash

# Test the MCP server with proper initialization sequence
(
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}'
sleep 0.1
echo '{"method":"notifications/initialized","jsonrpc":"2.0"}'
sleep 0.1
echo '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":2}'
sleep 1
) | ./target/release/unified-think 2>server.log

echo "Server log:"
cat server.log