import os
import logging
import requests
import re
import time
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

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
SEC_BASE_URL = "https://www.sec.gov"
SEC_RSS_URL = f"{SEC_BASE_URL}/cgi-bin/browse-edgar"

# Enhanced cybersecurity keywords for comprehensive detection
CYBERSECURITY_KEYWORDS = [
    # Primary indicators (high weight)
    "item 1.05",
    "material cybersecurity",
    "cybersecurity incident",
    "data breach",
    "security incident",
    "security breach",

    # Attack types
    "unauthorized access",
    "cyber attack",
    "data compromise",
    "ransomware",
    "malware",
    "phishing",
    "social engineering",
    "insider threat",

    # Data types (common in breach descriptions)
    "customer data",
    "personal information",
    "personally identifiable",
    "social security",
    "credit card",
    "financial information",
    "account information",
    "government id",
    "driver's license",
    "passport",

    # Impact indicators
    "threat actor",
    "extortion",
    "demanded money",
    "law enforcement",
    "forensic investigation",
    "customer reimbursement",
    "remediation costs",

    # Technical indicators
    "internal systems",
    "compromised information",
    "accessed without authorization",
    "improper data access",
    "security monitoring",
    "information security",
    "data security incident"
]

# Source ID for SEC EDGAR 8-K
SOURCE_ID_SEC_EDGAR_8K = 1

# SEC-compliant headers (REQUIRED by SEC)
REQUEST_HEADERS = {
    'User-Agent': 'Breach Monitor Bot admin@breachmonitor.com',  # SEC requires proper identification
    'Accept-Encoding': 'gzip, deflate'
}

# Separate headers for different SEC endpoints
SEC_DATA_HEADERS = {
    'User-Agent': 'Breach Monitor Bot admin@breachmonitor.com',
    'Accept-Encoding': 'gzip, deflate',
    'Host': 'data.sec.gov'
}

SEC_WWW_HEADERS = {
    'User-Agent': 'Breach Monitor Bot admin@breachmonitor.com',
    'Accept-Encoding': 'gzip, deflate',
    'Host': 'www.sec.gov'
}

# Rate limiting: SEC allows max 10 requests per second
RATE_LIMIT_DELAY = 0.1  # 100ms between requests

def rate_limit_request():
    """Implement SEC rate limiting - max 10 requests per second"""
    time.sleep(RATE_LIMIT_DELAY)

def get_recent_8k_filings(days_back=1):
    """
    Get recent 8-K filings from SEC EDGAR using RSS feeds.
    This approach gets ALL recent 8-K filings, not just from specific companies.

    Args:
        days_back (int): Number of days back to search.

    Returns:
        list: List of 8-K filing metadata.
    """
    filings = []

    try:
        # Use SEC RSS feed for recent filings - gets ALL companies
        params = {
            "action": "getcurrent",
            "type": "8-K",
            "count": "200",  # Get more filings to catch cybersecurity incidents
            "output": "atom"
        }

        logger.info("Fetching recent 8-K filings from SEC RSS feed...")

        rate_limit_request()
        response = requests.get(SEC_RSS_URL, params=params, headers=SEC_WWW_HEADERS, timeout=30)
        response.raise_for_status()

        # Parse RSS/Atom feed
        try:
            root = ET.fromstring(response.text)

            # Find entries in the feed
            entries = root.findall('.//{http://www.w3.org/2005/Atom}entry')

            logger.info(f"Found {len(entries)} recent 8-K filings")

            for entry in entries:
                try:
                    # Extract filing information
                    title = entry.find('.//{http://www.w3.org/2005/Atom}title')
                    link = entry.find('.//{http://www.w3.org/2005/Atom}link')
                    updated = entry.find('.//{http://www.w3.org/2005/Atom}updated')
                    summary = entry.find('.//{http://www.w3.org/2005/Atom}summary')

                    if title is not None and link is not None:
                        filing_info = {
                            "title": title.text if title.text else "",
                            "document_url": link.get('href', ''),
                            "filing_date": updated.text if updated is not None else "",
                            "summary": summary.text if summary is not None else "",
                            "form_type": "8-K"
                        }

                        # Extract company name from title
                        title_text = filing_info["title"]
                        if " - " in title_text:
                            company_part = title_text.split(" - ")[0]
                            filing_info["company_name"] = company_part.strip()

                        # Check if filing is recent
                        if is_recent_filing(filing_info.get("filing_date", ""), days_back):
                            filings.append(filing_info)

                except Exception as entry_error:
                    logger.warning(f"Error processing RSS entry: {entry_error}")
                    continue

        except ET.ParseError as parse_error:
            logger.error(f"Failed to parse RSS feed: {parse_error}")
            # Fallback to HTML parsing
            filings = get_8k_filings_html_fallback(response.text, days_back)

    except Exception as e:
        logger.error(f"Error fetching 8-K filings: {e}")

    return filings

