#!/usr/bin/env python3
"""
Database Change Tracker for Breach Scraping

This script tracks database changes before and after scraper runs to provide
comprehensive reporting on new breaches, news articles, and affected individuals.

Usage:
  python database_change_tracker.py --snapshot    # Take pre-scraping snapshot
  python database_change_tracker.py --report      # Generate post-scraping report
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Snapshot file location
SNAPSHOT_FILE = '/tmp/scraper_snapshot.json'

def get_database_stats():
    """
    Get comprehensive database statistics.
    """
    try:
        # Import here to avoid issues if not available
        from supabase import create_client, Client
        
        SUPABASE_URL = os.environ.get("SUPABASE_URL")
        SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
        
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
            
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        
        stats = {}
        
        # Overall counts
        response = supabase.table("scraped_items").select("*", count="exact", head=True).execute()
        stats['total_items'] = response.count or 0
        
        # Counts by source type
        response = supabase.table("v_breach_dashboard").select("source_type").execute()
        source_type_counts = {}
        for item in response.data or []:
            source_type = item.get('source_type', 'Unknown')
            source_type_counts[source_type] = source_type_counts.get(source_type, 0) + 1
        stats['by_source_type'] = source_type_counts

        # Counts by individual source
        response = supabase.table("v_breach_dashboard").select("source_name").execute()
        source_counts = {}
        for item in response.data or []:
            source_name = item.get('source_name', 'Unknown')
            source_counts[source_name] = source_counts.get(source_name, 0) + 1
        stats['by_source'] = source_counts
        
        # Get all data and categorize in Python to avoid complex Supabase queries
        all_response = supabase.table("v_breach_dashboard").select("source_type, affected_individuals").execute()

        breach_count = 0
        news_count = 0
        total_affected = 0

        breach_types = ['State AG', 'Government Portal', 'Breach Database', 'State Cybersecurity', 'State Agency', 'API']
        news_types = ['News Feed', 'Company IR']

        for item in all_response.data or []:
            source_type = item.get('source_type', '')
            affected = item.get('affected_individuals', 0) or 0

            if source_type in breach_types:
                breach_count += 1
                total_affected += affected
            elif source_type in news_types:
                news_count += 1

        stats['breach_count'] = breach_count
        stats['news_count'] = news_count
        stats['total_affected'] = total_affected
        
        # Recent items (last 24 hours)
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        response = supabase.table("scraped_items").select("*", count="exact", head=True).gte('scraped_at', yesterday).execute()
        stats['recent_items'] = response.count or 0
        
        # Today's items
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        response = supabase.table("scraped_items").select("*", count="exact", head=True).gte('scraped_at', today).execute()
        stats['today_items'] = response.count or 0
        
        stats['timestamp'] = datetime.now().isoformat()
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        return None

def take_snapshot():
    """
    Take a snapshot of current database state.
    """
    logger.info("📸 Taking database snapshot...")
    
    stats = get_database_stats()
    if not stats:
        logger.error("Failed to get database statistics")
        return False
        
    try:
        with open(SNAPSHOT_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
        
        logger.info(f"✅ Snapshot saved to {SNAPSHOT_FILE}")
        logger.info(f"📊 Current totals: {stats['total_items']} items, {stats['breach_count']} breaches, {stats['news_count']} news")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save snapshot: {e}")
        return False

def generate_report():
    """
    Generate a report comparing current state to snapshot.
    """
    logger.info("📊 Generating database change report...")
    
    # Load snapshot
    try:
        with open(SNAPSHOT_FILE, 'r') as f:
            before_stats = json.load(f)
    except FileNotFoundError:
        logger.error("No snapshot file found. Run with --snapshot first.")
        return False
    except Exception as e:
        logger.error(f"Failed to load snapshot: {e}")
        return False
    
    # Get current stats
    after_stats = get_database_stats()
    if not after_stats:
        logger.error("Failed to get current database statistics")
        return False
    
    # Calculate changes
    changes = {
        'total_items': after_stats['total_items'] - before_stats['total_items'],
        'breach_count': after_stats['breach_count'] - before_stats['breach_count'],
        'news_count': after_stats['news_count'] - before_stats['news_count'],
        'total_affected': after_stats['total_affected'] - before_stats['total_affected'],
        'recent_items': after_stats['recent_items'] - before_stats.get('recent_items', 0),
        'today_items': after_stats['today_items'] - before_stats.get('today_items', 0)
    }
    
    # Calculate source-specific changes
    source_changes = {}
    for source, after_count in after_stats['by_source'].items():
        before_count = before_stats['by_source'].get(source, 0)
        change = after_count - before_count
        if change > 0:
            source_changes[source] = change
    
    # Calculate source type changes
    source_type_changes = {}
    for source_type, after_count in after_stats['by_source_type'].items():
        before_count = before_stats['by_source_type'].get(source_type, 0)
        change = after_count - before_count
        if change > 0:
            source_type_changes[source_type] = change
    
    # Generate report
    print("\n" + "="*80)
    print("🚨 BREACH SCRAPING RESULTS SUMMARY")
    print("="*80)
    
    print(f"📅 Scraping Period: {before_stats['timestamp']} → {after_stats['timestamp']}")
    print()
    
    # Overall changes
    print("📊 OVERALL CHANGES:")
    print(f"   📄 Total Items: {before_stats['total_items']:,} → {after_stats['total_items']:,} (+{changes['total_items']:,})")
    print(f"   🚨 Breach Records: {before_stats['breach_count']:,} → {after_stats['breach_count']:,} (+{changes['breach_count']:,})")
    print(f"   📰 News Articles: {before_stats['news_count']:,} → {after_stats['news_count']:,} (+{changes['news_count']:,})")
    print(f"   👥 People Affected: {before_stats['total_affected']:,} → {after_stats['total_affected']:,} (+{changes['total_affected']:,})")
    print()
    
    # Source type breakdown
    if source_type_changes:
        print("📋 NEW ITEMS BY CATEGORY:")
        for source_type, count in sorted(source_type_changes.items(), key=lambda x: x[1], reverse=True):
            print(f"   {source_type}: +{count:,}")
        print()
    
    # Individual source breakdown
    if source_changes:
        print("🔍 NEW ITEMS BY SOURCE:")
        for source, count in sorted(source_changes.items(), key=lambda x: x[1], reverse=True):
            print(f"   {source}: +{count:,}")
        print()
    
    # Summary
    if changes['total_items'] > 0:
        print("✅ SCRAPING SUCCESS!")
        print(f"   🎯 {changes['total_items']:,} new items discovered")
        if changes['breach_count'] > 0:
            print(f"   🚨 {changes['breach_count']:,} new breach notifications")
        if changes['news_count'] > 0:
            print(f"   📰 {changes['news_count']:,} new news articles")
        if changes['total_affected'] > 0:
            print(f"   👥 {changes['total_affected']:,} additional people affected")
    else:
        print("ℹ️  NO NEW ITEMS FOUND")
        print("   All sources appear to be up-to-date")
    
    print("="*80)
    
    # Set GitHub Actions output
    if os.environ.get('GITHUB_ACTIONS'):
        with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
            f.write(f"new_items={changes['total_items']}\n")
            f.write(f"new_breaches={changes['breach_count']}\n")
            f.write(f"new_news={changes['news_count']}\n")
            f.write(f"new_affected={changes['total_affected']}\n")
    
    return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage:")
        print("  python database_change_tracker.py --snapshot    # Take pre-scraping snapshot")
        print("  python database_change_tracker.py --report      # Generate post-scraping report")
        sys.exit(1)
    
    if sys.argv[1] == "--snapshot":
        success = take_snapshot()
        sys.exit(0 if success else 1)
    elif sys.argv[1] == "--report":
        success = generate_report()
        sys.exit(0 if success else 1)
    else:
        print("Invalid argument. Use --snapshot or --report")
        sys.exit(1)
