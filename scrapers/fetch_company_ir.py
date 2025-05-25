import os
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from dateutil import parser as dateutil_parser
import re

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

COMPANY_IR_SITES = [
    {"name": "Microsoft IR", "url": "https://www.microsoft.com/en-us/Investor/", "source_id": 31},
    {"name": "Apple IR", "url": "https://investor.apple.com/investor-relations/default.aspx", "source_id": 32},
    {"name": "Amazon IR", "url": "https://ir.aboutamazon.com/", "source_id": 33},
    {"name": "Alphabet IR", "url": "https://abc.xyz/investor/", "source_id": 34},
    {"name": "Meta IR", "url": "https://investor.fb.com/", "source_id": 35},
]

KEYWORDS_BREACH = [
    "data breach", "cybersecurity incident", "security incident", "security event",
    "unauthorized access", "data security", "vulnerability", "customer data",
    "information security", "security breach", "cyber attack", "data compromise",
    "systems compromised", "security vulnerability", "data exposure"
]

# Common terms found in links to news/press/filings pages
SUBPAGE_LINK_KEYWORDS = [
    "news", "press", "releases", "investor", "events", "sec filings", "financial information",
    "reports", "quarterly", "annual", "blog", "updates", "statements", "presentations"
]
# Max sub-pages to check per company to avoid excessive crawling
MAX_SUBPAGES_PER_COMPANY = 10
# Max depth for recursive search for links (to prevent runaway scraping on very large sites)
MAX_LINK_DEPTH = 1 
# Context window for summary snippet (chars around keyword)
SNIPPET_CONTEXT_WINDOW = 200


# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9'
}


