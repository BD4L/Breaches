import os
import logging
import requests
import csv
import io
import hashlib
import re
from datetime import datetime, date
from urllib.parse import urljoin
from bs4 import BeautifulSoup
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

def extract_detail_page_info(detail_url: str) -> dict:
    """
    Extract information from individual breach detail pages (Tier 2).
    """
    try:
        logger.info(f"Fetching detail page: {detail_url}")
        response = requests.get(detail_url, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()

        # Parse the detail page
        soup = BeautifulSoup(response.content, 'html.parser')

        detail_info = {
            'detail_page_url': detail_url,
            'pdf_links': [],
            'organization_name_detail': None,
            'breach_dates_detail': None,
            'additional_info': None
        }

        # Extract organization name from detail page
        org_name_elem = soup.find('strong', string='Organization Name:')
        if org_name_elem and org_name_elem.next_sibling:
            detail_info['organization_name_detail'] = org_name_elem.next_sibling.strip()

        # Extract breach dates from detail page
        breach_date_elem = soup.find('strong', string='Date(s) of Breach (if known):')
        if breach_date_elem and breach_date_elem.next_sibling:
            detail_info['breach_dates_detail'] = breach_date_elem.next_sibling.strip()

        # Find PDF links (Sample Notification)
        pdf_links = soup.find_all('a', href=True)
        for link in pdf_links:
            href = link.get('href', '')
            if href.endswith('.pdf') or 'pdf' in href.lower():
                full_pdf_url = urljoin(detail_url, href)
                detail_info['pdf_links'].append({
                    'url': full_pdf_url,
                    'text': link.get_text(strip=True),
                    'title': link.get('title', '')
                })

        return detail_info

    except Exception as e:
        logger.error(f"Failed to extract detail page info from {detail_url}: {e}")
        return {
            'detail_page_url': detail_url,
            'error': str(e),
            'pdf_links': [],
            'organization_name_detail': None,
            'breach_dates_detail': None,
            'additional_info': None
        }

def analyze_pdf_content(pdf_url: str) -> dict:
    """
    Analyze PDF content to extract breach details (Tier 3).
    """
    try:
        logger.info(f"Analyzing PDF: {pdf_url}")

        # For now, we'll use a simple requests approach to get PDF content
        # In production, this would use Firecrawl or another PDF extraction service
        response = requests.get(pdf_url, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()

        # For this initial implementation, we'll create a placeholder analysis
        # In production, this would use proper PDF parsing (PyPDF2, pdfplumber, or Firecrawl)
        analysis = {
            'pdf_url': pdf_url,
            'content_length': len(response.content),
            'affected_individuals': None,
            'data_types_compromised': [],
            'discovery_date': None,
            'notification_date': None,
            'incident_description': None,
            'contact_info': None,
            'analysis_status': 'placeholder_implementation',
            'note': 'PDF analysis requires proper PDF parsing library integration'
        }

        # Extract basic info from PDF filename if possible
        filename = pdf_url.split('/')[-1].lower()
        if 'security' in filename or 'breach' in filename or 'notification' in filename:
            analysis['incident_description'] = f"Security notification document: {filename}"

        return analysis

    except Exception as e:
        logger.error(f"Failed to analyze PDF {pdf_url}: {e}")
        return {
            'pdf_url': pdf_url,
            'error': str(e),
            'content_length': 0,
            'affected_individuals': None,
            'data_types_compromised': [],
            'discovery_date': None,
            'notification_date': None,
            'incident_description': None,
            'contact_info': None
        }

def fetch_html_table_urls() -> dict:
    """
    Fetch the HTML table from the main page to get organization name to detail URL mapping.
    """
    try:
        logger.info("Fetching HTML table to map organization names to detail URLs...")
        response = requests.get(CALIFORNIA_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the table with breach data
        table = soup.find('table')
        if not table:
            logger.warning("No table found on the main page")
            return {}

        org_url_mapping = {}

        # Process table rows (skip header row)
        rows = table.find_all('tr')[1:]  # Skip header

        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 3:  # Organization Name, Breach Dates, Reported Date
                # First cell contains the organization name and link
                org_cell = cells[0]
                org_link = org_cell.find('a', href=True)

                if org_link:
                    org_name = org_link.get_text(strip=True)
                    detail_url = urljoin(CALIFORNIA_AG_BREACH_URL, org_link.get('href'))
                    org_url_mapping[org_name] = detail_url

        logger.info(f"Mapped {len(org_url_mapping)} organizations to detail URLs")
        return org_url_mapping

    except Exception as e:
        logger.error(f"Failed to fetch HTML table URLs: {e}")
        return {}

def enhance_breach_data(breach_record: dict, org_url_mapping: dict) -> dict:
    """
    Enhance breach data by fetching detailed information (Tier 2 - Derived/Enriched).
    """
    try:
        org_name = breach_record['organization_name']

        enhanced_data = breach_record.copy()
        enhanced_data['enhancement_attempted'] = True
        enhanced_data['enhancement_timestamp'] = datetime.now().isoformat()

        # Check if we have a detail URL for this organization
        detail_url = org_url_mapping.get(org_name)

        if detail_url:
            logger.info(f"Enhancing data for {org_name} with detail URL: {detail_url}")

            # Tier 2: Extract detail page information
            detail_info = extract_detail_page_info(detail_url)
            enhanced_data['detail_page_info'] = detail_info

            # Tier 3: Analyze PDFs if available
            pdf_analyses = []
            for pdf_link in detail_info.get('pdf_links', []):
                pdf_url = pdf_link['url']
                logger.info(f"Analyzing PDF for {org_name}: {pdf_url}")
                pdf_analysis = analyze_pdf_content(pdf_url)
                pdf_analyses.append(pdf_analysis)

            enhanced_data['pdf_analyses'] = pdf_analyses

            # Extract the best affected individuals count from PDF analysis
            affected_individuals = None
            for analysis in pdf_analyses:
                if analysis.get('affected_individuals'):
                    affected_individuals = analysis['affected_individuals']
                    break

            enhanced_data['affected_individuals_from_pdf'] = affected_individuals

        else:
            logger.warning(f"No detail URL found for organization: {org_name}")
            enhanced_data['detail_page_info'] = {
                'status': 'no_url_mapping',
                'note': f'No detail URL found for {org_name}'
            }

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

        # Fetch HTML table to map organization names to detail URLs
        org_url_mapping = fetch_html_table_urls()

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
                enhanced_record = enhance_breach_data(breach_record, org_url_mapping)

                # Extract enhanced information
                detail_page_info = enhanced_record.get('detail_page_info', {})
                pdf_analyses = enhanced_record.get('pdf_analyses', [])
                affected_individuals_from_pdf = enhanced_record.get('affected_individuals_from_pdf')

                # Get the detail page URL if available
                detail_url = detail_page_info.get('detail_page_url', CALIFORNIA_AG_BREACH_URL)

                # Get PDF URLs for notice_document_url
                pdf_urls = []
                for pdf_link in detail_page_info.get('pdf_links', []):
                    pdf_urls.append(pdf_link['url'])
                notice_document_url = pdf_urls[0] if pdf_urls else None

                # Create enhanced summary with PDF analysis
                summary_parts = [f"Data breach reported by {enhanced_record['organization_name']}"]

                if affected_individuals_from_pdf:
                    summary_parts.append(f"Affected individuals: {affected_individuals_from_pdf:,}")

                if pdf_analyses:
                    for analysis in pdf_analyses:
                        data_types = analysis.get('data_types_compromised', [])
                        if data_types:
                            summary_parts.append(f"Data types: {', '.join(data_types[:3])}")  # Limit to first 3
                            break

                summary_text = ". ".join(summary_parts)

                # Create enhanced full content
                full_content_parts = [
                    f"Organization: {enhanced_record['organization_name']}",
                    f"Breach Date(s): {', '.join(enhanced_record['breach_dates']) if enhanced_record['breach_dates'] else 'Not specified'}",
                    f"Reported Date: {enhanced_record['reported_date'] or 'Not specified'}"
                ]

                if affected_individuals_from_pdf:
                    full_content_parts.append(f"Affected Individuals: {affected_individuals_from_pdf:,}")

                if pdf_analyses:
                    for analysis in pdf_analyses:
                        if analysis.get('incident_description'):
                            full_content_parts.append(f"Incident Description: {analysis['incident_description']}")
                            break

                full_content = "\n".join(full_content_parts)

                # Convert to database format
                db_item = {
                    'source_id': SOURCE_ID_CALIFORNIA_AG,
                    'item_url': detail_url,
                    'title': enhanced_record['organization_name'],
                    'publication_date': enhanced_record['reported_date'],
                    'summary_text': summary_text,
                    'full_content': full_content,
                    'reported_date': enhanced_record['reported_date'],
                    'breach_date': enhanced_record['breach_dates'][0] if enhanced_record['breach_dates'] else None,
                    'affected_individuals': affected_individuals_from_pdf,
                    'notice_document_url': notice_document_url,
                    'raw_data_json': {
                        'scraper_version': '3.0_full_enhanced',
                        'tier_1_csv_data': enhanced_record['raw_csv_data'],
                        'tier_2_detail_page': detail_page_info,
                        'tier_3_pdf_analyses': pdf_analyses,
                        'enhancement_metadata': {
                            'incident_uid': enhanced_record['incident_uid'],
                            'breach_dates_all': enhanced_record['breach_dates'],
                            'enhancement_attempted': enhanced_record.get('enhancement_attempted', False),
                            'enhancement_timestamp': enhanced_record.get('enhancement_timestamp'),
                            'affected_individuals_from_pdf': affected_individuals_from_pdf,
                            'pdf_count': len(pdf_analyses)
                        }
                    }
                }

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
