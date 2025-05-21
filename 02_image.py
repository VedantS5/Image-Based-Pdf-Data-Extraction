import os
import json
import csv
import base64
import io
import fitz  # PyMuPDF
import requests
from PIL import Image
import re
import argparse
import traceback
import sys
import concurrent.futures
import socket
import time
from typing import List, Dict, Any, Optional, Tuple

# Default path to JSON configuration file
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# Function to load configuration from external JSON file
def load_json_config(config_file=None):
    """Load configuration from JSON file with fallback to default values if file not found."""
    # Default configuration as fallback
    default_config = {
        "ollama": {
            "fallback_api_url": "http://localhost:11434/api/generate",
            "model": "gemma3:27b",
            "timeout": 180,
            "auto_detect": True
        },
        "pdf_processing": {
            "pages_to_process": {
                "mode": "all",           # Options: "all", "range", "first_n"
                "first_n": 0,            # When mode is "first_n", process this many pages (0 means all)
                "range": [1, 1],         # When mode is "range", process these pages (inclusive)
                "always_include_first": True  # Always include first page regardless of mode
            },
            "support_pages": 3,
            "image_scale": 2.0
        },
        "output": {
            "csv_filename": "author_extraction_results.csv"
        },
        "features": {
            "document_type_detection": True,
            "institution_detection": True,
            "email_validation": True,
            "prioritize_first_page": True,
            "metadata_filtering": True
        },
        "metadata": {
            "csv_path": "/N/project/fads_ng/analyst_reports_project/data/reports_metadata.csv",
            "skip_terms": ["termination", "dropping", "terminate", "drop coverage", "discontinue coverage", "discontinuing coverage"],
            "id_extraction_pattern": "key_(\\d+)"
        },
        "debug": {
            "enabled": False
        }
    }
    
    # Use provided config file or default path
    file_to_load = config_file if config_file else DEFAULT_CONFIG_PATH
    
    try:
        if os.path.exists(file_to_load):
            with open(file_to_load, 'r') as f:
                loaded_config = json.load(f)
                print(f"Loaded configuration from {file_to_load}")
                
                # Recursively update default config with loaded values
                def update_nested_dict(d, u):
                    for k, v in u.items():
                        if isinstance(v, dict):
                            d[k] = update_nested_dict(d.get(k, {}), v)
                        else:
                            d[k] = v
                    return d
                
                return update_nested_dict(default_config, loaded_config)
        else:
            print(f"Config file not found: {file_to_load}")
            print("Using default configuration")
            return default_config
    except Exception as e:
        print(f"Error loading config file: {e}")
        print("Using default configuration")
        return default_config

# Load config into global variables for easier access
def load_config(config=None):
    global CONFIG, OLLAMA_API_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT, OLLAMA_INSTANCES, NUM_WORKERS
    global PAGE_PROCESSING_CONFIG, MAX_TEXT_PAGES_FOR_SUPPORT, IMAGE_SCALE_FACTOR, OUTPUT_CSV_FILENAME
    global ENABLE_DOCUMENT_TYPE_DETECTION, ENABLE_INSTITUTION_DETECTION, ENABLE_EMAIL_VALIDATION, PRIORITIZE_FIRST_PAGE, DEBUG_MODE
    global ENABLE_METADATA_FILTERING, METADATA_CSV_PATH, SKIP_TERMS, ID_EXTRACTION_PATTERN, METADATA_CACHE
    global MAX_FILES, SKIP_PROCESSED_FILES
    
    # If no config provided, load from the default JSON file
    if config is None:
        config = load_json_config()
        
    CONFIG = config
    
    # Ollama settings
    OLLAMA_API_URL = config["ollama"]["fallback_api_url"]
    OLLAMA_MODEL = config["ollama"]["model"]
    OLLAMA_TIMEOUT = config["ollama"]["timeout"]
    
    # PDF processing settings
    PAGE_PROCESSING_CONFIG = config["pdf_processing"]["pages_to_process"]
    MAX_TEXT_PAGES_FOR_SUPPORT = config["pdf_processing"]["support_pages"]
    IMAGE_SCALE_FACTOR = config["pdf_processing"]["image_scale"]
    
    # Output settings
    OUTPUT_CSV_FILENAME = config["output"]["csv_filename"]
    
    # Feature toggles
    ENABLE_DOCUMENT_TYPE_DETECTION = config["features"]["document_type_detection"]
    ENABLE_INSTITUTION_DETECTION = config["features"]["institution_detection"]
    ENABLE_EMAIL_VALIDATION = config["features"]["email_validation"]
    PRIORITIZE_FIRST_PAGE = config["features"]["prioritize_first_page"]
    # Metadata filtering
    ENABLE_METADATA_FILTERING = config.get("features", {}).get("metadata_filtering", False)
    metadata_config = config.get("metadata", {})
    METADATA_CSV_PATH = metadata_config.get("csv_path", "")
    SKIP_TERMS = metadata_config.get("skip_terms", [])
    ID_EXTRACTION_PATTERN = metadata_config.get("id_extraction_pattern", "key_(\d+)")
    METADATA_CACHE = {}
    
    # Execution settings
    execution_config = config.get("execution", {})
    MAX_FILES = execution_config.get("max_files", 0)  # 0 means process all files
    SKIP_PROCESSED_FILES = execution_config.get("skip_processed_files", True)
    
    # Debug settings
    DEBUG_MODE = config["debug"]["enabled"]
    
    # Default Ollama instance config (will be auto-detected if auto_detect is True)
    OLLAMA_INSTANCES = [{"url": OLLAMA_API_URL, "model": OLLAMA_MODEL}]
    NUM_WORKERS = 1

