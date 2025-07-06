-- Migration: Create archived_tickets table
-- Purpose: Store archived tickets with full history and metadata
-- Date: 2025-01-05

CREATE TABLE IF NOT EXISTS archived_tickets (
    -- Primary identification
    id VARCHAR(255) PRIMARY KEY,
    
    -- Core ticket data
    title TEXT NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL,
    priority VARCHAR(20) NOT NULL,
    assignee VARCHAR(100),
    reporter VARCHAR(100),
    
    -- Temporal data
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    resolved_at TIMESTAMP WITH TIME ZONE,
    
    -- Additional fields
    labels TEXT[],
    comments JSONB DEFAULT '[]'::JSONB,
    
    -- Full ticket history as JSONB
    history JSONB NOT NULL DEFAULT '[]'::JSONB,
    
    -- Additional metadata
    metadata JSONB DEFAULT '{}'::JSONB,
    
    -- Search and performance indexes
    CONSTRAINT chk_status CHECK (status IN ('OPEN', 'IN_PROGRESS', 'BLOCKED', 'REVIEW', 'TESTING', 'CLOSED', 'CANCELLED')),
    CONSTRAINT chk_priority CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT'))
);

-- Create indexes for common query patterns
CREATE INDEX idx_archived_tickets_status ON archived_tickets(status);
CREATE INDEX idx_archived_tickets_priority ON archived_tickets(priority);
CREATE INDEX idx_archived_tickets_assignee ON archived_tickets(assignee);
CREATE INDEX idx_archived_tickets_reporter ON archived_tickets(reporter);
CREATE INDEX idx_archived_tickets_created_at ON archived_tickets(created_at);
CREATE INDEX idx_archived_tickets_resolved_at ON archived_tickets(resolved_at);

-- GIN index for JSONB columns (efficient for containment queries)
CREATE INDEX idx_archived_tickets_history_gin ON archived_tickets USING GIN (history);
CREATE INDEX idx_archived_tickets_metadata_gin ON archived_tickets USING GIN (metadata);
CREATE INDEX idx_archived_tickets_comments_gin ON archived_tickets USING GIN (comments);

-- GIN index for labels array
CREATE INDEX idx_archived_tickets_labels_gin ON archived_tickets USING GIN (labels);

-- Full text search index on title and description
CREATE INDEX idx_archived_tickets_search ON archived_tickets USING GIN (
    to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(description, ''))
);

-- Add comment to table
COMMENT ON TABLE archived_tickets IS 'Stores archived tickets matching the main ticket structure for historical data and analysis';