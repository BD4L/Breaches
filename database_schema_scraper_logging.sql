-- ============================================================================
-- SCRAPER LOGGING SYSTEM - Database Schema
-- ============================================================================
-- This schema provides comprehensive logging for all scraper activities
-- Run this script in your Supabase SQL Editor to create the logging tables

-- ============================================================================
-- 1. SCRAPER RUNS TABLE - Track individual scraper executions
-- ============================================================================
CREATE TABLE IF NOT EXISTS scraper_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scraper_name TEXT NOT NULL,
    source_id BIGINT REFERENCES data_sources(id),
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'cancelled')) DEFAULT 'running',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_seconds DECIMAL(10,2),
    
    -- Statistics
    items_processed INTEGER DEFAULT 0,
    items_inserted INTEGER DEFAULT 0,
    items_skipped INTEGER DEFAULT 0,
    success BOOLEAN,
    error_message TEXT,
    
    -- Context information
    github_context JSONB DEFAULT '{}',
    environment JSONB DEFAULT '{}',
    performance_metrics JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_scraper_runs_scraper_name ON scraper_runs(scraper_name);
CREATE INDEX IF NOT EXISTS idx_scraper_runs_started_at ON scraper_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_scraper_runs_status ON scraper_runs(status);
CREATE INDEX IF NOT EXISTS idx_scraper_runs_success ON scraper_runs(success);

