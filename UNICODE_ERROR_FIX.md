# Unicode Error Fix for California AG Scraper

## Problem Description

The California AG scraper was encountering a PostgreSQL Unicode error during database updates:

```
Error updating item enhancement: {'message': 'unsupported Unicode escape sequence', 'code': '22P05', 'hint': None, 'details': '\\u0000 cannot be converted to text.'}
```

**Root Cause**: PDF text extraction using PyPDF2 and pdfplumber was including null bytes (`\u0000`) and other control characters that PostgreSQL cannot handle in text fields.

## Solution Implemented

### 1. Text Cleaning Utility Functions

Added to `utils/supabase_client.py`:

- **`clean_text_for_database(text)`**: Removes null bytes and problematic control characters from individual text strings
- **`clean_data_recursively(data)`**: Recursively cleans all text content in complex data structures (dicts, lists, strings)

### 2. Database Operation Safety

Enhanced both database operations in `utils/supabase_client.py`:

- **`insert_item()`**: Now cleans all data before insertion
- **`update_item_enhancement()`**: Now cleans all data before updates

### 3. PDF Text Extraction Cleaning

Modified `scrapers/fetch_california_ag.py` to clean PDF text immediately after extraction:

- **PyPDF2 extraction**: Text cleaned after successful extraction
- **pdfplumber extraction**: Text cleaned after successful extraction  
- **Fallback extraction**: Text cleaned for low-confidence extractions

## Technical Details

### Characters Removed
- Null bytes: `\u0000` and `\x00`
- Control characters: `\x00-\x08`, `\x0B-\x0C`, `\x0E-\x1F`
- Preserves: newlines (`\n`), tabs (`\t`), and regular text

### Implementation Points
1. **Early cleaning**: Text is cleaned immediately after PDF extraction
2. **Comprehensive cleaning**: All database operations clean data recursively
3. **Safe fallbacks**: Even failed PDF extractions get cleaned text
4. **Preserves content**: Only removes problematic characters, keeps meaningful text

## Files Modified

1. **`utils/supabase_client.py`**
   - Added `clean_text_for_database()` function
   - Added `clean_data_recursively()` function
   - Enhanced `insert_item()` with data cleaning
   - Enhanced `update_item_enhancement()` with data cleaning

2. **`scrapers/fetch_california_ag.py`**
   - Added import for `clean_text_for_database`
   - Added text cleaning after PyPDF2 extraction
   - Added text cleaning after pdfplumber extraction
   - Added text cleaning for fallback extraction

## Testing

✅ Text cleaning functions tested and working correctly
✅ California AG scraper imports and functions properly
✅ Supabase client properly cleans complex data structures
✅ All modified files compile without syntax errors

## Expected Result

The Unicode error should be resolved, and the California AG scraper should successfully:
- Extract PDF content without null byte issues
- Update existing breach records with enhanced data
- Store all text content safely in PostgreSQL
- Continue processing all breaches without database errors

## Prevention

This fix prevents similar Unicode errors across all scrapers by:
- Cleaning all text data at the database layer
- Providing reusable text cleaning utilities
- Handling PDF extraction edge cases
- Ensuring database compatibility for all text content
