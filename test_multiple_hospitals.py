import json
import logging
import time
import argparse
from test_search import validate_file_content, crawl_for_data_files
from serpapi import GoogleSearch
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("search_crawler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def normalize_url(url):
    """Normalize URL to avoid duplicates due to minor differences."""
    parsed = urlparse(url)
    # Remove query parameters and fragments
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".lower().rstrip('/')

def test_hospital(hospital_name, state=None):
    """Test searching for and validating price transparency files for a specific hospital."""
    logger.info(f"\n===== TESTING HOSPITAL: {hospital_name} =====")
    
    # Construct search query
    search_query = f"{hospital_name} {state if state else ''} price transparency file csv json download standardcharges"
    logger.info(f"SEARCH QUERY: '{search_query}'")
    
    print(f"Search query: '{search_query}'")
    print("Step 1: Searching for price transparency pages...")
    logger.info("STEP 1: Searching for price transparency pages")
    
    # Search parameters
    params = {
        "engine": "google",
        "q": search_query,
        "api_key": os.getenv("SERPAPI_KEY"),
        "num": 10,
        "gl": "us",
        "hl": "en"
    }
    
    start_time = time.time()
    potential_files = set()  # Use a set to avoid duplicates
    
    try:
        # Perform search
        search = GoogleSearch(params)
        results = search.get_dict()
        
        if "error" in results:
            logger.error(f"Search error: {results['error']}")
            return False
            
        if "organic_results" not in results:
            logger.error("No search results found")
            return False
            
        search_results = results["organic_results"]
        logger.info(f"Found {len(search_results)} search results")
        
        # Process search results
        direct_data_files = []
        for result in search_results:
            title = result.get('title', '')
            link = result.get('link', '')
            logger.info(f"RESULT: '{title}' - {link}")
            
            # Check if the URL directly points to a data file
            if any(ext in link.lower() for ext in ['.csv', '.json', '.xlsx', '.xls']):
                logger.info(f"DIRECT DATA FILE: {link}")
                direct_data_files.append(link)
                potential_files.add(normalize_url(link))
        
        logger.info(f"Found {len(direct_data_files)} direct data files in search results")
        print(f"Found {len(direct_data_files)} direct data files in search results")
        
        # Crawl top results to find more files
        print("Step 2: Crawling top search results to find data files...")
        logger.info("STEP 2: Crawling top search results to find data files")
        
        for i, result in enumerate(search_results[:3], 1):
            title = result.get('title', '')
            link = result.get('link', '')
            
            print(f"Crawling result #{i}: {title}")
            logger.info(f"CRAWLING RESULT #{i}: {title} - {link}")
            
            # Try to crawl and find data files
            files_found = crawl_for_data_files(link, max_depth=2)
            if files_found:
                logger.info(f"Found {len(files_found)} potential data files from {link}")
                print(f"Found {len(files_found)} potential data files")
                for file in files_found:
                    potential_files.add(normalize_url(file))
                
                # Check if files specifically match this hospital
                matching_files = [f for f in files_found if any(
                    term.lower() in f.lower() 
                    for term in hospital_name.lower().split()
                )]
                if matching_files:
                    logger.info(f"Found {len(matching_files)} files matching hospital name")
                    print(f"Found {len(matching_files)} files specifically matching this hospital")
        
        # Validate files
        validated_files = []
        invalid_files = []
        for file_url in potential_files:  # Use the deduplicated set
            try:
                validation_result = validate_file_content(file_url)
                if validation_result['valid']:
                    validated_files.append({
                        'url': file_url,
                        'file_type': validation_result['file_type'],
                        'size_bytes': validation_result['size_bytes']
                    })
                else:
                    invalid_files.append({
                        'url': file_url,
                        'reason': validation_result.get('reason', 'Unknown validation failure')
                    })
            except Exception as e:
                logger.error(f"Error validating file {file_url}: {str(e)}")
                invalid_files.append({
                    'url': file_url,
                    'reason': str(e)
                })
        
        # Log results
        execution_time = time.time() - start_time
        stats = {
            "hospital": hospital_name,
            "search_success": True,
            "search_results": len(search_results),
            "data_files_found": len(potential_files),
            "validated_files": len(validated_files),
            "execution_time": execution_time,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        logger.info(f"HOSPITAL TEST COMPLETED: {hospital_name}")
        logger.info(f"STATS: {json.dumps(stats)}")
        
        print(f"\nSearch and crawl completed in {execution_time:.2f} seconds")
        print(f"Found {len(potential_files)} total potential price transparency data files")
        
        if validated_files:
            print("\nValidated price transparency files:")
            for file in validated_files:
                print(f"- {file['url']}")
                print(f"  Type: {file['file_type']}")
                if file['size_bytes']:
                    print(f"  Size: {file['size_bytes']:,} bytes")
        else:
            print("\nNo validated price transparency files found.")
            if invalid_files:
                print("\nFiles that failed validation:")
                for file in invalid_files[:5]:  # Show first 5 invalid files
                    print(f"- {file['url']}")
                    print(f"  Reason: {file['reason']}")
                if len(invalid_files) > 5:
                    print(f"... and {len(invalid_files) - 5} more files")
        
        return True
        
    except Exception as e:
        logger.error(f"Error testing hospital {hospital_name}: {str(e)}")
        print(f"Error: {str(e)}")
        return False

def main():
    """Main function to test multiple hospitals."""
    parser = argparse.ArgumentParser(description='Test hospital price transparency file search and validation.')
    parser.add_argument('--master_db', type=str, required=True, help='Path to master hospital database JSON file')
    parser.add_argument('--states', type=str, help='Comma-separated list of states to test')
    parser.add_argument('--sample', type=int, default=10, help='Number of hospitals to test per state')
    args = parser.parse_args()
    
    try:
        # Load hospital database
        with open(args.master_db, 'r') as f:
            hospitals = json.load(f)
        
        # Filter by states if specified
        if args.states:
            states = [s.strip().upper() for s in args.states.split(',')]
            hospitals = [h for h in hospitals if h.get('state') in states]
        
        # Take sample
        if args.sample and args.sample < len(hospitals):
            from random import sample
            hospitals = sample(hospitals, args.sample)
        
        print(f"Testing {len(hospitals)} hospitals from master database")
        
        # Test each hospital
        successful_searches = 0
        total_files_found = 0
        validated_files = 0
        
        start_time = time.time()
        for hospital in hospitals:
            success = test_hospital(
                hospital['name'],
                hospital.get('state')
            )
            if success:
                successful_searches += 1
            
        # Print summary
        print("\n=== SUMMARY ===")
        print(f"Tested {len(hospitals)} hospitals")
        print(f"Successful searches: {successful_searches} ({successful_searches/len(hospitals)*100:.1f}%)")
        print(f"Total unique data files found: {total_files_found}")
        print(f"Validated files: {validated_files}")
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 