#!/bin/bash
# Embedding Service Control Script

SERVICE_NAME="com.legacymind.embedding"
PLIST_PATH="/Users/samuelatagana/Projects/LegacyMind/com.legacymind.embedding.plist"
LAUNCHD_PATH="$HOME/Library/LaunchAgents/$SERVICE_NAME.plist"

case "$1" in
    install)
        echo "Installing embedding service..."
        cp "$PLIST_PATH" "$LAUNCHD_PATH"
        launchctl load "$LAUNCHD_PATH"
        echo "Service installed and started"
        ;;
    
    uninstall)
        echo "Uninstalling embedding service..."
        launchctl unload "$LAUNCHD_PATH" 2>/dev/null
        rm -f "$LAUNCHD_PATH"
        echo "Service uninstalled"
        ;;
    
    start)
        echo "Starting embedding service..."
        launchctl start "$SERVICE_NAME"
        echo "Service started"
        ;;
    
    stop)
        echo "Stopping embedding service..."
        launchctl stop "$SERVICE_NAME"
        echo "Service stopped"
        ;;
    
    restart)
        echo "Restarting embedding service..."
        launchctl stop "$SERVICE_NAME"
        sleep 2
        launchctl start "$SERVICE_NAME"
        echo "Service restarted"
        ;;
    
    status)
        echo "Checking service status..."
        launchctl list | grep "$SERVICE_NAME"
        echo ""
        echo "Process check:"
        ps aux | grep -E "background_embedding_service|start_background_service" | grep -v grep
        ;;
    
    logs)
        echo "=== Recent logs ==="
        tail -n 50 /Users/samuelatagana/Projects/LegacyMind/logs/embedding_service.log
        echo ""
        echo "=== Recent errors ==="
        tail -n 20 /Users/samuelatagana/Projects/LegacyMind/logs/embedding_service_error.log
        ;;
    
    test)
        echo "Running test mode..."
        cd /Users/samuelatagana/Projects/LegacyMind
        python3 start_background_service.py --test
        ;;
    
    *)
        echo "Usage: $0 {install|uninstall|start|stop|restart|status|logs|test}"
        echo ""
        echo "Commands:"
        echo "  install   - Install and start the service"
        echo "  uninstall - Stop and remove the service"
        echo "  start     - Start the service"
        echo "  stop      - Stop the service"
        echo "  restart   - Restart the service"
        echo "  status    - Check service status"
        echo "  logs      - View recent logs"
        echo "  test      - Run in test mode (single batch)"
        exit 1
        ;;
esac