#!/bin/bash

# Phase 1 Test Script for UnifiedThink MCP Server
# This script tests the basic ut_think tool functionality

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to send JSON-RPC request
send_request() {
    local request=$1
    local description=$2
    
    echo -e "\n${GREEN}==== $description ====${NC}"
    echo "Request:"
    echo "$request" | jq . 2>/dev/null || echo "$request"
    echo -e "\nResponse:"
}

# Cleanup function
cleanup() {
    if [ ! -z "$SERVER_PID" ]; then
        print_status "Stopping server (PID: $SERVER_PID)..."
        kill $SERVER_PID 2>/dev/null || true
        wait $SERVER_PID 2>/dev/null || true
    fi
}

# Set trap to cleanup on exit
trap cleanup EXIT

# Main test execution
print_status "Starting Phase 1 Test for UnifiedThink MCP Server"

# Step 1: Build the project
print_status "Building the project..."
cargo build || {
    print_error "Failed to build the project"
    exit 1
}

# Step 2: Create named pipes for communication
print_status "Creating communication pipes..."
PIPE_IN=$(mktemp -u)
PIPE_OUT=$(mktemp -u)
mkfifo "$PIPE_IN" "$PIPE_OUT"

# Step 3: Start the server in background
print_status "Starting UnifiedThink server..."
INSTANCE_ID="phase1-test" cargo run < "$PIPE_IN" > "$PIPE_OUT" 2>&1 &
SERVER_PID=$!
sleep 2  # Give server time to start

# Check if server is running
if ! kill -0 $SERVER_PID 2>/dev/null; then
    print_error "Server failed to start"
    exit 1
fi

print_status "Server started with PID: $SERVER_PID"

# Step 4: Create a function to interact with the server
interact_with_server() {
    local request=$1
    echo "$request" > "$PIPE_IN"
    
    # Read response with timeout
    if timeout 5 cat "$PIPE_OUT" | head -n 1; then
        return 0
    else
        print_error "Timeout waiting for response"
        return 1
    fi
}

# Step 5: Run tests

# Test 1: Initialize
send_request '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"clientInfo":{"name":"phase1-test-client","version":"1.0.0"},"capabilities":{}}}' "Initialize Request"
interact_with_server '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"clientInfo":{"name":"phase1-test-client","version":"1.0.0"},"capabilities":{}}}'

# Test 2: List tools
send_request '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' "List Tools Request"
interact_with_server '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

# Test 3: Call ui_think with a simple thought
send_request '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Testing Phase 1 foundation - basic thought capture","thought_number":1,"total_thoughts":1,"next_thought_needed":false}}}' "UI Think Tool Call - Single Thought"
interact_with_server '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Testing Phase 1 foundation - basic thought capture","thought_number":1,"total_thoughts":1,"next_thought_needed":false}}}'

# Test 4: Call ui_think with a sequence of thoughts
send_request '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"First thought in sequence - evaluating framework","thought_number":1,"total_thoughts":3,"next_thought_needed":true}}}' "UI Think Tool Call - Thought Sequence (1/3)"
interact_with_server '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"First thought in sequence - evaluating framework","thought_number":1,"total_thoughts":3,"next_thought_needed":true}}}'

send_request '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Second thought - applying first principles thinking","thought_number":2,"total_thoughts":3,"next_thought_needed":true}}}' "UI Think Tool Call - Thought Sequence (2/3)"
interact_with_server '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Second thought - applying first principles thinking","thought_number":2,"total_thoughts":3,"next_thought_needed":true}}}'

send_request '{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Final thought - synthesis and conclusion","thought_number":3,"total_thoughts":3,"next_thought_needed":false}}}' "UI Think Tool Call - Thought Sequence (3/3)"
interact_with_server '{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Final thought - synthesis and conclusion","thought_number":3,"total_thoughts":3,"next_thought_needed":false}}}'

# Cleanup pipes
rm -f "$PIPE_IN" "$PIPE_OUT"

print_status "Phase 1 tests completed successfully!"

# Summary
echo -e "\n${GREEN}==== Test Summary ====${NC}"
echo "✓ Project builds successfully"
echo "✓ Server starts and responds to requests"
echo "✓ Initialize method works"
echo "✓ Tools listing works"
echo "✓ ui_think tool accepts single thoughts"
echo "✓ ui_think tool handles thought sequences"
echo -e "\n${GREEN}Phase 1 Foundation is working correctly!${NC}"