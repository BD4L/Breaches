"""
Breach Intelligence Module
Detects and extracts structured information from cybersecurity news articles
to identify data breaches and extract relevant details.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json

logger = logging.getLogger(__name__)

# Breach detection keywords and patterns
BREACH_KEYWORDS = {
    'primary': [
        'data breach', 'security breach', 'cyber attack', 'cyberattack', 'ransomware',
        'data leak', 'data exposure', 'security incident', 'hack', 'hacked',
        'compromised', 'unauthorized access', 'data stolen', 'personal information exposed'
    ],
    'secondary': [
        'phishing', 'malware', 'vulnerability', 'exposed database', 'leaked data',
        'security flaw', 'data compromise', 'privacy breach', 'information disclosure',
        'credential theft', 'identity theft', 'payment card', 'credit card data'
    ],
    'impact': [
        'affected', 'impacted', 'exposed', 'compromised', 'stolen', 'accessed',
        'records', 'customers', 'users', 'patients', 'employees', 'individuals'
    ]
}

# Data types that might be compromised
DATA_TYPES = [
    'personal information', 'personally identifiable information', 'pii',
    'social security numbers', 'ssn', 'credit card', 'payment card', 'financial data',
    'medical records', 'health information', 'phi', 'protected health information',
    'email addresses', 'passwords', 'usernames', 'phone numbers', 'addresses',
    'names', 'dates of birth', 'driver license', 'passport', 'bank account',
    'tax information', 'employee data', 'customer data', 'student records'
]

# Number extraction patterns
NUMBER_PATTERNS = [
    r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:million|m)\s*(?:records|customers|users|individuals|people|patients|employees)',
    r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:thousand|k)\s*(?:records|customers|users|individuals|people|patients|employees)',
    r'(\d{1,3}(?:,\d{3})*)\s*(?:records|customers|users|individuals|people|patients|employees)',
    r'(?:over|more than|up to|approximately|around)\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:million|m|thousand|k)?\s*(?:records|customers|users|individuals|people|patients|employees)',
    r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:billion|b)\s*(?:records|customers|users|individuals|people|patients|employees)'
]

# Organization name extraction patterns
ORG_PATTERNS = [
    r'([A-Z][a-zA-Z\s&\.]+(?:Inc|Corp|Corporation|Company|LLC|Ltd|Limited|Group|Holdings|Systems|Technologies|Healthcare|Hospital|Medical|University|College|School|Bank|Credit Union)\.?)',
    r'([A-Z][a-zA-Z\s&\.]{2,30})\s+(?:suffered|experienced|reported|disclosed|announced|confirmed)\s+(?:a\s+)?(?:data\s+)?breach',
    r'(?:breach|attack|incident)\s+(?:at|on|against)\s+([A-Z][a-zA-Z\s&\.]{2,30})',
    r'([A-Z][a-zA-Z\s&\.]{2,30})\s+(?:data|security|cyber)\s+(?:breach|incident|attack)'
]

def is_breach_related(title: str, content: str, summary: str = "") -> Tuple[bool, float, List[str]]:
    """
    Determine if a news article is related to a data breach.
    
    Returns:
        Tuple of (is_breach, confidence_score, detected_keywords)
    """
    text = f"{title} {summary} {content}".lower()
    detected_keywords = []
    score = 0.0
    
    # Check for primary breach keywords (high weight)
    for keyword in BREACH_KEYWORDS['primary']:
        if keyword in text:
            detected_keywords.append(keyword)
            score += 3.0
    
    # Check for secondary breach keywords (medium weight)
    for keyword in BREACH_KEYWORDS['secondary']:
        if keyword in text:
            detected_keywords.append(keyword)
            score += 1.5
    
    # Check for impact keywords (low weight)
    for keyword in BREACH_KEYWORDS['impact']:
        if keyword in text:
            detected_keywords.append(keyword)
            score += 0.5
    
    # Boost score if multiple categories are present
    categories_found = 0
    if any(kw in BREACH_KEYWORDS['primary'] for kw in detected_keywords):
        categories_found += 1
    if any(kw in BREACH_KEYWORDS['secondary'] for kw in detected_keywords):
        categories_found += 1
    if any(kw in BREACH_KEYWORDS['impact'] for kw in detected_keywords):
        categories_found += 1
    
    if categories_found >= 2:
        score *= 1.5
    
    # Normalize score to 0-1 range
    confidence = min(score / 10.0, 1.0)
    
    # Consider it breach-related if confidence > 0.3
    is_breach = confidence > 0.3
    
    return is_breach, confidence, detected_keywords

def extract_affected_count(text: str) -> Optional[int]:
    """
    Extract the number of affected individuals from text.
    """
    text = text.lower()
    
    for pattern in NUMBER_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                number_str = match.group(1).replace(',', '')
                number = float(number_str)
                
                # Check for scale indicators
                if 'million' in match.group(0).lower() or ' m ' in match.group(0).lower():
                    number *= 1_000_000
                elif 'billion' in match.group(0).lower() or ' b ' in match.group(0).lower():
                    number *= 1_000_000_000
                elif 'thousand' in match.group(0).lower() or ' k ' in match.group(0).lower():
                    number *= 1_000
                
                return int(number)
            except (ValueError, IndexError):
                continue
    
    return None

def extract_organization_name(text: str) -> Optional[str]:
    """
    Extract the organization name from breach-related text.
    """
    for pattern in ORG_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            org_name = match.group(1).strip()
            # Filter out common false positives
            if len(org_name) > 3 and not org_name.lower() in ['the company', 'a company', 'this company']:
                return org_name
    
    return None

def extract_data_types(text: str) -> List[str]:
    """
    Extract types of data that were compromised.
    """
    text = text.lower()
    found_types = []
    
    for data_type in DATA_TYPES:
        if data_type in text:
            found_types.append(data_type)
    
    return list(set(found_types))  # Remove duplicates

def extract_breach_date(text: str) -> Optional[str]:
    """
    Extract breach occurrence date from text.
    """
    # Common date patterns in breach reports
    date_patterns = [
        r'(?:on|in|during)\s+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})',  # "on January 15, 2024"
        r'(?:on|in|during)\s+(\d{1,2}/\d{1,2}/\d{4})',  # "on 1/15/2024"
        r'(?:occurred|happened|took place)\s+(?:on|in|during)\s+([A-Z][a-z]+\s+\d{4})',  # "occurred in January 2024"
        r'(?:between|from)\s+([A-Z][a-z]+\s+\d{1,2})\s+(?:and|to)\s+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})'  # Date ranges
    ]
    
    for pattern in date_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            return match.group(1)
    
    return None

def process_breach_intelligence(title: str, content: str, summary: str = "", item_url: str = "") -> Dict:
    """
    Process a news article and extract breach intelligence.
    
    Returns:
        Dictionary with extracted breach information
    """
    # Check if it's breach-related
    is_breach, confidence, keywords = is_breach_related(title, content, summary)
    
    if not is_breach:
        return {
            'is_breach_related': False,
            'confidence_score': confidence,
            'detected_keywords': keywords
        }
    
    # Extract breach details
    full_text = f"{title} {summary} {content}"
    
    result = {
        'is_breach_related': True,
        'confidence_score': confidence,
        'detected_keywords': keywords,
        'organization_name': extract_organization_name(full_text),
        'affected_individuals': extract_affected_count(full_text),
        'data_types_compromised': extract_data_types(full_text),
        'breach_date': extract_breach_date(full_text),
        'what_was_leaked': ', '.join(extract_data_types(full_text)) if extract_data_types(full_text) else None,
        'incident_nature_text': title,  # Use title as incident nature
        'raw_intelligence': {
            'source_url': item_url,
            'extraction_timestamp': datetime.now().isoformat(),
            'full_content_analyzed': len(full_text),
            'keywords_context': {}
        }
    }
    
    # Add keyword contexts for better analysis
    for keyword in keywords[:5]:  # Limit to top 5 keywords
        context_start = max(0, full_text.lower().find(keyword) - 50)
        context_end = min(len(full_text), full_text.lower().find(keyword) + len(keyword) + 50)
        result['raw_intelligence']['keywords_context'][keyword] = full_text[context_start:context_end]
    
    logger.info(f"Extracted breach intelligence: {result['organization_name']} - {result['affected_individuals']} affected")
    
    return result
