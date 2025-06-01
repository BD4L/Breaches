import os
import logging
import requests # feedparser might use it, good to have for potential fallbacks or direct fetches if needed
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
from dateutil import parser as dateutil_parser
import time # For converting time_struct to datetime

import yaml
from .breach_intelligence import process_breach_intelligence # For loading config

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

# Path to the configuration file
CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')

# Headers for feedparser/requests. Some feeds might require a User-Agent.
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'application/rss+xml, application/xml, text/xml, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive'
}

# Configuration
FILTER_DAYS_BACK = int(os.environ.get("NEWS_FILTER_DAYS_BACK", "7"))  # Only process news from last N days
MAX_ITEMS_PER_FEED = int(os.environ.get("NEWS_MAX_ITEMS_PER_FEED", "50"))  # Limit items per feed
PROCESSING_MODE = os.environ.get("NEWS_PROCESSING_MODE", "ENHANCED")  # BASIC, ENHANCED
BREACH_INTELLIGENCE_ENABLED = os.environ.get("BREACH_INTELLIGENCE_ENABLED", "true").lower() == "true"
BREACH_CONFIDENCE_THRESHOLD = float(os.environ.get("BREACH_CONFIDENCE_THRESHOLD", "0.3"))  # Minimum confidence for breach detection

