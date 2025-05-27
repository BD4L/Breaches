-- Comprehensive Breach Data Aggregator - Database Schema
-- Run this script in your Supabase SQL Editor to recreate all tables

-- ============================================================================
-- 1. CREATE DATA_SOURCES TABLE
-- ============================================================================
CREATE TABLE data_sources (
    id BIGINT PRIMARY KEY, -- Manually assigned ID, must match scraper configs
    name TEXT NOT NULL UNIQUE,
    url TEXT, -- Main URL of the data source
    type TEXT, -- e.g., 'State AG', 'News Feed', 'API', 'Government Portal'
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 2. CREATE SCRAPED_ITEMS TABLE (Enhanced with Standardized Fields)
-- ============================================================================
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

    -- STANDARDIZED BREACH FIELDS (added for cross-portal analysis)
    affected_individuals INTEGER, -- Number of people affected
    breach_date DATE, -- When incident occurred (or TEXT for unparseable dates)
    reported_date DATE, -- When reported to authority (or TEXT for unparseable dates)
    notice_document_url TEXT, -- Link to official notice document

    -- SEC-SPECIFIC FIELDS (Enhanced for comprehensive SEC data extraction)
    -- Core Filing Metadata
    cik TEXT, -- Central Index Key (company identifier)
    ticker_symbol TEXT, -- Stock ticker
    accession_number TEXT, -- Unique EDGAR filing ID
    form_type TEXT, -- 8-K, 8-K/A, 10-K, 10-Q, etc.
    filing_date DATE, -- When filed with SEC
    report_date DATE, -- Period of report (earliest event date)
    primary_document_url TEXT, -- Direct link to main filing document
    xbrl_instance_url TEXT, -- Link to XBRL instance document

    -- Filing Classification
    items_disclosed TEXT[], -- 8-K items (1.05, 8.01, etc.)
    is_cybersecurity_related BOOLEAN DEFAULT FALSE, -- Cybersecurity incident flag
    is_amendment BOOLEAN DEFAULT FALSE, -- Whether this is an 8-K/A amendment
    is_delayed_disclosure BOOLEAN DEFAULT FALSE, -- National security delay flag

    -- Cybersecurity Incident Details (from CYD taxonomy)
    incident_nature_text TEXT, -- MaterialCybersecurityIncidentNatureTextBlock
    incident_scope_text TEXT, -- MaterialCybersecurityIncidentScopeTextBlock
    incident_timing_text TEXT, -- MaterialCybersecurityIncidentTimingTextBlock
    incident_impact_text TEXT, -- MaterialCybersecurityIncidentMaterialImpactTextBlock
    incident_unknown_details_text TEXT, -- InformationNotAvailableOrUndeterminedTextBlock

    -- Incident Timeline
    incident_discovery_date DATE, -- When incident was discovered
    incident_disclosure_date DATE, -- When publicly disclosed
    incident_containment_date DATE, -- When incident was contained

    -- Impact Assessment
    estimated_cost_min DECIMAL, -- Minimum estimated financial impact
    estimated_cost_max DECIMAL, -- Maximum estimated financial impact
    estimated_cost_currency TEXT DEFAULT 'USD', -- Currency for cost estimates
    data_types_compromised TEXT[], -- Types of data affected (PII, PHI, etc.)

    -- Document Analysis
    exhibit_urls TEXT[], -- Links to exhibits (customer notices, press releases)
    keywords_detected TEXT[], -- Specific cybersecurity keywords found
    keyword_contexts JSONB, -- Context around detected keywords
    file_size_bytes INTEGER, -- Size of filing document

    -- Business Context
    business_description TEXT, -- Company business description
    industry_classification TEXT -- Industry/sector classification
);

-- ============================================================================
-- 3. CREATE INDEXES FOR PERFORMANCE
-- ============================================================================
-- Original indexes
CREATE INDEX idx_scraped_items_source_id ON scraped_items(source_id);
CREATE INDEX idx_scraped_items_publication_date ON scraped_items(publication_date);
CREATE INDEX idx_scraped_items_scraped_at ON scraped_items(scraped_at);
CREATE INDEX idx_scraped_items_affected_individuals ON scraped_items(affected_individuals);
CREATE INDEX idx_scraped_items_breach_date ON scraped_items(breach_date);
CREATE INDEX idx_scraped_items_reported_date ON scraped_items(reported_date);
CREATE INDEX idx_scraped_items_tags ON scraped_items USING GIN(tags_keywords);
CREATE INDEX idx_scraped_items_raw_data ON scraped_items USING GIN(raw_data_json);

