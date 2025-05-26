# Enhanced SEC EDGAR 8-K Scraper Guide

## Overview

The Enhanced SEC EDGAR 8-K Scraper builds upon the existing SEC scraper to provide comprehensive cybersecurity incident detection and data extraction using the latest SEC requirements and XBRL/CYD taxonomy standards.

## Key Enhancements

### 1. XBRL/CYD Taxonomy Parsing
- **Structured Data Extraction**: Parses XBRL instance documents to extract machine-readable cybersecurity data
- **CYD Taxonomy Support**: Extracts all Material Cybersecurity Incident fields required by SEC Item 1.05
- **Automated XBRL Discovery**: Automatically constructs XBRL instance URLs from main filing URLs

### 2. Enhanced Database Schema
The scraper now populates comprehensive SEC-specific fields:

#### Core Filing Metadata
- `cik` - Central Index Key (company identifier)
- `ticker_symbol` - Stock ticker symbol
- `accession_number` - Unique EDGAR filing ID
- `form_type` - SEC form type (8-K, 8-K/A, etc.)
- `filing_date` - When filed with SEC
- `primary_document_url` - Direct link to main filing
- `xbrl_instance_url` - Link to XBRL instance document

#### Cybersecurity Incident Details (CYD Taxonomy)
- `incident_nature_text` - What happened (MaterialCybersecurityIncidentNatureTextBlock)
- `incident_scope_text` - Systems/data affected (MaterialCybersecurityIncidentScopeTextBlock)
- `incident_timing_text` - Discovery/containment timeline (MaterialCybersecurityIncidentTimingTextBlock)
- `incident_impact_text` - Business/financial impact (MaterialCybersecurityIncidentMaterialImpactTextBlock)
- `incident_unknown_details_text` - Unknown details flag (InformationNotAvailableOrUndeterminedTextBlock)

#### Impact Assessment
- `estimated_cost_min/max` - Financial impact range
- `estimated_cost_currency` - Currency for estimates
- `data_types_compromised` - Array of affected data types (PII, PHI, SSN, etc.)
- `affected_individuals` - Number of people affected

#### Document Analysis
- `exhibit_urls` - Links to exhibits (customer notices, press releases)
- `keywords_detected` - Cybersecurity keywords found
- `keyword_contexts` - Context around detected keywords
- `file_size_bytes` - Document size

### 3. Advanced Data Extraction

#### Financial Impact Detection
Automatically extracts cost estimates from filing text:
```python
# Detects patterns like:
# "$180 million to $400 million"
# "approximately $50 thousand"
# "costs of $2.5 billion"
```

#### Data Type Classification
Identifies compromised data types:
- **PII** - Personally Identifiable Information
- **SSN** - Social Security Numbers
- **Credit Card** - Payment card data
- **PHI** - Protected Health Information
- **Government ID** - Driver's licenses, passports
- **Financial** - Bank accounts, financial records

#### Incident Timeline Extraction
Parses incident-related dates:
- **Discovery Date** - When incident was discovered
- **Containment Date** - When incident was contained
- **Disclosure Date** - When publicly disclosed

### 4. Exhibit Document Analysis
- Automatically discovers and catalogs exhibit documents
- Extracts customer notice letters and press releases
- Provides direct links to additional breach details

## Usage

### Running the Enhanced Scraper
```bash
# Run the enhanced SEC scraper
python scrapers/fetch_sec_edgar_8k.py

# Test the enhanced features
python test_enhanced_sec_scraper.py
```

### Database Migration
The enhanced scraper requires the updated database schema:
```sql
-- Apply the enhanced schema
psql -d your_database -f database_schema.sql
```

## Data Flow

### 1. RSS Feed Monitoring
- Monitors SEC EDGAR RSS feed for all recent 8-K filings
- Filters for cybersecurity-related content using enhanced keyword detection

### 2. Enhanced Content Analysis
- Downloads main filing document
- Constructs XBRL instance URL
- Parses both HTML content and XBRL structured data

### 3. XBRL/CYD Parsing
- Extracts structured cybersecurity data using CYD taxonomy
- Maps XBRL elements to database fields
- Preserves both structured and unstructured data

### 4. Comprehensive Data Storage
- Stores data in standardized cross-portal fields
- Populates SEC-specific enhanced fields
- Maintains rich raw_data_json for analysis

## CYD Taxonomy Tags

The scraper extracts these key CYD (Cybersecurity Disclosure) taxonomy elements:

### Material Cybersecurity Incident Tags (Item 1.05)
- `MaterialCybersecurityIncidentNatureTextBlock`
- `MaterialCybersecurityIncidentScopeTextBlock`
- `MaterialCybersecurityIncidentTimingTextBlock`
- `MaterialCybersecurityIncidentMaterialImpactOrReasonablyLikelyMaterialImpactTextBlock`
- `MaterialCybersecurityIncidentInformationNotAvailableOrUndeterminedTextBlock`

### Risk Management Tags (10-K/10-Q)
- `CybersecurityRiskManagementProcessesForAssessingIdentifyingAndManagingThreatsTextBlock`
- `CybersecurityRiskBoardOfDirectorsOversightTextBlock`
- `CybersecurityRiskRoleOfManagementTextBlock`

## Example Output

### Enhanced Raw Data JSON
```json
{
  "organization_name": "Coinbase Global Inc",
  "cik": "0001679788",
  "ticker_symbol": "COIN",
  "accession_number": "0001679788-25-000094",
  "xbrl_instance_url": "https://www.sec.gov/Archives/edgar/data/1679788/000167978825000094/coin-20250514_htm.xml",
  "cyd_taxonomy_data": {
    "incident_nature": "Unauthorized access to customer data...",
    "incident_impact": "Estimated costs of $180-400 million...",
    "entity_name": "Coinbase Global Inc"
  },
  "financial_impact_min": 180000000,
  "financial_impact_max": 400000000,
  "data_types_compromised": ["PII", "Financial", "Account Data"],
  "exhibit_urls": ["https://www.sec.gov/Archives/edgar/data/1679788/000167978825000094/tm2514190d1_ex99-1.htm"],
  "enhancement_version": "2.0"
}
```

## Benefits

### 1. Comprehensive Coverage
- Captures ALL recent 8-K filings from any company
- No longer limited to specific company lists
- Detects cybersecurity incidents across entire market

### 2. Structured Data
- Machine-readable cybersecurity incident data
- Standardized fields for cross-portal analysis
- Rich metadata for advanced analytics

### 3. Regulatory Compliance
- Follows SEC CYD taxonomy standards
- Captures Item 1.05 Material Cybersecurity Incidents
- Tracks amendments and delayed disclosures

### 4. Enhanced Analytics
- Financial impact quantification
- Data type classification
- Timeline analysis
- Exhibit document tracking

## Monitoring and Alerts

The enhanced scraper provides rich data for:
- **Real-time incident detection**
- **Financial impact analysis**
- **Industry trend monitoring**
- **Regulatory compliance tracking**
- **Cross-portal correlation analysis**

## Future Enhancements

Potential future improvements:
- **10-K/10-Q parsing** for annual cybersecurity risk disclosures
- **Real-time API integration** for immediate incident detection
- **Machine learning classification** for incident severity
- **Cross-filing correlation** to track incident updates
- **Industry benchmarking** for comparative analysis

---

*This enhanced SEC scraper represents the most comprehensive cybersecurity incident detection system for public company disclosures, providing structured, machine-readable data that enables advanced analytics and real-time monitoring.*