def clean_html(html_content: str, max_length: int = 500) -> str:
    """Strips HTML from a string and truncates it."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    return (text[:max_length] + '...') if len(text) > max_length else text

def parse_feed_date(entry) -> str | None:
    """
    Parses date from a feed entry, trying various common fields.
    Returns ISO 8601 string or None.
    """
    date_to_parse = None
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        date_to_parse = entry.published_parsed
    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        date_to_parse = entry.updated_parsed
    elif hasattr(entry, 'created_parsed') and entry.created_parsed: # Less common
        date_to_parse = entry.created_parsed
    elif hasattr(entry, 'published') and entry.published: # Fallback to string parsing
        try: return dateutil_parser.parse(entry.published).isoformat()
        except (ValueError, TypeError): pass
    elif hasattr(entry, 'updated') and entry.updated:
        try: return dateutil_parser.parse(entry.updated).isoformat()
        except (ValueError, TypeError): pass
    
    if date_to_parse:
        try:
            # feedparser's *_parsed fields return a time.struct_time
            return datetime.fromtimestamp(time.mktime(date_to_parse)).isoformat()
        except (TypeError, ValueError) as e:
            logger.warning(f"Could not parse time.struct_time {date_to_parse}: {e}")
            return None
    return None

def fetch_feed_with_fallback(feed_url: str, feed_name: str) -> feedparser.FeedParserDict:
    """
    Fetch RSS feed with SSL fallback handling.
    Returns parsed feed or empty feed on failure.
    """
    try:
        # First try: Direct feedparser with user agent
        parsed_feed = feedparser.parse(feed_url, agent=REQUEST_HEADERS['User-Agent'])

        # Check if we got entries or if there was an SSL error
        if parsed_feed.entries or not parsed_feed.bozo:
            return parsed_feed

        # If bozo bit is set and it's an SSL error, try with requests
        if parsed_feed.bozo and 'SSL' in str(parsed_feed.bozo_exception):
            logger.info(f"SSL error for {feed_name}, trying with requests fallback...")

            # Try with requests and custom headers
            response = requests.get(feed_url, headers=REQUEST_HEADERS, timeout=30, verify=False)
            response.raise_for_status()

            # Parse the content with feedparser
            parsed_feed = feedparser.parse(response.content)
            return parsed_feed

    except requests.exceptions.SSLError:
        logger.warning(f"SSL error for {feed_name}, trying without SSL verification...")
        try:
            response = requests.get(feed_url, headers=REQUEST_HEADERS, timeout=30, verify=False)
            response.raise_for_status()
            parsed_feed = feedparser.parse(response.content)
            return parsed_feed
        except Exception as e:
            logger.error(f"Failed to fetch {feed_name} even without SSL verification: {e}")
    except Exception as e:
        logger.error(f"Error fetching feed {feed_name}: {e}")

    # Return empty feed on failure
    empty_feed = feedparser.FeedParserDict()
    empty_feed.entries = []
    empty_feed.bozo = False
    return empty_feed

def should_process_news_item(publication_date_iso: str) -> bool:
    """
    Check if news item should be processed based on date filtering.
    """
    if not publication_date_iso or FILTER_DAYS_BACK <= 0:
        return True

    try:
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=FILTER_DAYS_BACK)
        item_date = dateutil_parser.parse(publication_date_iso)
        return item_date.replace(tzinfo=None) >= cutoff_date
    except (ValueError, TypeError):
        # If date parsing fails, include the item
        return True

def process_cybersecurity_news_feeds():
    """
    Fetches and processes cybersecurity news from various RSS/Atom feeds,
    and inserts relevant data into Supabase with enhanced error handling and duplicate detection.
    """
    logger.info("Starting Cybersecurity News Feed processing...")
    logger.info(f"Configuration: Filter last {FILTER_DAYS_BACK} days, Max {MAX_ITEMS_PER_FEED} items per feed, Mode: {PROCESSING_MODE}")

    try:
        with open(CONFIG_FILE_PATH, 'r') as f:
            config = yaml.safe_load(f)
            NEWS_FEEDS = config.get('cybersecurity_news_feeds', [])
            if not NEWS_FEEDS:
                logger.error(f"Could not find 'cybersecurity_news_feeds' in {CONFIG_FILE_PATH} or it's empty.")
                return
    except FileNotFoundError:
        logger.error(f"Configuration file {CONFIG_FILE_PATH} not found.")
        return
    except yaml.YAMLError as e_yaml:
        logger.error(f"Error parsing YAML configuration file {CONFIG_FILE_PATH}: {e_yaml}")
        return
    except Exception as e_conf:
        logger.error(f"An unexpected error occurred while loading configuration: {e_conf}")
        return

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    total_inserted_all_feeds = 0
    total_processed_all_feeds = 0
    total_skipped_all_feeds = 0

    for feed_info in NEWS_FEEDS:
        feed_name = feed_info.get("name")
        feed_url = feed_info.get("url")
        source_id = feed_info.get("source_id")

        if not all([feed_name, feed_url, source_id]):
            logger.warning(f"Skipping feed entry due to missing name, url, or source_id in config: {feed_info}")
            continue
        
        logger.info(f"Processing feed: {feed_name} from {feed_url}")

        # Use enhanced feed fetching with SSL fallback
        parsed_feed = fetch_feed_with_fallback(feed_url, feed_name)

        if parsed_feed.bozo: # Indicates potential issues with the feed (e.g. not well-formed XML)
            logger.warning(f"Feed {feed_name} ({feed_url}) may be ill-formed. Bozo bit set. Exception: {parsed_feed.bozo_exception}")
            # Continue processing entries if any, but log the warning.

        if not parsed_feed.entries:
            logger.info(f"No entries found in feed {feed_name} ({feed_url}). It might be empty, stale (e.g., Threatpost), or an error occurred that didn't raise an exception.")
            if feed_name == "Threatpost":
                 logger.info("Threatpost has ceased new publications, so an empty feed is expected.")
            continue
            
        logger.info(f"Found {len(parsed_feed.entries)} entries in {feed_name} feed.")
        
        feed_inserted_count = 0
        feed_processed_count = 0
        feed_skipped_count = 0

        # Limit entries per feed for performance
        entries_to_process = parsed_feed.entries[:MAX_ITEMS_PER_FEED] if MAX_ITEMS_PER_FEED > 0 else parsed_feed.entries

        for entry in entries_to_process:
            feed_processed_count += 1
            try:
                title = entry.get("title", "No Title Provided")
                item_url = entry.get("link")
                
                if not item_url: # Skip if no URL, as it's a key identifier
                    logger.warning(f"Skipping entry in {feed_name} due to missing item URL. Title: '{title}'")
                    feed_skipped_count += 1
                    continue

                publication_date_iso = parse_feed_date(entry)
                if not publication_date_iso: # Try to use current time if no date found, or skip
                    logger.warning(f"No parsable publication date found for entry '{title}' in {feed_name}. Using current time as fallback.")
                    publication_date_iso = datetime.now().isoformat()
                    # Alternatively, skip:
                    # feed_skipped_count += 1
                    # continue

                # Check if item already exists in database (duplicate detection)
                if supabase_client.check_item_exists(item_url):
                    logger.debug(f"Item '{title}' already exists in database. Skipping.")
                    feed_skipped_count += 1
                    continue

                # Apply date filtering
                if not should_process_news_item(publication_date_iso):
                    logger.debug(f"Skipping '{title}' - outside date filter range (older than {FILTER_DAYS_BACK} days)")
                    feed_skipped_count += 1
                    continue

                summary_html = entry.get("summary") or entry.get("description") # 'description' is common in RSS 2.0
                summary_text = clean_html(summary_html, max_length=1000) # Longer max_length for news summaries

                # Get full content if available
                full_content = ""
                if entry.get("content"):
                    full_content = clean_html(entry.get("content", [{}])[0].get("value", ""), max_length=5000)

                # Process breach intelligence if enabled
                breach_data = {}
                if BREACH_INTELLIGENCE_ENABLED and PROCESSING_MODE == "ENHANCED":
                    try:
                        breach_intelligence = process_breach_intelligence(
                            title=title,
                            content=full_content or "",
                            summary=summary_text or "",
                            item_url=item_url
                        )

                        # Only include breach data if confidence meets threshold
                        if breach_intelligence.get('is_breach_related') and breach_intelligence.get('confidence_score', 0) >= BREACH_CONFIDENCE_THRESHOLD:
                            breach_data = {
                                'is_cybersecurity_related': True,
                                'affected_individuals': breach_intelligence.get('affected_individuals'),
                                'breach_date': breach_intelligence.get('breach_date'),
                                'what_was_leaked': breach_intelligence.get('what_was_leaked'),
                                'data_types_compromised': breach_intelligence.get('data_types_compromised'),
                                'incident_nature_text': breach_intelligence.get('incident_nature_text'),
                                'keywords_detected': breach_intelligence.get('detected_keywords'),
                                'keyword_contexts': breach_intelligence.get('raw_intelligence', {}).get('keywords_context', {})
                            }
                            logger.info(f"🚨 BREACH DETECTED: {breach_intelligence.get('organization_name', 'Unknown')} - Confidence: {breach_intelligence.get('confidence_score', 0):.2f}")
                        else:
                            # Still mark as cybersecurity related even if not a breach
                            breach_data['is_cybersecurity_related'] = breach_intelligence.get('is_breach_related', False)

                    except Exception as e:
                        logger.error(f"Error processing breach intelligence for '{title}': {e}")
                        breach_data = {'is_cybersecurity_related': False}

                # Prepare raw_data_json
                raw_data = {
                    "feed_entry_id": entry.get("id"),
                    "authors": [author.get("name") for author in entry.get("authors", []) if author.get("name")],
                    "feed_tags": [tag.get("term") for tag in entry.get("tags", []) if tag.get("term")],
                    "comments_url": entry.get("comments"), # Link to comments section if available
                    "full_content_encoded": entry.get("content", [{}])[0].get("value") if entry.get("content") else None # If full content is in feed
                }
                # Clean None values from raw_data
                raw_data_json = {k: v for k, v in raw_data.items() if v is not None and v != [] and v != ""}


                tags = [feed_name.lower().replace(" ", "_").replace("/", "_"), "cybersecurity_news"]
                if raw_data_json.get("feed_tags"):
                    # Add sanitized feed tags to our tags list
                    sanitized_feed_tags = [t.lower().replace(" ", "_") for t in raw_data_json["feed_tags"] if len(t) < 50] # Basic sanitization and length check
                    tags.extend(sanitized_feed_tags)
                tags = list(set(tags)) # Ensure uniqueness


                item_data = {
                    "source_id": source_id,
                    "item_url": item_url,
                    "title": title,
                    "publication_date": publication_date_iso,
                    "summary_text": summary_text,
                    "full_content": full_content if full_content else None,
                    "raw_data_json": raw_data_json if raw_data_json else None, # Ensure it's None if empty
                    "tags_keywords": tags
                }

                # Merge breach intelligence data if available
                if breach_data:
                    item_data.update(breach_data)
                
                # Duplicate detection is now handled above before processing
                insert_response = supabase_client.insert_item(**item_data)
                if insert_response:
                    # logger.debug(f"Successfully inserted item '{title}' from {feed_name}. URL: {item_url}")
                    feed_inserted_count += 1
                else:
                    logger.error(f"Failed to insert item '{title}' from {feed_name}. URL: {item_url}")
            
            except Exception as e:
                logger.error(f"Error processing entry '{entry.get('title', 'Unknown Title')}' from {feed_name}: {e}", exc_info=True)
                feed_skipped_count +=1
        
        logger.info(f"Finished processing feed {feed_name}. Processed: {feed_processed_count}, Inserted: {feed_inserted_count}, Skipped: {feed_skipped_count}")
        total_inserted_all_feeds += feed_inserted_count
        total_processed_all_feeds += feed_processed_count
        total_skipped_all_feeds += feed_skipped_count

    logger.info(f"Finished all cybersecurity news feeds. Total items processed: {total_processed_all_feeds}. Total items inserted: {total_inserted_all_feeds}. Total items skipped: {total_skipped_all_feeds}")

if __name__ == "__main__":
    logger.info("Cybersecurity News RSS Feed Scraper Started")
    
    # Check for Supabase env vars first, as they are critical for the script's core function.
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set for Supabase client.")
        # Optionally, print to console if run directly without these, as logger might not be fully configured or visible.
        if __name__ == "__main__":
             print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_cybersecurity_news_feeds() # This function now loads its own config.
        
    logger.info("Cybersecurity News RSS Feed Scraper Finished")
