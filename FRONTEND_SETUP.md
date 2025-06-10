# Frontend Setup and Security Guide

## 🚀 Current Status
The frontend is successfully deployed at: https://bd4l.github.io/Breaches/

## ✅ Recent Fixes Applied

### 1. Configuration Corrections
- **Fixed Astro site URL**: Updated from `hackermanmarlin.github.io` to `bd4l.github.io`
- **Fixed navigation links**: Updated to use correct base path `/Breaches/`

### 2. Security Improvements
- **Improved Supabase configuration**: Better environment variable handling
- **Reduced hardcoded credentials exposure**: Added fallback system with clear documentation

### 3. Environment Setup
- **GitHub Actions**: Frontend deployment is working correctly
- **Supabase Integration**: Successfully connecting to backend database

## 🔧 Setup Instructions

### Prerequisites
- Node.js 18+
- npm or yarn

### Local Development
```bash
cd frontend
npm install
npm run dev
```

### Environment Variables
Create a `.env` file in the frontend directory:
```env
PUBLIC_SUPABASE_URL=your_supabase_url
PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
```

### Production Deployment
The site automatically deploys via GitHub Actions when changes are pushed to the `main` branch in the `frontend/` directory.

## 🔒 Security Recommendations

### Immediate Actions Needed:

1. **Rotate Supabase Keys** (High Priority)
   - The current anon key is exposed in the repository
   - Generate new keys in Supabase dashboard
   - Update GitHub Secrets with new keys

2. **Update GitHub Secrets**
   ```
   PUBLIC_SUPABASE_URL=https://your-project.supabase.co
   PUBLIC_SUPABASE_ANON_KEY=your_new_anon_key
   ```

3. **Enable Row Level Security (RLS)**
   - Ensure RLS is enabled on all Supabase tables
   - Create appropriate policies for public read access

### Long-term Security Improvements:

1. **API Rate Limiting**
   - Implement rate limiting on Supabase
   - Consider using Supabase Edge Functions for sensitive operations

2. **Content Security Policy (CSP)**
   - Add CSP headers to prevent XSS attacks
   - Whitelist only necessary domains

3. **Environment Separation**
   - Use separate Supabase projects for development/staging/production
   - Implement proper secret management

## 📊 Current Data Flow

```
GitHub Actions (Scrapers) → Supabase Database → Frontend (GitHub Pages)
```

### Data Sources Connected:
- **Government Portals**: 2 sources, 23 breaches
- **State AG Sites**: 17 sources, 879 breaches  
- **Specialized Breach Sites**: 1 source, 0 breaches
- **RSS News Feeds**: Multiple sources, 288 articles
- **Company IR Sites**: Various sources

## 🐛 Known Issues & Fixes

### Data Quality Issues:
1. **Future dates**: Some records show "Jan 17, 2029" - likely date parsing errors
2. **Missing data**: Some breach records have "Unknown" values

### Recommended Fixes:
```sql
-- Fix future dates in database
UPDATE breach_records 
SET publication_date = NULL 
WHERE publication_date > CURRENT_DATE + INTERVAL '1 year';

-- Add data validation constraints
ALTER TABLE breach_records 
ADD CONSTRAINT reasonable_dates 
CHECK (publication_date <= CURRENT_DATE + INTERVAL '30 days');
```

## 🔄 Monitoring & Maintenance

### GitHub Actions Status:
- ✅ Frontend deployment: Working
- ❌ Scraper workflows: Some failures (check logs)

### Performance Metrics:
- **Load time**: ~2-3 seconds
- **Data freshness**: Updated daily
- **Uptime**: 99%+ (GitHub Pages)

### Regular Maintenance Tasks:
1. Monitor scraper success rates
2. Check for data quality issues
3. Update dependencies monthly
4. Review security logs

## 📞 Support

For issues or questions:
1. Check GitHub Actions logs
2. Review Supabase dashboard
3. Monitor browser console for errors
4. Check network requests in DevTools

## 🚀 Future Enhancements

### Planned Features:
1. **Real-time updates**: WebSocket integration
2. **Advanced filtering**: Date ranges, severity levels
3. **Export functionality**: CSV/PDF reports
4. **User authentication**: Save preferences, bookmarks
5. **Mobile optimization**: Responsive design improvements

### Technical Debt:
1. Add comprehensive error handling
2. Implement proper loading states
3. Add unit and integration tests
4. Optimize bundle size
5. Add accessibility improvements