def load_metadata_csv():
    """Load and parse the metadata CSV file into a dictionary for fast lookups.
    The CSV must have at minimum 'document_id' and 'headline' columns.
    Returns a dictionary mapping document_id -> headline for quick filtering.
    """
    global METADATA_CACHE
    
    if not ENABLE_METADATA_FILTERING or not METADATA_CSV_PATH:
        print("Metadata filtering is disabled or no CSV path provided.")
        return {}
    
    if METADATA_CACHE:  # Return cached data if already loaded
        return METADATA_CACHE
    
    try:
        metadata = {}
        print(f"Loading metadata from: {METADATA_CSV_PATH}")
        with open(METADATA_CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'document_id' in row and 'headline' in row:
                    metadata[row['document_id']] = row['headline'].lower()
        
        print(f"Loaded metadata for {len(metadata)} documents")
        METADATA_CACHE = metadata
        return metadata
    
    except Exception as e:
        print(f"Error loading metadata CSV: {e}")
        return {}

def extract_document_id(filename):
    """Extract document ID from a PDF filename using the pattern in configuration.
    Returns None if no ID could be extracted.
    """
    if not ENABLE_METADATA_FILTERING or not ID_EXTRACTION_PATTERN:
        return None
    
    try:
        match = re.search(ID_EXTRACTION_PATTERN, os.path.basename(filename))
        if match:
            return f"key_{match.group(1)}"
        return None
    except Exception as e:
        print(f"Error extracting document ID from {filename}: {e}")
        return None

def should_skip_document(filename):
    """Check if a document should be skipped based on metadata.
    Returns True if document should be skipped, False otherwise.
    """
    if not ENABLE_METADATA_FILTERING:
        return False
    
    # Load metadata if not already loaded
    metadata = load_metadata_csv()
    if not metadata:
        # If we can't load metadata, don't skip any documents
        return False
    
    # Extract document ID
    doc_id = extract_document_id(filename)
    if not doc_id or doc_id not in metadata:
        # If we can't extract ID or ID not in metadata, don't skip
        if DEBUG_MODE:
            print(f"Document ID {doc_id} not found in metadata for {filename}")
        return False
    
    # Check headline against skip terms
    headline = metadata[doc_id]
    for term in SKIP_TERMS:
        if term.lower() in headline.lower():
            print(f"Skipping {filename} due to metadata filter: '{term}' found in headline")
            return True
    
    return False

# Initialize with default config
load_config()

def convert_pdf_page_to_image(pdf_path, page_num, scale=IMAGE_SCALE_FACTOR):
    """Convert a PDF page to a PIL Image using PyMuPDF."""
    try:
        doc = fitz.open(pdf_path)
        if page_num >= len(doc):
            # This case should ideally not be hit if page_num is managed correctly by the caller
            print(f"Warning: Page number {page_num} is out of range for PDF '{pdf_path}' with {len(doc)} pages.")
            doc.close()
            return None
        page = doc[page_num]

        matrix = fitz.Matrix(scale, scale)
        pixmap = page.get_pixmap(matrix=matrix)

        img_data = pixmap.samples
        img = Image.frombytes("RGB", [pixmap.width, pixmap.height], img_data)

        doc.close()
        return img
    except Exception as e:
        print(f"Error converting PDF page {page_num} of '{pdf_path}' to image: {e}")
        return None

def extract_text_from_pdf_for_support(pdf_path, max_pages=MAX_TEXT_PAGES_FOR_SUPPORT):
    """Extract text from the initial pages of a PDF to assist image-based extraction."""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        # Ensure max_pages is not None and is positive before using it with min
        pages_to_extract_count = len(doc)
        if max_pages is not None and max_pages > 0:
             pages_to_extract_count = min(len(doc), max_pages)

        for page_num in range(pages_to_extract_count):
            text += doc[page_num].get_text() + "\n\n" # Add separator for readability
        doc.close()
        return text
    except Exception as e:
        print(f"Error extracting supporting text from PDF '{pdf_path}': {e}")
        return ""

def normalize_credential(name):
    """Normalize author name with credentials to a standard format."""
    if not name: return ""
    name = str(name) # Ensure name is a string
    # Normalize spacing around commas
    name = re.sub(r'\s*,\s*', ', ', name)
    # Ensure consistent capitalization for credentials
    name = re.sub(r'(?i)\bcfa\b', 'CFA', name)
    name = re.sub(r'(?i)\bphd\b', 'PhD', name)
    name = re.sub(r'(?i)\bmd\b', 'MD', name) # Added MD
    # Add more credentials if needed, e.g., Esq, etc.
    return name.strip()

def clean_author_name(name):
    """Clean author name by removing document metadata and other extraneous text."""
    if not name:
        return ""
    name = str(name) # Ensure name is a string

    MAX_NAME_LENGTH = 70

    metadata_keywords = [
        "SECURITIES", "LLC", "EQUITY", "RESEARCH", "DEPARTMENT",
        "Newsletter", "WELLS FARGO", "Corporation", "CORP",
        "INC", "LTD", "COMPANY", "SECTION", "CONTENTS", "DISCLAIMER",
        "DISCLOSURES", "PUBLICATION", "PAGE", "REPORT", "TMT",
        "Edition", "Conference", "Market", "GLOBAL", "STRATEGY",
        "INVESTMENT", "BANKING", "GROUP", "ASSOCIATES", "ANALYSIS",
        "CONTACT", "INFORMATION", "APPENDIX", "INDEX"
    ]

    name = ' '.join(name.split()) # Preliminary cleaning: remove excessive whitespace

    if len(name) > MAX_NAME_LENGTH:
        delimiters = [", Ph.D.", ", PhD", ", CFA", ", M.D.", ", MD", "\n", " ("]
        original_name = name
        for delim_full in delimiters:
            delim_base = delim_full.split(",")[0].strip()
            if delim_full.lower() in name.lower():
                parts = re.split(f'({re.escape(delim_base)}[^a-zA-Z]?)', name, 1, flags=re.IGNORECASE)
                if len(parts) > 1:
                    name = parts[0] + parts[1]
                    break
        if name == original_name and len(name) > MAX_NAME_LENGTH: # If no delimiter found or still too long
            name_parts = name.split(',')
            if len(name_parts) > 1:
                if not any(cred.lower() in name_parts[1].lower() for cred in ["CFA", "PhD", "MD", "Analyst", "Director"]):
                    name = name_parts[0].strip()

    for keyword in metadata_keywords:
        name = re.sub(fr'\b{re.escape(keyword)}\b.*$', '', name, flags=re.IGNORECASE).strip()
        if name.upper().startswith(keyword + " "):
             name = re.sub(fr'^{re.escape(keyword)}\s*', '', name, flags=re.IGNORECASE).strip()

    name = name.strip("., \t\n")
    name = normalize_credential(name)

    if len(name) > MAX_NAME_LENGTH:
        name = ' '.join(name.split()[:5]) # Truncate if still too long
        name = name.strip("., \t\n")
        name = normalize_credential(name)

    if not re.search(r'\b(Jr\.?|Sr\.?|I{2,3}|IV|V)\b', name, re.IGNORECASE): # Allow Jr/Sr/Roman numerals
        name = re.sub(r'\d+', '', name).strip() # Remove other digits

    name = ' '.join(name.split())
    return name


def standardize_credentials_in_authors(authors):
    """Standardize credential format and remove duplicates with different credential formats."""
    if not authors: return []
    name_map = {}

    for author_obj in authors:
        name = author_obj.get("name", "")
        if not name:
            continue

        name = normalize_credential(name)
        author_obj["name"] = name

        base_name_parts = []
        temp_name = name
        # More robustly remove credentials for base_name generation
        creds_to_strip = ["CFA", "PhD", "MD"] # Add other common credentials here
        for cred in creds_to_strip:
            temp_name = re.sub(r",\s*" + re.escape(cred) + r"\b", "", temp_name, flags=re.IGNORECASE)
            temp_name = re.sub(r"\s+" + re.escape(cred) + r"\b", "", temp_name, flags=re.IGNORECASE) # if no comma

        base_name = temp_name.split(',')[0].strip().lower()

        if not base_name:
            continue

        if base_name not in name_map:
            name_map[base_name] = author_obj
        else:
            existing_author = name_map[base_name]
            existing_name = existing_author.get("name", "")

            current_creds_set = set(re.findall(r"(CFA|PhD|MD)", name, re.IGNORECASE))
            existing_creds_set = set(re.findall(r"(CFA|PhD|MD)", existing_name, re.IGNORECASE))

            if len(current_creds_set) > len(existing_creds_set) or \
               (len(current_creds_set) == len(existing_creds_set) and len(name) > len(existing_name)):
                # Current entry is better, replace, but try to merge title/email
                new_author_obj = author_obj.copy() # Work on a copy
                if not new_author_obj.get("title") and existing_author.get("title"):
                    new_author_obj["title"] = existing_author.get("title")
                if not new_author_obj.get("email") and existing_author.get("email"):
                    new_author_obj["email"] = existing_author.get("email")
                name_map[base_name] = new_author_obj
            else:
                # Existing entry is better or same, try to merge title/email into existing
                if not existing_author.get("title") and author_obj.get("title"):
                    existing_author["title"] = author_obj.get("title")
                if not existing_author.get("email") and author_obj.get("email"):
                    existing_author["email"] = author_obj.get("email")
                # Merge credentials if new one has some not in existing
                all_creds = existing_creds_set.union(current_creds_set)
                if all_creds != existing_creds_set:
                    # Reconstruct name for existing_author with all credentials
                    base_part_of_existing = re.sub(r"(,\s*(CFA|PhD|MD))+", "", existing_name, flags=re.IGNORECASE).split(',')[0].strip()
                    if all_creds:
                         existing_author["name"] = base_part_of_existing + ", " + ", ".join(sorted(list(c.upper() for c in all_creds)))
                    else:
                         existing_author["name"] = base_part_of_existing


    return list(name_map.values())


def escape_for_regex(text):
    """Escape LaTeX commands and other problematic characters for regex."""
    if not text:  # Add null check
        return ""
        
    # Replace common LaTeX commands with placeholders
    replacements = [
        (r'\\hline', '_HLINE_'),
        (r'\\begin', '_BEGIN_'),
        (r'\\end', '_END_'),
        (r'\\section', '_SECTION_'),
        (r'\\\\', '_NEWLINE_'),
        (r'\\tabular', '_TABULAR_'),
        (r'\\multicolumn', '_MULTICOL_'),
        (r'\\cite', '_CITE_'),
        (r'\\ref', '_REF_')
    ]
    
    for pattern, replacement in replacements:
        text = text.replace(pattern, replacement)
    
    return text

def detect_document_type(text):
    """Detect if document is a compilation report with multiple authors."""
    # Use escaped text to prevent regex issues
    if not text:  # Add null check
        return "standard"
        
    text = escape_for_regex(text)
    
    try:
        # Check for patterns indicating a compilation report
        toc_patterns = [
            r"(?i)Page\s+Headline\s+Analyst",
            r"(?i)Table of Contents.*Analyst",
            r"(?i)SECTION.*AUTHOR",
            r"(?i)Contents.*Author",
            r"(?i)Analyst:\s*[A-Z][a-z]+", 
            r"(?i)\|\s*Analyst\s*\|"
        ]
        
        for pattern in toc_patterns:
            if re.search(pattern, text):
                return "compilation"
        
        # Check for termination of coverage reports - they typically don't have individual authors
        termination_patterns = [
            r"(?i)Termination of Coverage",
            r"(?i)owing to the (?:primary )?analyst's departure",
            r"(?i)we are [tT]erminating [cC]overage",
            r"(?i)terminating coverage for the following names",
            r"(?i)terminating our coverage of",
            r"(?i)terminating research coverage" 
        ]
        
        for pattern in termination_patterns:
            if re.search(pattern, text):
                print("Detected termination of coverage report - may not have individual authors")
                return "termination"
                
        return "standard"
    except re.error as e:
        print(f"Warning: Regex error in detect_document_type: {e}")
        return "standard"

def identify_institution(text):
    """Identify the institution that published the report."""
    if not text:  # Add null check
        return None, None
        
    institutions = {
        "stephens": "stephens.com",
        "wells fargo": "wellsfargo.com",
        "morgan stanley": "morganstanley.com",
        "goldman sachs": "gs.com",
        "jp morgan": "jpmorgan.com",
        "credit suisse": "credit-suisse.com",
        "ubs": "ubs.com",
        "barclays": "barclays.com",
        "citigroup": "citi.com",
        "deutsche bank": "db.com",
        "bank of america": "bofa.com",
        "jefferies": "jefferies.com",
        "cowen": "cowen.com"
    }
    
    for institution, domain in institutions.items():
        if institution.lower() in text.lower():
            return institution, domain
    
    return None, None

def is_institutional_author(name, title=None, email=None):
    """Determine if an author is actually an institutional entity rather than a person."""
    if not name:
        return False
        
    # Institutional department patterns
    institutional_patterns = [
        r"(?i)Research\s+(?:Analysts|Department)",
        r"(?i)[A-Z]{2,}\s+(?:US\s+)?Eq\.\s+Res",
        r"(?i)Equity\s+Research",
        r"(?i)Securities\s+Research",
        r"(?i)Investment\s+Research",
        r"(?i)Global\s+Research",
        r"(?i)Research\s+Team",
        r"(?i)Research\s+Desk"
    ]
    
    # Check name against institutional patterns
    for pattern in institutional_patterns:
        if re.search(pattern, name):
            return True
    
    # Check if the name follows specific departmental formats
    institutional_keywords = [
        "US Eq. Res", "Eq. Res", "Research Team", "Research Dept", 
        "Equity Research", "Global Research", "Research Division",
        "Research Analysts", "Credit Suisse Research"
    ]
    
    for keyword in institutional_keywords:
        if keyword.lower() in name.lower():
            return True
    
    # Check if email is a generic department email
    if email:
        generic_email_patterns = [
            r"(?i)equity\.research@",
            r"(?i)research@",
            r"(?i)info@",
            r"(?i)contact@",
            r"(?i)^[a-z]+@"  # Single word emails like "research@domain.com"
        ]
        for pattern in generic_email_patterns:
            if re.search(pattern, email):
                return True
    
    # Check if title suggests institutional attribution
    if title:
        institutional_title_patterns = [
            r"(?i)^Department$",
            r"(?i)^Team$", 
            r"(?i)^Group$"
        ]
        for pattern in institutional_title_patterns:
            if re.search(pattern, title):
                return True
    
    # Names with fewer than two parts (first and last) are suspicious
    parts = name.split()
    if len(parts) < 2:
        return True
        
    return False

def extract_authors_from_text_pattern(text, institution=None, doc_type=None):
    """Attempt to extract author information from text using institution-specific patterns."""
    if not text:
        return []
        
    authors = []
    
    # Credit Suisse specific pattern
    if institution and "credit suisse" in institution.lower():
        # Pattern: Name / Title / Phone / Email
        cs_pattern = r"([A-Z][a-z]+\s+[A-Z][a-zA-Z\-']+)\s*\/\s*([^/]+)\s*\/\s*([\d\s\+\-\.]+)\s*\/\s*([a-zA-Z0-9\.\-_]+@[a-zA-Z0-9\-_\.]+\.[a-zA-Z]{2,})"
        matches = re.findall(cs_pattern, text)
        
        for match in matches:
            name, title, phone, email = match
            if name and not is_institutional_author(name, title, email):
                authors.append({
                    "name": clean_author_name(name),
                    "title": title.strip() if title else "",
                    "email": email.strip() if email else ""
                })
    
    # Check for analyst patterns in termination notices
    if doc_type == "termination":
        # Pattern: looking for former analyst attributions
        analyst_pattern = r"(?:former|previous)\s+(?:analyst|author|coverage)\s+(?:was|by)?\s+([A-Z][a-z]+\s+[A-Z][a-zA-Z\-']+)"
        matches = re.findall(analyst_pattern, text, re.IGNORECASE)
        
        for match in matches:
            name = match
            if name and not is_institutional_author(name):
                authors.append({
                    "name": clean_author_name(name),
                    "title": "Former Analyst",
                    "email": ""
                })
    
    return authors

def correct_email_domain(email, institution_domain):
    """Correct the email domain if an institution domain is known."""
    if not email or not institution_domain:
        return email
        
    # Don't modify perfectly valid emails
    if "@" in email and "." in email.split("@")[1]:
        # Check if domain matches institution
        domain = email.split("@")[1].lower()
        if domain == institution_domain:
            return email
    
    # Try to extract username and append institution domain
    username_match = re.search(r'^([a-zA-Z0-9\.\-_]+)(?:@.+)?$', email)
    if username_match:
        username = username_match.group(1)
        return f"{username}@{institution_domain}"
    
    return email

def detect_ollama_instances() -> List[Dict[str, str]]:
    """Detect active Ollama instances by checking open ports."""
    base_port = 11434
    max_port = 11465  # Maximum port to check based on ollama_server_deployment.sh
    active_instances = []
    
    for port in range(base_port, max_port + 1):
        try:
            # Create a socket object
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.1)  # Short timeout for quick checking
            
            # Try to connect to the port
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            
            # If the port is open (result is 0), the server is likely running
            if result == 0:
                instance = {
                    "url": f"http://127.0.0.1:{port}/api/generate",
                    "model": OLLAMA_MODEL
                }
                active_instances.append(instance)
                if DEBUG_MODE:
                    print(f"Found Ollama instance at port {port}")
        except:
            pass  # Ignore any connection errors
    
    if not active_instances:
        # If no instances detected, use the default configuration
        print(f"No Ollama instances detected, using default: {OLLAMA_API_URL}")
        active_instances = [{"url": OLLAMA_API_URL, "model": OLLAMA_MODEL}]
    else:
        print(f"Detected {len(active_instances)} Ollama instance(s)")
    
    return active_instances