-- ============================================================================
-- 2. SCRAPER PROGRESS TABLE - Track progress during execution
-- ============================================================================
CREATE TABLE IF NOT EXISTS scraper_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES scraper_runs(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    message TEXT NOT NULL,
    
    -- Progress metrics
    items_processed INTEGER DEFAULT 0,
    items_inserted INTEGER DEFAULT 0,
    items_skipped INTEGER DEFAULT 0,
    current_page INTEGER,
    total_pages INTEGER,
    
    -- Additional context
    context JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_scraper_progress_run_id ON scraper_progress(run_id);
CREATE INDEX IF NOT EXISTS idx_scraper_progress_timestamp ON scraper_progress(timestamp);

-- ============================================================================
-- 3. SCRAPER ERRORS TABLE - Track errors during execution
-- ============================================================================
CREATE TABLE IF NOT EXISTS scraper_errors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES scraper_runs(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    error_type TEXT NOT NULL DEFAULT 'general',
    error_message TEXT NOT NULL,
    
    -- Error context
    context JSONB DEFAULT '{}',
    stack_trace TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_scraper_errors_run_id ON scraper_errors(run_id);
CREATE INDEX IF NOT EXISTS idx_scraper_errors_error_type ON scraper_errors(error_type);
CREATE INDEX IF NOT EXISTS idx_scraper_errors_timestamp ON scraper_errors(timestamp);

-- ============================================================================
-- 4. SCRAPER ACTIVITIES TABLE - Simple activity logging
-- ============================================================================
CREATE TABLE IF NOT EXISTS scraper_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scraper_name TEXT NOT NULL,
    action TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    details JSONB DEFAULT '{}',
    github_context JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_scraper_activities_scraper_name ON scraper_activities(scraper_name);
CREATE INDEX IF NOT EXISTS idx_scraper_activities_action ON scraper_activities(action);
CREATE INDEX IF NOT EXISTS idx_scraper_activities_timestamp ON scraper_activities(timestamp);

-- ============================================================================
-- 5. SCRAPER STATISTICS VIEW - Aggregated statistics
-- ============================================================================
CREATE OR REPLACE VIEW v_scraper_statistics AS
SELECT 
    scraper_name,
    COUNT(*) as total_runs,
    COUNT(*) FILTER (WHERE success = true) as successful_runs,
    COUNT(*) FILTER (WHERE success = false) as failed_runs,
    ROUND(AVG(duration_seconds), 2) as avg_duration_seconds,
    SUM(items_processed) as total_items_processed,
    SUM(items_inserted) as total_items_inserted,
    SUM(items_skipped) as total_items_skipped,
    MAX(started_at) as last_run_at,
    MIN(started_at) as first_run_at
FROM scraper_runs 
WHERE status = 'completed'
GROUP BY scraper_name
ORDER BY last_run_at DESC;

-- ============================================================================
-- 6. RECENT SCRAPER ACTIVITY VIEW - Last 24 hours
-- ============================================================================
CREATE OR REPLACE VIEW v_recent_scraper_activity AS
SELECT 
    sr.scraper_name,
    sr.status,
    sr.started_at,
    sr.completed_at,
    sr.duration_seconds,
    sr.items_processed,
    sr.items_inserted,
    sr.items_skipped,
    sr.success,
    sr.error_message,
    ds.name as source_name,
    ds.type as source_type
FROM scraper_runs sr
LEFT JOIN data_sources ds ON sr.source_id = ds.id
WHERE sr.started_at >= NOW() - INTERVAL '24 hours'
ORDER BY sr.started_at DESC;

-- ============================================================================
-- 7. SCRAPER PERFORMANCE VIEW - Performance metrics
-- ============================================================================
CREATE OR REPLACE VIEW v_scraper_performance AS
SELECT 
    scraper_name,
    DATE(started_at) as run_date,
    COUNT(*) as runs_count,
    AVG(duration_seconds) as avg_duration,
    AVG(items_processed) as avg_items_processed,
    AVG(items_inserted) as avg_items_inserted,
    AVG(CASE WHEN items_processed > 0 THEN (items_inserted::float / items_processed) * 100 ELSE 0 END) as success_rate_percent
FROM scraper_runs 
WHERE status = 'completed' AND started_at >= NOW() - INTERVAL '30 days'
GROUP BY scraper_name, DATE(started_at)
ORDER BY run_date DESC, scraper_name;

-- ============================================================================
-- 8. FUNCTIONS FOR AUTOMATIC UPDATES
-- ============================================================================

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to automatically update updated_at on scraper_runs
DROP TRIGGER IF EXISTS update_scraper_runs_updated_at ON scraper_runs;
CREATE TRIGGER update_scraper_runs_updated_at
    BEFORE UPDATE ON scraper_runs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 9. CLEANUP FUNCTION - Remove old logs
-- ============================================================================
CREATE OR REPLACE FUNCTION cleanup_old_scraper_logs(days_to_keep INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Delete old scraper runs and related data (cascades to progress and errors)
    DELETE FROM scraper_runs 
    WHERE started_at < NOW() - (days_to_keep || ' days')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    -- Delete old activities
    DELETE FROM scraper_activities 
    WHERE timestamp < NOW() - (days_to_keep || ' days')::INTERVAL;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 10. SAMPLE QUERIES FOR MONITORING
-- ============================================================================

-- Get recent scraper runs
-- SELECT * FROM v_recent_scraper_activity LIMIT 20;

-- Get scraper statistics
-- SELECT * FROM v_scraper_statistics;

-- Get performance trends
-- SELECT * FROM v_scraper_performance WHERE scraper_name = 'california_ag' LIMIT 7;

-- Get current running scrapers
-- SELECT scraper_name, started_at, items_processed FROM scraper_runs WHERE status = 'running';

-- Get error summary for last 24 hours
-- SELECT scraper_name, error_type, COUNT(*) as error_count 
-- FROM scraper_runs sr JOIN scraper_errors se ON sr.id = se.run_id 
-- WHERE sr.started_at >= NOW() - INTERVAL '24 hours' 
-- GROUP BY scraper_name, error_type;

-- ============================================================================
-- 11. ENABLE ROW LEVEL SECURITY (Optional)
-- ============================================================================

-- Enable RLS on logging tables (uncomment if needed)
-- ALTER TABLE scraper_runs ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE scraper_progress ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE scraper_errors ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE scraper_activities ENABLE ROW LEVEL SECURITY;

-- Create policies for service role access (uncomment if RLS enabled)
-- CREATE POLICY "Service role can manage scraper logs" ON scraper_runs FOR ALL USING (true);
-- CREATE POLICY "Service role can manage scraper progress" ON scraper_progress FOR ALL USING (true);
-- CREATE POLICY "Service role can manage scraper errors" ON scraper_errors FOR ALL USING (true);
-- CREATE POLICY "Service role can manage scraper activities" ON scraper_activities FOR ALL USING (true);

-- ============================================================================
-- SETUP COMPLETE
-- ============================================================================
-- The scraper logging system is now ready to use!
-- 
-- Usage in scrapers:
-- 1. Import: from scraper_logger import ScraperLogger
-- 2. Initialize: logger = ScraperLogger("scraper_name")
-- 3. Start: logger.start_run()
-- 4. Progress: logger.log_progress("Processing page 1", items_processed=10)
-- 5. Errors: logger.log_error("Network timeout", "network")
-- 6. End: logger.end_run(success=True, items_processed=50, items_inserted=45)
