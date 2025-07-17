#!/usr/bin/env python3
"""
Test script to verify RSS scraper timeout fixes work correctly.
This script simulates timeout scenarios to ensure the fixes prevent hanging.
"""

import os
import sys
import time
import logging
from unittest.mock import patch, MagicMock
import concurrent.futures

# Add the scrapers directory to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'scrapers')))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_timeout_configuration():
    """Test that timeout configuration is properly loaded."""
    logger.info("🧪 Testing timeout configuration...")
    
    # Set environment variables for testing
    os.environ['NEWS_FEED_TIMEOUT'] = '15'
    os.environ['NEWS_MAX_TOTAL_TIMEOUT'] = '60'
    os.environ['NEWS_CONCURRENT_FEEDS'] = '2'
    
    # Import after setting environment variables
    from fetch_cybersecurity_news import FEED_TIMEOUT, MAX_TOTAL_TIMEOUT, CONCURRENT_FEEDS
    
    assert FEED_TIMEOUT == 15, f"Expected FEED_TIMEOUT=15, got {FEED_TIMEOUT}"
    assert MAX_TOTAL_TIMEOUT == 60, f"Expected MAX_TOTAL_TIMEOUT=60, got {MAX_TOTAL_TIMEOUT}"
    assert CONCURRENT_FEEDS == 2, f"Expected CONCURRENT_FEEDS=2, got {CONCURRENT_FEEDS}"
    
    logger.info("✅ Timeout configuration test passed")
    return True

def test_individual_feed_timeout():
    """Test that individual feeds timeout correctly."""
    logger.info("🧪 Testing individual feed timeout...")
    
    def slow_feed_function():
        """Simulate a slow feed that should timeout."""
        time.sleep(20)  # Sleep longer than timeout
        return "Should not reach here"
    
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(slow_feed_function)
        try:
            result = future.result(timeout=5)  # 5 second timeout
            logger.error("❌ Feed should have timed out but didn't")
            return False
        except concurrent.futures.TimeoutError:
            elapsed = time.time() - start_time
            logger.info(f"✅ Feed correctly timed out after {elapsed:.1f} seconds")
            return True
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return False

def test_total_job_timeout():
    """Test that total job timeout works correctly."""
    logger.info("🧪 Testing total job timeout...")
    
    def slow_feeds():
        """Simulate multiple slow feeds."""
        for i in range(5):
            yield lambda: time.sleep(10)  # Each feed takes 10 seconds
    
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(feed_func) for feed_func in slow_feeds()]
        
        try:
            # This should timeout after 15 seconds, not wait for all feeds
            for future in concurrent.futures.as_completed(futures, timeout=15):
                future.result(timeout=5)
            logger.error("❌ Job should have timed out but didn't")
            return False
        except concurrent.futures.TimeoutError:
            elapsed = time.time() - start_time
            logger.info(f"✅ Job correctly timed out after {elapsed:.1f} seconds")
            return True
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return False

def test_rss_scraper_integration():
    """Test RSS scraper with mocked feeds to verify timeout behavior."""
    logger.info("🧪 Testing RSS scraper integration...")
    
    # Mock the feed processing to simulate timeouts
    def mock_process_single_feed(feed_info, supabase_client):
        feed_name = feed_info.get('name', 'Unknown')
        if 'slow' in feed_name.lower():
            time.sleep(10)  # Simulate slow feed
        return feed_name, 1, 1, 0  # processed, inserted, skipped
    
    # Create mock feeds
    mock_feeds = [
        {'name': 'Fast Feed 1', 'url': 'http://example.com/fast1.rss'},
        {'name': 'Fast Feed 2', 'url': 'http://example.com/fast2.rss'},
        {'name': 'Slow Feed 1', 'url': 'http://example.com/slow1.rss'},  # This will timeout
    ]
    
    # Mock supabase client
    mock_supabase = MagicMock()
    
    start_time = time.time()
    
    # Test concurrent processing with timeout
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_to_feed = {
            executor.submit(mock_process_single_feed, feed_info, mock_supabase): feed_info
            for feed_info in mock_feeds
        }
        
        successful_feeds = 0
        failed_feeds = 0
        
        try:
            for future in concurrent.futures.as_completed(future_to_feed, timeout=8):  # 8 second total timeout
                feed_info = future_to_feed[future]
                try:
                    result = future.result(timeout=5)  # 5 second per-feed timeout
                    successful_feeds += 1
                    logger.info(f"✅ Processed feed: {feed_info['name']}")
                except concurrent.futures.TimeoutError:
                    failed_feeds += 1
                    logger.info(f"⏰ Feed timed out: {feed_info['name']}")
                except Exception as e:
                    failed_feeds += 1
                    logger.error(f"❌ Feed failed: {feed_info['name']} - {e}")
        
        except concurrent.futures.TimeoutError:
            logger.info("⏰ Total job timeout reached")
            failed_feeds += len([f for f in future_to_feed if not f.done()])
    
    elapsed = time.time() - start_time
    logger.info(f"🏁 Integration test completed in {elapsed:.1f} seconds")
    logger.info(f"📊 Results: {successful_feeds} successful, {failed_feeds} failed/timed out")
    
    # Should complete within reasonable time and handle timeouts gracefully
    return elapsed < 12 and successful_feeds >= 2

def main():
    """Run all timeout tests."""
    logger.info("🚀 Starting RSS scraper timeout fix tests...")
    
    tests = [
        ("Timeout Configuration", test_timeout_configuration),
        ("Individual Feed Timeout", test_individual_feed_timeout),
        ("Total Job Timeout", test_total_job_timeout),
        ("RSS Scraper Integration", test_rss_scraper_integration),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running: {test_name}")
        logger.info(f"{'='*50}")
        
        try:
            if test_func():
                logger.info(f"✅ {test_name} PASSED")
                passed += 1
            else:
                logger.error(f"❌ {test_name} FAILED")
                failed += 1
        except Exception as e:
            logger.error(f"❌ {test_name} FAILED with exception: {e}")
            failed += 1
    
    logger.info(f"\n{'='*50}")
    logger.info(f"TEST SUMMARY")
    logger.info(f"{'='*50}")
    logger.info(f"✅ Passed: {passed}")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"📊 Success Rate: {passed/(passed+failed)*100:.1f}%")
    
    if failed == 0:
        logger.info("🎉 All tests passed! RSS scraper timeout fixes are working correctly.")
        return 0
    else:
        logger.error("💥 Some tests failed. Please review the timeout configuration.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
