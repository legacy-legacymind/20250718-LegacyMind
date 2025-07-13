#!/bin/bash
# bot-cli.sh - Simple CLI wrapper for Ollama with memory support
# Usage: ./bot-cli.sh [options]

# Configuration
REDIS_CLI="redis-cli"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5-coder:1.5b}"
SESSION_ID="${BOT_SESSION:-default}"
REDIS_PREFIX="Bot/cli"

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
show_help() {
    echo "bot-cli - Chat with local Ollama model"
    echo ""
    echo "Usage:"
    echo "  ./bot-cli.sh                    Start interactive chat"
    echo "  ./bot-cli.sh -p 'prompt'        Single prompt mode"
    echo "  ./bot-cli.sh -f file.txt        Use file as context"
    echo "  ./bot-cli.sh -m model           Use specific model"
    echo "  ./bot-cli.sh -s session_id      Use specific session"
    echo "  ./bot-cli.sh --clear-session    Clear current session memory"
    echo "  ./bot-cli.sh --list-sessions    List all sessions"
    echo ""
    echo "Environment variables:"
    echo "  OLLAMA_MODEL     Default model (currently: $OLLAMA_MODEL)"
    echo "  BOT_SESSION      Default session ID (currently: $SESSION_ID)"
}

get_session_context() {
    local session_key="$REDIS_PREFIX/sessions/$SESSION_ID"
    $REDIS_CLI get "$session_key" 2>/dev/null || echo ""
}

save_interaction() {
    local prompt="$1"
    local response="$2"
    
    # Append to session memory
    local session_key="$REDIS_PREFIX/sessions/$SESSION_ID"
    local interaction="USER: $prompt\nBOT: $response\n---"
    
    $REDIS_CLI append "$session_key" "$interaction\n" > /dev/null 2>&1
    
    # Log interaction with timestamp
    local log_key="$REDIS_PREFIX/logs/$(date +%s)"
    $REDIS_CLI set "$log_key" "{\"session\":\"$SESSION_ID\",\"prompt\":\"$prompt\",\"response\":\"$response\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" > /dev/null 2>&1
}

single_prompt() {
    local prompt="$1"
    local context=""
    
    # Get session context if exists
    if [ "$SESSION_ID" != "none" ]; then
        context=$(get_session_context)
        if [ -n "$context" ]; then
            prompt="Previous context:\n$context\n\nCurrent request: $prompt"
        fi
    fi
    
    # Call Ollama
    response=$(echo "$prompt" | ollama run "$OLLAMA_MODEL" 2>/dev/null)
    
    echo "$response"
    
    # Save to memory
    if [ "$SESSION_ID" != "none" ]; then
        save_interaction "$1" "$response"
    fi
}

interactive_mode() {
    echo -e "${GREEN}Bot CLI - Interactive Mode${NC}"
    echo -e "${BLUE}Model: $OLLAMA_MODEL${NC}"
    echo -e "${BLUE}Session: $SESSION_ID${NC}"
    echo "Type 'exit' to quit, 'clear' to clear screen, 'session new' for new session"
    echo ""
    
    while true; do
        echo -en "${YELLOW}You: ${NC}"
        read -r user_input
        
        # Handle special commands
        case "$user_input" in
            "exit"|"quit")
                echo "Goodbye!"
                break
                ;;
            "clear")
                clear
                continue
                ;;
            "session new")
                SESSION_ID="session-$(date +%s)"
                echo -e "${BLUE}New session: $SESSION_ID${NC}"
                continue
                ;;
            "session clear")
                $REDIS_CLI del "$REDIS_PREFIX/sessions/$SESSION_ID" > /dev/null 2>&1
                echo -e "${BLUE}Session cleared${NC}"
                continue
                ;;
            "help")
                show_help
                continue
                ;;
            "")
                continue
                ;;
        esac
        
        # Get context and build prompt
        local context=$(get_session_context)
        local full_prompt="$user_input"
        
        if [ -n "$context" ] && [ ${#context} -lt 4000 ]; then
            # Include recent context if not too long
            full_prompt="Recent conversation:\n${context: -2000}\n\nUser: $user_input"
        fi
        
        # Call Ollama
        echo -e "${GREEN}Bot: ${NC}"
        response=$(echo "$full_prompt" | ollama run "$OLLAMA_MODEL" 2>/dev/null)
        echo "$response"
        echo ""
        
        # Save interaction
        save_interaction "$user_input" "$response"
    done
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -p|--prompt)
            single_prompt "$2"
            exit 0
            ;;
        -f|--file)
            if [ -f "$2" ]; then
                content=$(cat "$2")
                single_prompt "File: $2\n\n$content\n\nTask: ${3:-Analyze this file}"
            else
                echo "File not found: $2"
                exit 1
            fi
            exit 0
            ;;
        -m|--model)
            OLLAMA_MODEL="$2"
            shift 2
            ;;
        -s|--session)
            SESSION_ID="$2"
            shift 2
            ;;
        --clear-session)
            $REDIS_CLI del "$REDIS_PREFIX/sessions/$SESSION_ID" > /dev/null 2>&1
            echo "Session $SESSION_ID cleared"
            exit 0
            ;;
        --list-sessions)
            echo "Active sessions:"
            $REDIS_CLI keys "$REDIS_PREFIX/sessions/*" 2>/dev/null | sed "s|$REDIS_PREFIX/sessions/||g"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Start interactive mode if no arguments
interactive_mode