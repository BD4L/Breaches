# AI Agent System Deployment Guide

## 🚀 Quick Start Implementation

This guide walks you through deploying the AI agent system for your breach dashboard.

## Prerequisites

- ✅ Supabase project with existing breach data
- ✅ Google Cloud Platform account for Gemini API
- ✅ GitHub repository with Actions enabled
- ✅ Existing frontend deployed on GitHub Pages

## Step 1: Database Schema Updates

1. **Run the database schema updates:**
   ```sql
   -- Execute the contents of database_schema_ai_updates.sql in your Supabase SQL Editor
   ```

2. **Verify the updates:**
   ```sql
   -- Check that new columns were added to research_jobs
   SELECT column_name, data_type 
   FROM information_schema.columns 
   WHERE table_name = 'research_jobs';
   
   -- Check that ai_report_usage table was created
   SELECT * FROM ai_report_usage LIMIT 1;
   
   -- Test the v_ai_reports view
   SELECT * FROM v_ai_reports LIMIT 1;
   ```

## Step 2: Set Up Gemini API

1. **Enable Vertex AI in Google Cloud:**
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Enable the Vertex AI API
   - Create a service account with Vertex AI permissions

2. **Get API Key:**
   - Alternative: Use Google AI Studio for simpler setup
   - Go to [Google AI Studio](https://aistudio.google.com)
   - Create an API key for Gemini

## Step 3: Deploy Supabase Edge Function

1. **Install Supabase CLI:**
   ```bash
   npm install -g supabase
   ```

2. **Initialize Supabase (if not already done):**
   ```bash
   supabase init
   ```

3. **Deploy the Edge Function:**
   ```bash
   # Link to your Supabase project
   supabase link --project-ref YOUR_PROJECT_REF
   
   # Deploy the function
   supabase functions deploy generate-ai-report
   ```

4. **Set Environment Variables:**
   ```bash
   # Set the Gemini API key
   supabase secrets set GEMINI_API_KEY=your_gemini_api_key_here
   
   # Verify secrets
   supabase secrets list
   ```

## Step 4: Update Frontend

1. **The following files have been created/modified:**
   - ✅ `frontend/src/components/ai/AIReportButton.tsx` - New AI report button
   - ✅ `frontend/src/components/ai/AIReportViewer.tsx` - Report viewer component
   - ✅ `frontend/src/pages/ai-reports/[id].astro` - Report page
   - ✅ `frontend/src/components/dashboard/BreachTable.tsx` - Updated with AI button

2. **Deploy Frontend:**
   ```bash
   # Your existing GitHub Actions will handle deployment
   git add .
   git commit -m "Add AI agent system for breach reports"
   git push origin main
   ```

## Step 5: Test the System

1. **Test Database Functions:**
   ```sql
   -- Test rate limiting function
   SELECT check_daily_rate_limit('00000000-0000-0000-0000-000000000000', 10);
   
   -- Test usage tracking
   SELECT increment_usage_stats('00000000-0000-0000-0000-000000000000', 0.17, 5000);
   ```

2. **Test Edge Function:**
   ```bash
   # Test the function directly
   curl -X POST 'https://YOUR_PROJECT_REF.supabase.co/functions/v1/generate-ai-report' \
     -H 'Authorization: Bearer YOUR_ANON_KEY' \
     -H 'Content-Type: application/json' \
     -d '{"breachId": 1}'
   ```

3. **Test Frontend Integration:**
   - Navigate to your breach dashboard
   - Click the "🤖 AI Report" button on any breach
   - Verify the report generation process

## Step 6: Configure MCP Tools (Optional Enhancement)

To use real web search and scraping instead of mock data:

1. **Set up Brave Search API:**
   ```bash
   supabase secrets set BRAVE_SEARCH_API_KEY=your_brave_api_key
   ```

2. **Update the Edge Function:**
   - Replace mock search/scrape functions with real MCP calls
   - See comments in `supabase/functions/generate-ai-report/index.ts`

## Environment Variables Summary

Set these in your Supabase project:

```bash
# Required
GEMINI_API_KEY=your_gemini_api_key_here

# Optional (for enhanced functionality)
BRAVE_SEARCH_API_KEY=your_brave_search_api_key
CLEARBIT_API_KEY=your_clearbit_api_key  # For demographic data
```

## Monitoring and Maintenance

1. **Monitor Usage:**
   ```sql
   -- Check daily usage stats
   SELECT * FROM ai_report_usage 
   WHERE date >= CURRENT_DATE - INTERVAL '7 days'
   ORDER BY date DESC;
   
   -- Check report generation stats
   SELECT 
     status,
     COUNT(*) as count,
     AVG(processing_time_ms) as avg_time_ms,
     AVG(cost_estimate) as avg_cost
   FROM research_jobs 
   WHERE report_type = 'ai_breach_analysis'
   GROUP BY status;
   ```

2. **Monitor Costs:**
   ```sql
   -- Daily cost tracking
   SELECT 
     date,
     SUM(total_cost) as daily_cost,
     SUM(report_count) as daily_reports
   FROM ai_report_usage 
   WHERE date >= CURRENT_DATE - INTERVAL '30 days'
   GROUP BY date
   ORDER BY date DESC;
   ```

## Troubleshooting

### Common Issues

1. **"Function not found" error:**
   - Verify function deployment: `supabase functions list`
   - Check function logs: `supabase functions logs generate-ai-report`

2. **"API key not found" error:**
   - Verify secrets: `supabase secrets list`
   - Re-set the API key: `supabase secrets set GEMINI_API_KEY=...`

3. **Rate limit errors:**
   - Check usage: `SELECT * FROM ai_report_usage WHERE user_id = 'USER_ID'`
   - Adjust rate limits in the database function

4. **Frontend component not loading:**
   - Check browser console for errors
   - Verify Supabase client configuration
   - Check network requests in browser dev tools

### Performance Optimization

1. **Reduce costs:**
   - Use Gemini 2.5 Flash instead of Pro
   - Implement report caching
   - Limit search results and scraped pages

2. **Improve speed:**
   - Parallel processing of search/scrape operations
   - Optimize database queries
   - Use CDN for static assets

## Security Considerations

1. **Rate Limiting:**
   - Default: 10 reports per user per day
   - Adjust in `check_daily_rate_limit` function

2. **Authentication:**
   - Currently allows anonymous requests
   - Enable JWT verification for production: `verify_jwt = true`

3. **Input Validation:**
   - Validate breach IDs
   - Sanitize user inputs
   - Implement request size limits

## Next Steps

1. **Phase 2 Enhancements:**
   - Add AG2 multi-agent orchestration
   - Implement real-time streaming
   - Add report sharing and collaboration
   - Integrate demographic enrichment

2. **Analytics:**
   - Track report quality metrics
   - Monitor user engagement
   - A/B test different AI models

3. **Integration:**
   - Connect with email alert system
   - Add to saved breaches workflow
   - Integrate with GitHub Actions for automated reports

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Supabase function logs
3. Check browser console for frontend errors
4. Verify all environment variables are set correctly

The AI agent system is now ready to generate comprehensive breach reports! 🎉