def get_8k_filings_html_fallback(html_content, days_back):
    """Fallback method to parse 8-K filings from HTML."""
    filings = []

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Look for filing entries in the HTML
        filing_rows = soup.find_all('tr')

        for row in filing_rows[:50]:  # Limit to recent filings
            cells = row.find_all('td')
            if len(cells) >= 4:
                # Extract filing information from table cells
                filing_info = {
                    "company_name": cells[0].get_text(strip=True) if cells[0] else "",
                    "form_type": cells[1].get_text(strip=True) if cells[1] else "",
                    "filing_date": cells[2].get_text(strip=True) if cells[2] else "",
                    "document_url": ""
                }

                # Look for document link
                link = row.find('a')
                if link and link.get('href'):
                    filing_info["document_url"] = f"{SEC_BASE_URL}{link['href']}"

                if filing_info["form_type"] == "8-K" and is_recent_filing(filing_info["filing_date"], days_back):
                    filings.append(filing_info)

    except Exception as e:
        logger.error(f"Error in HTML fallback: {e}")

    return filings

def is_recent_filing(date_str, days_back):
    """Check if a filing date is recent."""
    if not date_str:
        return True  # If no date, assume recent

    try:
        # Parse various date formats from SEC
        if 'T' in date_str:
            filing_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
        else:
            filing_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        cutoff_date = (datetime.now() - timedelta(days=days_back)).date()
        return filing_date >= cutoff_date

    except:
        return True  # If parsing fails, assume recent

def extract_filing_content(document_url):
    """
    Extract full text content from an 8-K filing.

    Args:
        document_url (str): URL to the SEC filing document.

    Returns:
        dict: Extracted content and metadata.
    """
    content_data = {}

    try:
        logger.info(f"Extracting content from: {document_url}")

        rate_limit_request()
        response = requests.get(document_url, headers=SEC_WWW_HEADERS, timeout=30)

        if not response.ok:
            logger.warning(f"Failed to fetch document: {response.status_code}")
            return content_data

        # Parse the SEC filing format
        text_content = response.text

        # Extract different sections
        content_data["full_text"] = text_content
        content_data["text_length"] = len(text_content)

        # Look for specific cybersecurity sections
        cyber_sections = extract_cybersecurity_sections(text_content)
        content_data.update(cyber_sections)

        # Extract business description and other metadata
        metadata = extract_filing_metadata(text_content)
        content_data.update(metadata)

        logger.info(f"Extracted {len(content_data)} content fields")

    except Exception as e:
        logger.error(f"Error extracting filing content: {e}")

    return content_data

def search_text_for_keywords(text: str, keywords: list) -> list:
    """Searches text for keywords (case-insensitive) and returns found keywords."""
    if not text:
        return []
    found_keywords = []
    text_lower = text.lower()
    for keyword in keywords:
        if keyword.lower() in text_lower:
            found_keywords.append(keyword)
    return found_keywords

def fetch_filing_document_content(cik: str, accession_number: str, primary_document: str) -> tuple[str | None, str | None]:
    """
    Fetch the actual 8-K document content using SEC EDGAR URLs.
    Returns (document_url, document_text).
    """
    try:
        # Construct the document URL using SEC's standard path structure
        # Format: https://www.sec.gov/Archives/edgar/data/{cik}/{accession_number_no_dashes}/{primary_document}
        accession_no_dashes = accession_number.replace('-', '')
        document_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_no_dashes}/{primary_document}"

        rate_limit_request()
        response = requests.get(document_url, headers=SEC_WWW_HEADERS, timeout=30)
        response.raise_for_status()

        # Parse HTML content to extract text
        if primary_document.endswith(('.htm', '.html')):
            soup = BeautifulSoup(response.content, 'html.parser')
            document_text = soup.get_text(separator='\n', strip=True)
        else:
            document_text = response.text

        return document_url, document_text

    except Exception as e:
        logger.error(f"Error fetching document content for CIK {cik}, accession {accession_number}: {e}")
        return None, None

def is_cybersecurity_related(filing_info: dict, document_text: str = None) -> tuple[bool, list, str]:
    """
    Determine if a filing is cybersecurity-related based on items and content.
    Returns (is_related, found_keywords, reason).
    """
    found_keywords = []
    reasons = []

    # Check 8-K items first (faster than text search)
    items = filing_info.get('items', '')
    if items:
        for cyber_item in CYBERSECURITY_8K_ITEMS:
            if cyber_item in items:
                reasons.append(f"8-K Item {cyber_item}")
                found_keywords.append(f"item_{cyber_item}")

    # Search document text for cybersecurity keywords
    if document_text:
        text_keywords = search_text_for_keywords(document_text, CYBERSECURITY_KEYWORDS)
        if text_keywords:
            found_keywords.extend(text_keywords)
            reasons.append(f"Keywords: {', '.join(text_keywords[:3])}")  # Show first 3

    is_related = len(found_keywords) > 0
    reason = "; ".join(reasons) if reasons else "No cybersecurity indicators found"

    return is_related, found_keywords, reason

