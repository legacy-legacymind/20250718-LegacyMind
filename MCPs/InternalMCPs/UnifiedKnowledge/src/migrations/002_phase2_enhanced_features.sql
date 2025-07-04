-- Phase 2 Enhanced Features Migration
-- UnifiedWorkflow Database Schema Extension

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Work logs table for time tracking
CREATE TABLE IF NOT EXISTS work_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    hours_worked DECIMAL(5, 2) NOT NULL CHECK (hours_worked > 0),
    work_date DATE NOT NULL DEFAULT CURRENT_DATE,
    description TEXT,
    work_type VARCHAR(50) DEFAULT 'DEVELOPMENT',
    billable BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Ticket statistics materialized view
CREATE MATERIALIZED VIEW IF NOT EXISTS ticket_stats_mv AS
SELECT
    t.status,
    t.priority,
    t.type,
    t.category,
    t.assignee,
    t.reporter,
    COUNT(*) as count,
    AVG(t.estimated_hours) as avg_estimated_hours,
    SUM(COALESCE(wl.total_hours, 0)) as total_logged_hours,
    AVG(COALESCE(wl.total_hours, 0)) as avg_logged_hours,
    MIN(t.created_at) as oldest_ticket,
    MAX(t.created_at) as newest_ticket,
    COUNT(CASE WHEN t.status IN ('CLOSED', 'CANCELLED') THEN 1 END) as completed_count,
    COUNT(CASE WHEN t.status NOT IN ('CLOSED', 'CANCELLED') THEN 1 END) as active_count,
    EXTRACT(EPOCH FROM (MAX(t.updated_at) - MIN(t.created_at))) / 3600 as lifecycle_hours
FROM tickets t
LEFT JOIN (
    SELECT 
        ticket_id,
        SUM(hours_worked) as total_hours,
        COUNT(*) as log_count
    FROM work_logs
    GROUP BY ticket_id
) wl ON t.ticket_id = wl.ticket_id
GROUP BY t.status, t.priority, t.type, t.category, t.assignee, t.reporter;

-- Indexes for work_logs table
CREATE INDEX IF NOT EXISTS idx_work_logs_ticket_id ON work_logs(ticket_id);
CREATE INDEX IF NOT EXISTS idx_work_logs_user_id ON work_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_work_logs_work_date ON work_logs(work_date DESC);
CREATE INDEX IF NOT EXISTS idx_work_logs_created_at ON work_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_work_logs_billable ON work_logs(billable);
CREATE INDEX IF NOT EXISTS idx_work_logs_work_type ON work_logs(work_type);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_work_logs_ticket_user ON work_logs(ticket_id, user_id);
CREATE INDEX IF NOT EXISTS idx_work_logs_user_date ON work_logs(user_id, work_date DESC);

-- Function to refresh materialized view
CREATE OR REPLACE FUNCTION refresh_ticket_stats()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW ticket_stats_mv;
END;
$$ LANGUAGE plpgsql;

-- Trigger for automatic updated_at timestamp on work_logs
CREATE TRIGGER update_work_logs_updated_at BEFORE UPDATE ON work_logs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to automatically refresh stats after significant changes
CREATE OR REPLACE FUNCTION trigger_stats_refresh()
RETURNS TRIGGER AS $$
BEGIN
    -- Refresh materialized view asynchronously (in production, consider using job queue)
    PERFORM refresh_ticket_stats();
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Triggers to refresh stats on data changes
CREATE TRIGGER refresh_stats_on_ticket_change 
    AFTER INSERT OR UPDATE OR DELETE ON tickets
    FOR EACH STATEMENT EXECUTE FUNCTION trigger_stats_refresh();

CREATE TRIGGER refresh_stats_on_work_log_change 
    AFTER INSERT OR UPDATE OR DELETE ON work_logs
    FOR EACH STATEMENT EXECUTE FUNCTION trigger_stats_refresh();

-- Initial refresh of materialized view
SELECT refresh_ticket_stats();