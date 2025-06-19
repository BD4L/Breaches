# 📧 Email Alerts Setup Guide

This guide will help you set up email alerts for your breach dashboard using Resend.

## 🚀 Quick Setup

### 1. Get a Resend API Key

1. **Sign up for Resend**: Go to [resend.com](https://resend.com) and create a free account
2. **Verify your domain** (or use their test domain for now):
   - For testing: You can use `onboarding@resend.dev` as your from email
   - For production: Add and verify your own domain
3. **Create an API key**:
   - Go to API Keys in your Resend dashboard
   - Click "Create API Key"
   - Give it a name like "Breach Dashboard"
   - Copy the API key (starts with `re_`)

### 2. Set Environment Variables

Add these to your environment (`.bashrc`, `.zshrc`, or export them):

```bash
# Required - Your Supabase credentials (you should already have these)
export SUPABASE_URL="your-supabase-project-url"
export SUPABASE_SERVICE_KEY="your-supabase-service-key"

# Required - Your Resend API key
export RESEND_API_KEY="re_your-resend-api-key-here"

# Optional - Customize the from email (default: alerts@yourdomain.com)
export ALERT_FROM_EMAIL="alerts@yourdomain.com"  # or onboarding@resend.dev for testing

# Optional - Your dashboard URL (default: https://bd4l.github.io/Breaches/)
export DASHBOARD_URL="https://bd4l.github.io/Breaches/"
```

### 3. Run the Setup Script

```bash
# Make sure you're in the project directory
cd /path/to/your/Breaches

# Run the setup script
python3 setup_email_alerts.py
```

The script will:
- ✅ Check your environment variables
- ✅ Test the Resend API by sending you a test email
- ✅ Test your database connection
- ✅ Create test user preferences
- ✅ Test the complete email alert flow

## 🔧 Manual Testing

If you want to test individual components:

### Test Resend API Only
```bash
python3 test_email_system.py
```

### Test Email Alerts Script
```bash
# Test with a specific email
python3 scrapers/email_alerts.py --test-email your@email.com

# Process real alerts (if you have recent breaches)
python3 scrapers/email_alerts.py --since-minutes 60
```

## 📊 Add to GitHub Actions

Once everything is working, add the email alerts to your scraper workflows.

### Add Environment Variables to GitHub

1. Go to your GitHub repository
2. Settings → Secrets and variables → Actions
3. Add these repository secrets:
   - `RESEND_API_KEY`: Your Resend API key
   - `ALERT_FROM_EMAIL`: Your from email address

### Update Workflow Files

The email notification jobs are already in your workflows, but they need the environment variables:

```yaml
email-notifications:
  name: "📧 Email Alert Notifications"
  runs-on: ubuntu-latest
  needs: [summary]
  if: needs.summary.outputs.new_breaches > 0
  env:
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
    RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}
    ALERT_FROM_EMAIL: ${{ secrets.ALERT_FROM_EMAIL }}
    PYTHONUNBUFFERED: "1"
  steps:
    # ... existing steps ...
    - name: Send email notifications
      run: |
        echo "📧 Sending email notifications for ${{ needs.summary.outputs.new_breaches }} new breaches..."
        python scrapers/email_alerts.py --source "Automated" --new-count "${{ needs.summary.outputs.new_breaches }}"
```

## 🎨 Frontend Integration

### Add Email Preferences to Your Dashboard

The `EmailPreferences` component is already created. Add it to your main dashboard:

```typescript
import { EmailPreferences } from './components/preferences/EmailPreferences'

// Add a preferences button/modal to your dashboard
<EmailPreferences onClose={() => setShowPreferences(false)} />
```

### User Workflow

1. **User visits dashboard**
2. **Clicks "Email Preferences"**
3. **Enters email and sets preferences**:
   - Minimum affected people threshold
   - Source types to monitor
   - Keywords to watch for
   - Email format (HTML/text)
4. **Clicks "Verify Email"** (currently auto-verifies for testing)
5. **Saves preferences**

## 📧 How Email Alerts Work

### Trigger Conditions

Emails are sent when:
- ✅ New breaches are detected by scrapers
- ✅ Breach matches user's preferences (threshold, sources, keywords)
- ✅ User's email is verified
- ✅ Alert hasn't been sent before for this breach

### Email Content

Each email includes:
- 🏢 **Organization name**
- 👥 **Number of people affected**
- 📅 **Breach date**
- 📄 **What data was compromised**
- 🔗 **Link to full details**
- ⚙️ **Unsubscribe/preferences links**

### Rate Limiting

- Maximum 10 alerts per day per user (configurable)
- Duplicate prevention (won't send same breach twice)
- Respects user's frequency preferences (immediate/daily/weekly)

## 🐛 Troubleshooting

### "RESEND_API_KEY not found"
- Make sure you exported the environment variable
- Check the API key starts with `re_`
- Verify it's not expired in your Resend dashboard

### "Database function test failed"
- Make sure your Supabase credentials are correct
- Check that the `match_alert_recipients` function exists in your database
- Run the database schema if needed

### "No recipients found"
- Create user preferences with your email
- Set threshold to 0 to get all alerts
- Make sure email_verified is true
- Check that source_types includes the sources you want

### "Email failed to send"
- Check your from email is verified in Resend
- For testing, use `onboarding@resend.dev`
- Check Resend dashboard for delivery status

### "No recent breaches found"
- Run some scrapers first to get test data
- Check the `v_breach_dashboard` view has recent data
- Adjust the `--since-minutes` parameter

## 🎯 Production Checklist

Before going live:

- [ ] ✅ Resend API key added to GitHub Secrets
- [ ] ✅ Domain verified in Resend (for custom from email)
- [ ] ✅ Database schema includes user_prefs and alert_history tables
- [ ] ✅ Email workflows added to GitHub Actions
- [ ] ✅ Frontend preferences component integrated
- [ ] ✅ Test emails working end-to-end
- [ ] ✅ Rate limiting configured appropriately
- [ ] ✅ Unsubscribe mechanism working

## 💡 Tips

- **Start with testing**: Use `onboarding@resend.dev` as from email initially
- **Monitor delivery**: Check Resend dashboard for bounce/delivery rates
- **User feedback**: Add a way for users to report email issues
- **Gradual rollout**: Start with a few test users before full deployment
- **Backup plan**: Consider SMS alerts for critical breaches

---

🎉 **That's it!** Your email alert system should now be working. Users can set their preferences and receive immediate notifications when new breaches match their criteria.
