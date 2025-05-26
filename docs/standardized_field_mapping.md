# Standardized Field Mapping Across Breach Portals

## Overview

This document defines the standardized field mapping used across all breach portal scrapers to ensure consistent data structure and enable cross-portal analysis.

## Core Database Schema

### Primary Table: `scraped_items`

```sql
-- Core identification fields
source_id: INTEGER (portal identifier)
item_url: TEXT (unique constraint - link to specific breach)
title: TEXT (organization/entity name)
publication_date: TIMESTAMP (primary date for sorting)
scraped_at: TIMESTAMP (auto)
created_at: TIMESTAMP (auto)

-- Content fields  
summary_text: TEXT (human-readable summary)
full_content: TEXT (full document content when available)
raw_data_json: JSONB (portal-specific data)
tags_keywords: TEXT[] (searchable tags)

-- STANDARDIZED BREACH FIELDS (consistent across all portals)
affected_individuals: INTEGER (number of people affected)
breach_date: DATE (when incident occurred)
reported_date: DATE (when reported to authority)
notice_document_url: TEXT (link to official notice document)
```

## Standardized Field Definitions

### 1. `title` - Entity Name
**Purpose**: Name of the organization that experienced the breach
**Format**: Clean organization name only (no prefixes like "SEC 8-K:")
**Examples**:
- Delaware AG: "Bayhealth Medical Center"
- California AG: "Acme Healthcare Inc."
- SEC EDGAR: "VISA INC." (not "SEC 8-K: VISA INC. - Cybersecurity Filing")
- HHS OCR: "Regional Medical Center"

### 2. `affected_individuals` - Impact Count
**Purpose**: Number of individuals affected by the breach
**Format**: Integer (null if unknown/not specified)
**Extraction Patterns**:
- "affecting 1,000 individuals"
- "1.5 million customers impacted"
- "approximately 500 residents"
- "data of 2,000 users compromised"

### 3. `breach_date` - Incident Date
**Purpose**: When the actual security incident occurred
**Format**: DATE (YYYY-MM-DD) or original text if unparseable
**Portal Mapping**:
- Delaware AG: "Date(s) of Breach" column
- California AG: "Date(s) of Breach" field
- SEC EDGAR: Filing date (when disclosed)
- HHS OCR: Breach submission date
- State AGs: Varies by portal structure

### 4. `reported_date` - Authority Notification Date
**Purpose**: When the breach was reported to the relevant authority
**Format**: DATE (YYYY-MM-DD) or original text if unparseable
**Portal Mapping**:
- Delaware AG: "Reported Date" column
- California AG: "Date Submitted to AG"
- SEC EDGAR: SEC filing date
- HHS OCR: Breach submission date
- State AGs: Date reported to Attorney General

### 5. `notice_document_url` - Official Document Link
**Purpose**: Direct link to the official breach notification document
**Format**: Full URL to PDF, HTML page, or filing
**Portal Mapping**:
- Delaware AG: PDF notice link
- California AG: PDF notice link
- SEC EDGAR: Direct link to 8-K filing
- HHS OCR: Constructed reference URL
- State AGs: PDF or notice page links

### 6. `publication_date` - Primary Sorting Date
**Purpose**: Primary date used for chronological sorting and filtering
**Format**: ISO 8601 timestamp
**Logic**: Prefer reported_date, fallback to breach_date, fallback to scraped_at

## Portal-Specific Field Mapping

### SEC EDGAR (Source ID: 1)
```json
{
  "title": "VISA INC.",
  "affected_individuals": 1500000,
  "breach_date": "2025-04-29",
  "reported_date": "2025-04-29",
  "notice_document_url": "https://www.sec.gov/Archives/edgar/data/1403161/...",
  "raw_data_json": {
    "organization_name": "VISA INC.",
    "cik": "0001403161",
    "ticker_symbol": "V",
    "accession_number": "0001403161-25-000035",
    "items_disclosed": "2.02,8.01,9.01",
    "keywords_detected": ["cybersecurity", "data breach"],
    "source_portal": "SEC EDGAR"
  }
}
```

