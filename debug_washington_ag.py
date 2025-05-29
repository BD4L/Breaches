#!/usr/bin/env python3
"""
Debug script for Washington AG scraper to see what data is actually being extracted.
"""

import requests
from bs4 import BeautifulSoup
import sys
import os

# Add the parent directory to the path so we can import from scrapers
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from scrapers.fetch_washington_ag import (
    WASHINGTON_AG_BREACH_URL, REQUEST_HEADERS, REQUEST_TIMEOUT,
    extract_pdf_url_wa, parse_affected_individuals_wa, 
    parse_date_flexible_wa, parse_data_types_compromised_wa
)

def debug_washington_ag_extraction():
    """
    Debug the Washington AG data extraction to see what's actually being parsed.
    """
    print("🔍 Debugging Washington AG data extraction...")
    
    try:
        response = requests.get(WASHINGTON_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        print(f"✅ Successfully fetched page from {WASHINGTON_AG_BREACH_URL}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find the main data table
    data_table = soup.find('table')
    if not data_table:
        print("❌ No table found on the page")
        return
    
    print(f"✅ Found table on the page")
    
    tbody = data_table.find('tbody')
    if not tbody:
        notifications = data_table.find_all('tr')[1:]  # Skip header row
    else:
        notifications = tbody.find_all('tr')
    
    print(f"✅ Found {len(notifications)} notification rows")
    
    # Debug the first 3 rows
    for i, row in enumerate(notifications[:3]):
        print(f"\n🔍 === ROW {i+1} DEBUG ===")
        cols = row.find_all(['td', 'th'])
        print(f"Number of columns: {len(cols)}")
        
        if len(cols) >= 5:
            # Extract raw text from each column
            date_reported_raw = cols[0].get_text(strip=True)
            org_name_raw = cols[1].get_text(strip=True)
            date_of_breach_raw = cols[2].get_text(strip=True)
            residents_affected_raw = cols[3].get_text(strip=True)
            information_compromised_raw = cols[4].get_text(strip=True)
            
            print(f"Column 0 (Date Reported): '{date_reported_raw}'")
            print(f"Column 1 (Organization): '{org_name_raw}'")
            print(f"Column 2 (Date of Breach): '{date_of_breach_raw}'")
            print(f"Column 3 (Residents Affected): '{residents_affected_raw}'")
            print(f"Column 4 (Information Compromised): '{information_compromised_raw[:100]}...'")
            
            # Test PDF URL extraction
            pdf_url = extract_pdf_url_wa(cols[1])
            print(f"PDF URL extracted: '{pdf_url}'")
            
            # Test parsing functions
            affected_count = parse_affected_individuals_wa(residents_affected_raw)
            print(f"Affected individuals parsed: {affected_count}")
            
            reported_date_parsed = parse_date_flexible_wa(date_reported_raw)
            print(f"Reported date parsed: {reported_date_parsed}")
            
            breach_date_parsed = parse_date_flexible_wa(date_of_breach_raw)
            print(f"Breach date parsed: {breach_date_parsed}")
            
            data_types = parse_data_types_compromised_wa(information_compromised_raw)
            print(f"Data types parsed: {data_types[:3]}...")
            
            # Check the HTML structure of the organization cell
            print(f"\nHTML structure of organization cell:")
            print(cols[1].prettify()[:300] + "...")
            
        else:
            print(f"❌ Row has insufficient columns ({len(cols)})")
            print(f"Row text: {row.get_text(strip=True)[:100]}...")

if __name__ == "__main__":
    debug_washington_ag_extraction()
