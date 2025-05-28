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

    def check_item_exists(self, item_url: str) -> bool:
        """
        Check if an item with the given URL already exists in the database.
        """
        try:
            response = self.client.table("scraped_items").select("id").eq("item_url", item_url).execute()
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Error checking if item exists for URL {item_url}: {e}")
            return False

    def insert_item(self, source_id: int, item_url: str, title: str, publication_date: str, summary_text: str = None, full_content: str = None, raw_data_json: dict = None, tags_keywords: list = None, affected_individuals: int = None, breach_date: str = None, reported_date: str = None, notice_document_url: str = None,
                    # SEC-specific fields
                    cik: str = None, ticker_symbol: str = None, accession_number: str = None, form_type: str = None, filing_date: str = None, report_date: str = None, primary_document_url: str = None, xbrl_instance_url: str = None,
                    items_disclosed: list = None, is_cybersecurity_related: bool = None, is_amendment: bool = None, is_delayed_disclosure: bool = None,
                    incident_nature_text: str = None, incident_scope_text: str = None, incident_timing_text: str = None, incident_impact_text: str = None, incident_unknown_details_text: str = None,
                    incident_discovery_date: str = None, incident_disclosure_date: str = None, incident_containment_date: str = None,
                    estimated_cost_min: float = None, estimated_cost_max: float = None, estimated_cost_currency: str = None, data_types_compromised: list = None,
                    exhibit_urls: list = None, keywords_detected: list = None, keyword_contexts: dict = None, file_size_bytes: int = None,
                    business_description: str = None, industry_classification: str = None):
        """
        Inserts a single item into the scraped_items table.
        publication_date should be an ISO 8601 string.
        """
        try:
            data_to_insert = {
                # Core fields
                "source_id": source_id,
                "item_url": item_url,
                "title": title,
                "publication_date": publication_date,
                "summary_text": summary_text,
                "full_content": full_content,
                "raw_data_json": raw_data_json,
                "tags_keywords": tags_keywords,

                # Standardized breach fields
                "affected_individuals": affected_individuals,
                "breach_date": breach_date,
                "reported_date": reported_date,
                "notice_document_url": notice_document_url,

                # SEC-specific fields
                "cik": cik,
                "ticker_symbol": ticker_symbol,
                "accession_number": accession_number,
                "form_type": form_type,
                "filing_date": filing_date,
                "report_date": report_date,
                "primary_document_url": primary_document_url,
                "xbrl_instance_url": xbrl_instance_url,
                "items_disclosed": items_disclosed,
                "is_cybersecurity_related": is_cybersecurity_related,
                "is_amendment": is_amendment,
                "is_delayed_disclosure": is_delayed_disclosure,
                "incident_nature_text": incident_nature_text,
                "incident_scope_text": incident_scope_text,
                "incident_timing_text": incident_timing_text,
                "incident_impact_text": incident_impact_text,
                "incident_unknown_details_text": incident_unknown_details_text,
                "incident_discovery_date": incident_discovery_date,
                "incident_disclosure_date": incident_disclosure_date,
                "incident_containment_date": incident_containment_date,
                "estimated_cost_min": estimated_cost_min,
                "estimated_cost_max": estimated_cost_max,
                "estimated_cost_currency": estimated_cost_currency,
                "data_types_compromised": data_types_compromised,
                "exhibit_urls": exhibit_urls,
                "keywords_detected": keywords_detected,
                "keyword_contexts": keyword_contexts,
                "file_size_bytes": file_size_bytes,
                "business_description": business_description,
                "industry_classification": industry_classification,
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
