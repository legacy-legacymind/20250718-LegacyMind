#!/bin/bash
# Quick Ollama wrapper for Claude to delegate tasks
OLLAMA_BIN="/usr/local/bin/ollama"
MODEL="${OLLAMA_MODEL:-qwen2.5-coder:1.5b}"

# Usage: ./ollama-quick.sh "prompt"
if [ -z "$1" ]; then
    echo "Usage: $0 'prompt'"
    exit 1
fi

# Run Ollama and capture output
$OLLAMA_BIN run "$MODEL" "$1" 2>/dev/null