import os
import json
import time
import logging
import requests
import pandas as pd
import io
from urllib.parse import urlparse
from datetime import datetime
from serpapi import GoogleSearch
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Chargemaster-specific keywords and patterns
CHARGEMASTER_KEYWORDS = [
    'chargemaster',
    'charge master',
    'cdm',
    'standard charges',
    'standard-charges',
    'standardcharges',
    'machine readable',
    'machine-readable'
]

# Required column patterns for chargemaster validation
CHARGEMASTER_COLUMNS = [
    # Standard CDM format
    ['code', 'description', 'gross charge', 'discounted cash', 'payer specific'],
    ['cpt', 'description', 'gross charge', 'cash price', 'negotiated'],
    ['drg', 'ms-drg', 'description', 'charge', 'cash price'],
    # Common variations
    ['procedure', 'description', 'gross charge', 'self pay', 'insurance'],
    ['service', 'description', 'list price', 'cash price', 'contracted']
]

# Required content indicators
REQUIRED_PRICE_TYPES = [
    ['gross', 'charge'],  # Gross charges
    ['cash', 'price', 'self-pay', 'self pay'],  # Cash price/discounted cash price
    ['payer', 'insurance', 'negotiated', 'contracted']  # Payer-specific negotiated charges
]

def serp_search(query):
    """
    Perform a Google search using SerpAPI.
    
    Args:
        query: Search query string
        
    Returns:
        List of search results with title and URL
    """
    try:
        # Build search params
        params = {
            "engine": "google",
            "q": query,
            "api_key": os.getenv("SERPAPI_KEY"),
            "num": 10,  # Request 10 results
            "hl": "en",
            "gl": "us",
            "google_domain": "google.com"
        }
        
        # Perform search
        search = GoogleSearch(params)
        results = search.get_dict()
        
        if "error" in results:
            logger.error(f"SERPAPI ERROR: {results['error']}")
            return []
            
        if "organic_results" in results:
            # Convert results to simplified format
            search_results = []
            for result in results["organic_results"]:
                search_results.append({
                    'title': result.get('title', ''),
                    'url': result.get('link', '')
                })
            return search_results
            
        return []
        
    except Exception as e:
        logger.error(f"Error during search: {str(e)}")
        return []

def is_data_file_url(url):
    """
    Check if a URL points to a potential machine-readable chargemaster file
    
    Args:
        url: URL string to check
        
    Returns:
        bool: True if URL likely points to a chargemaster file
    """
    url_lower = url.lower()
    
    # Check file extensions for machine-readable formats
    data_extensions = ['.csv', '.json', '.xlsx', '.xls']
    if any(url_lower.endswith(ext) for ext in data_extensions):
        # Must also contain chargemaster keywords
        return any(keyword in url_lower for keyword in CHARGEMASTER_KEYWORDS)
        
    # Check for explicit chargemaster indicators in URL
    return any(keyword in url_lower for keyword in CHARGEMASTER_KEYWORDS)

