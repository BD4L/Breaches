# AI Agent System - Setup and Test Guide

## 🚀 Complete Setup Instructions

### Step 1: Database Schema Updates

1. **Open Supabase SQL Editor**
   - Go to your Supabase dashboard: https://supabase.com/dashboard
   - Navigate to your `breachdash` project
   - Click "SQL Editor" in the left sidebar

2. **Run the Schema Updates**
   ```sql
   -- Copy and paste the entire contents of database_schema_ai_updates.sql
   -- Execute it in the SQL Editor
   ```

3. **Verify the Updates**
   ```sql
   -- Check that new columns were added to research_jobs
   SELECT column_name, data_type 
   FROM information_schema.columns 
   WHERE table_name = 'research_jobs'
   ORDER BY ordinal_position;
   
   -- Check that ai_report_usage table was created
   \d ai_report_usage;
   
   -- Test the v_ai_reports view
   SELECT COUNT(*) FROM v_ai_reports;
   
   -- Test helper functions
   SELECT check_daily_rate_limit('00000000-0000-0000-0000-000000000000', 10);
   ```

### Step 2: Get Gemini API Key

**Option A: Google AI Studio (Recommended for testing)**
1. Go to https://aistudio.google.com
2. Sign in with your Google account
3. Click "Get API key" 
4. Create a new API key
5. Copy the key (starts with `AIza...`)

**Option B: Google Cloud Vertex AI (For production)**
1. Go to https://console.cloud.google.com
2. Enable Vertex AI API
3. Create service account with Vertex AI permissions
4. Download JSON key file

### Step 3: Install Supabase CLI

```bash
# Install Supabase CLI globally
npm install -g supabase

# Verify installation
supabase --version
```

### Step 4: Deploy Edge Function

1. **Initialize Supabase (if not already done)**
   ```bash
   cd /Users/sebastienbell/Breaches
   supabase init
   ```

2. **Link to your project**
   ```bash
   # Replace with your actual project reference
   supabase link --project-ref hilbbjnnxkitxbptektg
   ```

3. **Set environment variables**
   ```bash
   # Set your Gemini API key
   supabase secrets set GEMINI_API_KEY=your_actual_api_key_here
   
   # Verify it was set
   supabase secrets list
   ```

4. **Deploy the function**
   ```bash
   # Deploy the AI report generation function
   supabase functions deploy generate-ai-report
   
   # Check deployment status
   supabase functions list
   ```

### Step 5: Test Edge Function

1. **Test with curl**
   ```bash
   # Replace with your actual project ref and anon key
   curl -X POST 'https://hilbbjnnxkitxbptektg.supabase.co/functions/v1/generate-ai-report' \
     -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhpbGJiam5ueGtpdHhicHRla3RnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDgxOTYwNDIsImV4cCI6MjA2Mzc3MjA0Mn0.vk8AJ2pofRAy5y26WQeMYgEFudU1plXnYa6sMFyATFM' \
     -H 'Content-Type: application/json' \
     -d '{"breachId": 1}'
   ```

2. **Expected Response**
   ```json
   {
     "reportId": "uuid-here",
     "status": "completed",
     "processingTimeMs": 15000,
     "searchResultsCount": 3,
     "scrapedUrlsCount": 3
   }
   ```

### Step 6: Deploy Frontend

1. **Commit and push changes**
   ```bash
   git add .
   git commit -m "Add AI agent system for breach reports"
   git push origin main
   ```

2. **Monitor GitHub Actions**
   - Go to your GitHub repository
   - Click "Actions" tab
   - Watch the deployment process
   - Verify it completes successfully

3. **Check deployment**
   - Visit: https://bd4l.github.io/Breaches/
   - Look for the new "🤖 AI Report" buttons in the breach table

## 🧪 Testing the Complete System

### Test 1: Basic Functionality

1. **Navigate to your dashboard**
   - Go to https://bd4l.github.io/Breaches/
   - Wait for breach data to load

2. **Find a breach with good data**
   - Look for breaches with organization names and affected individuals
   - Click the "🤖 AI Report" button

3. **Monitor the process**
   - Button should show "Generating..." with spinning icon
   - Should automatically open report when complete
   - Or show error message if something fails

### Test 2: Database Verification

