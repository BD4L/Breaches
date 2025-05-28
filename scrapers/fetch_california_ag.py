import os
import logging
import requests
import csv
import io
import hashlib
from bs4 import BeautifulSoup
from datetime import datetime, date
from urllib.parse import urljoin
from dateutil import parser as dateutil_parser # For flexible date parsing

# Assuming SupabaseClient is in utils.supabase_client
try:
    from utils.supabase_client import SupabaseClient
except ImportError:
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from utils.supabase_client import SupabaseClient

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
CALIFORNIA_AG_BREACH_URL = "https://oag.ca.gov/privacy/databreach/list"
CALIFORNIA_AG_CSV_URL = "https://oag.ca.gov/privacy/databreach/list-export"
SOURCE_ID_CALIFORNIA_AG = 4 # California AG source ID

# Configuration for date filtering
# Set to None to collect all historical data (for testing)
# Set to a date string like "2025-05-27" for production filtering
FILTER_FROM_DATE = os.environ.get("CA_AG_FILTER_FROM_DATE", None)  # None = collect all data

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://oag.ca.gov/' # Referer can sometimes help
}

def generate_incident_uid(organization_name: str, reported_date: str) -> str:
    """
    Generate a unique incident identifier for deduplication.
    """
    # Create a unique string combining organization and reported date
    unique_string = f"ca_ag_{organization_name}_{reported_date}".lower().replace(" ", "_")
    # Generate a hash for consistent UIDs
    return hashlib.md5(unique_string.encode()).hexdigest()[:16]

