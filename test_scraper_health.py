#!/usr/bin/env python3
"""
Scraper Health Check Script
Tests the current status of scrapers and identifies any immediate issues.
"""

import os
import sys
import logging
import requests
from datetime import datetime, timedelta

# Add the parent directory to the path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from utils.supabase_client import SupabaseClient

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_github_actions_status():
    """Check the status of GitHub Actions workflows."""
    
    logger.info("🔍 Checking GitHub Actions workflow status...")
    
    try:
        github_token = os.environ.get('GITHUB_TOKEN')
        if not github_token:
            logger.warning("⚠️ GITHUB_TOKEN not found - skipping GitHub Actions check")
            return None
        
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Get workflow runs for parallel scrapers
        parallel_url = "https://api.github.com/repos/BD4L/Breaches/actions/workflows/165181175/runs?per_page=5"
        parallel_response = requests.get(parallel_url, headers=headers)
        
        if parallel_response.status_code == 200:
            parallel_runs = parallel_response.json()['workflow_runs']
            logger.info(f"✅ Parallel Scrapers - Last 5 runs:")
            for run in parallel_runs:
                status = run['conclusion'] or run['status']
                created = run['created_at'][:19].replace('T', ' ')
                logger.info(f"   {created} UTC: {status}")
        else:
            logger.warning(f"⚠️ Failed to get parallel scraper status: {parallel_response.status_code}")
        
        # Get workflow runs for RSS/API scrapers
        rss_url = "https://api.github.com/repos/BD4L/Breaches/actions/workflows/168948208/runs?per_page=5"
        rss_response = requests.get(rss_url, headers=headers)
        
        if rss_response.status_code == 200:
            rss_runs = rss_response.json()['workflow_runs']
            logger.info(f"✅ RSS/API Scrapers - Last 5 runs:")
            for run in rss_runs:
                status = run['conclusion'] or run['status']
                created = run['created_at'][:19].replace('T', ' ')
                logger.info(f"   {created} UTC: {status}")
        else:
            logger.warning(f"⚠️ Failed to get RSS/API scraper status: {rss_response.status_code}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error checking GitHub Actions: {e}")
        return False

def check_recent_scraping_activity():
    """Check recent scraping activity in the database."""
    
    logger.info("\n📊 Checking recent scraping activity...")
    
    try:
        client = SupabaseClient()
        
        # Check items scraped in last 24 hours
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        
        recent_response = client.supabase.table('scraped_items').select('source_id, scraped_at').gte('scraped_at', yesterday).execute()
        recent_data = recent_response.data
        
        if recent_data:
            logger.info(f"✅ Found {len(recent_data)} items scraped in last 24 hours")
            
            # Group by source
            source_counts = {}
            for item in recent_data:
                source_id = item['source_id']
                source_counts[source_id] = source_counts.get(source_id, 0) + 1
            
            # Get source names
            sources_response = client.supabase.table('data_sources').select('id, name, type').execute()
            sources_data = sources_response.data
            source_map = {s['id']: s for s in sources_data}
            
            logger.info("   Recent activity by source:")
            for source_id, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
                source_info = source_map.get(source_id, {'name': f'Unknown (ID: {source_id})', 'type': 'Unknown'})
                logger.info(f"     {source_info['name']} ({source_info['type']}): {count} items")
        else:
            logger.warning("⚠️ No items scraped in last 24 hours - this might indicate an issue")
        
        return len(recent_data)
        
    except Exception as e:
        logger.error(f"❌ Error checking recent activity: {e}")
        return 0

def check_data_quality():
    """Check for basic data quality issues."""
    
    logger.info("\n🔍 Checking data quality...")
    
    try:
        client = SupabaseClient()
        
        # Check for items without titles
        no_title_response = client.supabase.table('scraped_items').select('id', count='exact').or_('title.is.null,title.eq.').execute()
        no_title_count = no_title_response.count
        
        # Check for items without URLs
        no_url_response = client.supabase.table('scraped_items').select('id', count='exact').or_('item_url.is.null,item_url.eq.').execute()
        no_url_count = no_url_response.count
        
        # Check for items without publication dates
        no_date_response = client.supabase.table('scraped_items').select('id', count='exact').is_('publication_date', None).execute()
        no_date_count = no_date_response.count
        
        # Check total items
        total_response = client.supabase.table('scraped_items').select('id', count='exact').execute()
        total_count = total_response.count
        
        logger.info(f"📊 Data Quality Report:")
        logger.info(f"   Total items: {total_count}")
        logger.info(f"   Missing titles: {no_title_count} ({(no_title_count/total_count*100):.1f}%)")
        logger.info(f"   Missing URLs: {no_url_count} ({(no_url_count/total_count*100):.1f}%)")
        logger.info(f"   Missing pub dates: {no_date_count} ({(no_date_count/total_count*100):.1f}%)")
        
        # Quality score
        quality_score = 100 - (no_title_count + no_url_count + no_date_count) / total_count * 100
        logger.info(f"   Quality Score: {quality_score:.1f}%")
        
        if quality_score > 95:
            logger.info("✅ Excellent data quality!")
        elif quality_score > 90:
            logger.info("✅ Good data quality")
        elif quality_score > 80:
            logger.warning("⚠️ Fair data quality - some issues detected")
        else:
            logger.warning("🚨 Poor data quality - significant issues detected")
        
        return quality_score
        
    except Exception as e:
        logger.error(f"❌ Error checking data quality: {e}")
        return 0

