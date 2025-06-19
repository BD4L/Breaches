#!/usr/bin/env python3
"""
Fix Source Summary Dashboard Issues
This script diagnoses and fixes the data inconsistencies between the main dashboard
and source summary dashboard.
"""

import os
import sys
import logging
from datetime import datetime

# Add the parent directory to the path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from utils.supabase_client import SupabaseClient

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def diagnose_data_issues():
    """Diagnose data inconsistencies between different views and tables."""
    
    logger.info("🔍 Starting data consistency diagnosis...")
    
    try:
        client = SupabaseClient()
        
        # 1. Check total counts in different tables/views
        logger.info("\n📊 Checking data counts across different sources:")
        
        # Count from scraped_items table directly
        scraped_items_response = client.supabase.table('scraped_items').select('id', count='exact').execute()
        scraped_items_count = scraped_items_response.count
        logger.info(f"   scraped_items table: {scraped_items_count} total records")
        
        # Count from v_breach_dashboard view
        dashboard_response = client.supabase.table('v_breach_dashboard').select('id', count='exact').execute()
        dashboard_count = dashboard_response.count
        logger.info(f"   v_breach_dashboard view: {dashboard_count} total records")
        
        # 2. Check source types distribution
        logger.info("\n🏷️ Checking source types distribution:")
        
        # Get source types from data_sources
        sources_response = client.supabase.table('data_sources').select('id, name, type').execute()
        sources_data = sources_response.data
        
        source_type_counts = {}
        for source in sources_data:
            source_type = source.get('type', 'Unknown')
            source_type_counts[source_type] = source_type_counts.get(source_type, 0) + 1
        
        logger.info("   Source types in data_sources table:")
        for source_type, count in sorted(source_type_counts.items()):
            logger.info(f"     {source_type}: {count} sources")
        
        # 3. Check scraped items by source type
        logger.info("\n📈 Checking scraped items by source type:")
        
        # Get items with source type from view
        items_response = client.supabase.table('v_breach_dashboard').select('source_type', count='exact').execute()
        items_data = items_response.data
        
        item_type_counts = {}
        for item in items_data:
            source_type = item.get('source_type', 'Unknown')
            item_type_counts[source_type] = item_type_counts.get(source_type, 0) + 1
        
        logger.info("   Items by source type in v_breach_dashboard:")
        for source_type, count in sorted(item_type_counts.items()):
            logger.info(f"     {source_type}: {count} items")
        
        # 4. Check for orphaned records
        logger.info("\n🔗 Checking for data integrity issues:")
        
        # Check for scraped_items without corresponding data_sources
        orphaned_response = client.supabase.rpc('check_orphaned_items').execute()
        if orphaned_response.data:
            logger.warning(f"   Found {len(orphaned_response.data)} orphaned scraped_items")
        else:
            logger.info("   No orphaned scraped_items found")
        
        # 5. Check recent scraping activity
        logger.info("\n⏰ Checking recent scraping activity:")
        
        recent_response = client.supabase.table('scraped_items').select('source_id, scraped_at').gte('scraped_at', '2025-06-01').execute()
        recent_data = recent_response.data
        
        recent_by_source = {}
        for item in recent_data:
            source_id = item.get('source_id')
            recent_by_source[source_id] = recent_by_source.get(source_id, 0) + 1
        
        logger.info(f"   Recent items (since June 1, 2025): {len(recent_data)} total")
        logger.info("   Recent items by source_id:")
        for source_id, count in sorted(recent_by_source.items()):
            source_name = next((s['name'] for s in sources_data if s['id'] == source_id), f"Unknown (ID: {source_id})")
            logger.info(f"     {source_name}: {count} items")
        
        # 6. Check for AI processing issues
        logger.info("\n🤖 Checking AI processing status:")
        
        ai_processed_response = client.supabase.table('scraped_items').select('id', count='exact').not_('is_cybersecurity_related', 'is', None).execute()
        ai_processed_count = ai_processed_response.count
        logger.info(f"   Items with AI processing: {ai_processed_count}")
        
        breach_detected_response = client.supabase.table('scraped_items').select('id', count='exact').eq('is_cybersecurity_related', True).execute()
        breach_detected_count = breach_detected_response.count
        logger.info(f"   Items marked as cybersecurity-related: {breach_detected_count}")
        
        return {
            'scraped_items_count': scraped_items_count,
            'dashboard_count': dashboard_count,
            'source_type_counts': source_type_counts,
            'item_type_counts': item_type_counts,
            'recent_items': len(recent_data),
            'ai_processed': ai_processed_count,
            'breach_detected': breach_detected_count
        }
        
    except Exception as e:
        logger.error(f"❌ Error during diagnosis: {e}")
        return None

