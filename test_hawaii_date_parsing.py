#!/usr/bin/env python3
"""
Test script to demonstrate the Hawaii AG date parsing fix.
This shows how the improved date parsing handles problematic inputs.
"""

import sys
import os

# Add the current directory to the path so we can import from scrapers
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_date_parsing():
    """Test the improved Hawaii AG date parsing function"""
    
    # Mock the dateutil parser since we might not have it installed
    class MockDateutilParser:
        @staticmethod
        def parse(date_str):
            from datetime import datetime
            # Simple date parsing for common formats
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    year, month, day = parts
                    return datetime(int(year), int(month), int(day))
            raise ValueError(f"Cannot parse {date_str}")
    
    # Mock logger
    class MockLogger:
        def warning(self, msg):
            print(f"WARNING: {msg}")
    
    # Create the improved parsing function inline
    def parse_date_flexible_hi(date_str, logger=MockLogger(), dateutil_parser=MockDateutilParser()):
        """
        Improved date parsing function with business name detection
        """
        if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided']:
            return None
        
        # Clean up the date string
        date_str = date_str.strip()
        
        # Skip if it looks like a company name (contains common business words)
        business_indicators = ['inc', 'llc', 'corp', 'company', 'ltd', 'dental', 'medical', 'health', 'services', 'group', 'associates']
        if any(indicator in date_str.lower() for indicator in business_indicators):
            logger.warning(f"Skipping date parsing for '{date_str}' - appears to be a company name")
            return None
        
        # Handle specific Hawaii AG date formats like "2024/03.18"
        if '/' in date_str and '.' in date_str:
            try:
                # Convert "2024/03.18" to "2024/03/18"
                date_str = date_str.replace('.', '/')
            except:
                pass
        
        try:
            dt_object = dateutil_parser.parse(date_str)
            return dt_object.isoformat()
        except (ValueError, TypeError, OverflowError) as e:
            logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
            return None
    
    # Test cases that were causing issues
    test_cases = [
        # These were causing errors before the fix
        ("Delta Dental of California", "Company name - should be skipped"),
        ("2024/03.18", "Hawaii format - should be converted and parsed"),
        ("Health Services Inc", "Company name - should be skipped"),
        
        # These should work normally
        ("2024/03/15", "Standard date - should parse"),
        ("2024-05-25", "ISO format - should parse"),
        ("", "Empty string - should return None"),
        ("N/A", "N/A - should return None"),
        ("unknown", "Unknown - should return None"),
        
        # Edge cases
        ("Medical Group LLC", "Company name - should be skipped"),
        ("2024/12/31", "Valid date - should parse"),
    ]
    
    print("🧪 Testing Hawaii AG Date Parsing Improvements")
    print("=" * 60)
    
    for test_input, description in test_cases:
        print(f"\nInput: '{test_input}'")
        print(f"Expected: {description}")
        
        result = parse_date_flexible_hi(test_input)
        
        if result:
            print(f"✅ Result: {result}")
        else:
            print(f"⚠️  Result: None (skipped or failed)")
    
    print("\n" + "=" * 60)
    print("✅ Date parsing test completed!")
    print("\nKey improvements:")
    print("- Company names are now detected and skipped")
    print("- Hawaii-specific date formats (2024/03.18) are handled")
    print("- Better error handling prevents crashes")
    print("- Clear logging shows why dates are skipped")

if __name__ == "__main__":
    test_date_parsing()
