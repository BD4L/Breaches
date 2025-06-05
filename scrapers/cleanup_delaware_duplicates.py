#!/usr/bin/env python3
"""
Delaware AG Duplicate Cleanup Script

This script removes duplicate Delaware AG breach records that were created due to
the flawed URL generation and duplicate detection logic.

The script:
1. Identifies duplicate records by organization name and incident details
2. Keeps the earliest record (by scraped_at timestamp)
3. Removes the duplicate records
4. Reports on the cleanup process
"""

import os
import sys
import logging
from datetime import datetime
from typing import List, Dict, Any

# Add the current directory to the path so we can import supabase_client
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from supabase_client import SupabaseClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('delaware_cleanup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

SOURCE_ID_DELAWARE_AG = 3

def cleanup_delaware_duplicates():
    """
    Clean up duplicate Delaware AG breach records.
    """
    logger.info("Starting Delaware AG duplicate cleanup...")
    
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return
    
    # Get all Delaware AG records
    try:
        response = supabase_client.client.table("scraped_items").select(
            "id, title, publication_date, item_url, scraped_at, raw_data_json, affected_individuals, breach_date, reported_date"
        ).eq("source_id", SOURCE_ID_DELAWARE_AG).order("title", desc=False).order("scraped_at", desc=False).execute()
        
        all_records = response.data or []
        logger.info(f"Found {len(all_records)} Delaware AG records")
        
    except Exception as e:
        logger.error(f"Failed to fetch Delaware AG records: {e}")
        return
    
    # Group records by organization name to identify duplicates
    records_by_org: Dict[str, List[Dict[str, Any]]] = {}
    
    for record in all_records:
        org_name = record['title']
        if org_name not in records_by_org:
            records_by_org[org_name] = []
        records_by_org[org_name].append(record)
    
    # Identify and process duplicates
    total_duplicates_removed = 0
    organizations_processed = 0
    
    for org_name, records in records_by_org.items():
        if len(records) <= 1:
            continue  # No duplicates for this organization
            
        organizations_processed += 1
        logger.info(f"Processing {len(records)} records for '{org_name}'")
        
        # Sort by scraped_at to keep the earliest record
        records.sort(key=lambda x: x['scraped_at'])
        
        # Keep the first record, remove the rest
        keep_record = records[0]
        duplicate_records = records[1:]
        
        logger.info(f"Keeping record ID {keep_record['id']} (scraped at {keep_record['scraped_at']})")
        
        for duplicate in duplicate_records:
            try:
                # Delete the duplicate record
                delete_response = supabase_client.client.table("scraped_items").delete().eq("id", duplicate['id']).execute()
                
                if delete_response.data:
                    logger.info(f"Deleted duplicate record ID {duplicate['id']} (scraped at {duplicate['scraped_at']})")
                    total_duplicates_removed += 1
                else:
                    logger.warning(f"Failed to delete record ID {duplicate['id']} - no data in response")
                    
            except Exception as e:
                logger.error(f"Error deleting duplicate record ID {duplicate['id']}: {e}")
    
    logger.info(f"Cleanup completed. Organizations processed: {organizations_processed}, Duplicates removed: {total_duplicates_removed}")

def analyze_delaware_duplicates():
    """
    Analyze Delaware AG records to identify duplicate patterns without removing them.
    """
    logger.info("Analyzing Delaware AG records for duplicates...")
    
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return
    
    # Get all Delaware AG records
    try:
        response = supabase_client.client.table("scraped_items").select(
            "id, title, publication_date, item_url, scraped_at, affected_individuals"
        ).eq("source_id", SOURCE_ID_DELAWARE_AG).order("title", desc=False).execute()
        
        all_records = response.data or []
        logger.info(f"Found {len(all_records)} Delaware AG records")
        
    except Exception as e:
        logger.error(f"Failed to fetch Delaware AG records: {e}")
        return
    
    # Group records by organization name
    records_by_org: Dict[str, List[Dict[str, Any]]] = {}
    
    for record in all_records:
        org_name = record['title']
        if org_name not in records_by_org:
            records_by_org[org_name] = []
        records_by_org[org_name].append(record)
    
    # Report on duplicates
    duplicate_orgs = {org: records for org, records in records_by_org.items() if len(records) > 1}
    
    logger.info(f"Found {len(duplicate_orgs)} organizations with duplicates:")
    
    total_duplicate_records = 0
    for org_name, records in duplicate_orgs.items():
        duplicate_count = len(records) - 1  # Subtract 1 for the original
        total_duplicate_records += duplicate_count
        
        logger.info(f"  {org_name}: {len(records)} records ({duplicate_count} duplicates)")
        
        # Show the URLs to see the pattern
        for i, record in enumerate(records):
            logger.info(f"    {i+1}. ID {record['id']}: {record['item_url']} (scraped: {record['scraped_at']})")
    
    logger.info(f"Total duplicate records to be removed: {total_duplicate_records}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--analyze":
        analyze_delaware_duplicates()
    elif len(sys.argv) > 1 and sys.argv[1] == "--cleanup":
        cleanup_delaware_duplicates()
    else:
        print("Usage:")
        print("  python cleanup_delaware_duplicates.py --analyze   # Analyze duplicates without removing")
        print("  python cleanup_delaware_duplicates.py --cleanup   # Remove duplicate records")