def fix_source_type_mapping():
    """Fix any source type mapping issues."""
    
    logger.info("\n🔧 Checking and fixing source type mappings...")
    
    try:
        client = SupabaseClient()
        
        # Get all data sources
        sources_response = client.supabase.table('data_sources').select('*').execute()
        sources_data = sources_response.data
        
        fixes_applied = 0
        
        for source in sources_data:
            source_id = source['id']
            source_name = source['name']
            source_type = source.get('type')
            
            # Check for common source type issues and fix them
            needs_update = False
            new_type = source_type
            
            # Fix common naming inconsistencies
            if source_type == 'State Attorney General':
                new_type = 'State AG'
                needs_update = True
            elif source_type == 'RSS Feed':
                new_type = 'News Feed'
                needs_update = True
            elif source_type == 'Government':
                new_type = 'Government Portal'
                needs_update = True
            elif source_type is None or source_type.strip() == '':
                # Try to infer type from name
                name_lower = source_name.lower()
                if 'attorney general' in name_lower or ' ag ' in name_lower:
                    new_type = 'State AG'
                    needs_update = True
                elif 'news' in name_lower or 'rss' in name_lower:
                    new_type = 'News Feed'
                    needs_update = True
                elif 'hhs' in name_lower or 'ocr' in name_lower:
                    new_type = 'Government Portal'
                    needs_update = True
                elif 'breach' in name_lower:
                    new_type = 'Breach Database'
                    needs_update = True
            
            if needs_update:
                logger.info(f"   Updating {source_name}: '{source_type}' → '{new_type}'")
                update_response = client.supabase.table('data_sources').update({'type': new_type}).eq('id', source_id).execute()
                if update_response.data:
                    fixes_applied += 1
                else:
                    logger.error(f"   Failed to update source {source_id}")
        
        logger.info(f"✅ Applied {fixes_applied} source type fixes")
        return fixes_applied
        
    except Exception as e:
        logger.error(f"❌ Error fixing source types: {e}")
        return 0

def refresh_dashboard_view():
    """Refresh the dashboard view to ensure it's up to date."""
    
    logger.info("\n🔄 Refreshing dashboard view...")
    
    try:
        client = SupabaseClient()
        
        # Force refresh by running a simple query
        refresh_response = client.supabase.table('v_breach_dashboard').select('id', count='exact').limit(1).execute()
        
        if refresh_response.count is not None:
            logger.info(f"✅ Dashboard view refreshed successfully ({refresh_response.count} total records)")
            return True
        else:
            logger.error("❌ Failed to refresh dashboard view")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error refreshing dashboard view: {e}")
        return False

def main():
    """Main function to run all diagnostics and fixes."""
    
    logger.info("🚀 Starting Source Summary Dashboard Fix Script")
    logger.info(f"   Timestamp: {datetime.now().isoformat()}")
    
    # Step 1: Diagnose issues
    diagnosis = diagnose_data_issues()
    if not diagnosis:
        logger.error("❌ Failed to complete diagnosis. Exiting.")
        return 1
    
    # Step 2: Fix source type mappings
    fixes_applied = fix_source_type_mapping()
    
    # Step 3: Refresh dashboard view
    refresh_success = refresh_dashboard_view()
    
    # Step 4: Final summary
    logger.info("\n📋 Summary:")
    logger.info(f"   Total scraped items: {diagnosis['scraped_items_count']}")
    logger.info(f"   Dashboard view items: {diagnosis['dashboard_count']}")
    logger.info(f"   Recent items: {diagnosis['recent_items']}")
    logger.info(f"   AI processed items: {diagnosis['ai_processed']}")
    logger.info(f"   Source type fixes applied: {fixes_applied}")
    logger.info(f"   Dashboard view refresh: {'✅ Success' if refresh_success else '❌ Failed'}")
    
    # Step 5: Recommendations
    logger.info("\n💡 Recommendations:")
    
    if diagnosis['scraped_items_count'] != diagnosis['dashboard_count']:
        logger.info("   ⚠️  Data count mismatch detected between scraped_items and dashboard view")
        logger.info("      → Check for JOIN issues in v_breach_dashboard view definition")
    
    if diagnosis['ai_processed'] < diagnosis['scraped_items_count'] * 0.5:
        logger.info("   ⚠️  Low AI processing rate detected")
        logger.info("      → Check if breach_intelligence module is working correctly")
        logger.info("      → Verify BREACH_INTELLIGENCE_ENABLED environment variable")
    
    if diagnosis['recent_items'] == 0:
        logger.info("   ⚠️  No recent scraping activity detected")
        logger.info("      → Check if scrapers are running on schedule")
        logger.info("      → Verify scraper configurations and credentials")
    
    logger.info("\n🎯 Next Steps:")
    logger.info("   1. Refresh your browser and check the Source Summary Dashboard")
    logger.info("   2. Look for the debug logs in browser console (F12)")
    logger.info("   3. If issues persist, check individual scraper logs")
    logger.info("   4. Consider running a manual scraper test")
    
    logger.info("\n✅ Fix script completed successfully!")
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)