-- SEC-specific indexes for enhanced performance
CREATE INDEX idx_scraped_items_cik ON scraped_items(cik);
CREATE INDEX idx_scraped_items_ticker ON scraped_items(ticker_symbol);
CREATE INDEX idx_scraped_items_accession ON scraped_items(accession_number);
CREATE INDEX idx_scraped_items_form_type ON scraped_items(form_type);
CREATE INDEX idx_scraped_items_filing_date ON scraped_items(filing_date);
CREATE INDEX idx_scraped_items_cybersecurity_flag ON scraped_items(is_cybersecurity_related);
CREATE INDEX idx_scraped_items_amendment_flag ON scraped_items(is_amendment);
CREATE INDEX idx_scraped_items_items_disclosed ON scraped_items USING GIN(items_disclosed);
CREATE INDEX idx_scraped_items_keywords_detected ON scraped_items USING GIN(keywords_detected);
CREATE INDEX idx_scraped_items_data_types ON scraped_items USING GIN(data_types_compromised);
CREATE INDEX idx_scraped_items_incident_discovery ON scraped_items(incident_discovery_date);
CREATE INDEX idx_scraped_items_estimated_cost ON scraped_items(estimated_cost_min, estimated_cost_max);
CREATE INDEX idx_scraped_items_keyword_contexts ON scraped_items USING GIN(keyword_contexts);

-- ============================================================================
-- 4. INSERT DATA SOURCES (All Current Breach Portals)
-- ============================================================================

-- Government Portals
INSERT INTO data_sources (id, name, url, type, description) VALUES
(1, 'SEC EDGAR 8-K', 'https://www.sec.gov/edgar/search/', 'Government Portal', 'SEC cybersecurity incident disclosures via 8-K filings'),
(2, 'HHS OCR Breach Portal', 'https://ocrportal.hhs.gov/ocr/breach/breach_report.jsf', 'Government Portal', 'Healthcare data breaches reported to HHS Office for Civil Rights');

-- State Attorney General Portals
INSERT INTO data_sources (id, name, url, type, description) VALUES
(3, 'Delaware AG', 'https://attorneygeneral.delaware.gov/fraud/cpu/securitybreach/', 'State AG', 'Delaware Attorney General data breach notifications'),
(4, 'California AG', 'https://oag.ca.gov/privacy/databreach/list', 'State AG', 'California Attorney General data breach notifications'),
(5, 'Washington AG', 'https://www.atg.wa.gov/data-breach-notifications', 'State AG', 'Washington Attorney General data breach notifications'),
(6, 'Hawaii AG', 'https://ag.hawaii.gov/cpja/data-breach-notice/', 'State AG', 'Hawaii Attorney General data breach notifications'),
(7, 'Indiana AG', 'https://www.in.gov/attorneygeneral/consumer-protection/data-breach-notifications/', 'State AG', 'Indiana Attorney General data breach notifications'),
(8, 'Iowa AG', 'https://www.iowaattorneygeneral.gov/for-consumers/data-breach-notifications', 'State AG', 'Iowa Attorney General data breach notifications'),
(9, 'Maine AG', 'https://www.maine.gov/ag/dynld/documents/clg/breach_notifications.html', 'State AG', 'Maine Attorney General data breach notifications'),
(10, 'Maryland AG', 'https://www.marylandattorneygeneral.gov/Pages/IdentityTheft/breachnotice.aspx', 'State AG', 'Maryland Attorney General data breach notifications'),
(11, 'Massachusetts AG', 'https://www.mass.gov/lists/data-breach-notifications', 'State AG', 'Massachusetts Attorney General data breach notifications'),
(12, 'Montana AG', 'https://dojmt.gov/consumer/databreach/', 'State AG', 'Montana Attorney General data breach notifications'),
(13, 'New Hampshire AG', 'https://www.doj.nh.gov/consumer/security-breaches/', 'State AG', 'New Hampshire Attorney General data breach notifications'),
(14, 'New Jersey Cybersecurity', 'https://www.cyber.nj.gov/alerts-advisories/data-breach-notifications', 'State Cybersecurity', 'New Jersey cybersecurity data breach notifications'),
(15, 'North Dakota AG', 'https://attorneygeneral.nd.gov/consumer-resources/data-breach-notifications', 'State AG', 'North Dakota Attorney General data breach notifications'),
(16, 'Oklahoma Cybersecurity', 'https://www.ok.gov/cybersecurity/', 'State Cybersecurity', 'Oklahoma cybersecurity data breach notifications'),
(17, 'Vermont AG', 'https://ago.vermont.gov/focus/data-broker-privacy/data-breach-notifications/', 'State AG', 'Vermont Attorney General data breach notifications'),
(18, 'Wisconsin DATCP', 'https://datcp.wi.gov/Pages/Programs_Services/DataBreachNotifications/default.aspx', 'State Agency', 'Wisconsin Department of Agriculture data breach notifications');