def process_edgar_filings():
    """
    Process recent SEC EDGAR 8-K filings using RSS feed approach.
    Gets ALL recent 8-K filings and analyzes them for cybersecurity content.
    """
    logger.info("Starting SEC EDGAR 8-K processing using RSS feed...")

    # Initialize Supabase client
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return

    # Get recent 8-K filings from ALL companies using RSS feed
    logger.info("Fetching recent 8-K filings from SEC RSS feed...")
    recent_filings = get_recent_8k_filings(days_back=2)  # Get last 2 days of filings

    if not recent_filings:
        logger.warning("No recent 8-K filings found")
        return

    logger.info(f"Found {len(recent_filings)} recent 8-K filings to analyze")

    total_processed = 0
    total_inserted = 0
    cybersecurity_found = 0

    for filing in recent_filings:
        try:
            company_name = filing.get("company_name", "Unknown Company")
            logger.info(f"Processing {company_name}")

            total_processed += 1

            # Extract full content from the filing
            content_data = extract_filing_content(filing.get("document_url", ""))

            if not content_data.get("full_text"):
                logger.warning(f"Could not fetch document content for {company_name}")
                continue

            # Analyze for cybersecurity content
            cyber_data = content_data
            is_cybersecurity = cyber_data.get("is_cybersecurity_related", False)
            found_keywords = cyber_data.get("cybersecurity_keywords_found", [])

            if is_cybersecurity:
                cybersecurity_found += 1
                logger.info(f"🔒 Cybersecurity filing found: {company_name}")

                # Create summary snippet from cybersecurity context
                summary_snippet = f"Cybersecurity-related 8-K filing from {company_name}."

                # Get context from keyword analysis
                keyword_contexts = cyber_data.get("keyword_contexts", [])
                if keyword_contexts:
                    # Use the first context as summary
                    first_context = keyword_contexts[0]["context"]
                    summary_snippet = f"...{first_context[:300]}..."

                # Prepare data for insertion
                item_data = {
                    "source_id": SOURCE_ID_SEC_EDGAR_8K,
                    "item_url": filing.get("document_url", ""),
                    "title": f"SEC 8-K: {company_name} - Cybersecurity Filing",
                    "publication_date": filing.get("filing_date", datetime.now().isoformat()),
                    "summary_text": summary_snippet,
                    "raw_data_json": {
                        "company_name": company_name,
                        "filing_date": filing.get("filing_date", ""),
                        "form_type": filing.get("form_type", "8-K"),
                        "keywords_found": found_keywords,
                        "cybersecurity_keyword_count": cyber_data.get("cybersecurity_keyword_count", 0),
                        "keyword_contexts": keyword_contexts[:5],  # First 5 contexts
                        "item_105_content": cyber_data.get("item_105_content", ""),
                        "dates_mentioned": cyber_data.get("dates_mentioned", [])
                    },
                    "tags_keywords": ["sec_filing", "8-k", "cybersecurity"] + [kw.lower().replace(" ", "_") for kw in found_keywords[:5]]
                }

                # Insert into database
                try:
                    insert_response = supabase_client.insert_item(**item_data)
                    if insert_response:
                        logger.info(f"✅ Successfully inserted cybersecurity filing for {company_name}")
                        total_inserted += 1
                    else:
                        logger.error(f"❌ Failed to insert filing for {company_name}")
                except Exception as e:
                    if "duplicate key value violates unique constraint" in str(e):
                        logger.info(f"📋 Filing already exists for {company_name}")
                    else:
                        logger.error(f"❌ Error inserting filing: {e}")
            else:
                logger.debug(f"No cybersecurity content found in {company_name} filing")

        except Exception as e:
            logger.error(f"Error processing filing for {company_name}: {e}", exc_info=True)

    logger.info(f"🎯 SEC EDGAR processing complete:")
    logger.info(f"   📊 Total filings processed: {total_processed}")
    logger.info(f"   🔒 Cybersecurity filings found: {cybersecurity_found}")
    logger.info(f"   💾 Successfully inserted: {total_inserted}")

if __name__ == "__main__":
    logger.info("SEC EDGAR 8-K Scraper Started")

    # Check for Supabase environment variables
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
        # Optionally, exit if critical env vars are missing
        # sys.exit(1)
    else:
        logger.info("Supabase environment variables seem to be set.")

    process_edgar_filings()
    logger.info("SEC EDGAR 8-K Scraper Finished")
