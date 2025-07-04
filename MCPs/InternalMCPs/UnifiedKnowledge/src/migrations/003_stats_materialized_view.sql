-- Create materialized view for ticket statistics
-- This view pre-aggregates ticket data for efficient stats queries

CREATE MATERIALIZED VIEW IF NOT EXISTS ticket_stats_mv AS
SELECT 
    -- Basic counts by status
    COUNT(*) FILTER (WHERE status = 'OPEN') as open_count,
    COUNT(*) FILTER (WHERE status = 'IN_PROGRESS') as in_progress_count,
    COUNT(*) FILTER (WHERE status = 'COMPLETE') as complete_count,
    COUNT(*) FILTER (WHERE status = 'CLOSED') as closed_count,
    COUNT(*) as total_count,
    
    -- Counts by priority
    COUNT(*) FILTER (WHERE priority = 'critical') as critical_count,
    COUNT(*) FILTER (WHERE priority = 'high') as high_count,
    COUNT(*) FILTER (WHERE priority = 'medium') as medium_count,
    COUNT(*) FILTER (WHERE priority = 'low') as low_count,
    
    -- Average times
    AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/3600)::numeric(10,2) as avg_lifetime_hours,
    AVG(estimated_hours)::numeric(10,2) as avg_estimated_hours,
    
    -- Work log statistics from work_logs table
    COALESCE((SELECT SUM(hours_worked)::numeric(10,2) FROM work_logs), 0) as total_logged_hours,
    COALESCE((SELECT COUNT(DISTINCT user_id) FROM work_logs), 0) as unique_contributors,
    
    -- Completion metrics
    COUNT(*) FILTER (WHERE status IN ('COMPLETE', 'CLOSED')) as completed_count,
    CASE 
        WHEN COUNT(*) > 0 THEN 
            (COUNT(*) FILTER (WHERE status IN ('COMPLETE', 'CLOSED'))::numeric / COUNT(*)::numeric * 100)::numeric(5,2)
        ELSE 0 
    END as completion_rate,
    
    -- Time-based metrics
    MIN(created_at) as oldest_ticket_date,
    MAX(created_at) as newest_ticket_date,
    
    -- Grouping dimensions (for filtering)
    status,
    priority,
    type,
    category,
    assignee,
    reporter
FROM tickets
GROUP BY status, priority, type, category, assignee, reporter;

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_ticket_stats_mv_status ON ticket_stats_mv(status);
CREATE INDEX IF NOT EXISTS idx_ticket_stats_mv_priority ON ticket_stats_mv(priority);
CREATE INDEX IF NOT EXISTS idx_ticket_stats_mv_type ON ticket_stats_mv(type);
CREATE INDEX IF NOT EXISTS idx_ticket_stats_mv_category ON ticket_stats_mv(category);
CREATE INDEX IF NOT EXISTS idx_ticket_stats_mv_assignee ON ticket_stats_mv(assignee);
CREATE INDEX IF NOT EXISTS idx_ticket_stats_mv_reporter ON ticket_stats_mv(reporter);

-- Function to refresh the materialized view
CREATE OR REPLACE FUNCTION refresh_ticket_stats_mv()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY ticket_stats_mv;
END;
$$ LANGUAGE plpgsql;

-- Create a trigger to refresh stats periodically (requires pg_cron extension)
-- Alternatively, call refresh_ticket_stats_mv() manually or via scheduled job