def extract_text_from_html(html_content: str) -> str:
    """Extracts all text from HTML content."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, 'html.parser')
    # Remove script and style elements
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()
    return soup.get_text(separator=" ", strip=True)


def find_keywords_in_text(text_content: str, keywords: list) -> list:
    """Searches for keywords in text (case-insensitive) and returns found keywords."""
    found = []
    text_lower = text_content.lower()
    for keyword in keywords:
        if keyword.lower() in text_lower:
            found.append(keyword)
    return list(set(found)) # Unique keywords

def create_snippet(text_content: str, found_keywords: list, window: int) -> str:
    """Creates a text snippet around the first found keyword."""
    if not found_keywords or not text_content:
        return ""
    
    text_lower = text_content.lower()
    first_keyword = found_keywords[0].lower()
    
    try:
        keyword_index = text_lower.index(first_keyword)
    except ValueError:
        return "Keyword not found in text for snippet creation (should not happen if keyword was found initially)."

    start_index = max(0, keyword_index - window)
    end_index = min(len(text_content), keyword_index + len(first_keyword) + window)
    
    snippet = text_content[start_index:end_index]
    if start_index > 0:
        snippet = "..." + snippet
    if end_index < len(text_content):
        snippet = snippet + "..."
    return snippet


def extract_publication_date(soup: BeautifulSoup, page_url: str) -> str | None:
    """
    Tries to extract a publication date from various common HTML meta tags or elements.
    Returns ISO 8601 string or None.
    """
    date_str = None
    # Common meta tags
    meta_selectors = [
        "meta[property='article:published_time']",
        "meta[property='og:published_time']",
        "meta[name='publication_date']",
        "meta[name='publishdate']",
        "meta[name='DC.date.issued']",
        "meta[name='date']",
        "meta[itemprop='datePublished']",
        "meta[name='parsely-pub-date']", # Common in news sites
    ]
    for selector in meta_selectors:
        tag = soup.select_one(selector)
        if tag and tag.has_attr('content') and tag['content']:
            date_str = tag['content']
            break
    
    # Common time elements
    if not date_str:
        time_tag = soup.find('time')
        if time_tag and time_tag.has_attr('datetime'):
            date_str = time_tag['datetime']
        elif time_tag and time_tag.string:
            date_str = time_tag.string

    # Less specific: Search for elements with classes/IDs like "date", "timestamp", "published"
    if not date_str:
        date_elements = soup.find_all(attrs={'class': re.compile(r'date|time|publish', re.I)})
        for el in date_elements:
            if el.string and len(el.string.strip()) > 5 : # Basic check for valid date string
                # Further check if it contains numbers and common date separators
                if re.search(r'\d', el.string) and re.search(r'[\s,/.-]', el.string):
                    date_str = el.string.strip()
                    break
    
    if date_str:
        try:
            dt_object = dateutil_parser.parse(date_str)
            # If timezone naive, assume UTC, or try to infer if possible (hard)
            if dt_object.tzinfo is None or dt_object.tzinfo.utcoffset(dt_object) is None:
                # logger.debug(f"Assuming UTC for timezone-naive date '{date_str}' from {page_url}")
                # dt_object = dt_object.replace(tzinfo=timezone.utc) # This might be too presumptive
                # Better to parse with default today and if result is in future, it's likely wrong.
                # For now, let dateutil handle it; it often defaults to local if no tz.
                # For IR news, often specific time isn't critical, just the date.
                pass
            return dt_object.isoformat()
        except (ValueError, TypeError, OverflowError) as e:
            logger.warning(f"Could not parse extracted date string '{date_str}' from {page_url}: {e}")
            
    # Default to today if no date found, or could be None
    # return datetime.now(timezone.utc).isoformat() # Or None if preferred
    return None


def get_internal_links(soup: BeautifulSoup, base_url: str, keywords: list) -> set:
    """Extracts internal links relevant to news/press/etc. from a parsed page."""
    links = set()
    parsed_base_url = urlparse(base_url)
    
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        # Resolve relative URLs
        absolute_url = urljoin(base_url, href)
        parsed_absolute_url = urlparse(absolute_url)

        # Check if it's an internal link (same domain)
        if parsed_absolute_url.netloc == parsed_base_url.netloc:
            link_text = a_tag.get_text(strip=True).lower()
            path_lower = parsed_absolute_url.path.lower()
            
            # Check if link text or path contains any of the subpage keywords
            if any(keyword.lower() in link_text for keyword in keywords) or \
               any(keyword.lower() in path_lower for keyword in keywords):
                # Basic file extension filter (optional, can be expanded)
                if not any(absolute_url.lower().endswith(ext) for ext in ['.pdf', '.zip', '.jpg', '.png', '.mp4', '.mov']):
                    links.add(absolute_url)
    return links


def process_single_page(page_url: str, company_name: str, source_id: int, supabase_client: SupabaseClient, is_main_page: bool = False):
    """Fetches a single page, searches for keywords, and inserts into Supabase if found."""
    try:
        logger.info(f"Fetching page: {page_url} for {company_name}")
        response = requests.get(page_url, headers=REQUEST_HEADERS, timeout=20)
        response.raise_for_status()
        
        # Check content type - only process HTML
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' not in content_type:
            logger.info(f"Skipping non-HTML page {page_url} (Content-Type: {content_type})")
            return 0 # Return 0 inserted items

        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        
        page_title_tag = soup.find('title')
        page_title = page_title_tag.string.strip() if page_title_tag else "N/A"

        text_content = extract_text_from_html(html_content)
        if not text_content:
            logger.info(f"No text content extracted from {page_url}")
            return 0

        found_breach_keywords = find_keywords_in_text(text_content, KEYWORDS_BREACH)

        if found_breach_keywords:
            logger.info(f"Keywords {found_breach_keywords} found on {page_url} for {company_name}")
            
            publication_date_iso = extract_publication_date(soup, page_url)
            if not publication_date_iso and not is_main_page: # For sub-pages, if no date, use current time
                logger.warning(f"No publication date found for sub-page {page_url}, using current time.")
                publication_date_iso = datetime.now(timezone.utc).isoformat()
            elif not publication_date_iso and is_main_page: # For main IR page, null date is fine
                 logger.info(f"No publication date found for main IR page {page_url}. Setting to null.")
                 publication_date_iso = None


            summary = create_snippet(text_content, found_breach_keywords, SNIPPET_CONTEXT_WINDOW)

            item_data = {
                "source_id": source_id,
                "item_url": page_url,
                "title": f"{company_name}: Potential Breach Mention on {'Main IR Page' if is_main_page else 'Sub-Page'}",
                "publication_date": publication_date_iso,
                "summary_text": summary if summary else "Snippet could not be generated.",
                "raw_data_json": {
                    "company_name": company_name,
                    "keywords_found": found_breach_keywords,
                    "original_page_title": page_title,
                    "page_type": "main_ir_page" if is_main_page else "sub_page"
                },
                "tags_keywords": [company_name.lower().replace(" ", "_").replace(".","") + "_ir", "company_ir"] + \
                                 [kw.lower().replace(" ", "_") for kw in found_breach_keywords]
            }
            
            # TODO: Implement check for existing record

            insert_response = supabase_client.insert_item(**item_data)
            if insert_response:
                logger.info(f"Successfully inserted item for {company_name} from {page_url}")
                return 1 # 1 item inserted
            else:
                logger.error(f"Failed to insert item for {company_name} from {page_url}")
        else:
            logger.info(f"No relevant keywords found on {page_url} for {company_name}")
        
        return 0 # 0 items inserted
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching or processing page {page_url}: {e}")
        return 0
    except Exception as e_proc:
        logger.error(f"Unexpected error processing page {page_url}: {e_proc}", exc_info=True)
        return 0


def process_company_ir_sites():
    logger.info("Starting Company Investor Relations (IR) site processing...")

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    total_inserted_all_sites = 0

    for company_site in COMPANY_IR_SITES:
        company_name = company_site["name"]
        base_ir_url = company_site["url"]
        source_id = company_site["source_id"]
        
        logger.info(f"Processing company: {company_name}, URL: {base_ir_url}")
        
        # 1. Process the main IR page itself
        inserted_main = process_single_page(base_ir_url, company_name, source_id, supabase_client, is_main_page=True)
        total_inserted_all_sites += inserted_main

        # 2. Find and process relevant sub-pages
        try:
            main_page_response = requests.get(base_ir_url, headers=REQUEST_HEADERS, timeout=20)
            main_page_response.raise_for_status()
            main_soup = BeautifulSoup(main_page_response.content, 'html.parser')
            
            # Find links on the main IR page that might lead to news/press releases
            sub_page_links = get_internal_links(main_soup, base_ir_url, SUBPAGE_LINK_KEYWORDS)
            logger.info(f"Found {len(sub_page_links)} potential sub-pages for {company_name} from main IR page.")

            processed_subpage_count = 0
            for sub_page_url in list(sub_page_links): # Convert to list to avoid issues if set changes (not expected here)
                if processed_subpage_count >= MAX_SUBPAGES_PER_COMPANY:
                    logger.info(f"Reached max sub-pages ({MAX_SUBPAGES_PER_COMPANY}) for {company_name}. Moving to next company.")
                    break
                
                inserted_sub = process_single_page(sub_page_url, company_name, source_id, supabase_client, is_main_page=False)
                total_inserted_all_sites += inserted_sub
                processed_subpage_count += 1
                
                # Optional: Small delay between sub-page requests
                # time.sleep(0.5) 

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching main IR page {base_ir_url} for {company_name} to find sub-links: {e}")
        except Exception as e_main:
            logger.error(f"Unexpected error processing main IR page or finding sub-links for {company_name} ({base_ir_url}): {e_main}", exc_info=True)
            
        logger.info(f"Finished processing for {company_name}. Total items inserted for this company so far: {total_inserted_all_sites - (total_inserted_all_sites - inserted_main - sum(1 for _ in range(processed_subpage_count) if _ > 0)) }") # Approx

    logger.info(f"Finished all Company IR sites. Total items inserted across all sites: {total_inserted_all_sites}")


if __name__ == "__main__":
    logger.info("Company Investor Relations (IR) Scraper Started")
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_company_ir_sites()
        
    logger.info("Company Investor Relations (IR) Scraper Finished")
