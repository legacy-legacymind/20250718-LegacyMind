# UnifiedKnowledge MCP

Multi-database knowledge management system for tickets and system documentation.

## Architecture

- **Redis**: Active data storage with TTL management
- **PostgreSQL**: Long-term archival storage
- **Qdrant**: Vector embeddings for semantic search
- **OpenAI**: Embedding generation for search capabilities

## Phase 1: Ticket Management (Implemented)

### Available Tools

- `uk_tickets.create` - Create new tickets
- `uk_tickets.update` - Modify ticket details and status
- `uk_tickets.query` - Retrieve single or all tickets
- `uk_tickets.delete` - Remove tickets (with safeguards)
- `uk_tickets.add_member` - Add federation members with roles
- `uk_tickets.remove_member` - Remove members from tickets
- `uk_tickets.link_ticket` - Associate tickets with a ticket
- `uk_tickets.unlink_ticket` - Remove ticket associations
- `uk_tickets.help` - Help documentation

### Ticket Lifecycle

1. Created tickets start with status "OPEN"
2. Status progression: OPEN → IN_PROGRESS → REVIEW → TESTING → CLOSED
3. When closed/cancelled:
   - Archived to PostgreSQL
   - Embedding generated via OpenAI
   - Stored in Qdrant for semantic search
   - Redis entry gets 1-hour TTL

## Phase 2: System Documentation (Planned)

- `uk_system_docs.create` - Create versioned documentation
- `uk_system_docs.update` - Create new versions with temporal validity
- `uk_system_docs.query` - Retrieve docs by category or validity
- `uk_system_docs.delete` - Soft delete with history preservation
- `uk_system_docs.add_reference` - Link to other docs/resources
- `uk_system_docs.remove_reference` - Unlink references
- `uk_system_docs.help` - Help documentation

## Environment Variables

```bash
# Redis
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=

# PostgreSQL
DATABASE_URL=postgresql://user:pass@localhost/db

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=

# OpenAI
OPENAI_API_KEY=your-key-here
```

## Docker Deployment

Build and run:
```bash
docker build -t unified-knowledge .
docker run --rm -it \
  -e REDIS_URL=redis://redis:6379 \
  -e DATABASE_URL=postgresql://postgres:postgres@postgres/legacymind \
  -e QDRANT_HOST=qdrant \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  unified-knowledge
```

## Development

```bash
npm install
npm run dev  # Run with file watching
npm test     # Run tests
```