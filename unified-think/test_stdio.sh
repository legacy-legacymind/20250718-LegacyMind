#!/bin/bash

# Test what happens when we send proper MCP messages
echo "Testing MCP server with full conversation..." >&2

# Create a named pipe for bidirectional communication
mkfifo /tmp/mcp_pipe_in /tmp/mcp_pipe_out 2>/dev/null || true

# Start the server with pipes
./target/release/unified-think < /tmp/mcp_pipe_in > /tmp/mcp_pipe_out 2>server_test.log &
SERVER_PID=$!

# Give it a moment to start
sleep 0.5

# Function to send a message and read response
send_and_read() {
    echo "$1" > /tmp/mcp_pipe_in
    timeout 1 cat /tmp/mcp_pipe_out
}

# Send initialize
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}' > /tmp/mcp_pipe_in
sleep 0.5

# Read responses
timeout 2 cat /tmp/mcp_pipe_out

# Keep the server alive
sleep 2

# Check if server is still running
if kill -0 $SERVER_PID 2>/dev/null; then
    echo "Server still running after 2 seconds" >&2
else
    echo "Server exited!" >&2
fi

# Cleanup
kill $SERVER_PID 2>/dev/null
rm -f /tmp/mcp_pipe_in /tmp/mcp_pipe_out

echo "Server log:" >&2
cat server_test.log >&2