# Comprehensive Breach Data Aggregator

## Overview

This project aggregates data related to data breaches and security incidents from a wide array of sources. These sources include government portals (like SEC EDGAR and State Attorney General websites), cybersecurity news RSS feeds, direct API integrations (e.g., HIBP), company investor relations pages, and custom scraping solutions (like using Apify for specific state data).

The collected data is standardized and stored in a Supabase PostgreSQL database. A simple, read-only web interface, hosted via GitHub Pages, provides a dashboard to view the aggregated breach information. The entire data collection process is automated using GitHub Actions, which run the scraper scripts daily.

## Features

*   **Diverse Data Sourcing:** Scrapes and ingests data from over 25 distinct sources.
*   **Source Categories:**
    *   Governmental Filings (SEC EDGAR 8-K)
    *   Health Sector Breach Portals (HHS OCR)
    *   State Attorney General (AG) Data Breach Notification Sites (13 states)
    *   Cybersecurity News RSS Feeds (10 sources, configurable)
    *   Company Investor Relations (IR) News Sections (5 major tech companies, configurable)
    *   Specialized Breach Listing Sites (BreachSense)
    *   Breach Databases via API (HIBP)
    *   Custom Scraper Integrations (e.g., Texas AG data via Apify)
*   **Automated Collection:** Daily data updates via a GitHub Actions workflow.
*   **Centralized Storage:** Uses Supabase (PostgreSQL) for robust and accessible data storage.
*   **Basic Dashboard:** A simple frontend hosted on GitHub Pages to view the latest aggregated data.
*   **Configurable Sources:** News feeds and company IR sites can be configured via `config.yaml`.

## Data Sources

The project gathers data from several categories:

*   **US Federal Government:**
    *   SEC EDGAR 8-K Filings (for material cybersecurity incidents)
    *   HHS OCR Breach Portal (healthcare breaches)

*   **US State Attorney General Portals & Similar:**
    *   California, Delaware, Hawaii, Indiana, Iowa, Maine, Maryland, Massachusetts, Montana, New Hampshire, New Jersey (Cybersecurity), North Dakota, Oklahoma (Cybersecurity), Texas (via Apify actor), Vermont, Wisconsin (DATCP).
*   **Cybersecurity News & Reporting Sites:**
    *   KrebsOnSecurity, BleepingComputer, The Hacker News, SecurityWeek, Dark Reading, DataBreaches.net, Cybersecurity Ventures, Reddit r/cybersecurity, Reddit r/databreaches. (Configurable via `config.yaml`)
    *   BreachSense

*   **Company Investor Relations (IR) Pages:**
    *   Microsoft, Apple, Amazon, Alphabet, Meta. (Configurable via `config.yaml`)
*   **API-based Services:**
    *   Have I Been Pwned (HIBP) - Breach data for websites.

For a detailed list of configurable news feeds and company IR sites, please see the `config.yaml` file.

## Tech Stack

*   **Backend & Scrapers:** Python 3.10
    *   `requests`: For making HTTP requests.
    *   `BeautifulSoup4`: For parsing HTML content.
    *   `feedparser`: For parsing RSS/Atom feeds.
    *   `python-dateutil`: For flexible date parsing.
    *   `PyYAML`: For reading `config.yaml`.
    *   `apify-client`: For interacting with the Apify platform.
*   **Database:** Supabase (PostgreSQL)
*   **Automation:** GitHub Actions
*   **Frontend Dashboard:** HTML, CSS, JavaScript (hosted on GitHub Pages)

## Setup and Installation

### Prerequisites

*   Python 3.10 or newer
*   pip (Python package installer)
*   Git

### 1. Clone Repository

