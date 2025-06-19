-- Data Integrity Check Script
-- Run this in your Supabase SQL Editor to check for data issues

-- 1. Check for orphaned scraped_items (items without corresponding data_sources)
SELECT 
    'Orphaned scraped_items' as check_type,
    COUNT(*) as count
FROM scraped_items si
LEFT JOIN data_sources ds ON si.source_id = ds.id
WHERE ds.id IS NULL;

-- 2. Check source type distribution
SELECT 
    'Source types distribution' as check_type,
    ds.type as source_type,
    COUNT(ds.id) as source_count,
    COUNT(si.id) as items_count
FROM data_sources ds
LEFT JOIN scraped_items si ON ds.id = si.source_id
GROUP BY ds.type
ORDER BY items_count DESC;

-- 3. Check recent scraping activity (last 30 days)
SELECT 
    'Recent scraping activity' as check_type,
    ds.name as source_name,
    ds.type as source_type,
    COUNT(si.id) as recent_items,
    MAX(si.scraped_at) as last_scraped
FROM data_sources ds
LEFT JOIN scraped_items si ON ds.id = si.source_id 
    AND si.scraped_at >= NOW() - INTERVAL '30 days'
GROUP BY ds.id, ds.name, ds.type
ORDER BY recent_items DESC;

-- 4. Check AI processing status
SELECT 
    'AI processing status' as check_type,
    COUNT(*) as total_items,
    COUNT(CASE WHEN is_cybersecurity_related IS NOT NULL THEN 1 END) as ai_processed,
    COUNT(CASE WHEN is_cybersecurity_related = true THEN 1 END) as breach_detected,
    ROUND(
        COUNT(CASE WHEN is_cybersecurity_related IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 
        2
    ) as processing_percentage
FROM scraped_items;

-- 5. Check for data quality issues
SELECT 
    'Data quality issues' as check_type,
    COUNT(CASE WHEN title IS NULL OR title = '' THEN 1 END) as missing_titles,
    COUNT(CASE WHEN item_url IS NULL OR item_url = '' THEN 1 END) as missing_urls,
    COUNT(CASE WHEN publication_date IS NULL THEN 1 END) as missing_pub_dates,
    COUNT(CASE WHEN scraped_at IS NULL THEN 1 END) as missing_scraped_dates
FROM scraped_items;

-- 6. Check view vs table consistency
SELECT 
    'View vs table consistency' as check_type,
    (SELECT COUNT(*) FROM scraped_items) as scraped_items_count,
    (SELECT COUNT(*) FROM v_breach_dashboard) as dashboard_view_count,
    (SELECT COUNT(*) FROM scraped_items) - (SELECT COUNT(*) FROM v_breach_dashboard) as difference;

-- 7. Create function to check orphaned items (for Python script)
CREATE OR REPLACE FUNCTION check_orphaned_items()
RETURNS TABLE(scraped_item_id BIGINT, source_id BIGINT)
LANGUAGE SQL
AS $$
    SELECT si.id, si.source_id
    FROM scraped_items si
    LEFT JOIN data_sources ds ON si.source_id = ds.id
    WHERE ds.id IS NULL;
$$;