```sql
-- Check if reports are being created
SELECT * FROM research_jobs 
WHERE report_type = 'ai_breach_analysis' 
ORDER BY created_at DESC 
LIMIT 5;

-- Check usage tracking
SELECT * FROM ai_report_usage 
ORDER BY date DESC 
LIMIT 5;

-- View generated reports
SELECT 
  id, 
  status, 
  processing_time_ms, 
  search_results_count,
  organization_name,
  created_at
FROM v_ai_reports 
ORDER BY created_at DESC 
LIMIT 5;
```

### Test 3: Rate Limiting

1. **Generate multiple reports quickly**
   - Try clicking AI Report buttons on 5+ different breaches
   - Should work for first 10, then show rate limit message

2. **Check rate limit in database**
   ```sql
   SELECT * FROM ai_report_usage WHERE date = CURRENT_DATE;
   ```

### Test 4: Error Handling

1. **Test with invalid breach ID**
   ```bash
   curl -X POST 'https://hilbbjnnxkitxbptektg.supabase.co/functions/v1/generate-ai-report' \
     -H 'Authorization: Bearer YOUR_ANON_KEY' \
     -H 'Content-Type: application/json' \
     -d '{"breachId": 999999}'
   ```

2. **Test without API key**
   ```bash
   # Temporarily remove API key
   supabase secrets unset GEMINI_API_KEY
   
   # Try generating report (should fail gracefully)
   # Then restore the key
   supabase secrets set GEMINI_API_KEY=your_key_here
   ```

## 🔍 Troubleshooting Common Issues

### Issue 1: "Function not found"
```bash
# Check if function is deployed
supabase functions list

# If not listed, redeploy
supabase functions deploy generate-ai-report
```

### Issue 2: "API key not found"
```bash
# Check secrets
supabase secrets list

# Should show GEMINI_API_KEY (value hidden)
# If missing, set it again
supabase secrets set GEMINI_API_KEY=your_key_here
```

### Issue 3: Frontend button not appearing
1. Check browser console for errors
2. Verify GitHub Actions deployment completed
3. Hard refresh the page (Cmd+Shift+R / Ctrl+Shift+F5)
4. Check if new components are in the deployed files

### Issue 4: Database errors
```sql
-- Check if schema updates were applied
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'research_jobs' AND column_name = 'report_type';

-- If empty, re-run database_schema_ai_updates.sql
```

### Issue 5: CORS errors
- Edge functions should handle CORS automatically
- If issues persist, check the function logs:
```bash
supabase functions logs generate-ai-report
```

## 📊 Monitoring and Logs

### View Function Logs
```bash
# Real-time logs
supabase functions logs generate-ai-report --follow

# Recent logs
supabase functions logs generate-ai-report
```

### Monitor Performance
```sql
-- Average processing times
SELECT 
  AVG(processing_time_ms) as avg_time_ms,
  COUNT(*) as total_reports,
  AVG(cost_estimate) as avg_cost
FROM research_jobs 
WHERE report_type = 'ai_breach_analysis' 
AND status = 'completed';

-- Success rate
SELECT 
  status,
  COUNT(*) as count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM research_jobs 
WHERE report_type = 'ai_breach_analysis'
GROUP BY status;
```

## ✅ Success Checklist

- [ ] Database schema updated successfully
- [ ] Gemini API key obtained and set
- [ ] Supabase CLI installed and linked
- [ ] Edge function deployed without errors
- [ ] Frontend deployed via GitHub Actions
- [ ] AI Report button appears in breach table
- [ ] Can generate reports successfully
- [ ] Reports display properly in viewer
- [ ] Rate limiting works correctly
- [ ] Error handling works gracefully

## 🎉 You're Ready!

Once all tests pass, your AI agent system is fully operational! Users can now generate comprehensive breach reports with a single click. The system will:

1. ✅ Search the web for additional breach information
2. ✅ Analyze the data with Gemini 2.5 Flash
3. ✅ Generate comprehensive reports with hyperlinks
4. ✅ Track usage and enforce rate limits
5. ✅ Provide shareable report URLs

**Cost**: ~$0.17 per report
**Speed**: ~15-30 seconds per report
**Limit**: 10 reports per user per day

Your breach dashboard now has AI superpowers! 🤖🚀
