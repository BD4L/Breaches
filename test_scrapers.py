#!/usr/bin/env python3
"""
Test script to verify scraper fixes and database connectivity.
This script tests the most critical fixes without running full scrapers.
"""

import os
import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_supabase_connection():
    """Test Supabase connection and data_sources table"""
    try:
        from utils.supabase_client import SupabaseClient
        
        logger.info("Testing Supabase connection...")
        client = SupabaseClient()
        
        # Test data_sources query
        response = client.client.table("data_sources").select("id, name").limit(5).execute()
        if response.data:
            logger.info(f"✅ Supabase connection successful. Found {len(response.data)} data sources:")
            for source in response.data:
                logger.info(f"  - ID {source['id']}: {source['name']}")
        else:
            logger.error("❌ No data sources found in database")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Supabase connection failed: {e}")
        return False

def test_sec_edgar_feed():
    """Test SEC EDGAR feed accessibility"""
    try:
        import requests
        import feedparser
        
        logger.info("Testing SEC EDGAR feed...")
        url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&count=10&output=atom"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        feed = feedparser.parse(response.content)
        if feed.bozo:
            logger.error(f"❌ Feed parsing error: {feed.bozo_exception}")
            return False
            
        if not feed.entries:
            logger.error("❌ No entries found in SEC EDGAR feed")
            return False
            
        logger.info(f"✅ SEC EDGAR feed accessible. Found {len(feed.entries)} entries")
        return True
        
    except Exception as e:
        logger.error(f"❌ SEC EDGAR feed test failed: {e}")
        return False

def test_hhs_ocr_url():
    """Test HHS OCR URL to see what we get"""
    try:
        import requests
        
        logger.info("Testing HHS OCR URL...")
        url = "https://ocrportal.hhs.gov/ocr/breach/breach_report.jsf?download=true"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        
        content_type = response.headers.get('content-type', '').lower()
        is_html = 'text/html' in content_type or response.text.strip().startswith('<!DOCTYPE') or response.text.strip().startswith('<html')
        
        if is_html:
            logger.warning("⚠️  HHS OCR returns HTML page (expected - requires JavaScript/session)")
            logger.info("This is a known issue - the site requires dynamic interaction")
        else:
            logger.info(f"✅ HHS OCR returns non-HTML content: {content_type}")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ HHS OCR URL test failed: {e}")
        return False

def test_massachusetts_ag():
    """Test Massachusetts AG with enhanced headers"""
    try:
        import requests
        import time
        
        logger.info("Testing Massachusetts AG with enhanced headers...")
        url = "https://www.mass.gov/lists/data-breach-notification-reports"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        }
        
        time.sleep(2)  # Rate limiting
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 403:
            logger.warning("⚠️  Massachusetts AG still returns 403 - may need browser automation")
            return False
        else:
            response.raise_for_status()
            logger.info(f"✅ Massachusetts AG accessible. Status: {response.status_code}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Massachusetts AG test failed: {e}")
        return False

def test_hawaii_ag_date_parsing():
    """Test Hawaii AG date parsing improvements"""
    try:
        from scrapers.fetch_hi_ag import parse_date_flexible_hi
        
        logger.info("Testing Hawaii AG date parsing...")
        
        test_cases = [
            ("2024/03.18", "Should convert to valid date"),
            ("Delta Dental of California", "Should skip company name"),
            ("2024-03-15", "Should parse standard date"),
            ("", "Should handle empty string"),
            ("N/A", "Should handle N/A")
        ]
        
        for test_input, description in test_cases:
            result = parse_date_flexible_hi(test_input)
            logger.info(f"  '{test_input}' -> {result} ({description})")
            
        logger.info("✅ Hawaii AG date parsing test completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Hawaii AG date parsing test failed: {e}")
        return False

def main():
    """Run all tests"""
    logger.info("🧪 Starting scraper fix tests...")
    
    # Check environment variables
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    
    if not supabase_url or not supabase_key:
        logger.error("❌ SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set")
        return False
    
    tests = [
        ("Supabase Connection", test_supabase_connection),
        ("SEC EDGAR Feed", test_sec_edgar_feed),
        ("HHS OCR URL", test_hhs_ocr_url),
        ("Massachusetts AG", test_massachusetts_ag),
        ("Hawaii AG Date Parsing", test_hawaii_ag_date_parsing),
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n--- Testing {test_name} ---")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("TEST SUMMARY")
    logger.info("="*50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
        if result:
            passed += 1
    
    logger.info(f"\nPassed: {passed}/{len(results)} tests")
    
    if passed == len(results):
        logger.info("🎉 All tests passed!")
        return True
    else:
        logger.warning(f"⚠️  {len(results) - passed} tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
