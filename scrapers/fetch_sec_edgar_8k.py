import os
import logging
import requests
import json
import time
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from urllib.parse import urljoin

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
SEC_API_BASE_URL = "https://data.sec.gov"
SEC_SUBMISSIONS_URL = f"{SEC_API_BASE_URL}/submissions"
SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

# Keywords to search for in filing documents (enhanced for 2025 cybersecurity rules)
CYBERSECURITY_KEYWORDS = [
    "cybersecurity", "cyber security", "data breach", "security incident",
    "unauthorized access", "ransomware", "information security",
    "material cybersecurity incident", "cyber attack", "cyber incident",
    "data security", "privacy breach", "security vulnerability",
    "malware", "phishing", "social engineering", "insider threat",
    "business email compromise", "supply chain attack"
]

# 8-K Item codes related to cybersecurity (Item 1.05 and 8.01 are common)
CYBERSECURITY_8K_ITEMS = ["1.05", "8.01"]

# Source ID for SEC EDGAR 8-K
SOURCE_ID_SEC_EDGAR_8K = 1

# SEC-compliant headers (REQUIRED by SEC)
REQUEST_HEADERS = {
    'User-Agent': 'Breach Monitor Bot admin@breachmonitor.com',  # SEC requires proper identification
    'Accept-Encoding': 'gzip, deflate',
    'Host': 'data.sec.gov'
}

# Rate limiting: SEC allows max 10 requests per second
RATE_LIMIT_DELAY = 0.1  # 100ms between requests

def rate_limit_request():
    """Implement SEC rate limiting - max 10 requests per second"""
    time.sleep(RATE_LIMIT_DELAY)

