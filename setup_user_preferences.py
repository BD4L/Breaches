#!/usr/bin/env python3
"""
Quick script to set up user preferences for email alerts testing via GitHub Actions.
This creates the necessary database records so you can receive email alerts.
"""

import os
import sys
from datetime import datetime

def setup_user_preferences():
    """Set up user preferences for email alerts"""
    
    # Get email from user
    email = input("Enter your email address for breach alerts: ").strip()
    if not email or '@' not in email:
        print("❌ Invalid email address")
        return False
    
    print(f"\n🔧 Setting up email preferences for: {email}")
    
    try:
        from utils.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        
        # Create comprehensive user preferences
        user_prefs = {
            'user_id': 'anonymous',  # Using anonymous for testing
            'email': email,
            'email_verified': True,  # Mark as verified for testing
            'threshold': 0,  # Alert for ALL breaches (no minimum threshold)
            'alert_frequency': 'immediate',
            'email_format': 'html',
            'include_summary': True,
            'include_links': True,
            'max_alerts_per_day': 50,  # High limit for testing
            'notify_high_impact': True,
            'notify_critical_sectors': True,
            'notify_local_breaches': True,
            'source_types': [
                'State AG',
                'Government Portal', 
                'News Feed',
                'RSS Feed',
                'API Feed'
            ],  # All source types
            'keywords': [],  # No keyword filtering - get all breaches
            'updated_at': datetime.now().isoformat()
        }
        
        print("📊 Preferences being set:")
        print(f"   ✅ Email: {email}")
        print(f"   ✅ Verified: True")
        print(f"   ✅ Threshold: 0 (all breaches)")
        print(f"   ✅ Frequency: immediate")
        print(f"   ✅ Source types: All types")
        print(f"   ✅ Max alerts/day: 50")
        
        # Insert/update preferences
        response = supabase.table('user_prefs').upsert(user_prefs).execute()
        
        if response.data:
            print(f"\n✅ User preferences created successfully!")
            print(f"📧 You will now receive email alerts for:")
            print(f"   • ALL new breaches (no minimum threshold)")
            print(f"   • From ALL source types")
            print(f"   • Sent immediately when found")
            print(f"   • Up to 50 alerts per day")
            
            # Test the matching function
            print(f"\n🧪 Testing alert matching...")
            test_response = supabase.rpc('match_alert_recipients', {
                'p_source_id': 1,
                'p_source_type': 'State AG',
                'p_affected': 1000,
                'p_title': 'Test Organization',
                'p_data_types': ['PII'],
                'p_what_leaked': 'Personal information'
            }).execute()
            
            if test_response.data and len(test_response.data) > 0:
                print(f"✅ Alert matching works! Found {len(test_response.data)} recipients")
                for recipient in test_response.data:
                    if recipient.get('user_email') == email:
                        print(f"   📧 Your email ({email}) will receive alerts")
                        break
            else:
                print(f"⚠️ Alert matching test found no recipients")
            
            return True
        else:
            print(f"❌ Failed to create user preferences")
            return False
            
    except Exception as e:
        print(f"❌ Error setting up preferences: {e}")
        return False

def main():
    print("🚀 Email Alerts User Preferences Setup")
    print("=" * 50)
    print("This will set up your email preferences so you receive breach alerts via GitHub Actions.")
    print()
    
    # Check environment
    if not os.environ.get('SUPABASE_URL') or not os.environ.get('SUPABASE_SERVICE_KEY'):
        print("❌ Missing Supabase environment variables")
        print("You need to set SUPABASE_URL and SUPABASE_SERVICE_KEY")
        print()
        print("For GitHub Actions testing, these are already set as secrets.")
        print("This script is mainly for local testing or verification.")
        return
    
    if setup_user_preferences():
        print(f"\n🎉 Setup Complete!")
        print(f"\n💡 Next Steps:")
        print(f"   1. Wait for scrapers to find new breaches")
        print(f"   2. Check GitHub Actions logs for email notifications")
        print(f"   3. Check your email inbox for breach alerts")
        print(f"   4. Monitor workflow runs at: https://github.com/BD4L/Breaches/actions")
        
        print(f"\n🔍 How to Test:")
        print(f"   • Manually trigger a scraper workflow")
        print(f"   • Wait for scheduled runs (every 30 min for main scrapers)")
        print(f"   • California AG runs hourly")
        print(f"   • RSS/API scrapers run every 2 hours")
        
        print(f"\n📧 Email Alert Conditions:")
        print(f"   • New breaches found by scrapers")
        print(f"   • Breach matches your preferences (currently: ALL breaches)")
        print(f"   • Email hasn't been sent for this breach before")
        print(f"   • GitHub Actions has valid RESEND_API_KEY secret")
    else:
        print(f"\n❌ Setup failed. Check the error messages above.")

if __name__ == "__main__":
    main()
