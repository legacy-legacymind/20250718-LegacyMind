-- UnifiedWorkflow Database Schema
-- This file contains the schema for PostgreSQL persistence layer

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Existing tickets table (for reference)
-- Already created by the existing system

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    project_id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'ACTIVE',
    priority VARCHAR(20) DEFAULT 'MEDIUM',
    category VARCHAR(100),
    owner VARCHAR(100) NOT NULL,
    members JSONB DEFAULT '[]'::jsonb,
    linked_tickets JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    start_date DATE,
    end_date DATE,
    estimated_hours INTEGER DEFAULT 0,
    actual_hours INTEGER DEFAULT 0,
    budget_allocated DECIMAL(10, 2),
    budget_used DECIMAL(10, 2) DEFAULT 0,
    milestones JSONB DEFAULT '[]'::jsonb,
    tags JSONB DEFAULT '[]'::jsonb
);

-- System documentation table
CREATE TABLE IF NOT EXISTS system_docs (
    doc_id VARCHAR(255) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    category VARCHAR(100) NOT NULL,
    doc_type VARCHAR(50) DEFAULT 'GENERAL',
    version VARCHAR(20) DEFAULT '1.0.0',
    status VARCHAR(50) DEFAULT 'ACTIVE',
    author VARCHAR(100) NOT NULL,
    valid_from TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    valid_until TIMESTAMP WITH TIME ZONE,
    parent_doc_id VARCHAR(255),
    doc_references JSONB DEFAULT '[]'::jsonb,
    tags JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    review_date DATE,
    approval_status VARCHAR(50) DEFAULT 'DRAFT',
    approved_by VARCHAR(100),
    approved_at TIMESTAMP WITH TIME ZONE,
    FOREIGN KEY (parent_doc_id) REFERENCES system_docs(doc_id) ON DELETE SET NULL
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_owner ON projects(owner);
CREATE INDEX IF NOT EXISTS idx_projects_category ON projects(category);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_projects_updated_at ON projects(updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_system_docs_category ON system_docs(category);
CREATE INDEX IF NOT EXISTS idx_system_docs_status ON system_docs(status);
CREATE INDEX IF NOT EXISTS idx_system_docs_author ON system_docs(author);
CREATE INDEX IF NOT EXISTS idx_system_docs_valid_from ON system_docs(valid_from);
CREATE INDEX IF NOT EXISTS idx_system_docs_created_at ON system_docs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_docs_parent_doc ON system_docs(parent_doc_id);

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for automatic timestamp updates
CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_system_docs_updated_at BEFORE UPDATE ON system_docs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();