def parse_date_flexible(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Returns ISO format date string or None if parsing fails.
    """
    if not date_str or date_str.strip() == "" or date_str.strip().lower() == "n/a":
        return None

    try:
        # Clean up the date string
        date_str = date_str.strip()

        # Handle multiple dates (take the first one)
        if ',' in date_str:
            date_str = date_str.split(',')[0].strip()

        # Handle common formats
        parsed_date = dateutil_parser.parse(date_str)
        return parsed_date.strftime('%Y-%m-%d')
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to parse date '{date_str}': {e}")
        return None

def parse_breach_dates(date_str: str) -> list:
    """
    Parse multiple breach dates from a comma-separated string.
    """
    if not date_str or date_str.strip() == "" or date_str.strip().lower() == "n/a":
        return []

    dates = []
    for date_part in date_str.split(','):
        parsed_date = parse_date_flexible(date_part.strip())
        if parsed_date:
            dates.append(parsed_date)

    return dates

def fetch_csv_data() -> list:
    """
    Fetch breach data from the CSV endpoint (Tier 1 - Portal Raw Data).
    """
    logger.info("Fetching California AG breach data from CSV endpoint...")

    try:
        response = requests.get(CALIFORNIA_AG_CSV_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()

        # Parse CSV data
        csv_data = []
        csv_reader = csv.DictReader(io.StringIO(response.text))

        for row in csv_reader:
            # Generate incident UID for deduplication
            incident_uid = generate_incident_uid(
                row.get('Organization Name', ''),
                row.get('Reported Date', '')
            )

            # Parse dates
            breach_dates = parse_breach_dates(row.get('Date(s) of Breach (if known)', ''))
            reported_date = parse_date_flexible(row.get('Reported Date', ''))

            # Create standardized breach record
            breach_record = {
                'organization_name': row.get('Organization Name', '').strip(),
                'breach_dates': breach_dates,
                'reported_date': reported_date,
                'incident_uid': incident_uid,
                'detail_url': f"https://oag.ca.gov/ecrime/databreach/reports/{incident_uid}" if incident_uid else None,
                'raw_csv_data': dict(row)
            }

            csv_data.append(breach_record)

        logger.info(f"Successfully parsed {len(csv_data)} breach records from CSV")
        return csv_data

    except Exception as e:
        logger.error(f"Failed to fetch CSV data: {e}")
        return []

def scrape_detail_page(detail_url: str) -> dict:
    """
    Scrape the detail page for additional breach information (Tier 2).
    """
    try:
        logger.info(f"Scraping detail page: {detail_url}")

        response = requests.get(detail_url, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        detail_data = {
            'detail_page_scraped': True,
            'detail_page_url': detail_url,
            'pdf_links': [],
            'organization_name_detail': None,
            'breach_date_detail': None
        }

        # Extract organization name from detail page
        org_name_elem = soup.find('strong', string='Organization Name:')
        if org_name_elem and org_name_elem.next_sibling:
            detail_data['organization_name_detail'] = org_name_elem.next_sibling.strip()

        # Extract breach date from detail page
        breach_date_elem = soup.find('strong', string='Date(s) of Breach (if known):')
        if breach_date_elem and breach_date_elem.next_sibling:
            detail_data['breach_date_detail'] = breach_date_elem.next_sibling.strip()

        # Find PDF links - only look for breach notification PDFs, not general site PDFs
        pdf_links = []

        # Look for PDFs in the main content area, specifically under "Sample of Notice:"
        # First, try to find the main content section
        main_content = soup.find('div', {'id': 'main-content'}) or soup

        # Look for PDF links that are likely breach notifications
        for link in main_content.find_all('a', href=True):
            href = link.get('href', '')
            if href.endswith('.pdf'):
                # Filter out generic site PDFs (annual reports, etc.)
                href_lower = href.lower()

                # Skip generic annual reports and site-wide PDFs
                skip_patterns = [
                    'data-breach-report',  # Annual reports
                    'data_breach_rpt',     # Annual reports
                    'annual',
                    'report.pdf',
                    '/agweb/pdfs/',        # General site PDFs
                    '/sites/all/files/agweb/'  # Old site structure
                ]

                # Check if this is a generic PDF to skip
                should_skip = any(pattern in href_lower for pattern in skip_patterns)

                if not should_skip:
                    # This looks like a breach notification PDF
                    full_pdf_url = urljoin(detail_url, href)
                    pdf_title = link.get_text(strip=True) or 'Sample Notification'
                    pdf_links.append({
                        'url': full_pdf_url,
                        'title': pdf_title
                    })

        detail_data['pdf_links'] = pdf_links

        logger.info(f"Found {len(detail_data['pdf_links'])} PDF links on detail page")
        return detail_data

    except Exception as e:
        logger.error(f"Failed to scrape detail page {detail_url}: {e}")
        return {
            'detail_page_scraped': False,
            'detail_page_url': detail_url,
            'error': str(e)
        }

def analyze_pdf_content(pdf_url: str) -> dict:
    """
    Analyze PDF content for breach details (Tier 3).
    """
    try:
        logger.info(f"Analyzing PDF: {pdf_url}")

        # Use Firecrawl to extract PDF content
        import requests as req_lib

        # For now, we'll use a simple approach to extract basic info
        # In a full implementation, we'd use proper PDF parsing

        pdf_analysis = {
            'pdf_analyzed': True,
            'pdf_url': pdf_url,
            'affected_individuals': None,
            'data_types_compromised': [],
            'incident_details': None,
            'contact_information': None
        }

        # Try to extract content using requests (basic approach)
        try:
            response = req_lib.get(pdf_url, headers=REQUEST_HEADERS, timeout=30)
            if response.status_code == 200:
                # Basic text extraction (this would be enhanced with proper PDF parsing)
                content = response.text.lower()

                # Look for affected individuals count
                import re

                # Common patterns for affected individuals
                patterns = [
                    r'(\d+(?:,\d+)*)\s+(?:individuals?|people|persons?|employees?|customers?|patients?)',
                    r'(?:approximately|about|over|more than|up to)\s+(\d+(?:,\d+)*)\s+(?:individuals?|people|persons?)',
                    r'(\d+(?:,\d+)*)\s+(?:affected|impacted|involved)'
                ]

                for pattern in patterns:
                    match = re.search(pattern, content)
                    if match:
                        try:
                            count = int(match.group(1).replace(',', ''))
                            pdf_analysis['affected_individuals'] = count
                            break
                        except ValueError:
                            continue

                # Look for data types
                data_types = []
                if 'social security' in content or 'ssn' in content:
                    data_types.append('Social Security Numbers')
                if 'driver' in content and 'license' in content:
                    data_types.append('Driver License Numbers')
                if 'credit card' in content or 'payment card' in content:
                    data_types.append('Payment Card Information')
                if 'medical' in content or 'health' in content:
                    data_types.append('Medical Information')
                if 'email' in content:
                    data_types.append('Email Addresses')
                if 'phone' in content:
                    data_types.append('Phone Numbers')
                if 'address' in content:
                    data_types.append('Addresses')

                pdf_analysis['data_types_compromised'] = data_types

        except Exception as e:
            logger.warning(f"Could not extract PDF content from {pdf_url}: {e}")

        return pdf_analysis

    except Exception as e:
        logger.error(f"Failed to analyze PDF {pdf_url}: {e}")
        return {
            'pdf_analyzed': False,
            'pdf_url': pdf_url,
            'error': str(e)
        }

def enhance_breach_data(breach_record: dict) -> dict:
    """
    Enhance breach data by fetching detailed information (Tier 2 - Derived/Enriched).
    """
    try:
        enhanced_data = breach_record.copy()
        enhanced_data['enhancement_attempted'] = True
        enhanced_data['enhancement_timestamp'] = datetime.now().isoformat()

        # Construct detail page URL from organization name and CSV data
        # The URLs follow pattern: https://oag.ca.gov/ecrime/databreach/reports/sb24-XXXXXX
        # We need to find the actual URL by scraping the main page or using the CSV incident UID

        # For now, we'll try to construct the URL based on the incident UID pattern
        # This would be enhanced to actually scrape the main page for the real URLs

        # Try to find the detail page URL by scraping the main listing
        detail_url = None
        try:
            # Scrape the main page to find the actual detail URL
            response = requests.get(CALIFORNIA_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find the table and look for the organization name
            org_name = enhanced_data['organization_name']

            # Look for links containing the organization name
            for link in soup.find_all('a', href=True):
                if org_name.lower() in link.get_text().lower():
                    detail_url = urljoin(CALIFORNIA_AG_BREACH_URL, link.get('href'))
                    break

        except Exception as e:
            logger.warning(f"Could not find detail URL for {enhanced_data['organization_name']}: {e}")

        if detail_url:
            # Tier 2: Scrape detail page
            detail_data = scrape_detail_page(detail_url)
            enhanced_data['tier_2_detail'] = detail_data

            # Tier 3: Analyze PDFs if found
            if detail_data.get('pdf_links'):
                enhanced_data['tier_3_pdf_analysis'] = []
                for pdf_link in detail_data['pdf_links']:
                    pdf_analysis = analyze_pdf_content(pdf_link['url'])
                    enhanced_data['tier_3_pdf_analysis'].append(pdf_analysis)

        return enhanced_data

    except Exception as e:
        logger.error(f"Failed to enhance breach data for {breach_record.get('organization_name', 'Unknown')}: {e}")
        return breach_record

def process_california_ag_breaches():
    """
    Enhanced California AG breach scraper using 3-tier approach.
    """
    logger.info("Starting enhanced California AG breach data fetch...")

    try:
        # Initialize Supabase client
        supabase_client = SupabaseClient()

        # Tier 1: Fetch raw CSV data
        csv_breach_data = fetch_csv_data()
        if not csv_breach_data:
            logger.error("No CSV data retrieved, aborting")
            return

        # Filter breaches based on configuration
        if FILTER_FROM_DATE:
            # Production mode: filter from specified date
            try:
                filter_date = datetime.strptime(FILTER_FROM_DATE, '%Y-%m-%d').date()
                logger.info(f"Production mode: filtering breaches from {filter_date} onward")
            except ValueError:
                logger.warning(f"Invalid FILTER_FROM_DATE format '{FILTER_FROM_DATE}', using today's date")
                filter_date = date.today()
        else:
            # Testing mode: collect all historical data
            filter_date = None
            logger.info("Testing mode: collecting ALL historical breach data (no date filtering)")

        filtered_breaches = []

        for breach in csv_breach_data:
            if filter_date is None:
                # No filtering - include all breaches
                filtered_breaches.append(breach)
            elif breach['reported_date']:
                try:
                    # Parse the YYYY-MM-DD format from our parse_date_flexible function
                    reported_date_obj = datetime.strptime(breach['reported_date'], '%Y-%m-%d').date()
                    if reported_date_obj >= filter_date:
                        filtered_breaches.append(breach)
                except ValueError:
                    # If date parsing fails, include the breach to be safe
                    filtered_breaches.append(breach)
            else:
                # If no reported date, include the breach
                filtered_breaches.append(breach)

        if filter_date:
            logger.info(f"Filtered to {len(filtered_breaches)} breaches (from {filter_date} onward)")
        else:
            logger.info(f"Collected {len(filtered_breaches)} total historical breaches (no filtering)")

        # Process each breach record
        processed_count = 0
        for breach_record in filtered_breaches:
            try:
                # Tier 2: Enhance with additional data
                enhanced_record = enhance_breach_data(breach_record)

                # Extract enhanced data for database fields
                affected_individuals = None
                data_types_compromised = []
                notice_document_url = None

                # Extract from PDF analysis if available
                if enhanced_record.get('tier_3_pdf_analysis'):
                    for pdf_analysis in enhanced_record['tier_3_pdf_analysis']:
                        if pdf_analysis.get('affected_individuals'):
                            affected_individuals = pdf_analysis['affected_individuals']
                        if pdf_analysis.get('data_types_compromised'):
                            data_types_compromised.extend(pdf_analysis['data_types_compromised'])

                # Get PDF URL for notice_document_url
                if enhanced_record.get('tier_2_detail', {}).get('pdf_links'):
                    notice_document_url = enhanced_record['tier_2_detail']['pdf_links'][0]['url']

                # Create enhanced summary
                summary_parts = [f"Data breach reported by {enhanced_record['organization_name']}"]
                if data_types_compromised:
                    summary_parts.append(f"Data types involved: {', '.join(data_types_compromised)}")
                if affected_individuals:
                    summary_parts.append(f"Affected individuals: {affected_individuals:,}")

                summary_text = ". ".join(summary_parts)

                # Create enhanced full content
                content_parts = [
                    f"Organization: {enhanced_record['organization_name']}",
                    f"Breach Date(s): {', '.join(enhanced_record['breach_dates']) if enhanced_record['breach_dates'] else 'Not specified'}",
                    f"Reported Date: {enhanced_record['reported_date'] or 'Not specified'}"
                ]

                if data_types_compromised:
                    content_parts.append(f"Data Types Compromised: {', '.join(data_types_compromised)}")
                if affected_individuals:
                    content_parts.append(f"Affected Individuals: {affected_individuals:,}")
                if notice_document_url:
                    content_parts.append(f"Notification Document: {notice_document_url}")

                full_content = "\n".join(content_parts)

                # Convert to database format - be conservative with field mapping
                db_item = {
                    'source_id': SOURCE_ID_CALIFORNIA_AG,
                    'item_url': enhanced_record.get('tier_2_detail', {}).get('detail_page_url', CALIFORNIA_AG_BREACH_URL),
                    'title': enhanced_record['organization_name'],
                    'publication_date': enhanced_record['reported_date'],
                    'summary_text': summary_text,
                    'full_content': full_content,
                    'reported_date': enhanced_record['reported_date'],
                    'breach_date': enhanced_record['breach_dates'][0] if enhanced_record['breach_dates'] else None,
                    'affected_individuals': affected_individuals,
                    'notice_document_url': notice_document_url,
                    'raw_data_json': {
                        'scraper_version': '3.0_enhanced_with_pdfs',
                        'tier_1_csv_data': enhanced_record['raw_csv_data'],
                        'tier_2_enhanced': {
                            'incident_uid': enhanced_record['incident_uid'],
                            'breach_dates_all': enhanced_record['breach_dates'],
                            'enhancement_attempted': enhanced_record.get('enhancement_attempted', False),
                            'enhancement_timestamp': enhanced_record.get('enhancement_timestamp'),
                            'detail_page_data': enhanced_record.get('tier_2_detail', {})
                        },
                        'tier_3_pdf_analysis': enhanced_record.get('tier_3_pdf_analysis', []),
                        # Store data types in raw_data_json for now (until schema is updated)
                        'data_types_compromised': data_types_compromised,
                        'pdf_analysis_summary': {
                            'affected_individuals_extracted': affected_individuals,
                            'data_types_found': data_types_compromised,
                            'pdf_documents_analyzed': len(enhanced_record.get('tier_3_pdf_analysis', []))
                        }
                    }
                }

                # Note: data_types_compromised field is stored in raw_data_json
                # The database schema may not have this field in all instances

                # Insert into database
                supabase_client.insert_item(**db_item)
                processed_count += 1
                logger.info(f"Processed: {enhanced_record['organization_name']}")

            except Exception as e:
                logger.error(f"Failed to process breach record for {breach_record.get('organization_name', 'Unknown')}: {e}")

        logger.info(f"California AG enhanced breach fetch completed. Processed {processed_count} items.")

    except Exception as e:
        logger.error(f"Unexpected error in California AG breach fetch: {e}")

# Legacy function name for compatibility
def fetch_california_ag_breaches():
    """
    Legacy function name - calls the enhanced process function.
    """
    return process_california_ag_breaches()

if __name__ == "__main__":
    logger.info("California AG Security Breach Scraper Started")

    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_california_ag_breaches()

    logger.info("California AG Security Breach Scraper Finished")
