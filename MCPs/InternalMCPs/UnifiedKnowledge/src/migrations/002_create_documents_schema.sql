-- Migration 002: Create document versioning schema for Active-Archive pattern
-- Created: 2025-07-06
-- Author: CCD (Database & Docker Specialist)
-- Purpose: Implement PostgreSQL archive layer for document versioning system

-- Table to store master document information
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Table to store every version of a document's content
CREATE TABLE IF NOT EXISTS document_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT,
    author VARCHAR(255),
    version_number INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT
);

-- Indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_documents_created_by ON documents(created_by);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_updated_at ON documents(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_metadata ON documents USING GIN(metadata);

CREATE INDEX IF NOT EXISTS idx_doc_revisions_document_id ON document_revisions(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_revisions_created_at ON document_revisions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_doc_revisions_version ON document_revisions(document_id, version_number);
CREATE INDEX IF NOT EXISTS idx_doc_revisions_author ON document_revisions(author);

-- Trigger function to automatically update the 'updated_at' timestamp on the parent document
CREATE OR REPLACE FUNCTION update_document_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE documents
    SET updated_at = NOW()
    WHERE id = NEW.document_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to execute the timestamp update function
CREATE TRIGGER trigger_update_document_timestamp
AFTER INSERT ON document_revisions
FOR EACH ROW
EXECUTE FUNCTION update_document_timestamp();

-- Additional constraint to ensure version numbers are sequential
CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_revisions_unique_version 
ON document_revisions(document_id, version_number);

-- View for latest document revisions (useful for queries)
CREATE OR REPLACE VIEW latest_document_revisions AS
SELECT DISTINCT ON (d.id) 
    d.id as document_id,
    d.title,
    d.created_by,
    d.created_at as document_created_at,
    d.updated_at as document_updated_at,
    d.metadata,
    dr.id as revision_id,
    dr.content,
    dr.author as last_author,
    dr.version_number,
    dr.created_at as revision_created_at,
    dr.notes
FROM documents d
LEFT JOIN document_revisions dr ON d.id = dr.document_id
ORDER BY d.id, dr.version_number DESC;

-- Grant necessary permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON documents TO legacymind;
GRANT SELECT, INSERT, UPDATE, DELETE ON document_revisions TO legacymind;
GRANT SELECT ON latest_document_revisions TO legacymind;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO legacymind;