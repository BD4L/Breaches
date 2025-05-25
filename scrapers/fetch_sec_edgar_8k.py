import os
import logging
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin

# Assuming SupabaseClient is in utils.supabase_client
# Adjust the import path if your project structure is different
try:
    from utils.supabase_client import SupabaseClient
except ImportError:
    # This is to allow the script to be run directly for testing
    # without having the utils package installed in the traditional sense.
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from utils.supabase_client import SupabaseClient


# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
SEC_EDGAR_8K_ATOM_FEED_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&count=100&output=atom"
# Keywords to search for in filing documents
KEYWORDS = [
    "cybersecurity", "data breach", "security incident",
    "unauthorized access", "ransomware", "information security",
    "material cybersecurity incident" # Added based on new SEC rules
]
# Placeholder for the source_id from the 'data_sources' table in Supabase
# This ID should correspond to "SEC EDGAR 8-K"
SOURCE_ID_SEC_EDGAR_8K = 1

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def fetch_filing_document_url_and_content(index_url: str) -> tuple[str | None, str | None]:
    """
    Fetches the filing index page and attempts to find the main 8-K document URL and its content.
    Returns a tuple (document_url, document_content_text).
    """
    try:
        response = requests.get(index_url, headers=REQUEST_HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the link to the main 8-K document
        # Common pattern: first .htm file that is not an XSL file, or contains '8-k' in its name
        document_link_tag = None
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.endswith(('.htm', '.html')) and not href.endswith('.xsl'):
                if '8-k' in href.lower() or '8k' in href.lower(): # More specific
                    document_link_tag = link
                    break
                if not document_link_tag: # Fallback to first htm/html
                     document_link_tag = link

        if not document_link_tag: # Try to find .txt if no .htm found
            for link in soup.find_all('a', href=True):
                href = link['href']
                if href.endswith('.txt'):
                    document_link_tag = link
                    break

        if document_link_tag:
            document_url = urljoin(index_url, document_link_tag['href'])
            logger.info(f"Found document URL: {document_url}")

            doc_response = requests.get(document_url, headers=REQUEST_HEADERS)
            doc_response.raise_for_status()

            if document_url.endswith(('.htm', '.html')):
                doc_soup = BeautifulSoup(doc_response.content, 'html.parser')
                # Extract text, trying to get main content if possible
                # This can be very complex; a simple .get_text() is a starting point
                return document_url, doc_soup.get_text(separator='\n', strip=True)
            elif document_url.endswith('.txt'):
                return document_url, doc_response.text # Already plain text
            else:
                logger.warning(f"Document at {document_url} is neither HTML nor TXT.")
                return document_url, None # Return URL but no content if not parsable as text

        logger.warning(f"Could not find a suitable document link on index page: {index_url}")
        return index_url, None # Return index_url if no specific document found, and no content
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching or parsing page {index_url}: {e}")
        return index_url, None # Return index_url if error, and no content

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

def process_edgar_feed():
    """
    Fetches the SEC EDGAR 8-K feed, processes each filing,
    and inserts relevant data into Supabase.
    """
    logger.info("Starting SEC EDGAR 8-K feed processing...")

    try:
        # First try to fetch the feed with requests to check if it's accessible
        response = requests.get(SEC_EDGAR_8K_ATOM_FEED_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
        logger.info(f"Successfully fetched feed. Status: {response.status_code}, Length: {len(response.content)} bytes")

        # Parse the feed
        feed = feedparser.parse(response.content)

        if feed.bozo:
            logger.error(f"Error parsing feed: {feed.bozo_exception}")
            logger.error(f"Feed content preview: {response.text[:500]}")
            return

        if not feed.entries:
            logger.warning("No entries found in the feed")
            return

        logger.info(f"Fetched {len(feed.entries)} filings from the feed.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching SEC EDGAR feed: {e}")
        return
    except Exception as e:
        logger.error(f"Unexpected error processing feed: {e}")
        return

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    inserted_count = 0
    for entry in feed.entries:
        try:
            title = entry.get("title", "N/A")
            link_to_index = entry.get("link") # This is usually the index page
            published_parsed = entry.get("published_parsed")

            if not link_to_index or not published_parsed:
                logger.warning(f"Skipping entry due to missing link or publication date: {title}")
                continue

            # Extract CIK (Central Index Key) if available, often in 'summary' or 'id'
            cik_number = None
            summary_detail = entry.get('summary_detail', {})
            if summary_detail:
                summary_text_for_cik = summary_detail.get('value', '')
                # Example: 'Form 8-K for FOO BAR CORP, CIK: 0001234567, Filing Date: ...'
                if 'CIK:' in summary_text_for_cik:
                    cik_number = summary_text_for_cik.split('CIK:')[1].split(',')[0].strip()

            if not cik_number and entry.get('id'): # Fallback: try to get CIK from entry ID
                # Example id: urn:tag:sec.gov,2008:accession-number=0001193125-23-287834
                # CIK is not directly in the id, but accession number is.
                # Company name is in the title: "8-K - FOO BAR CORP (0001234567)"
                if '(' in title and ')' in title:
                    potential_cik = title.split('(')[-1].split(')')[0]
                    if potential_cik.isdigit():
                        cik_number = potential_cik

            company_name = title.replace(f"({cik_number})", "").replace("8-K - ", "").strip() if cik_number else title.replace("8-K - ", "").strip()

            publication_date = datetime(*published_parsed[:6]).isoformat()

            logger.info(f"Processing: {company_name} (CIK: {cik_number if cik_number else 'N/A'}), Link: {link_to_index}, Published: {publication_date}")

            # Fetch the actual filing document URL and its text content
            document_url, document_text = fetch_filing_document_url_and_content(link_to_index)

            if not document_text:
                logger.warning(f"No document text found for {company_name} at {link_to_index}. Skipping.")
                continue

            found_keywords = search_text_for_keywords(document_text, KEYWORDS)

            if found_keywords:
                logger.info(f"Keywords {found_keywords} found for {company_name} (CIK: {cik_number})")

                # Create a summary snippet
                summary_snippet = "Keywords found: " + ", ".join(found_keywords)
                # Try to find a more contextual snippet (this is a simple version)
                first_keyword_pos = -1
                if document_text:
                    first_keyword_pos = document_text.lower().find(found_keywords[0].lower())
                if first_keyword_pos != -1:
                    start_index = max(0, first_keyword_pos - 150) # 150 chars before
                    end_index = min(len(document_text), first_keyword_pos + len(found_keywords[0]) + 150) # 150 chars after
                    summary_snippet = f"...{document_text[start_index:end_index]}..."


                item_data = {
                    "source_id": SOURCE_ID_SEC_EDGAR_8K,
                    "item_url": document_url if document_url else link_to_index, # Prefer specific doc URL
                    "title": f"SEC 8-K Filing: {company_name}",
                    "publication_date": publication_date,
                    "summary_text": summary_snippet,
                    "full_content": None, # Optionally, store full_content if needed, but can be large
                    "raw_data_json": {"cik": cik_number, "keywords_found": found_keywords, "feed_entry_id": entry.get('id')},
                    "tags_keywords": ["sec_filing", "8-k"] + [kw.lower().replace(" ", "_") for kw in found_keywords]
                }

                insert_response = supabase_client.insert_item(**item_data)
                if insert_response:
                    logger.info(f"Successfully inserted item for {company_name} (CIK: {cik_number}) into Supabase.")
                    inserted_count += 1
                else:
                    logger.error(f"Failed to insert item for {company_name} (CIK: {cik_number}).")
            else:
                logger.info(f"No relevant keywords found for {company_name} (CIK: {cik_number}).")

        except Exception as e:
            logger.error(f"Error processing entry {entry.get('title', 'N/A')}: {e}", exc_info=True)

    logger.info(f"Finished processing feed. Total items inserted: {inserted_count}")

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

    process_edgar_feed()
    logger.info("SEC EDGAR 8-K Scraper Finished")