```bash
git clone https://github.com/your-username/your-repo-name.git # Replace with your repo URL
cd your-repo-name
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Supabase Setup

*   **Create a Supabase Project:**
    1.  Go to [Supabase.io](https://supabase.io) and sign up/log in.
    2.  Create a new project. Choose your region.
    3.  Save your project's **URL** and **anon key** (for the frontend) and **service_role key** (for the scrapers).
*   **Database Schema:**
    You need to create two main tables in your Supabase SQL Editor: `data_sources` and `scraped_items`.

    **`data_sources` Table:**
    This table stores information about where the data comes from.
    ```sql
    CREATE TABLE data_sources (
        id BIGINT PRIMARY KEY, -- Manually assigned ID, must match scraper configs
        name TEXT NOT NULL UNIQUE,
        url TEXT, -- Main URL of the data source
        type TEXT, -- e.g., 'State AG', 'News Feed', 'API', 'Government Portal'
        description TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    ```
    *Example `source_id` values to insert into `data_sources` (ensure these match the `source_id` used in each scraper script and `config.yaml`):*
      *   1: SEC EDGAR 8-K
      *   2: HHS OCR
      *   3-5: Delaware, California, Washington AGs
      *   6-18: Other State AGs/Cybersecurity sites (HI, IN, IA, ME, MD, MA, MT, NH, NJ, ND, OK, VT, WI)
      *   19: BreachSense
      *   20-29: Cybersecurity News Feeds (from `config.yaml`)
      *   30: Privacy Rights Clearinghouse
      *   31-35: Company IR Sites (from `config.yaml`)
      *   36: Have I Been Pwned (HIBP) API
      *   37: Texas AG (via Apify)

    **`scraped_items` Table:**
    This table stores the actual breach/vulnerability records with comprehensive fields for different data types.
    ```sql
    CREATE TABLE scraped_items (
        id BIGSERIAL PRIMARY KEY,
        source_id BIGINT NOT NULL REFERENCES data_sources(id),
        item_url TEXT UNIQUE, -- Unique URL for the specific breach/article page
        title TEXT NOT NULL,
        publication_date TIMESTAMPTZ,
        scraped_at TIMESTAMPTZ DEFAULT NOW(),
        summary_text TEXT,
        full_content TEXT, -- Optional, for full article text if scraped
        raw_data_json JSONB, -- Store original or additional data from source
        tags_keywords TEXT[], -- Array of tags/keywords
        created_at TIMESTAMPTZ DEFAULT NOW(),

        -- STANDARDIZED BREACH FIELDS (for cross-portal analysis)
        affected_individuals INTEGER, -- Number of people affected
        breach_date TEXT, -- When incident occurred (flexible text field)
        reported_date DATE, -- When reported to authority
        notice_document_url TEXT, -- Link to official notice document
        what_was_leaked TEXT, -- What information was compromised

        -- SEC-SPECIFIC FIELDS (for SEC EDGAR 8-K filings)
        cik TEXT, -- Central Index Key (company identifier)
        ticker_symbol TEXT, -- Stock ticker
        accession_number TEXT, -- Unique EDGAR filing ID
        form_type TEXT, -- 8-K, 8-K/A, 10-K, 10-Q, etc.
        filing_date DATE, -- When filed with SEC
        report_date DATE, -- Period of report
        primary_document_url TEXT, -- Direct link to main filing document
        xbrl_instance_url TEXT, -- Link to XBRL instance document
        items_disclosed TEXT[], -- 8-K items (1.05, 8.01, etc.)
        is_cybersecurity_related BOOLEAN DEFAULT FALSE,
        is_amendment BOOLEAN DEFAULT FALSE,
        is_delayed_disclosure BOOLEAN DEFAULT FALSE,

        -- CYBERSECURITY INCIDENT DETAILS
        incident_nature_text TEXT,
        incident_scope_text TEXT,
        incident_timing_text TEXT,
        incident_impact_text TEXT,
        incident_unknown_details_text TEXT,
        incident_discovery_date DATE,
        incident_disclosure_date DATE,
        incident_containment_date DATE,

        -- IMPACT ASSESSMENT
        estimated_cost_min DECIMAL,
        estimated_cost_max DECIMAL,
        estimated_cost_currency TEXT DEFAULT 'USD',
        data_types_compromised TEXT[], -- Types of data affected (PII, PHI, etc.)

        -- DOCUMENT ANALYSIS
        exhibit_urls TEXT[], -- Links to exhibits
        keywords_detected TEXT[], -- Specific cybersecurity keywords found
        keyword_contexts JSONB, -- Context around detected keywords
        file_size_bytes INTEGER, -- Size of filing document

        -- BUSINESS CONTEXT
        business_description TEXT,
        industry_classification TEXT
    );
    ```

    **Note:** The actual database includes 44+ fields optimized for comprehensive breach data collection across multiple source types (State AGs, SEC filings, news feeds, etc.). See `database_schema.sql` for the complete schema.

### 4. API Keys and Environment Variables (Local Development)

For local execution of certain scrapers, create a `.env` file in the project root:
```
SUPABASE_URL="your_supabase_project_url"
SUPABASE_SERVICE_KEY="your_supabase_service_role_key"

# Required for HIBP API scraper
HIBP_API_KEY="your_hibp_api_key"



# Required for Apify integration (Texas scraper)
APIFY_API_TOKEN="your_apify_api_token"
APIFY_TEXAS_BREACH_ACTOR_ID="your_apify_actor_id_for_texas_data"
```
**Important:** Ensure `.env` is listed in your `.gitignore` file to prevent committing secrets.

### 5. GitHub Secrets (for Automation)

For the GitHub Actions workflow to run successfully, configure the following secrets in your GitHub repository settings (Settings -> Secrets and variables -> Actions -> New repository secret):

*   `SUPABASE_URL`: Your Supabase project URL.
*   `SUPABASE_SERVICE_KEY`: Your Supabase service_role key.
*   `HIBP_API_KEY`: Your Have I Been Pwned API key.
*   `APIFY_API_TOKEN`: Your Apify API token.
*   `APIFY_TEXAS_BREACH_ACTOR_ID`: The ID of your Apify actor for Texas data.

## Running Scrapers Locally

You can run individual scraper scripts from the project root directory:

```bash
# Example:
python scrapers/fetch_sec_edgar_8k.py
python scrapers/fetch_hhs_ocr.py
python scrapers/fetch_cybersecurity_news.py
# ...and so on for other scrapers.
```
Ensure your environment variables are set (e.g., loaded from `.env` if you use a library like `python-dotenv`, or set manually in your shell).

## GitHub Actions Automation

The workflow defined in `.github/workflows/main_scraper_workflow.yml` automates the data collection process using **parallel execution** for optimal performance.

**Execution Strategy:**
*   **6 parallel groups** run simultaneously for ~3x speed improvement
*   **Government & Federal** (SEC, HHS OCR)
*   **State AG Groups 1-4** (organized by geographic/processing similarity)
*   **News & API** (BreachSense, Cybersecurity News, Company IR, HIBP)
*   **Problematic Scrapers** (Maryland AG - isolated due to website issues)

**Schedule & Triggers:**
*   Runs daily at 3 AM UTC
*   Can be triggered manually from the Actions tab in your GitHub repository
*   Uses configured GitHub Secrets for API keys and Supabase credentials

**Performance:**
*   **Execution time**: ~8-12 minutes (vs 30-40 minutes sequential)
*   **Failure isolation**: If one group fails, others continue
*   **Comprehensive reporting**: Summary job shows results of all groups

## Viewing the Dashboard

The project includes a simple frontend dashboard to display the aggregated data. It's located in the `/docs` folder and is designed to be hosted using GitHub Pages.

*   **Setup GitHub Pages:**
    1.  Go to your repository on GitHub.
    2.  Click on "Settings".
    3.  Navigate to the "Pages" section (under "Code and automation").
    4.  Under "Build and deployment", select "Deploy from a branch" as the Source.
    5.  Choose the `main` (or `master`) branch and the `/docs` folder as the source. Click "Save".
*   **Accessing the Dashboard:**
    GitHub Pages will provide a URL for your live site (e.g., `https://your-username.github.io/your-repo-name/`). It might take a few minutes for the site to become available after the first deployment.
    The `SUPABASE_URL` and `SUPABASE_ANON_KEY` used by the frontend dashboard are hardcoded in `docs/script.js`. Ensure these are correct for your Supabase project.

## Configuration

The `config.yaml` file in the project root is used to configure:
*   `cybersecurity_news_feeds`: A list of RSS/Atom feeds for cybersecurity news. Each entry requires `name`, `url`, and `source_id`.
*   `company_ir_sites`: A list of company investor relations websites to monitor. Each entry requires `name`, `url`, and `source_id`. Optional `subpage_hints` can be added to guide the scraper to specific news sections if the default keywords are not sufficient.

## Database Schema Summary

### `data_sources` Table
Stores metadata about each data source.
*   `id` (BIGINT, PK): Unique identifier for the source. Must be manually assigned and correspond to scraper configurations.
*   `name` (TEXT, NOT NULL, UNIQUE): Human-readable name of the source (e.g., "SEC EDGAR 8-K", "KrebsOnSecurity").
*   `url` (TEXT): The main URL for the data source, if applicable.
*   `type` (TEXT): Category of the source (e.g., "State AG", "News Feed", "API").
*   `description` (TEXT): Optional brief description of the source.
*   `created_at` (TIMESTAMPTZ, default NOW()): Timestamp of when the source record was created.

### `scraped_items` Table
Stores the individual breach/vulnerability/news items collected with comprehensive fields for different data types.

**Core Fields:**
*   `id` (BIGSERIAL, PK): Auto-incrementing primary key for each scraped item.
*   `source_id` (BIGINT, FK to `data_sources.id`): Identifies which data source the item came from.
*   `item_url` (TEXT, UNIQUE): The unique URL pointing to the specific breach report, news article, or vulnerability detail page. This is a key field for avoiding duplicates.
*   `title` (TEXT, NOT NULL): Title of the item (e.g., company name for a breach, article title, vulnerability name).
*   `publication_date` (TIMESTAMPTZ): The date the item was officially published or reported.
*   `scraped_at` (TIMESTAMPTZ, default NOW()): Timestamp of when the item was scraped by the system.
*   `summary_text` (TEXT): A brief summary or description of the item.
*   `full_content` (TEXT): Optional field to store the full text content, if scraped.
*   `raw_data_json` (JSONB): Stores original or additional data from the source as a JSON object.
*   `tags_keywords` (TEXT[]): An array of relevant tags or keywords associated with the item.
*   `created_at` (TIMESTAMPTZ, default NOW()): Timestamp of when the record was inserted into the database.

**Standardized Breach Fields:**
*   `affected_individuals` (INTEGER): Number of people affected by the breach.
*   `breach_date` (TEXT): When the incident occurred (flexible text field for various date formats).
*   `reported_date` (DATE): When the breach was reported to authorities.
*   `notice_document_url` (TEXT): Link to official breach notification document.
*   `what_was_leaked` (TEXT): Description of what information was compromised.

**SEC-Specific Fields:**
*   `cik` (TEXT): Central Index Key (company identifier).
*   `ticker_symbol` (TEXT): Stock ticker symbol.
*   `accession_number` (TEXT): Unique EDGAR filing ID.
*   `form_type` (TEXT): Filing type (8-K, 8-K/A, 10-K, 10-Q, etc.).
*   `filing_date` (DATE): When filed with SEC.
*   `is_cybersecurity_related` (BOOLEAN): Flag for cybersecurity-related filings.
*   `items_disclosed` (TEXT[]): 8-K items disclosed (1.05, 8.01, etc.).

**Advanced Analysis Fields:**
*   `data_types_compromised` (TEXT[]): Types of data affected (PII, PHI, financial, etc.).
*   `keywords_detected` (TEXT[]): Specific cybersecurity keywords found.
*   `keyword_contexts` (JSONB): Context around detected keywords.
*   `incident_discovery_date` (DATE): When the incident was discovered.
*   `estimated_cost_min/max` (DECIMAL): Financial impact estimates.
*   `industry_classification` (TEXT): Industry/sector classification.

**Total Fields:** 44+ fields optimized for comprehensive breach data analysis across multiple source types.

---

This README provides a comprehensive guide to understanding, setting up, and using the Comprehensive Breach Data Aggregator project.
