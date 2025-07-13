#!/bin/bash
# Simple wrapper for Claude to call Ollama directly

# Usage: ./ollama-task.sh "prompt" [model]

PROMPT="$1"
MODEL="${2:-qwen2.5-coder:1.5b}"

if [ -z "$PROMPT" ]; then
    echo "Usage: $0 'prompt' [model]"
    exit 1
fi

# Call Ollama directly
ollama run "$MODEL" "$PROMPT" 2>/dev/null