def process_image_with_ollama(image, page_num_display, total_pages_in_doc, supporting_text="", doc_type="standard", institution=None, ollama_instance=None):
    """Send image to Ollama model for author extraction. page_num_display is 1-based."""
    # Convert PIL image to base64
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    
    # Clean the supporting text to prevent issues
    supporting_text = escape_for_regex(supporting_text)[:300]  # Limit to catch context
    
    # Get prompt templates from config
    if "prompts" not in CONFIG:
        print("Warning: No prompts found in configuration. Using defaults.")
        # If no prompts in config, use built-in defaults (should never happen with proper config)
        CONFIG["prompts"] = {
            "compilation_report": CONFIG["prompts"]["compilation_report"] if "prompts" in CONFIG and "compilation_report" in CONFIG["prompts"] else """\
            Analyze this document image (page {page_num_display} of {total_pages_in_doc}) to identify only the TRUE AUTHORS of the research report sections.\
            [... default compilation prompt ...]\
            """,
            "standard_report": CONFIG["prompts"]["standard_report"] if "prompts" in CONFIG and "standard_report" in CONFIG["prompts"] else """\
            Analyze this document image (page {page_num_display} of {total_pages_in_doc}) to identify only the true authors of the document.\
            [... default standard prompt ...]\
            """,
            "credit_suisse_specific": CONFIG["prompts"]["credit_suisse_specific"] if "prompts" in CONFIG and "credit_suisse_specific" in CONFIG["prompts"] else """\
            This is a Credit Suisse research report. Credit Suisse often formats author information like:\
            [... default Credit Suisse pattern ...]\
            """,
            "first_page_emphasis": CONFIG["prompts"]["first_page_emphasis"] if "prompts" in CONFIG and "first_page_emphasis" in CONFIG["prompts"] else """\
            THIS IS THE FIRST PAGE where authors typically appear at the very top. Focus on the top section only.\
            """,
            "termination_specific": CONFIG["prompts"]["termination_specific"] if "prompts" in CONFIG and "termination_specific" in CONFIG["prompts"] else """\
            This appears to be a termination of coverage report which may not have individual analysts assigned.\
            [... default termination prompt ...]\
            """
        }
    
    # Additional instructions based on the institution
    institution_specific = ""
    if institution:
        if "credit suisse" in institution.lower():
            institution_specific = CONFIG["prompts"]["credit_suisse_specific"]
        else:
            institution_specific = f"This is a research report from {institution}. "
    
    # First page gets a more specific prompt
    is_first_page = page_num_display == 1
    first_page_emphasis = CONFIG["prompts"]["first_page_emphasis"] if is_first_page else ""
    
    # Additional instructions for termination of coverage reports
    termination_specific = ""
    if doc_type == "termination":
        termination_specific = CONFIG["prompts"]["termination_specific"]
    
    # Format the variables in the prompt template
    template_vars = {
        "page_num_display": page_num_display,
        "total_pages_in_doc": total_pages_in_doc,
        "institution_specific": institution_specific,
        "first_page_emphasis": first_page_emphasis,
        "supporting_text": supporting_text,
        "termination_specific": termination_specific
    }
    
    # Adjust prompt based on document type
    if doc_type == "compilation":
        prompt_template = CONFIG["prompts"]["compilation_report"]
    else:
        prompt_template = CONFIG["prompts"]["standard_report"]
    
    # Format the prompt with the template variables
    prompt = prompt_template.format(**template_vars)
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "images": [img_base64],
        "stream": False,
        "format": "json"
    }

    # Use the specified Ollama instance if provided
    api_url = ollama_instance["url"] if ollama_instance else OLLAMA_API_URL

    try:
        response = requests.post(api_url, json=payload, timeout=OLLAMA_TIMEOUT)
        response.raise_for_status()
        result = response.json()

        if "response" in result:
            try:
                author_data = json.loads(result["response"])
                return author_data.get("authors", [])
            except json.JSONDecodeError as jde:
                print(f"  Error parsing JSON response from Ollama for page {page_num_display}: {jde}")
                print(f"  Ollama raw response snippet: {result['response'][:500]}")
                return []
        else:
            print(f"  Unexpected response format from Ollama for page {page_num_display}: {result}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"  Error communicating with Ollama for page {page_num_display}: {e}")
        return []
    except Exception as e:
        print(f"  An unexpected error occurred while processing with Ollama for page {page_num_display}: {e}")
        return []

def clean_author_data_list(authors_list):
    """Clean a list of author dicts: apply name cleaning, title cleaning, and filter out non-authors."""
    if not authors_list:
        return []
    
    cleaned_authors_accumulator = []
    for author in authors_list:
        if not isinstance(author, dict):
            print(f"  Skipping non-dict item in authors_list: {author}")
            continue

        cleaned_name = clean_author_name(author.get("name", ""))
        
        if not cleaned_name or len(cleaned_name.split()) < 2:
            # Allow single word names if they are likely last names found on TOCs, etc.
            # but for LLM output, usually expect First Last.
            if len(cleaned_name) < 3 : # Skip very short names like initials if alone
                print(f"  Skipping very short or empty name after cleaning: '{cleaned_name}' from '{author.get('name', '')}'")
                continue
        
        cleaned_title = author.get("title", "")
        if cleaned_title and isinstance(cleaned_title, str):
            cleaned_title = re.sub(r'\s*\([^)]*\)', '', cleaned_title).strip()
            cleaned_title = re.sub(r'(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}', '', cleaned_title).strip()
            cleaned_title = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', cleaned_title).strip()
            cleaned_title = ' '.join(cleaned_title.split())

            for cred in ["CFA", "PhD", "MD"]:
                if re.search(fr'\b{cred}\b', cleaned_title, re.IGNORECASE) and not re.search(fr'\b{cred}\b', cleaned_name, re.IGNORECASE):
                    cleaned_name = f"{cleaned_name}, {cred.upper()}" # Use .upper() for consistency
                    cleaned_title = re.sub(fr'(?i)\s*,?\s*\b{cred}\b', '', cleaned_title).strip() # Remove from title
            cleaned_name = normalize_credential(cleaned_name)
            cleaned_title = ' '.join(cleaned_title.split())

        non_author_keywords_in_name = [
            "Securities", "Equity", "Research", "Capital", "Markets", "Group", "LLC", "Inc.",
            "Limited", "Advisors", "Asset", "Management", "Financial", "Bank", "Investment",
            "Corporation", "Department", "Contents", "Disclaimer", "Publication", "Report"
        ]
        # If the cleaned name itself is one of these keywords or mostly consists of them
        name_words = set(w.lower() for w in cleaned_name.split())
        keyword_words = set(kw.lower() for kw in non_author_keywords_in_name)
        if name_words.intersection(keyword_words) and len(cleaned_name.split()) <=3:
             if not any(n_part.endswith(',') for n_part in cleaned_name.split()): # check if it's like "Name, CFA"
                print(f"  Skipping likely non-author name (keyword match): '{cleaned_name}'")
                continue
        
        if cleaned_name.upper() in ["CFA", "PHD", "MD", "ANALYST", "AUTHOR", "CONTACT", "TEAM"]:
            print(f"  Skipping likely non-author name (is a credential/role): '{cleaned_name}'")
            continue
        if re.match(r"^[A-Z\s.,&'-]+$", cleaned_name) and len(cleaned_name.split()) > 4:
             if not any(kw.lower() in cleaned_name.lower() for kw in ["jr", "sr", "iii", "iv"]):
                # print(f"  Skipping potential non-author name (all caps, long): {cleaned_name}") # Too noisy
                pass # Reconsider this rule, might filter valid names if they are typed in ALL CAPS.

        email = author.get("email", "")
        if email and isinstance(email, str):
            # Extract first valid email if multiple are concatenated
            email_match = re.search(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", email)
            email = email_match.group(1) if email_match else ""
        else:
            email = ""

        cleaned_authors_accumulator.append({
            "name": cleaned_name,
            "title": cleaned_title if cleaned_title else "", # Ensure empty string not None
            "email": email
        })
    return cleaned_authors_accumulator

def prioritize_first_page_authors(all_authors, page_authors_map):
    """Give higher priority to authors found on the first page."""
    if not PRIORITIZE_FIRST_PAGE or not all_authors or not page_authors_map or 0 not in page_authors_map:
        return all_authors
        
    # Get authors from the first page
    first_page_authors = page_authors_map.get(0, [])
    if not first_page_authors:
        return all_authors
        
    # Extract base names without credentials for matching
    first_page_base_names = set()
    for author in first_page_authors:
        if not author.get("name"):
            continue
        # Remove credentials for base name comparison
        base_name = re.sub(r',\s*(?:CFA|PhD|MD).*$', '', author.get("name", "")).strip().lower()
        first_page_base_names.add(base_name)
    
    # Reorder authors to prioritize those found on the first page
    prioritized_authors = []
    remaining_authors = []
    
    for author in all_authors:
        # Get base name without credentials
        base_name = re.sub(r',\s*(?:CFA|PhD|MD).*$', '', author.get("name", "")).strip().lower()
        
        if base_name in first_page_base_names:
            prioritized_authors.append(author)
        else:
            remaining_authors.append(author)
    
    # Combine prioritized authors first, then remaining
    return prioritized_authors + remaining_authors

def validate_emails(authors, institution_domain):
    """Validate and correct email domains."""
    if not ENABLE_EMAIL_VALIDATION or not authors or not institution_domain:
        return authors
        
    for author in authors:
        if "email" in author and author["email"]:
            author["email"] = correct_email_domain(author["email"], institution_domain)
    
    return authors

def extract_authors_from_pdf(pdf_path):
    """Process pages of a PDF with Ollama and extract author information."""
    print(f"Processing PDF: {pdf_path}")
    all_authors_from_pages = []
    page_authors_map = {}  # Track which page authors were found on
    
    try:
        # Extract text from the PDF for context
        supporting_text = extract_text_from_pdf_for_support(pdf_path, max_pages=MAX_TEXT_PAGES_FOR_SUPPORT)
        
        # Document type detection and institution identification if enabled
        doc_type = "standard"
        institution = None
        institution_domain = None
        
        if ENABLE_DOCUMENT_TYPE_DETECTION:
            doc_type = detect_document_type(supporting_text)
            if doc_type != "standard":
                print(f"  Detected document type: {doc_type}")
        
        if ENABLE_INSTITUTION_DETECTION:
            institution, institution_domain = identify_institution(supporting_text)
            if institution:
                print(f"  Detected institution: {institution} ({institution_domain})")
        
        # For specific institutions with known formats, try text-based extraction as fallback
        text_authors = []
        if institution:
            text_authors = extract_authors_from_text_pattern(supporting_text, institution, doc_type)
            if text_authors:
                print(f"  Found {len(text_authors)} authors through text pattern matching")
        
        # Open the PDF to get page count
        doc_for_page_count = fitz.open(pdf_path)
        total_pages_in_doc = len(doc_for_page_count)
        doc_for_page_count.close()
        
        # --- LOGIC TO DETERMINE PAGES TO SCAN ---
        mode = PAGE_PROCESSING_CONFIG.get("mode", "all")
        always_include_first = PAGE_PROCESSING_CONFIG.get("always_include_first", True)
        pages_to_scan = []
        
        if mode == "all":
            pages_to_scan = list(range(total_pages_in_doc))  # All pages, 0-based indices
            print(f"  Configured to process ALL {total_pages_in_doc} page(s) with Ollama.")
        
        elif mode == "first_n":
            first_n = PAGE_PROCESSING_CONFIG.get("first_n", 0)
            if first_n <= 0:  # Treat as 'all' if 0 or negative
                pages_to_scan = list(range(total_pages_in_doc))
                print(f"  Configured to process ALL {total_pages_in_doc} page(s) with Ollama.")
            else:
                pages_to_scan = list(range(min(first_n, total_pages_in_doc)))
                print(f"  Configured to process first {first_n} page(s); will process {len(pages_to_scan)} page(s) with Ollama.")
        
        elif mode == "range":
            # Range is 1-based in config, convert to 0-based for internal use
            page_range = PAGE_PROCESSING_CONFIG.get("range", [1, 1])
            start_page = max(0, page_range[0] - 1)  # Convert to 0-based, ensure non-negative
            end_page = min(total_pages_in_doc - 1, page_range[1] - 1)  # Convert to 0-based, ensure in range
            
            if start_page <= end_page and start_page < total_pages_in_doc:
                pages_to_scan = list(range(start_page, end_page + 1))
                print(f"  Configured to process pages {page_range[0]}-{page_range[1]}; will process {len(pages_to_scan)} page(s) with Ollama.")
            else:
                # Invalid range, default to just page 1
                pages_to_scan = [0] if total_pages_in_doc > 0 else []
                print(f"  Invalid page range specified: {page_range}. Defaulting to first page.")
        
        # Always include the first page if specified and not already included
        if always_include_first and 0 not in pages_to_scan and total_pages_in_doc > 0:
            pages_to_scan.insert(0, 0)  # Add page 0 (first page) to the beginning
            print("  Added first page to processing list due to always_include_first setting.")
            
        # Sort pages to process them in order
        pages_to_scan.sort()
        
        # Now process each selected page
        for page_idx in pages_to_scan:  # page_idx is 0-based
            page_num_display = page_idx + 1 # For user messages, 1-based
            print(f"  Processing page {page_num_display}/{total_pages_in_doc} with Ollama...")
            
            image = convert_pdf_page_to_image(pdf_path, page_idx) # Use 0-based index for fitz
            if image is None:
                print(f"  Skipping page {page_num_display} due to image conversion error.")
                continue
            
            # Process image with Ollama using document type and institution info
            authors_on_page = process_image_with_ollama(
                image, 
                page_num_display, 
                total_pages_in_doc, 
                supporting_text,
                doc_type,
                institution
            )
            
            # Clean the author data, filtering out institutional authors
            cleaned_authors_on_page = clean_author_data_list(authors_on_page)
            
            # Store authors found on this page
            page_authors_map[page_idx] = cleaned_authors_on_page.copy() if cleaned_authors_on_page else []
            
            if cleaned_authors_on_page:
                print(f"    Found {len(cleaned_authors_on_page)} potential author entry(s) on page {page_num_display}.")
                all_authors_from_pages.extend(cleaned_authors_on_page)
            else:
                print(f"    No authors identified by Ollama on page {page_num_display}.")
        
        # If no authors found through image processing, try using text-based extraction
        if not all_authors_from_pages and text_authors:
            print("  Using text-based extraction results as no authors found through image processing")
            all_authors_from_pages = text_authors
            
        print(f"  Collected {len(all_authors_from_pages)} raw author entries from processed pages.")
        
        # Final filtering for institutional authors
        filtered_authors = []
        for author in all_authors_from_pages:
            if author and author.get("name") and not is_institutional_author(
                author.get("name"), author.get("title"), author.get("email")
            ):
                filtered_authors.append(author)
            elif author and author.get("name"):
                print(f"  Filtering out institutional author: {author.get('name')}")
        
        all_authors_from_pages = filtered_authors
        print(f"  After filtering institutional authors: {len(all_authors_from_pages)} entries.")
        
        # Prioritize authors found on first page
        if PRIORITIZE_FIRST_PAGE and all_authors_from_pages and page_authors_map:
            all_authors_from_pages = prioritize_first_page_authors(all_authors_from_pages, page_authors_map)
            print("  Prioritized authors from first page.")
        
        # Validate and correct email domains
        if ENABLE_EMAIL_VALIDATION and all_authors_from_pages and institution_domain:
            all_authors_from_pages = validate_emails(all_authors_from_pages, institution_domain)
            print("  Validated and corrected email domains.")
            
        # Standardize credentials and deduplicate
        final_authors = standardize_credentials_in_authors(all_authors_from_pages)
        print(f"  After standardization and deduplication: {len(final_authors)} unique author(s).")
        
        return final_authors
    
    except Exception as e:
        print(f"General error processing PDF '{pdf_path}': {e}")
        traceback.print_exc()
        return []


def determine_max_authors_columns(output_csv_path, current_run_authors_count):
    """Determine maximum number of author sets (name, title, email) needed for CSV columns."""
    max_sets = max(5, current_run_authors_count) 
    
    if os.path.isfile(output_csv_path):
        try:
            with open(output_csv_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header:
                    author_name_cols = sum(1 for col in header if col.startswith('author_') and col.endswith('_name'))
                    max_sets = max(max_sets, author_name_cols)
        except Exception as e:
            print(f"Warning: Could not read existing CSV header from {output_csv_path} to determine max authors: {e}")
    return max_sets

def write_to_csv(pdf_filename, authors_data, output_csv_path=OUTPUT_CSV_FILENAME):
    """Write extracted author data to CSV, updating if filename exists, extending columns if needed."""
    base_pdf_filename = os.path.splitext(os.path.basename(pdf_filename))[0]
    max_author_sets = determine_max_authors_columns(output_csv_path, len(authors_data))
    
    header = ["filename"]
    for i in range(1, max_author_sets + 1):
        header.extend([f"author_{i}_name", f"author_{i}_title", f"author_{i}_email"])
    
    current_row_data = [base_pdf_filename]
    for i in range(max_author_sets):
        if i < len(authors_data):
            author = authors_data[i]
            current_row_data.extend([
                author.get("name", ""),
                author.get("title", ""),
                author.get("email", "")
            ])
        else:
            current_row_data.extend(["", "", ""])

    rows_to_write = []
    file_exists = os.path.isfile(output_csv_path)
    header_to_use = header # Default to the newly generated header

    if file_exists:
        with open(output_csv_path, 'r', newline='', encoding='utf-8') as f_read:
            reader = csv.reader(f_read)
            try:
                existing_header = next(reader)
                if len(existing_header) >= len(header): # Use existing header if it's wider or same
                    header_to_use = existing_header
                # else new header is wider, so existing_header will be replaced by header_to_use (which is 'header')

                rows_to_write.append(header_to_use) # Add the determined header first
                found_and_updated = False
                for row in reader:
                    if not row: continue
                    # Pad row if it's shorter than the header we are using
                    if len(row) < len(header_to_use):
                        row.extend([""] * (len(header_to_use) - len(row)))

                    if row[0] == base_pdf_filename:
                        # Ensure current_row_data matches the width of header_to_use
                        padded_current_row = current_row_data[:len(header_to_use)] + \
                                             [""] * (len(header_to_use) - len(current_row_data))
                        rows_to_write.append(padded_current_row)
                        found_and_updated = True
                    else:
                        rows_to_write.append(row[:len(header_to_use)]) # Ensure row is not wider than header
                if not found_and_updated:
                    padded_current_row = current_row_data[:len(header_to_use)] + \
                                         [""] * (len(header_to_use) - len(current_row_data))
                    rows_to_write.append(padded_current_row)

            except StopIteration: # Empty file
                rows_to_write.append(header_to_use)
                padded_current_row = current_row_data[:len(header_to_use)] + \
                                     [""] * (len(header_to_use) - len(current_row_data))
                rows_to_write.append(padded_current_row)
            except Exception as e:
                print(f"Error reading existing CSV {output_csv_path}: {e}. Will create/overwrite with new data.")
                rows_to_write = [header_to_use]
                padded_current_row = current_row_data[:len(header_to_use)] + \
                                     [""] * (len(header_to_use) - len(current_row_data))
                rows_to_write.append(padded_current_row)
    else: # File does not exist
        rows_to_write.append(header_to_use)
        padded_current_row = current_row_data[:len(header_to_use)] + \
                             [""] * (len(header_to_use) - len(current_row_data))
        rows_to_write.append(padded_current_row)
    try:
        with open(output_csv_path, 'w', newline='', encoding='utf-8') as f_write:
            writer = csv.writer(f_write)
            writer.writerows(rows_to_write)
    except IOError as e:
        print(f"Error writing to CSV file {output_csv_path}: {e}")


def process_pdf_with_instance(pdf_file: str, output_csv: str, ollama_instance: Dict[str, str]):
    """Process a single PDF file using a specific Ollama instance."""
    try:
        # Extract just the PDF filename without path
        pdf_filename = os.path.basename(pdf_file)
        
        # Check if the document should be skipped based on metadata
        if ENABLE_METADATA_FILTERING and should_skip_document(pdf_file):
            print(f"Skipping {pdf_filename} based on metadata filtering")
            return pdf_file, []
            
        print(f"Processing '{pdf_filename}' with Ollama instance at {ollama_instance['url']}")
        
        # Custom extract_authors implementation that uses the specified Ollama instance
        def extract_with_instance(page_idx, image, page_num_display, total_pages, supporting_text, doc_type, institution):
            return process_image_with_ollama(
                image, page_num_display, total_pages, 
                supporting_text, doc_type, institution, 
                ollama_instance
            )
        
        # Extract text from the PDF for context
        supporting_text = extract_text_from_pdf_for_support(pdf_file, max_pages=MAX_TEXT_PAGES_FOR_SUPPORT)
        
        # Document type detection and institution identification if enabled
        doc_type = "standard"
        institution = None
        institution_domain = None
        
        if ENABLE_DOCUMENT_TYPE_DETECTION:
            doc_type = detect_document_type(supporting_text)
            if doc_type != "standard":
                print(f"  Detected document type: {doc_type}")
        
        if ENABLE_INSTITUTION_DETECTION:
            institution, institution_domain = identify_institution(supporting_text)
            if institution:
                print(f"  Detected institution: {institution}")
        
        # For specific institutions with known formats, try text-based extraction
        text_authors = []
        if institution:
            text_authors = extract_authors_from_text_pattern(supporting_text, institution, doc_type)
        
        # Open the PDF to get page count
        doc = fitz.open(pdf_file)
        total_pages_in_doc = len(doc)
        
        # Pages to process
        if PAGES_TO_PROCESS_PER_PDF is None or PAGES_TO_PROCESS_PER_PDF <= 0:
            pages_to_scan = total_pages_in_doc
        else:
            pages_to_scan = min(total_pages_in_doc, PAGES_TO_PROCESS_PER_PDF)
        
        all_authors_from_pages = []
        page_authors_map = {}
        
        # Process each page
        for page_idx in range(pages_to_scan):
            page_num_display = page_idx + 1
            
            image = convert_pdf_page_to_image(pdf_file, page_idx)
            if image is None:
                continue
                
            # Process with the specified instance
            authors_on_page = extract_with_instance(
                page_idx, image, page_num_display, total_pages_in_doc,
                supporting_text, doc_type, institution
            )
            
            # Clean and store authors
            cleaned_authors = clean_author_data_list(authors_on_page)
            page_authors_map[page_idx] = cleaned_authors.copy() if cleaned_authors else []
            
            if cleaned_authors:
                all_authors_from_pages.extend(cleaned_authors)
        
        doc.close()
        
        # Use text extraction if image-based extraction failed
        if not all_authors_from_pages and text_authors:
            all_authors_from_pages = text_authors
        
        # Final processing steps
        filtered_authors = [a for a in all_authors_from_pages if a.get("name") and 
                         not is_institutional_author(a.get("name"), a.get("title"), a.get("email"))]
        
        # Prioritize first page authors if enabled
        if PRIORITIZE_FIRST_PAGE and filtered_authors and page_authors_map:
            filtered_authors = prioritize_first_page_authors(filtered_authors, page_authors_map)
        
        # Validate emails if enabled
        if ENABLE_EMAIL_VALIDATION and filtered_authors and institution_domain:
            filtered_authors = validate_emails(filtered_authors, institution_domain)
        
        # Standardize credentials
        final_authors = standardize_credentials_in_authors(filtered_authors)
        
        # Save to CSV
        if final_authors:
            write_to_csv(pdf_file, final_authors, output_csv)
        
        return pdf_file, final_authors
            
    except Exception as e:
        print(f"Error processing {pdf_file}: {e}")
        traceback.print_exc()
        return pdf_file, []


def get_processed_files(csv_path):
    """Read the output CSV to get a list of already processed files.
    
    Args:
        csv_path: Path to the output CSV file
        
    Returns:
        Set of absolute paths of already processed files
    """
    processed_files = set()
    
    # If the file doesn't exist or we're not skipping processed files
    if not os.path.exists(csv_path) or not SKIP_PROCESSED_FILES:
        return processed_files
    
    try:
        with open(csv_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            # Skip header
            next(reader, None)
            for row in reader:
                if row and len(row) > 0:
                    # First column should be the file path
                    file_path = row[0]
                    processed_files.add(os.path.abspath(file_path))
                    
        print(f"Found {len(processed_files)} previously processed files in {csv_path}")
    except Exception as e:
        print(f"Error reading processed files from {csv_path}: {e}")
    
    return processed_files


def process_folder(folder_path, output_csv=OUTPUT_CSV_FILENAME):
    """Process all PDFs in a folder using multiple Ollama instances in parallel."""
    print(f"Processing all PDFs in folder: {folder_path}")
    pdf_files = []
    
    try:
        for filename in os.listdir(folder_path):
            if filename.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(folder_path, filename))
    except Exception as e:
        print(f"Error listing directory {folder_path}: {e}")
        return
    
    if not pdf_files:
        print(f"No PDF files found in {folder_path}")
        return
        
    # Get already processed files from output CSV
    processed_files = get_processed_files(output_csv)
    
    # Filter out already processed files if requested
    original_count = len(pdf_files)
    if SKIP_PROCESSED_FILES and processed_files:
        pdf_files = [f for f in pdf_files if os.path.abspath(f) not in processed_files]
        print(f"Filtered out {original_count - len(pdf_files)} already processed files")
    
    # Limit to max_files if specified
    if MAX_FILES > 0 and len(pdf_files) > MAX_FILES:
        print(f"Limiting to {MAX_FILES} files out of {len(pdf_files)} available")
        pdf_files = pdf_files[:MAX_FILES]
    
    if not pdf_files:
        print("No files to process after filtering. Exiting.")
        return
    
    # Auto-detect Ollama instances
    global OLLAMA_INSTANCES
    OLLAMA_INSTANCES = detect_ollama_instances()
    
    # Set number of worker threads based on available instances
    global NUM_WORKERS
    NUM_WORKERS = min(len(OLLAMA_INSTANCES), len(pdf_files))
    
    print(f"Found {len(pdf_files)} PDF file(s) to process using {NUM_WORKERS} worker(s).")
    
    if NUM_WORKERS > 1:
        # Multi-processing approach
        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            # Create tasks with round-robin assignment of instances to files
            futures = {}
            for i, pdf_file in enumerate(pdf_files):
                instance = OLLAMA_INSTANCES[i % len(OLLAMA_INSTANCES)]
                futures[executor.submit(process_pdf_with_instance, pdf_file, output_csv, instance)] = pdf_file
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(futures):
                pdf_file = futures[future]
                try:
                    _, authors = future.result()
                    if authors:
                        print(f"Processed '{os.path.basename(pdf_file)}': {len(authors)} author(s) extracted and saved to CSV.")
                    else:
                        print(f"Processed '{os.path.basename(pdf_file)}': No authors found.")
                except Exception as e:
                    print(f"Error processing {pdf_file}: {e}")
                
                print("-"*50)
    else:
        # Single instance processing
        for pdf_file in pdf_files:
            try:
                # Extract authors from the PDF
                authors = extract_authors_from_pdf(pdf_file)
                
                # Write results to CSV
                if authors:
                    write_to_csv(pdf_file, authors, output_csv)
                    print(f"Extracted {len(authors)} author(s) from '{os.path.basename(pdf_file)}' and wrote to CSV.")
                else:
                    print(f"No authors extracted from '{os.path.basename(pdf_file)}'.")
                    
                print("\n" + "-"*50 + "\n") # Add separator between files
                
            except Exception as e:
                print(f"Error processing {pdf_file}: {e}")
                continue


def parse_arguments():
    """Parse command-line arguments with support for JSON config file."""
    parser = argparse.ArgumentParser(description="Extract author information from PDF research reports using Ollama.")
    
    # Input path is required
    parser.add_argument('input', help='Path to a PDF file or directory containing PDF files')
    
    # Optional JSON config file
    parser.add_argument('--config', '-c', help='Path to JSON configuration file (default: config.json in script directory)')
    
    # Page selection arguments
    page_group = parser.add_argument_group('page selection')
    page_group.add_argument('--page-mode', choices=['all', 'range', 'first_n'], 
                           help='Mode for selecting which pages to process (all, range, or first_n)')
    page_group.add_argument('--page-range', nargs=2, type=int, metavar=('START', 'END'),
                           help='Process pages in this range (inclusive, 1-based indexing)')
    page_group.add_argument('--first-n', type=int, metavar='N',
                           help='Process only the first N pages')
    page_group.add_argument('--always-first', action='store_true',
                           help='Always include the first page regardless of other page selections')
    
    # Metadata filtering options
    metadata_group = parser.add_argument_group('metadata filtering')
    metadata_group.add_argument('--metadata-filtering', dest='metadata_filtering', action='store_true',
                           help='Enable metadata-based filtering to skip termination reports')
    metadata_group.add_argument('--no-metadata-filtering', dest='metadata_filtering', action='store_false',
                           help='Disable metadata-based filtering')
    metadata_group.add_argument('--metadata-csv', metavar='FILE',
                           help='Path to metadata CSV file (overrides config setting)')
    
    # Set default for metadata filtering based on configuration (will be overridden by config file later)
    parser.set_defaults(metadata_filtering=None)  # None means use config file setting
    
    # Execution options
    execution_group = parser.add_argument_group('execution')
    execution_group.add_argument('--max-files', type=int, metavar='N',
                            help='Process at most N new files (0 means process all files)')
    execution_group.add_argument('--skip-processed', dest='skip_processed', action='store_true',
                            help='Skip files that were already processed (already in output CSV)')
    execution_group.add_argument('--no-skip-processed', dest='skip_processed', action='store_false',
                            help='Process all files even if they were already processed')
    
    # Set default for skip_processed based on configuration (will be overridden by config file later)
    parser.set_defaults(skip_processed=None)  # None means use config file setting
    
    # Debug flag for quick access
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    return parser.parse_args()


def main():
    """Main entry point for the application with command-line argument handling."""
    global OLLAMA_INSTANCES, NUM_WORKERS
    
    args = parse_arguments()
    
    # Load configuration from specified file or default location
    config = load_json_config(args.config)
    
    # Override debug mode from command line if specified
    if args.debug:
        config["debug"]["enabled"] = True
        
    # Apply page selection arguments if provided
    if args.page_mode:
        config["pdf_processing"]["pages_to_process"]["mode"] = args.page_mode
        
    if args.page_range:
        config["pdf_processing"]["pages_to_process"]["range"] = args.page_range
        
    if args.first_n is not None:
        config["pdf_processing"]["pages_to_process"]["first_n"] = args.first_n
        
    if args.always_first is not None:
        config["pdf_processing"]["pages_to_process"]["always_include_first"] = args.always_first
        
    # Apply metadata filtering arguments if provided
    if args.metadata_filtering is not None:  # Only if explicitly set by user
        config["features"]["metadata_filtering"] = args.metadata_filtering
    
    if args.metadata_csv:
        if "metadata" not in config:
            config["metadata"] = {}
        config["metadata"]["csv_path"] = args.metadata_csv
    
    # Apply execution options if provided
    if args.max_files is not None:
        if "execution" not in config:
            config["execution"] = {}
        config["execution"]["max_files"] = args.max_files
        
    if args.skip_processed is not None:
        if "execution" not in config:
            config["execution"] = {}
        config["execution"]["skip_processed_files"] = args.skip_processed
    
    # Load the configuration into global variables
    load_config(config)
    
    # Auto-detect Ollama instances if enabled
    if config["ollama"]["auto_detect"]:
        detected_instances = detect_ollama_instances()
        if detected_instances:
            OLLAMA_INSTANCES = detected_instances
            if DEBUG_MODE:
                print(f"Detected {len(OLLAMA_INSTANCES)} Ollama instances")
        else:
            print("Warning: No Ollama instances detected. Using default configuration.")
            OLLAMA_INSTANCES = [{"url": OLLAMA_API_URL, "model": OLLAMA_MODEL}]
    
    NUM_WORKERS = min(len(OLLAMA_INSTANCES), 8)  # Cap workers at 8 to avoid excessive resource usage
    
    if DEBUG_MODE:
        print("\nCurrent Configuration:")
        print(json.dumps(config, indent=2))
        print(f"\nUsing {len(OLLAMA_INSTANCES)} Ollama instances with {NUM_WORKERS} workers")
        for i, instance in enumerate(OLLAMA_INSTANCES):
            print(f"Instance {i+1}: {instance['url']} ({instance['model']})")
    
    # Process the input path
    input_path = args.input
    
    # Print basic information about the tool
    print("PDF Author Extraction Tool with Advanced Features")
    print("============================================")
    print(f"Processing: {input_path}")
    print(f"Output file: {OUTPUT_CSV_FILENAME}")
    print(f"Using {len(OLLAMA_INSTANCES)} Ollama instances with {NUM_WORKERS} workers")
    print("============================================")
    
    # Process input based on type (file or directory)
    if os.path.isfile(input_path):
        process_file(input_path, OUTPUT_CSV_FILENAME)
    elif os.path.isdir(input_path):
        process_folder(input_path, OUTPUT_CSV_FILENAME)
    else:
        print(f"Error: Input path '{input_path}' does not exist.")
    
    # Additional configuration info shown only if not already displayed in debug mode
    if not DEBUG_MODE:
        print(f"Using Ollama Model: {OLLAMA_MODEL}")
        
        if PAGES_TO_PROCESS_PER_PDF is None or PAGES_TO_PROCESS_PER_PDF <= 0:
            print("Processing all pages in each PDF")
        else:
            print(f"Processing the first {PAGES_TO_PROCESS_PER_PDF} pages in each PDF")

if __name__ == "__main__":
    main()