def download_file_sample(url, max_size=1024*1024):
    """
    Download a sample of a file (first 1MB by default) to analyze
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
        
        # Get content type
        content_type = response.headers.get('content-type', '').lower()
        
        # Return first chunk for analysis
        return {
            'content': next(response.iter_content(chunk_size=max_size)),
            'content_type': content_type,
            'url': url
        }
    except Exception as e:
        logger.error(f"Error downloading {url}: {str(e)}")
        return None

def analyze_csv_content(content):
    """
    Analyze CSV content for chargemaster data
    """
    try:
        df = pd.read_csv(io.BytesIO(content))
        
        # Convert column names to lowercase for easier matching
        columns = [col.lower() for col in df.columns]
        
        # Must have at least 5 columns for a valid chargemaster
        if len(columns) < 5:
            return {
                'valid': False,
                'error': 'Too few columns for a valid chargemaster'
            }
        
        # Check if any required column combinations exist
        for required_cols in CHARGEMASTER_COLUMNS:
            if all(any(req in col for col in columns) for req in required_cols):
                # Found matching columns, now validate content
                
                # 1. Verify we have all required price types
                price_types_found = []
                for price_type in REQUIRED_PRICE_TYPES:
                    if any(any(term in col for term in price_type) for col in columns):
                        price_types_found.append(True)
                    else:
                        price_types_found.append(False)
                
                if not all(price_types_found):
                    continue  # Missing required price types, try next column pattern
                
                # 2. Verify we have numeric values in price columns
                price_cols = [col for col in columns if any(
                    price_term in col for price_term in 
                    ['charge', 'price', 'rate', 'amount', 'payment', 'cost']
                )]
                
                valid_prices = False
                sample_rows = df.head()
                
                for price_col in price_cols:
                    try:
                        numeric_values = pd.to_numeric(df[price_col].head(), errors='coerce')
                        if not numeric_values.isna().all() and (numeric_values > 0).any():
                            valid_prices = True
                            break
                    except:
                        continue
                
                if valid_prices:
                    return {
                        'valid': True,
                        'format': 'csv',
                        'columns': list(df.columns),
                        'sample_data': sample_rows.to_dict(orient='records')[:2],
                        'price_types': [pt[0] for pt, found in zip(REQUIRED_PRICE_TYPES, price_types_found) if found]
                    }
                            
        return {
            'valid': False,
            'error': 'No valid chargemaster data structure found'
        }
    except Exception as e:
        return {
            'valid': False,
            'error': f'Error parsing CSV: {str(e)}'
        }

def analyze_excel_content(content):
    """
    Analyze Excel content for chargemaster data
    """
    try:
        df = pd.read_excel(io.BytesIO(content))
        return analyze_csv_content(df.to_csv().encode())  # Convert to CSV and reuse analysis
    except Exception as e:
        return {
            'valid': False,
            'error': f'Error parsing Excel: {str(e)}'
        }

def analyze_json_content(content):
    """
    Analyze JSON content for chargemaster data
    """
    try:
        data = json.loads(content)
        
        # Handle array of objects
        if isinstance(data, list) and len(data) > 0:
            first_item = data[0]
            
            # Must have at least 5 fields for a valid chargemaster
            if len(first_item.keys()) < 5:
                return {
                    'valid': False,
                    'error': 'Too few fields for a valid chargemaster'
                }
            
            # Check if keys contain required fields
            keys = [k.lower() for k in first_item.keys()]
            
            # Check for required fields
            for required_cols in CHARGEMASTER_COLUMNS:
                if all(any(req in key for key in keys) for req in required_cols):
                    # Verify we have all required price types
                    price_types_found = []
                    for price_type in REQUIRED_PRICE_TYPES:
                        if any(any(term in key for term in price_type) for key in keys):
                            price_types_found.append(True)
                        else:
                            price_types_found.append(False)
                    
                    if not all(price_types_found):
                        continue  # Missing required price types, try next column pattern
                    
                    # Verify price fields contain numeric values
                    price_keys = [k for k in keys if any(
                        price_term in k for price_term in 
                        ['charge', 'price', 'rate', 'amount', 'payment', 'cost']
                    )]
                    
                    if price_keys:
                        for price_key in price_keys:
                            try:
                                # Check first few items for valid prices
                                prices = [float(item[price_key]) for item in data[:5] if price_key in item]
                                if prices and any(p > 0 for p in prices):
                                    return {
                                        'valid': True,
                                        'format': 'json',
                                        'fields': list(first_item.keys()),
                                        'sample_data': data[:2],
                                        'price_types': [pt[0] for pt, found in zip(REQUIRED_PRICE_TYPES, price_types_found) if found]
                                    }
                            except:
                                continue
        
        return {
            'valid': False,
            'error': 'No valid chargemaster data structure found'
        }
    except Exception as e:
        return {
            'valid': False,
            'error': f'Error parsing JSON: {str(e)}'
        }

def validate_file_content(url):
    """
    Validate if a URL contains valid price transparency data
    
    Args:
        url: URL to validate
        
    Returns:
        dict: Validation results including validity and any error messages
    """
    try:
        # First check if URL looks like a data file
        if not is_data_file_url(url):
            return {
                'valid': False,
                'url': url,
                'error': 'URL does not appear to be a data file'
            }
        
        # Download sample of file
        file_data = download_file_sample(url)
        if not file_data:
            return {
                'valid': False,
                'url': url,
                'error': 'Could not download file'
            }
        
        content = file_data['content']
        content_type = file_data['content_type']
        
        # Analyze based on content type
        if 'csv' in content_type or url.lower().endswith('.csv'):
            result = analyze_csv_content(content)
        elif 'excel' in content_type or any(url.lower().endswith(ext) for ext in ['.xlsx', '.xls']):
            result = analyze_excel_content(content)
        elif 'json' in content_type or url.lower().endswith('.json'):
            result = analyze_json_content(content)
        else:
            # Try CSV first, then Excel, then JSON
            result = analyze_csv_content(content)
            if not result['valid']:
                result = analyze_excel_content(content)
            if not result['valid']:
                result = analyze_json_content(content)
        
        result['url'] = url
        return result
        
    except Exception as e:
        return {
            'valid': False,
            'url': url,
            'error': str(e)
        }

def crawl_for_data_files(url):
    """
    Crawl a webpage to find links to data files
    
    Args:
        url: URL to crawl
        
    Returns:
        list: URLs of potential data files found
    """
    try:
        # TODO: Implement actual webpage crawling
        # For now, just check if the URL itself is a data file
        if is_data_file_url(url):
            return [url]
        return []
    except Exception as e:
        logger.error(f"Error crawling {url}: {str(e)}")
        return []

def test_search(query):
    """
    Test search functionality for hospital price transparency data
    
    Args:
        query: Search query string
        
    Returns:
        dict: Search results and statistics
    """
    start_time = time.time()
    logger.info(f"===== TESTING SEARCH: {query} =====")
    
    # Step 1: Perform search
    search_results = serp_search(query)
    
    if not search_results:
        logger.warning("No search results found")
        return {
            'query': query,
            'search_success': False,
            'search_results': 0,
            'data_files_found': 0,
            'execution_time': time.time() - start_time,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    logger.info(f"Found {len(search_results)} search results")
    for result in search_results:
        logger.info(f"RESULT: '{result['title']}' - {result['url']}")
    
    # Step 2: Find data files in search results
    direct_data_files = []
    for result in search_results:
        url = result['url']
        if is_data_file_url(url):
            logger.info(f"DIRECT DATA FILE: {url}")
            direct_data_files.append(url)
    
    if direct_data_files:
        logger.info(f"Found {len(direct_data_files)} direct data files in search results")
        print(f"Found {len(direct_data_files)} direct data files in search results")
    
    # Step 3: Crawl top results to find more data files
    print("Crawling top search results to find data files...")
    logger.info("Crawling top search results to find data files")
    
    all_data_files = []
    all_data_files.extend(direct_data_files)
    
    # Crawl top 3 results
    for i, result in enumerate(search_results[:3]):
        print(f"Crawling result #{i+1}: {result['title']}")
        logger.info(f"CRAWLING RESULT #{i+1}: {result['title']} - {result['url']}")
        
        data_files = crawl_for_data_files(result['url'])
        if data_files:
            logger.info(f"Found {len(data_files)} potential data files from {result['url']}")
            all_data_files.extend(data_files)
    
    # Deduplicate files while preserving order
    unique_data_files = []
    seen = set()
    for file in all_data_files:
        if file not in seen:
            unique_data_files.append(file)
            seen.add(file)
    
    print(f"\nSearch and crawl completed in {time.time() - start_time:.2f} seconds")
    print(f"Found {len(unique_data_files)} total potential price transparency data files\n")
    
    # Step 4: Validate data files
    validated_files = []
    unvalidated_files = []
    
    for file in unique_data_files:
        validation = validate_file_content(file)
        if validation['valid']:
            validated_files.append((file, validation))
        else:
            unvalidated_files.append((file, validation.get('error', 'Unknown error')))
    
    # Print validation results
    if validated_files:
        print("\nValidated price transparency files:")
        for file, validation in validated_files:
            print(f"- {file}")
            if validation.get('sample_data'):
                print(f"  Sample: {validation['sample_data']}")
    else:
        print("\nNo validated price transparency files found.")
    
    if unvalidated_files:
        print("\nPotential files that weren't validated:")
        for file, reason in unvalidated_files:
            print(f"- {file}")
            print(f"  Reason: {reason}")
    
    logger.info("SEARCH TEST COMPLETED")
    
    # Return test results
    results = {
        'query': query,
        'search_success': True,
        'search_results': len(search_results),
        'data_files_found': len(unique_data_files),
        'validated_files': len(validated_files),
        'execution_time': time.time() - start_time,
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'data_files': [f[0] for f in validated_files]
    }
    
    logger.info(f"STATS: {json.dumps(results)}")
    return results

def main():
    """
    Main test function
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Test hospital price transparency data search')
    parser.add_argument('--query', help='Search query')
    args = parser.parse_args()
    
    if not args.query:
        print("Please provide a search query with --query")
        return
    
    results = test_search(args.query)
    print(f"\nSearch completed in {results['execution_time']:.2f} seconds")
    print(f"Found {results['data_files_found']} potential data files")
    print(f"Validated {results['validated_files']} files")

if __name__ == '__main__':
    main() 