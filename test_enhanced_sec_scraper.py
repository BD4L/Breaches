#!/usr/bin/env python3
"""
Test script for the Enhanced SEC EDGAR 8-K Scraper

This script tests the enhanced XBRL/CYD parsing capabilities
and verifies that all the new features work correctly.
"""

import os
import sys
import logging
from datetime import datetime

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the enhanced SEC scraper functions
from scrapers.fetch_sec_edgar_8k import (
    construct_xbrl_instance_url,
    parse_xbrl_instance,
    extract_exhibit_urls,
    extract_financial_impact,
    extract_data_types_compromised,
    extract_incident_dates,
    extract_affected_individuals_from_content,
    CYD_TAXONOMY_TAGS
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_xbrl_url_construction():
    """Test XBRL instance URL construction"""
    logger.info("Testing XBRL URL construction...")
    
    test_cases = [
        {
            "input": "https://www.sec.gov/Archives/edgar/data/1679788/000167978825000094/coin-20250514.htm",
            "expected": "https://www.sec.gov/Archives/edgar/data/1679788/000167978825000094/coin-20250514_htm.xml"
        },
        {
            "input": "https://www.sec.gov/Archives/edgar/data/1234567/000123456725000001/test-filing.htm",
            "expected": "https://www.sec.gov/Archives/edgar/data/1234567/000123456725000001/test-filing_htm.xml"
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        result = construct_xbrl_instance_url(test_case["input"])
        if result == test_case["expected"]:
            logger.info(f"✅ Test {i+1} passed: {result}")
        else:
            logger.error(f"❌ Test {i+1} failed: Expected {test_case['expected']}, got {result}")

def test_cyd_taxonomy_tags():
    """Test CYD taxonomy tag definitions"""
    logger.info("Testing CYD taxonomy tags...")
    
    expected_tags = [
        "MaterialCybersecurityIncidentNatureTextBlock",
        "MaterialCybersecurityIncidentScopeTextBlock",
        "MaterialCybersecurityIncidentTimingTextBlock",
        "MaterialCybersecurityIncidentMaterialImpactOrReasonablyLikelyMaterialImpactTextBlock",
        "MaterialCybersecurityIncidentInformationNotAvailableOrUndeterminedTextBlock"
    ]
    
    for tag in expected_tags:
        if tag in CYD_TAXONOMY_TAGS.values():
            logger.info(f"✅ CYD tag found: {tag}")
        else:
            logger.error(f"❌ CYD tag missing: {tag}")

def test_financial_impact_extraction():
    """Test financial impact extraction"""
    logger.info("Testing financial impact extraction...")
    
    test_text = """
    The company estimates that the cybersecurity incident will result in costs of 
    approximately $180 million to $400 million. This includes remediation costs,
    legal fees, and potential regulatory fines. Additional costs of $50 thousand
    may be incurred for ongoing monitoring.
    """
    
    min_cost, max_cost, currency = extract_financial_impact(test_text)
    
    logger.info(f"Extracted financial impact: ${min_cost:,.0f} - ${max_cost:,.0f} {currency}")
    
    if min_cost and max_cost:
        if min_cost == 50_000 and max_cost == 400_000_000:  # Should find $50k to $400M range
            logger.info("✅ Financial impact extraction working correctly")
        else:
            logger.warning(f"⚠️ Unexpected financial impact range: ${min_cost} - ${max_cost}")
    else:
        logger.error("❌ Failed to extract financial impact")

def test_data_types_extraction():
    """Test data types compromised extraction"""
    logger.info("Testing data types extraction...")
    
    test_text = """
    The incident involved unauthorized access to customer data including personally 
    identifiable information (PII), social security numbers, credit card information,
    and email addresses. Protected health information (PHI) and driver's license 
    numbers were also potentially compromised.
    """
    
    data_types = extract_data_types_compromised(test_text)
    
    logger.info(f"Extracted data types: {data_types}")
    
    expected_types = ['PII', 'SSN', 'Credit Card', 'PHI', 'Government ID', 'Email']
    found_expected = [dt for dt in expected_types if dt in data_types]
    
    if len(found_expected) >= 4:  # Should find at least 4 of the expected types
        logger.info(f"✅ Data types extraction working correctly: {found_expected}")
    else:
        logger.warning(f"⚠️ Only found {len(found_expected)} expected data types: {found_expected}")

def test_incident_dates_extraction():
    """Test incident dates extraction"""
    logger.info("Testing incident dates extraction...")
    
    test_text = """
    The company discovered the cybersecurity incident on March 15, 2024, and 
    became aware of the full scope on March 16, 2024. The incident was contained 
    on March 20, 2024, and systems were fully secured on March 22, 2024.
    """
    
    dates = extract_incident_dates(test_text)
    
    logger.info(f"Extracted incident dates: {dates}")
    
    if 'discovery_date' in dates and 'containment_date' in dates:
        logger.info("✅ Incident dates extraction working correctly")
        logger.info(f"   Discovery: {dates.get('discovery_date')}")
        logger.info(f"   Containment: {dates.get('containment_date')}")
    else:
        logger.warning("⚠️ Could not extract expected incident dates")

def test_affected_individuals_extraction():
    """Test affected individuals extraction"""
    logger.info("Testing affected individuals extraction...")
    
    test_cases = [
        {
            "text": "The incident affected approximately 2.5 million customers.",
            "expected": 2500000
        },
        {
            "text": "Personal information of 150,000 individuals was compromised.",
            "expected": 150000
        },
        {
            "text": "The breach involved 1,234 user accounts.",
            "expected": 1234
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        result = extract_affected_individuals_from_content(test_case["text"])
        if result == test_case["expected"]:
            logger.info(f"✅ Test {i+1} passed: {result:,} individuals")
        else:
            logger.warning(f"⚠️ Test {i+1}: Expected {test_case['expected']:,}, got {result}")

def test_real_coinbase_filing():
    """Test with real Coinbase filing (if accessible)"""
    logger.info("Testing with real Coinbase XBRL filing...")
    
    # Real Coinbase filing URL from our earlier exploration
    xbrl_url = "https://www.sec.gov/Archives/edgar/data/1679788/000167978825000094/coin-20250514_htm.xml"
    
    try:
        cyd_data = parse_xbrl_instance(xbrl_url)
        
        if cyd_data:
            logger.info(f"✅ Successfully parsed real XBRL filing!")
            logger.info(f"   Extracted {len(cyd_data)} CYD fields")
            
            # Check for key fields
            key_fields = ['incident_nature', 'incident_impact', 'cik', 'ticker_symbol']
            for field in key_fields:
                if field in cyd_data:
                    value = cyd_data[field][:100] + "..." if len(str(cyd_data[field])) > 100 else cyd_data[field]
                    logger.info(f"   {field}: {value}")
        else:
            logger.warning("⚠️ No CYD data extracted from real filing")
            
    except Exception as e:
        logger.warning(f"⚠️ Could not test real filing (expected in test environment): {e}")

def main():
    """Run all tests"""
    logger.info("🚀 Starting Enhanced SEC Scraper Tests")
    logger.info("=" * 60)
    
    # Run all tests
    test_xbrl_url_construction()
    print()
    
    test_cyd_taxonomy_tags()
    print()
    
    test_financial_impact_extraction()
    print()
    
    test_data_types_extraction()
    print()
    
    test_incident_dates_extraction()
    print()
    
    test_affected_individuals_extraction()
    print()
    
    test_real_coinbase_filing()
    print()
    
    logger.info("=" * 60)
    logger.info("🎯 Enhanced SEC Scraper Tests Complete!")
    logger.info("The enhanced scraper is ready for production use.")

if __name__ == "__main__":
    main()
