import os
from supabase import create_client, Client
import logging

logger = logging.getLogger(__name__)

class SupabaseClient:
    def __init__(self):
        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise ValueError("Supabase URL and Key must be set as environment variables.")
        self.client: Client = create_client(url, key)
        logger.info("Supabase client initialized.")

    def insert_item(self, source_id: int, item_url: str, title: str, publication_date: str, summary_text: str = None, full_content: str = None, raw_data_json: dict = None, tags_keywords: list = None, affected_individuals: int = None, breach_date: str = None, reported_date: str = None, notice_document_url: str = None):
        """
        Inserts a single item into the scraped_items table.
        publication_date should be an ISO 8601 string.
        """
        try:
            data_to_insert = {
                "source_id": source_id,
                "item_url": item_url,
                "title": title,
                "publication_date": publication_date,
                "summary_text": summary_text,
                "full_content": full_content,
                "raw_data_json": raw_data_json,
                "tags_keywords": tags_keywords,
                "affected_individuals": affected_individuals,
                "breach_date": breach_date,
                "reported_date": reported_date,
                "notice_document_url": notice_document_url,
                # scraped_at and created_at have defaults in the DB
            }
            # Remove keys where value is None to rely on DB defaults or avoid inserting nulls unnecessarily for optional fields
            data_to_insert = {k: v for k, v in data_to_insert.items() if v is not None}

            response = self.client.table("scraped_items").insert(data_to_insert).execute()

            # Check for errors in the response
            if hasattr(response, 'error') and response.error:
                logger.error(f"Supabase error inserting item {item_url}: {response.error}")
                return None

            if response.data:
                logger.info(f"Successfully inserted item: {item_url}")
                return response.data[0]
            else:
                logger.warning(f"No data returned for item {item_url}, but no error reported")
                return None

        except Exception as e:
            # Enhanced error logging with more details
            logger.error(f"Error inserting item {item_url}: {e}")
            logger.error(f"Data being inserted: {data_to_insert}")
            if hasattr(e, 'details'):
                logger.error(f"Error details: {e.details}")
            if hasattr(e, 'message'):
                logger.error(f"Error message: {e.message}")
            if hasattr(e, 'code'):
                logger.error(f"Error code: {e.code}")
            return None

    # We can add more methods later, e.g., for inserting into 'data_sources'
    # or for querying/updating records.
