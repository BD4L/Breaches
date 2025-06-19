# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a comprehensive breach data aggregator that collects cybersecurity incident data from 25+ sources including government portals (SEC EDGAR, state AGs), news feeds, and APIs. The system uses Python scrapers with automated GitHub Actions workflows, stores data in Supabase PostgreSQL, and provides an Astro/React frontend dashboard.

## Development Commands

### Python Backend/Scrapers
```bash
# Install dependencies
pip install -r requirements.txt

# Run individual scrapers
python scrapers/fetch_sec_edgar_8k.py
python scrapers/fetch_california_ag.py

# Test email system
python test_email_system.py

# Test AI system
./test_ai_system.sh
```

### Frontend (Astro/React)
```bash
cd frontend
npm install
npm run dev        # Development server
npm run build      # Production build  
npm run preview    # Preview build
```

### Database Setup
Execute `database_schema.sql` in Supabase SQL Editor to create:
- `data_sources` table (source metadata)
- `scraped_items` table (44+ fields for comprehensive breach data)

## Architecture Overview

### Data Collection Layer
- **Python Scrapers** (`/scrapers/`): 30+ specialized scrapers for different sources
- **Automated Execution**: Two GitHub Actions workflows run scrapers on different schedules
  - Main state portals: every 30 minutes (`paralell.yml`)
  - RSS/API sources: every 2 hours (`rss-api-scrapers.yml`)

### Data Sources Configuration
- **Configurable Sources**: `config.yaml` defines RSS feeds and company IR sites
- **Source IDs**: Must match between scrapers, config, and database `data_sources` table
- **Categories**: State AGs (1-18), News feeds (20-48), Company IR (31-35), APIs (36+)

### Data Processing
- **Standardized Fields**: Common breach fields across all sources (affected_individuals, breach_date, etc.)
- **Source-Specific Fields**: SEC filings have CIK, ticker_symbol, accession_number
- **Duplicate Prevention**: Uses unique `item_url` field

### Frontend Dashboard
- **Technology**: Astro with React components, TailwindCSS
- **Data Access**: Supabase client with anon key for read-only access
- **Components**: Modular React components in `/src/components/`
- **Deployment**: Automatic GitHub Pages deployment

### AI Integration
- **AI Reports**: Supabase Edge Functions with Gemini API
- **Components**: `AIReportButton.tsx`, `AIReportViewer.tsx`
- **Rate Limiting**: Built-in daily limits per user

## Key Configuration Files

- `config.yaml`: RSS feeds and IR sites configuration
- `database_schema.sql`: Complete database schema
- `requirements.txt`: Python dependencies
- `frontend/package.json`: Frontend dependencies
- `.github/workflows/`: Automated scraper execution

## Testing

- `test_ai_system.sh`: Comprehensive AI system testing
- `test_email_system.py`: Email alerts verification
- Manual scraper testing: Run individual Python scripts

## Environment Variables

Required for scrapers:
- `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- `HIBP_API_KEY`, `APIFY_API_TOKEN`
- GitHub Secrets configured for automated workflows

## Data Flow

1. Scrapers collect data from sources → 2. Store in Supabase → 3. Frontend queries via API → 4. AI generates reports on demand

## Important Notes

- Source IDs must be consistent across scrapers, config.yaml, and database
- Use `scraper_logger.py` for standardized logging across all scrapers
- Frontend is read-only dashboard - no user data modification
- All sensitive operations use service_role key, frontend uses anon key