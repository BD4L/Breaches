# 🚀 AI Agent System - Quick Start Checklist

## ⚡ 5-Minute Setup

### Step 1: Database Setup (2 minutes)
```bash
# 1. Go to Supabase Dashboard
open https://supabase.com/dashboard/project/hilbbjnnxkitxbptektg

# 2. Click "SQL Editor" → "New Query"
# 3. Copy/paste contents of database_schema_ai_updates.sql
# 4. Click "Run" button
```

### Step 2: Get API Key (1 minute)
```bash
# 1. Go to Google AI Studio
open https://aistudio.google.com

# 2. Click "Get API key"
# 3. Copy the key (starts with AIza...)
```

### Step 3: Deploy Function (2 minutes)
```bash
# Install Supabase CLI (if needed)
npm install -g supabase

# Link project and deploy
supabase link --project-ref hilbbjnnxkitxbptektg
supabase secrets set GEMINI_API_KEY=your_api_key_here
supabase functions deploy generate-ai-report
```

### Step 4: Deploy Frontend (automatic)
```bash
# Commit and push (GitHub Actions handles deployment)
git add .
git commit -m "Add AI agent system"
git push origin main

# Wait 2-3 minutes for GitHub Actions to complete
```

## 🧪 Quick Test

### Option 1: Run Test Script
```bash
./test_ai_system.sh
```

### Option 2: Manual Test
1. Go to https://bd4l.github.io/Breaches/
2. Look for "🤖 AI Report" buttons in breach table
3. Click one and watch it generate a report
4. Verify report opens in new tab

## ✅ Success Indicators

- [ ] Database schema updated (no errors in SQL Editor)
- [ ] Gemini API key working (test_ai_system.sh passes)
- [ ] Edge function deployed (supabase functions list shows it)
- [ ] Frontend shows AI buttons (🤖 visible in breach table)
- [ ] Can generate reports (clicking button works)
- [ ] Reports display properly (markdown renders correctly)

## 🆘 Quick Fixes

### "Function not found"
```bash
supabase functions deploy generate-ai-report
```

### "API key error"
```bash
supabase secrets set GEMINI_API_KEY=your_actual_key
```

### "No AI buttons visible"
```bash
# Check GitHub Actions completed
# Hard refresh browser (Cmd+Shift+R)
```

### "Database errors"
```sql
-- Re-run in Supabase SQL Editor
-- Copy contents of database_schema_ai_updates.sql
```

## 🎯 Expected Results

**Cost**: ~$0.17 per report  
**Speed**: 15-30 seconds  
**Limit**: 10 reports/day per user  

**Report includes**:
- Executive summary
- Timeline analysis  
- Impact assessment
- Technical details
- Regulatory implications
- Recommendations
- Hyperlinked sources

## 📞 Need Help?

1. Run `./test_ai_system.sh` for diagnostics
2. Check `supabase functions logs generate-ai-report`
3. Verify all files were created correctly
4. Check GitHub Actions deployment status

## 🎉 You're Done!

Once the checklist is complete, your AI agent system is live! Users can now generate comprehensive breach analysis reports with a single click. The system will automatically research, analyze, and create detailed reports with expert insights and hyperlinked sources.

**Your breach dashboard now has AI superpowers!** 🤖✨
