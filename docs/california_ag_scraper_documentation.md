# California AG Enhanced Scraper Documentation

## 📋 Overview

The California Attorney General's Office enhanced scraper implements a **3-tier data collection approach** using the CSV export endpoint for reliable and comprehensive breach data collection. This implementation represents a significant upgrade from the previous HTML-based scraper.

## 🎯 Implementation Status

- **Status**: 🟢 EXCELLENT
- **Implementation Date**: May 27, 2025
- **Data Source**: California AG Data Breach Notification Portal
- **Primary URL**: https://oag.ca.gov/privacy/databreach/list
- **CSV Endpoint**: https://oag.ca.gov/privacy/databreach/list-export

## 🏗️ Architecture

### 3-Tier Data Collection Approach

#### **Tier 1: Portal Raw Data (CSV-based)**
- **Source**: CSV export endpoint (`/privacy/databreach/list-export`)
- **Method**: Direct CSV download and parsing
- **Advantages**: 
  - Reliable data structure
  - Complete dataset access
  - No HTML parsing complexity
  - Resistant to website layout changes

#### **Tier 2: Derived/Enriched Data**
- **Enhancement**: Incident UID generation for deduplication
- **Processing**: Date standardization and validation
- **Filtering**: Recent breaches only (today onward)
- **Structure**: Standardized field mapping

#### **Tier 3: Deep Analysis (Future Enhancement)**
- **Planned**: PDF notification analysis
- **Planned**: Affected individuals extraction
- **Planned**: Data type classification

## 📊 Data Structure

### CSV Source Fields
```csv
"Organization Name","Date(s) of Breach (if known)","Reported Date"
```

### Enhanced Database Fields
- `source_id`: 4 (California AG)
- `item_url`: Detail page URL (constructed)
- `title`: Organization name
- `publication_date`: Reported date (YYYY-MM-DD)
- `summary_text`: Generated summary
- `full_content`: Formatted breach details
- `reported_date`: Standardized reported date
- `breach_date`: First breach date (if available)
- `raw_data_json`: Complete tier data structure

### Raw Data JSON Structure
```json
{
  "scraper_version": "2.0_enhanced",
  "tier_1_csv_data": {
    "Organization Name": "...",
    "Date(s) of Breach (if known)": "...",
    "Reported Date": "..."
  },
  "tier_2_enhanced": {
    "incident_uid": "...",
    "breach_dates_all": ["2025-01-15", "2025-01-16"],
    "enhancement_attempted": true,
    "enhancement_timestamp": "2025-05-27T..."
  }
}
```

## 🔧 Technical Implementation

### Key Functions

#### `fetch_csv_data()`
- Downloads CSV data from the export endpoint
- Parses CSV into structured records
- Generates incident UIDs for deduplication
- Handles date parsing for multiple formats

#### `parse_date_flexible(date_str)`
- Supports MM/DD/YYYY format from CSV
- Handles multiple dates (comma-separated)
- Returns standardized YYYY-MM-DD format
- Graceful handling of "n/a" and empty values

#### `parse_breach_dates(date_str)`
- Extracts multiple breach dates from single field
- Returns list of standardized dates
- Handles various date formats and separators

#### `generate_incident_uid(org_name, reported_date)`
- Creates unique identifier for deduplication
- Format: MD5 hash of "ca_ag_{org}_{date}"
- Ensures consistent UIDs across runs

### Date Filtering
- **Filter Criteria**: Reported date >= today
- **Purpose**: Collect only recent breaches (user preference)
- **Fallback**: Include records with unparseable dates

## 📈 Performance Characteristics

### Advantages
- **Reliability**: CSV endpoint is stable and structured
- **Completeness**: Access to full dataset (1000+ records)
- **Speed**: Single HTTP request for all data
- **Maintenance**: Minimal maintenance required

### Data Quality
- **Coverage**: Comprehensive breach notifications
- **Accuracy**: Direct from official source
- **Timeliness**: Real-time updates from AG office
- **Standardization**: Consistent field mapping

## 🔍 Sample Data

### Recent Breach Examples
```
Organization: ALN Medical Management, LLC
Breach Date(s): 03/18/2024, 03/24/2024
Reported Date: 05/23/2025

Organization: Blue Shield of California
Breach Date(s): 04/01/2021
Reported Date: 04/09/2025
```

### Data Volume
- **Total Records**: 1000+ breach notifications
- **Date Range**: 2015-2025 (historical data available)
- **Recent Activity**: 5-10 new breaches per day

## 🚀 Usage

### Manual Execution
```bash
cd /path/to/Breaches
python3 scrapers/fetch_california_ag.py
```

### GitHub Actions Integration
- **Workflow**: `.github/workflows/main_scraper_workflow.yml`
- **Schedule**: Daily at 3 AM UTC
- **Command**: `python scrapers/fetch_california_ag.py`

## 🔧 Configuration

### Environment Variables
- `SUPABASE_URL`: Database connection URL
- `SUPABASE_SERVICE_KEY`: Database service key

### Constants
```python
CALIFORNIA_AG_BREACH_URL = "https://oag.ca.gov/privacy/databreach/list"
CALIFORNIA_AG_CSV_URL = "https://oag.ca.gov/privacy/databreach/list-export"
SOURCE_ID_CALIFORNIA_AG = 4
```

## 🛠️ Troubleshooting

### Common Issues

#### CSV Endpoint Unavailable
- **Symptom**: HTTP errors when accessing CSV URL
- **Solution**: Verify endpoint availability, check headers
- **Fallback**: Could implement HTML table parsing

#### Date Parsing Failures
- **Symptom**: Dates not parsing correctly
- **Solution**: Check date format in CSV, update parsing logic
- **Current Format**: MM/DD/YYYY

#### Duplicate Records
- **Symptom**: Same breach appearing multiple times
- **Solution**: Verify incident UID generation logic
- **Deduplication**: Based on organization + reported date

## 📊 Monitoring

### Success Metrics
- **Records Processed**: Track daily collection volume
- **Date Coverage**: Ensure recent breaches are captured
- **Error Rate**: Monitor parsing and insertion failures

### Logging
- **Level**: INFO for normal operations, ERROR for failures
- **Format**: Timestamp, level, message
- **Key Events**: CSV fetch, record processing, database insertion

## 🔮 Future Enhancements

### Tier 3 Implementation
1. **PDF Analysis**: Extract detailed breach information
2. **Affected Individuals**: Parse notification documents
3. **Data Classification**: Identify compromised data types
4. **Cost Analysis**: Extract financial impact information

### Additional Features
1. **Historical Analysis**: Trend analysis capabilities
2. **Enhanced Deduplication**: Cross-reference with other sources
3. **Real-time Monitoring**: Webhook notifications for new breaches

## 📚 Related Documentation

- [Implementation Status](../SCRAPER_IMPLEMENTATION_STATUS.md)
- [Database Schema](../database_schema.sql)
- [Delaware AG Implementation](./delaware_ag_scraper_documentation.md)
- [Standardized Field Mapping](./standardized_field_mapping.md)

---

**Last Updated**: May 27, 2025  
**Version**: 2.0 Enhanced  
**Maintainer**: Breach Monitoring System