def check_ai_processing():
    """Check AI processing status."""
    
    logger.info("\n🤖 Checking AI processing status...")
    
    try:
        client = SupabaseClient()
        
        # Check total items
        total_response = client.supabase.table('scraped_items').select('id', count='exact').execute()
        total_count = total_response.count
        
        # Check AI processed items
        ai_processed_response = client.supabase.table('scraped_items').select('id', count='exact').not_('is_cybersecurity_related', 'is', None).execute()
        ai_processed_count = ai_processed_response.count
        
        # Check breach detected items
        breach_response = client.supabase.table('scraped_items').select('id', count='exact').eq('is_cybersecurity_related', True).execute()
        breach_count = breach_response.count
        
        processing_rate = (ai_processed_count / total_count * 100) if total_count > 0 else 0
        breach_rate = (breach_count / ai_processed_count * 100) if ai_processed_count > 0 else 0
        
        logger.info(f"📊 AI Processing Report:")
        logger.info(f"   Total items: {total_count}")
        logger.info(f"   AI processed: {ai_processed_count} ({processing_rate:.1f}%)")
        logger.info(f"   Breaches detected: {breach_count} ({breach_rate:.1f}% of processed)")
        
        if processing_rate > 80:
            logger.info("✅ Good AI processing coverage")
        elif processing_rate > 50:
            logger.warning("⚠️ Moderate AI processing coverage")
        else:
            logger.warning("🚨 Low AI processing coverage - check breach intelligence module")
        
        return processing_rate
        
    except Exception as e:
        logger.error(f"❌ Error checking AI processing: {e}")
        return 0

def check_email_configuration():
    """Check email alert configuration."""
    
    logger.info("\n📧 Checking email configuration...")
    
    try:
        # Check environment variables
        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_SERVICE_KEY')
        resend_key = os.environ.get('RESEND_API_KEY')
        from_email = os.environ.get('ALERT_FROM_EMAIL')
        
        logger.info("📊 Email Configuration Status:")
        logger.info(f"   SUPABASE_URL: {'✅ Set' if supabase_url else '❌ Missing'}")
        logger.info(f"   SUPABASE_SERVICE_KEY: {'✅ Set' if supabase_key else '❌ Missing'}")
        logger.info(f"   RESEND_API_KEY: {'✅ Set' if resend_key else '❌ Missing'}")
        logger.info(f"   ALERT_FROM_EMAIL: {'✅ Set' if from_email else '❌ Missing'}")
        
        missing_count = sum([1 for var in [supabase_url, supabase_key, resend_key, from_email] if not var])
        
        if missing_count == 0:
            logger.info("✅ All email configuration variables are set")
            
            # Check user preferences
            client = SupabaseClient()
            prefs_response = client.supabase.table('user_prefs').select('*').execute()
            prefs_data = prefs_response.data
            
            if prefs_data:
                logger.info(f"✅ Found {len(prefs_data)} user email preferences")
                verified_count = sum(1 for pref in prefs_data if pref.get('email_verified', False))
                logger.info(f"   Verified emails: {verified_count}/{len(prefs_data)}")
            else:
                logger.warning("⚠️ No user email preferences found")
            
            return True
        else:
            logger.warning(f"⚠️ {missing_count} email configuration variables are missing")
            return False
        
    except Exception as e:
        logger.error(f"❌ Error checking email configuration: {e}")
        return False

def main():
    """Main function to run all health checks."""
    
    logger.info("🚀 Starting Scraper Health Check")
    logger.info(f"   Timestamp: {datetime.now().isoformat()}")
    
    results = {}
    
    # Run all checks
    results['github_actions'] = check_github_actions_status()
    results['recent_activity'] = check_recent_scraping_activity()
    results['data_quality'] = check_data_quality()
    results['ai_processing'] = check_ai_processing()
    results['email_config'] = check_email_configuration()
    
    # Overall health assessment
    logger.info("\n🎯 Overall Health Assessment:")
    
    health_score = 0
    max_score = 5
    
    if results['github_actions']:
        health_score += 1
        logger.info("✅ GitHub Actions: Healthy")
    else:
        logger.warning("⚠️ GitHub Actions: Issues detected")
    
    if results['recent_activity'] > 0:
        health_score += 1
        logger.info("✅ Recent Activity: Active")
    else:
        logger.warning("⚠️ Recent Activity: No recent scraping")
    
    if results['data_quality'] > 90:
        health_score += 1
        logger.info("✅ Data Quality: Good")
    else:
        logger.warning("⚠️ Data Quality: Needs attention")
    
    if results['ai_processing'] > 50:
        health_score += 1
        logger.info("✅ AI Processing: Working")
    else:
        logger.warning("⚠️ AI Processing: Low coverage")
    
    if results['email_config']:
        health_score += 1
        logger.info("✅ Email Config: Configured")
    else:
        logger.warning("⚠️ Email Config: Issues detected")
    
    overall_health = (health_score / max_score) * 100
    
    logger.info(f"\n📊 Overall Health Score: {overall_health:.0f}% ({health_score}/{max_score})")
    
    if overall_health >= 80:
        logger.info("🟢 System Status: HEALTHY")
    elif overall_health >= 60:
        logger.info("🟡 System Status: FAIR - Some issues need attention")
    else:
        logger.info("🔴 System Status: POOR - Multiple issues detected")
    
    logger.info("\n✅ Health check completed!")
    
    return 0 if overall_health >= 80 else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)