#!/bin/bash
# Enhanced Ollama wrapper with session support
# Maintains backward compatibility with ollama-quick.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/ollama-session.py"
OLLAMA_QUICK="$SCRIPT_DIR/ollama-quick.sh"

# Check if Python script exists and Redis is available
if [ -f "$PYTHON_SCRIPT" ] && command -v redis-cli >/dev/null 2>&1 && redis-cli ping >/dev/null 2>&1; then
    # Use session manager
    python3 "$PYTHON_SCRIPT" "$@"
else
    # Fallback to simple ollama-quick.sh
    if [ -z "$1" ]; then
        echo "Usage: $0 'prompt'"
        echo "       $0 -s SESSION_ID 'prompt'  # Continue existing session"
        echo "       $0 -n 'prompt'             # Start new session"
        echo "       $0 -l                      # List sessions"
        exit 1
    fi
    
    # Extract prompt from arguments (handle -s, -n flags gracefully)
    PROMPT=""
    while [[ $# -gt 0 ]]; do
        case $1 in
            -s|-n|-l|--*)
                shift
                ;;
            *)
                PROMPT="$1"
                break
                ;;
        esac
    done
    
    if [ -n "$PROMPT" ]; then
        exec "$OLLAMA_QUICK" "$PROMPT"
    fi
fi