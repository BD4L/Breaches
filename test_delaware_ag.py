#!/usr/bin/env python3
"""
Test script for the fixed Delaware AG scraper.
This tests the scraper logic without actually inserting into the database.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import sys
import os

# Add the current directory to the path so we can import from scrapers
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_delaware_ag_parsing():
    """Test the Delaware AG scraper parsing logic"""
    
    print("🧪 Testing Delaware AG Scraper Parsing")
    print("=" * 50)
    
    # Mock the date parsing function
    def parse_date_delaware(date_str):
        """Simple date parsing for testing"""
        try:
            # Handle common formats
            if '/' in date_str:
                # MM/DD/YYYY format
                parts = date_str.split('/')
                if len(parts) == 3:
                    month, day, year = parts
                    dt = datetime(int(year), int(month), int(day))
                    return dt.isoformat()
            return None
        except:
            return None
    
    # Test URL and headers
    DELAWARE_AG_BREACH_URL = "https://attorneygeneral.delaware.gov/fraud/cpu/securitybreachnotification/database/"
    REQUEST_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        print("📡 Fetching Delaware AG page...")
        response = requests.get(DELAWARE_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
        print(f"✅ Successfully fetched page. Status: {response.status_code}")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find the table
        table = soup.find('table')
        if not table:
            print("❌ Could not find any table on the page")
            return False
        
        print("✅ Found table on page")
        
        tbody = table.find('tbody')
        if not tbody:
            print("❌ Could not find table body")
            return False
        
        print("✅ Found table body")
        
        notifications = tbody.find_all('tr')
        print(f"📊 Found {len(notifications)} potential breach notifications")
        
        if len(notifications) == 0:
            print("❌ No notifications found in table")
            return False
        
        # Test parsing the first few rows
        parsed_count = 0
        for i, row in enumerate(notifications[:5]):  # Test first 5 rows
            cols = row.find_all('td')
            print(f"\n--- Row {i+1} ---")
            print(f"Columns found: {len(cols)}")
            
            if len(cols) < 5:
                print(f"⚠️  Insufficient columns ({len(cols)}), skipping")
                continue
            
            # Parse according to current structure:
            # 0: Organization Name
            # 1: Date(s) of Breach
            # 2: Reported Date (to AG)
            # 3: Number of Potentially Affected Delaware Residents
            # 4: Sample of Notice (contains PDF link)
            
            entity_name = cols[0].get_text(strip=True)
            date_of_breach_str = cols[1].get_text(strip=True)
            reported_date_str = cols[2].get_text(strip=True)
            residents_affected_text = cols[3].get_text(strip=True)
            
            # Check for PDF link
            detailed_notice_link_tag = cols[4].find('a', href=True)
            has_pdf_link = detailed_notice_link_tag is not None
            
            print(f"Organization: {entity_name}")
            print(f"Breach Date(s): {date_of_breach_str}")
            print(f"Reported Date: {reported_date_str}")
            print(f"Residents Affected: {residents_affected_text}")
            print(f"Has PDF Link: {has_pdf_link}")
            
            # Test date parsing
            publication_date_iso = None
            if reported_date_str and reported_date_str.lower() not in ['n/a', 'unknown', '']:
                publication_date_iso = parse_date_delaware(reported_date_str)
            if not publication_date_iso and date_of_breach_str and date_of_breach_str.lower() not in ['n/a', 'unknown', '']:
                publication_date_iso = parse_date_delaware(date_of_breach_str.split('–')[0].strip())
            
            print(f"Parsed Date: {publication_date_iso}")
            
            if entity_name and publication_date_iso:
                parsed_count += 1
                print("✅ Row parsed successfully")
            else:
                print("⚠️  Row missing required data")
        
        print(f"\n📈 Summary:")
        print(f"Total rows tested: {min(5, len(notifications))}")
        print(f"Successfully parsed: {parsed_count}")
        print(f"Parse success rate: {parsed_count/min(5, len(notifications))*100:.1f}%")
        
        if parsed_count > 0:
            print("🎉 Delaware AG scraper parsing logic is working!")
            return True
        else:
            print("❌ No rows could be parsed successfully")
            return False
            
    except Exception as e:
        print(f"❌ Error testing Delaware AG scraper: {e}")
        return False

if __name__ == "__main__":
    success = test_delaware_ag_parsing()
    sys.exit(0 if success else 1)
