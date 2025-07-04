# Makefile for the LegacyMind Project

# --- Variables ---
COMPOSE_FILE = docker-compose.yml

# --- Docker Commands ---

## Build all services
build:
	docker-compose -f $(COMPOSE_FILE) build

## Start all services in detached mode
up:
	docker-compose -f $(COMPOSE_FILE) up -d

## Stop all services
down:
	docker-compose -f $(COMPOSE_FILE) down

## View logs of all services
logs:
	docker-compose -f $(COMPOSE_FILE) logs -f

## Rebuild and restart a specific service
restart:
	docker-compose -f $(COMPOSE_FILE) up -d --build $(service)

# --- Utility Commands ---

## Show help
help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  build          Build all Docker containers"
	@echo "  up             Start all services in detached mode"
	@echo "  down           Stop all services"
	@echo "  logs           Follow the logs of all services"
	@echo "  restart        Rebuild and restart a specific service (e.g., make restart service=unified-intelligence)"
	@echo "  help           Show this help message"

.PHONY: build up down logs restart help