### Delaware AG (Source ID: 3)
```json
{
  "title": "Bayhealth Medical Center",
  "affected_individuals": 1023,
  "breach_date": "2021-05-04",
  "reported_date": "2021-05-28",
  "notice_document_url": "https://attorneygeneral.delaware.gov/.../notice.pdf",
  "raw_data_json": {
    "organization_name": "Bayhealth Medical Center",
    "date_of_breach": "5/4/2021",
    "reported_date": "5/28/2021",
    "delaware_residents_affected": "1,023",
    "source_portal": "Delaware AG"
  }
}
```

### California AG (Source ID: 4)
```json
{
  "title": "Healthcare Provider Inc.",
  "affected_individuals": 2500,
  "breach_date": "2024-03-15",
  "reported_date": "2024-04-01",
  "notice_document_url": "https://oag.ca.gov/.../notice.pdf",
  "raw_data_json": {
    "organization_name": "Healthcare Provider Inc.",
    "dates_of_breach": "March 15, 2024",
    "date_submitted_original": "April 1, 2024",
    "californians_affected_on_page": "2,500",
    "source_portal": "California AG"
  }
}
```

### HHS OCR (Source ID: 2)
```json
{
  "title": "Regional Medical Center",
  "affected_individuals": 50000,
  "breach_date": "2024-02-10",
  "reported_date": "2024-02-10",
  "notice_document_url": "https://ocrportal.hhs.gov/ocr/breach/...",
  "raw_data_json": {
    "name_of_covered_entity": "Regional Medical Center",
    "individuals_affected": 50000,
    "breach_submission_date": "02/10/2024",
    "type_of_breach": "Hacking/IT Incident",
    "covered_entity_type": "Healthcare Provider",
    "source_portal": "HHS OCR"
  }
}
```

## Data Quality Standards

### Required Fields
- `source_id`: Must be valid portal identifier
- `item_url`: Must be unique across all records
- `title`: Must contain organization name
- `publication_date`: Must be valid ISO 8601 timestamp

### Optional but Preferred Fields
- `affected_individuals`: Extract when available
- `breach_date`: Parse from available date fields
- `reported_date`: Extract authority notification date
- `notice_document_url`: Link to official documents

### Raw Data Preservation
- Always preserve original field values in `raw_data_json`
- Include `source_portal` identifier
- Store unparseable dates as original text
- Maintain portal-specific metadata

## Cross-Portal Analysis Benefits

### Standardized Queries
```sql
-- Find large breaches across all portals
SELECT title, affected_individuals, breach_date, source_id 
FROM scraped_items 
WHERE affected_individuals > 100000 
ORDER BY affected_individuals DESC;

-- Timeline analysis across portals
SELECT DATE_TRUNC('month', breach_date) as month, 
       COUNT(*) as breach_count,
       SUM(affected_individuals) as total_affected
FROM scraped_items 
WHERE breach_date IS NOT NULL 
GROUP BY month 
ORDER BY month;
```

### Consistent Filtering
- Filter by affected individual count ranges
- Timeline analysis using standardized dates
- Cross-portal entity name matching
- Document type analysis via notice URLs

## Implementation Guidelines

### For New Portal Scrapers
1. Map portal fields to standardized schema
2. Extract affected individuals using common patterns
3. Parse dates to standard format with fallbacks
4. Preserve all original data in `raw_data_json`
5. Use consistent tagging conventions

### For Existing Portal Updates
1. Maintain backward compatibility
2. Add standardized field mapping
3. Preserve existing `raw_data_json` structure
4. Update documentation with field mappings

---

**Last Updated**: 2025-05-26
**Version**: 1.0
**Applies To**: All breach portal scrapers
