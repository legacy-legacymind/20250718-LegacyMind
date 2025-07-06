-- Drop the existing table with wrong schema
DROP TABLE IF EXISTS archived_tickets CASCADE;

-- Create archived_tickets table with correct schema matching PostgreSQL manager
CREATE TABLE archived_tickets (
  id VARCHAR(255) PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  status VARCHAR(50) NOT NULL,
  priority VARCHAR(50) NOT NULL,
  type VARCHAR(50) NOT NULL,
  assignee VARCHAR(255),
  reporter VARCHAR(255),
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  resolved_at TIMESTAMPTZ,
  closed_at TIMESTAMPTZ,
  labels JSONB DEFAULT '[]'::jsonb,
  comments JSONB DEFAULT '[]'::jsonb,
  metadata JSONB DEFAULT '{}'::jsonb,
  tags JSONB DEFAULT '[]'::jsonb,
  members JSONB DEFAULT '[]'::jsonb,
  linked_tickets JSONB DEFAULT '[]'::jsonb
);

-- Create indexes for performance
CREATE INDEX idx_archived_tickets_status ON archived_tickets(status);
CREATE INDEX idx_archived_tickets_priority ON archived_tickets(priority);
CREATE INDEX idx_archived_tickets_assignee ON archived_tickets(assignee);
CREATE INDEX idx_archived_tickets_created_at ON archived_tickets(created_at);
CREATE INDEX idx_archived_tickets_updated_at ON archived_tickets(updated_at);
CREATE INDEX idx_archived_tickets_metadata ON archived_tickets USING GIN(metadata);
CREATE INDEX idx_archived_tickets_tags ON archived_tickets USING GIN(tags);