def fetch_company_tickers() -> dict:
    """
    Fetch the company tickers mapping from SEC.
    Returns dict mapping CIK to company info.
    """
    try:
        rate_limit_request()
        response = requests.get(SEC_COMPANY_TICKERS_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()

        tickers_data = response.json()
        # Convert to CIK-keyed dict for easier lookup
        cik_to_company = {}
        for ticker_info in tickers_data.values():
            cik = str(ticker_info['cik_str']).zfill(10)  # Pad to 10 digits
            cik_to_company[cik] = {
                'ticker': ticker_info.get('ticker', ''),
                'title': ticker_info.get('title', ''),
                'cik': cik
            }

        logger.info(f"Loaded {len(cik_to_company)} company ticker mappings")
        return cik_to_company

    except Exception as e:
        logger.error(f"Error fetching company tickers: {e}")
        return {}

def fetch_company_submissions(cik: str) -> dict | None:
    """
    Fetch submission history for a specific company using SEC API.
    Returns submissions data or None if error.
    """
    try:
        rate_limit_request()
        submissions_url = f"{SEC_SUBMISSIONS_URL}/CIK{cik}.json"
        response = requests.get(submissions_url, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()

        return response.json()

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching submissions for CIK {cik}: {e}")
        return None

def get_recent_8k_filings(submissions_data: dict, days_back: int = 30) -> list:
    """
    Extract recent 8-K filings from submissions data.
    Returns list of recent 8-K filings.
    """
    recent_filings = []

    if 'filings' not in submissions_data or 'recent' not in submissions_data['filings']:
        return recent_filings

    recent = submissions_data['filings']['recent']

    # Get current date for filtering
    cutoff_date = (datetime.now() - timedelta(days=days_back)).date()

    # Process each filing
    for i in range(len(recent.get('form', []))):
        form_type = recent['form'][i]

        # Only process 8-K filings
        if form_type != '8-K':
            continue

        filing_date_str = recent['filingDate'][i]
        filing_date = datetime.strptime(filing_date_str, '%Y-%m-%d').date()

        # Only include recent filings
        if filing_date < cutoff_date:
            continue

        filing_info = {
            'accessionNumber': recent['accessionNumber'][i],
            'filingDate': filing_date_str,
            'reportDate': recent.get('reportDate', [''])[i],
            'acceptanceDateTime': recent.get('acceptanceDateTime', [''])[i],
            'act': recent.get('act', [''])[i],
            'form': form_type,
            'fileNumber': recent.get('fileNumber', [''])[i],
            'filmNumber': recent.get('filmNumber', [''])[i],
            'items': recent.get('items', [''])[i],
            'size': recent.get('size', [0])[i],
            'isXBRL': recent.get('isXBRL', [0])[i],
            'isInlineXBRL': recent.get('isInlineXBRL', [0])[i],
            'primaryDocument': recent.get('primaryDocument', [''])[i],
            'primaryDocDescription': recent.get('primaryDocDescription', [''])[i]
        }

        recent_filings.append(filing_info)

    return recent_filings

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
        response = requests.get(document_url, headers=REQUEST_HEADERS, timeout=30)
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
    Process recent SEC EDGAR 8-K filings using the official SEC API.
    Focuses on cybersecurity-related filings.
    """
    logger.info("Starting SEC EDGAR 8-K processing using official API...")

    # Initialize Supabase client
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return

    # Fetch company ticker mappings
    logger.info("Fetching company ticker mappings...")
    company_mappings = fetch_company_tickers()
    if not company_mappings:
        logger.error("Failed to fetch company mappings. Cannot proceed.")
        return

    # Process a sample of companies (to avoid rate limits in initial implementation)
    # In production, you might want to process all companies or focus on specific ones
    sample_companies = list(company_mappings.items())[:50]  # Process first 50 companies

    total_processed = 0
    total_inserted = 0
    cybersecurity_found = 0

    for cik, company_info in sample_companies:
        try:
            logger.info(f"Processing {company_info['title']} (CIK: {cik})")

            # Fetch company submissions
            submissions_data = fetch_company_submissions(cik)
            if not submissions_data:
                continue

            # Get recent 8-K filings
            recent_8k_filings = get_recent_8k_filings(submissions_data, days_back=30)

            if not recent_8k_filings:
                logger.info(f"No recent 8-K filings for {company_info['title']}")
                continue

            logger.info(f"Found {len(recent_8k_filings)} recent 8-K filings for {company_info['title']}")

            # Process each 8-K filing
            for filing in recent_8k_filings:
                total_processed += 1

                # Fetch document content for detailed analysis
                document_url, document_text = fetch_filing_document_content(
                    cik, filing['accessionNumber'], filing['primaryDocument']
                )

                if not document_text:
                    logger.warning(f"Could not fetch document content for {filing['accessionNumber']}")
                    continue

                # Full cybersecurity analysis
                is_cybersecurity, found_keywords, reason = is_cybersecurity_related(filing, document_text)

                if is_cybersecurity:
                    cybersecurity_found += 1
                    logger.info(f"🔒 Cybersecurity filing found: {company_info['title']} - {reason}")

                    # Create summary snippet around first keyword
                    summary_snippet = f"Cybersecurity-related 8-K filing. {reason}"
                    if found_keywords and document_text:
                        first_keyword = next((kw for kw in found_keywords if kw in CYBERSECURITY_KEYWORDS), None)
                        if first_keyword:
                            keyword_pos = document_text.lower().find(first_keyword.lower())
                            if keyword_pos != -1:
                                start_idx = max(0, keyword_pos - 200)
                                end_idx = min(len(document_text), keyword_pos + len(first_keyword) + 200)
                                context = document_text[start_idx:end_idx].strip()
                                summary_snippet = f"...{context}..."

                    # Prepare data for insertion
                    item_data = {
                        "source_id": SOURCE_ID_SEC_EDGAR_8K,
                        "item_url": document_url,
                        "title": f"SEC 8-K: {company_info['title']} - Cybersecurity Filing",
                        "publication_date": filing['filingDate'] + "T00:00:00",  # Convert to ISO format
                        "summary_text": summary_snippet,
                        "raw_data_json": {
                            "cik": cik,
                            "ticker": company_info.get('ticker', ''),
                            "accession_number": filing['accessionNumber'],
                            "filing_date": filing['filingDate'],
                            "report_date": filing['reportDate'],
                            "items": filing['items'],
                            "keywords_found": found_keywords,
                            "cybersecurity_reason": reason,
                            "primary_document": filing['primaryDocument'],
                            "file_size": filing['size']
                        },
                        "tags_keywords": ["sec_filing", "8-k", "cybersecurity"] + [kw.lower().replace(" ", "_") for kw in found_keywords if kw in CYBERSECURITY_KEYWORDS]
                    }

                    # Insert into database
                    try:
                        insert_response = supabase_client.insert_item(**item_data)
                        if insert_response:
                            logger.info(f"✅ Successfully inserted cybersecurity filing for {company_info['title']}")
                            total_inserted += 1
                        else:
                            logger.error(f"❌ Failed to insert filing for {company_info['title']}")
                    except Exception as e:
                        if "duplicate key value violates unique constraint" in str(e):
                            logger.info(f"📋 Filing already exists for {company_info['title']}")
                        else:
                            logger.error(f"❌ Error inserting filing: {e}")
                else:
                    logger.debug(f"No cybersecurity content found in {company_info['title']} filing {filing['accessionNumber']}")

        except Exception as e:
            logger.error(f"Error processing company {company_info.get('title', cik)}: {e}", exc_info=True)

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