-- Specialized Breach Sites
INSERT INTO data_sources (id, name, url, type, description) VALUES
(19, 'BreachSense', 'https://breachsense.com/', 'Breach Database', 'Specialized data breach tracking and intelligence platform');

-- Cybersecurity News Feeds (20-29 reserved for config.yaml feeds)
INSERT INTO data_sources (id, name, url, type, description) VALUES
(20, 'KrebsOnSecurity', 'https://krebsonsecurity.com/feed/', 'News Feed', 'Cybersecurity news and breach reporting'),
(21, 'BleepingComputer', 'https://www.bleepingcomputer.com/feed/', 'News Feed', 'Technology news and security incidents'),
(22, 'The Hacker News', 'https://feeds.feedburner.com/TheHackersNews', 'News Feed', 'Cybersecurity and hacking news'),
(23, 'SecurityWeek', 'https://www.securityweek.com/feed', 'News Feed', 'Enterprise security news'),
(24, 'Dark Reading', 'https://www.darkreading.com/rss.xml', 'News Feed', 'Cybersecurity news and analysis'),
(25, 'DataBreaches.net', 'https://www.databreaches.net/feed/', 'News Feed', 'Data breach news and privacy issues'),
(26, 'Cybersecurity Ventures', 'https://cybersecurityventures.com/feed/', 'News Feed', 'Cybersecurity industry news'),
(27, 'Reddit r/cybersecurity', 'https://www.reddit.com/r/cybersecurity.rss', 'News Feed', 'Cybersecurity community discussions'),
(28, 'Reddit r/databreaches', 'https://www.reddit.com/r/databreaches.rss', 'News Feed', 'Data breach community discussions'),
(29, 'Cyber News Feed', NULL, 'News Feed', 'Additional cybersecurity news source');

-- Privacy and Breach Databases
INSERT INTO data_sources (id, name, url, type, description) VALUES
(30, 'Privacy Rights Clearinghouse', 'https://privacyrights.org/data-breaches', 'Breach Database', 'Comprehensive data breach database and privacy advocacy');

-- Company IR Sites (31-35 reserved for config.yaml companies)
INSERT INTO data_sources (id, name, url, type, description) VALUES
(31, 'Microsoft IR', 'https://www.microsoft.com/en-us/investor/', 'Company IR', 'Microsoft investor relations and security disclosures'),
(32, 'Google IR', 'https://abc.xyz/investor/', 'Company IR', 'Alphabet/Google investor relations'),
(33, 'Apple IR', 'https://investor.apple.com/', 'Company IR', 'Apple investor relations'),
(34, 'Amazon IR', 'https://ir.aboutamazon.com/', 'Company IR', 'Amazon investor relations'),
(35, 'Meta IR', 'https://investor.fb.com/', 'Company IR', 'Meta (Facebook) investor relations');

-- API Services
INSERT INTO data_sources (id, name, url, type, description) VALUES
(36, 'Have I Been Pwned API', 'https://haveibeenpwned.com/api/v3/', 'API', 'Website breach database and API service');

-- Custom Integrations
INSERT INTO data_sources (id, name, url, type, description) VALUES
(37, 'Texas AG', 'https://oag.my.site.com/datasecuritybreachreport/apex/DataSecurityReportsPage', 'State AG', 'Texas Attorney General data security breach reports portal');

-- ============================================================================
-- 5. ENABLE ROW LEVEL SECURITY (Optional - for public access)
-- ============================================================================
-- Uncomment these lines if you want to enable public read access to the data

-- ALTER TABLE data_sources ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE scraped_items ENABLE ROW LEVEL SECURITY;

-- CREATE POLICY "Allow public read access on data_sources" ON data_sources
--     FOR SELECT USING (true);

-- CREATE POLICY "Allow public read access on scraped_items" ON scraped_items
--     FOR SELECT USING (true);

-- ============================================================================
-- SCHEMA CREATION COMPLETE
-- ============================================================================
--
-- This schema includes:
-- ✅ data_sources table with all 37 breach portal sources
-- ✅ scraped_items table with standardized cross-portal fields
-- ✅ Performance indexes for fast querying
-- ✅ Standardized fields: affected_individuals, breach_date, reported_date, notice_document_url
-- ✅ All current breach portals (no vulnerability databases)
--
-- The database is now ready for breach data collection!
