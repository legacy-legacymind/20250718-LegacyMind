#!/bin/bash

# Create a named pipe for bidirectional communication
mkfifo /tmp/mcp_in /tmp/mcp_out 2>/dev/null || true

# Start the server with the pipes
./target/release/unified-think < /tmp/mcp_in > /tmp/mcp_out 2>server.log &
SERVER_PID=$!

# Give server time to start
sleep 1

# Function to send message and read response
send_and_read() {
    echo "$1" > /tmp/mcp_in
    timeout 2 head -n 1 /tmp/mcp_out || echo "No response"
}

# Start reading responses in background
tail -f /tmp/mcp_out | while read line; do
    echo "RESPONSE: $line"
done &
READER_PID=$!

# Send messages
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"pipe-test","version":"1.0"}}}' > /tmp/mcp_in
sleep 1

echo '{"jsonrpc":"2.0","method":"notifications/initialized"}' > /tmp/mcp_in
sleep 1

echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Test thought via pipe","thought_number":1,"total_thoughts":1,"next_thought_needed":false}}}' > /tmp/mcp_in
sleep 2

# Cleanup
kill $SERVER_PID $READER_PID 2>/dev/null
rm -f /tmp/mcp_in /tmp/mcp_out

echo "Server logs:"
cat server.log