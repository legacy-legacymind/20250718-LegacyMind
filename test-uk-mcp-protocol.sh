#!/bin/bash

echo "Testing UnifiedKnowledge MCP ticket creation..."

# Monitor logs in background
echo "Starting log monitor..."
docker logs -f legacymind_unified_knowledge 2>&1 | grep -E "(Qdrant|Embedding|ticket|Ticket|Error|creating)" > /tmp/uk-test-logs.txt &
LOG_PID=$!

# Give monitor time to start
sleep 1

# Create the requests
INIT_REQUEST='{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"0.1.0","capabilities":{"tools":{}}},"id":1}'

TICKET_REQUEST='{"jsonrpc":"2.0","method":"tools/call","params":{"name":"uk_ticket","arguments":{"action":"create","title":"Test Embedding and Qdrant Logging","description":"This ticket tests if embedding generation and Qdrant storage produce logs","priority":"high","type":"task","tags":["test","embedding","qdrant"],"assignee":"CC"}},"id":2}'

echo "Sending initialize request..."
echo "$INIT_REQUEST" | docker exec -i legacymind_unified_knowledge node /app/src/index.js > /tmp/uk-init-response.txt 2>&1 &
INIT_PID=$!

# Wait for initialization
sleep 3
kill $INIT_PID 2>/dev/null || true

echo "Sending ticket creation request..."
echo -e "$INIT_REQUEST\n$TICKET_REQUEST" | docker exec -i legacymind_unified_knowledge node /app/src/index.js > /tmp/uk-ticket-response.txt 2>&1 &
TICKET_PID=$!

# Wait for processing
sleep 5
kill $TICKET_PID 2>/dev/null || true

# Stop log monitoring
kill $LOG_PID 2>/dev/null || true

echo -e "\n=== RESPONSES ==="
echo "Init response:"
cat /tmp/uk-init-response.txt | grep -E "result|error" || echo "No result/error found"

echo -e "\nTicket response:"
cat /tmp/uk-ticket-response.txt | grep -E "result|error|success" || echo "No result/error found"

echo -e "\n=== CAPTURED LOGS ==="
if [ -s /tmp/uk-test-logs.txt ]; then
  cat /tmp/uk-test-logs.txt
else
  echo "No relevant logs captured"
fi

echo -e "\n=== CHECKING RECENT CONTAINER LOGS ==="
docker logs legacymind_unified_knowledge --tail 20 | grep -E "(Qdrant|Embedding|ticket)"