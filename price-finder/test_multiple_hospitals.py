import os
import json
import logging
import time
import argparse
import csv
import random
import sys
import traceback
from test_search import crawl_for_data_files, is_data_file_url, validate_file_content, serp_search
from serpapi import GoogleSearch
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global list to store all potential data files found
potential_data_files = []

# Default test hospitals if no other source is specified
TEST_HOSPITALS = [
    {"name": "Mayo Clinic Rochester", "state": "MN"},
    {"name": "Cleveland Clinic", "state": "OH"},
    {"name": "Massachusetts General Hospital", "state": "MA"},
    {"name": "Johns Hopkins Hospital", "state": "MD"},
    {"name": "UCLA Medical Center", "state": "CA"},
    {"name": "UCSF Medical Center", "state": "CA"},
    {"name": "NewYork-Presbyterian Hospital", "state": "NY"},
    {"name": "Stanford Health Care", "state": "CA"},
    {"name": "Northwestern Memorial Hospital", "state": "IL"},
    {"name": "University of Michigan Hospitals", "state": "MI"}
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
    Check if a URL points to a potential machine-readable data file
    
    Args:
        url: URL string to check
        
    Returns:
        bool: True if URL likely points to a data file
    """
    url_lower = url.lower()
    
    # Check file extensions
    data_extensions = ['.csv', '.json', '.xlsx', '.xls', '.txt']
    if any(url_lower.endswith(ext) for ext in data_extensions):
        return True
        
    # Check for data keywords in URL
    data_keywords = [
        'chargemaster', 
        'price', 
        'transparency', 
        'standard-charges',
        'standardcharges',
        'cdm',
        'machine-readable'
    ]
    if any(keyword in url_lower for keyword in data_keywords):
        return True
        
    return False

def validate_file_content(url):
    """
    Validate if a URL contains valid price transparency data
    
    Args:
        url: URL to validate
        
    Returns:
        dict: Validation results including validity and any error messages
    """
    try:
        # TODO: Implement actual file content validation
        # For now, just check if URL is accessible and looks like a data file
        return {
            'valid': is_data_file_url(url),
            'url': url,
            'sample_data': None
        }
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

def test_hospital(hospital_name, state, master_db=None):
    """
    Test price transparency data discovery for a single hospital
    
    Args:
        hospital_name: Name of the hospital
        state: Two-letter state code
        master_db: Optional master database of hospital info
        
    Returns:
        dict: Test results including search success, files found, etc.
    """
    logger.info(f"===== TESTING HOSPITAL: {hospital_name} =====")
    start_time = time.time()
    
    # Get additional hospital info from master db if available
    hospital_info = {}
    if master_db and state in master_db:
        for hospital in master_db[state]:
            if hospital.get('NAME') == hospital_name:
                hospital_info = hospital
                break
    
    # Build search query
    query = f"{hospital_name} {state} hospital price transparency machine readable file"
    if hospital_info:
        # Add address to query if available
        address = hospital_info.get('ADDRESS', '')
        city = hospital_info.get('CITY', '')
        if address and city:
            query = f"{hospital_name} {address} {city} {state} hospital price transparency machine readable file"
    
    logger.info(f"SEARCH QUERY: '{query}'")
    print(f"Searching for: {query}")
    
    # Step 1: Search for price transparency pages
    search_results = serp_search(query)
    
    if not search_results:
        logger.warning("No search results found")
        return {
            'hospital': hospital_name,
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
    
    # First check files that specifically match this hospital
    hospital_files = []
    for file in unique_data_files:
        filename = file.split('/')[-1].lower()
        hospital_terms = set(hospital_name.lower().split())
        if any(term in filename for term in hospital_terms):
            hospital_files.append(file)
    
    if hospital_files:
        logger.info(f"Found {len(hospital_files)} files matching hospital name")
        print(f"Found {len(hospital_files)} files specifically matching this hospital")
        
        # Validate hospital-specific files first
        for file in hospital_files:
            validation = validate_file_content(file)
            if validation['valid']:
                validated_files.append((file, validation))
            else:
                unvalidated_files.append((file, validation.get('error', 'Unknown error')))
        
        # Then validate remaining files
        remaining_files = [f for f in unique_data_files if f not in hospital_files]
        for file in remaining_files:
            validation = validate_file_content(file)
            if validation['valid']:
                validated_files.append((file, validation))
            else:
                unvalidated_files.append((file, validation.get('error', 'Unknown error')))
    else:
        # If no hospital-specific files, validate all files
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
    
    logger.info(f"HOSPITAL TEST COMPLETED: {hospital_name}")
    
    # Return test results
    results = {
        'hospital': hospital_name,
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

def read_hospital_csv(csv_file, sample_size=10):
    """Load a random sample of hospitals from a CSV file."""
    hospitals = []
    try:
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            all_hospitals = list(reader)
            
            # Sample hospitals
            if sample_size < len(all_hospitals):
                hospitals = random.sample(all_hospitals, sample_size)
            else:
                hospitals = all_hospitals
                
        return hospitals
    except Exception as e:
        logger.error(f"Error loading hospitals from CSV: {str(e)}")
        return []

def load_hospitals_by_state(master_db_file, states=None, sample_size=10):
    """
    Load a random sample of hospitals from the master hospital database.
    
    Args:
        master_db_file: Path to the hospital_data.json file
        states: Optional list of state codes to filter by (e.g., ['CA', 'NY'])
        sample_size: Number of hospitals to sample
    
    Returns:
        List of dictionaries with hospital details
    """
    try:
        with open(master_db_file, 'r') as f:
            # The file is structured as a dictionary with state codes as keys
            data = json.load(f)
        
        all_hospitals = []
        
        # If states is provided, only include those states
        state_codes = states if states else data.keys()
        
        # Collect hospitals from specified states
        for state_code in state_codes:
            if state_code in data:
                for hospital in data[state_code]:
                    # Convert to our format
                    if hospital.get('STATUS') == 'OPEN':  # Only include open hospitals
                        # Create a cleaner location string (city, state) for search
                        city = hospital.get('CITY', '')
                        state = hospital.get('STATE', '')
                        location_str = f"{city}, {state}" if city and state else ""
                        
                        all_hospitals.append({
                            'hospital_name': hospital.get('NAME', ''),
                            'location': location_str,
                            'state': state,
                            'address': hospital.get('ADDRESS', ''),
                            'zip': hospital.get('ZIP', ''),
                            'type': hospital.get('TYPE', ''),
                            'health_system': hospital.get('health_sys_name', '')
                        })
        
        # Sample hospitals
        if all_hospitals:
            if sample_size < len(all_hospitals):
                sampled_hospitals = random.sample(all_hospitals, sample_size)
            else:
                sampled_hospitals = all_hospitals
                
            logger.info(f"Loaded {len(sampled_hospitals)} hospitals from master database")
            return sampled_hospitals
        else:
            logger.error("No matching hospitals found in master database")
            return []
            
    except Exception as e:
        logger.error(f"Error loading hospitals from master database: {str(e)}")
        return []

def test_hospitals_from_csv(csv_file, sample_size=10):
    """Test the crawler on a sample of hospitals from a CSV file."""
    hospitals = read_hospital_csv(csv_file, sample_size)
    
    if not hospitals:
        print(f"Error: Could not load hospitals from {csv_file}")
        return
    
    print(f"Testing price transparency crawler on {len(hospitals)} hospitals")
    
    # Track results
    all_results = []
    
    for i, hospital in enumerate(hospitals, 1):
        hospital_name = hospital.get('hospital_name')
        location = hospital.get('location')
        state = hospital.get('state')
        
        if not hospital_name:
            continue
            
        print(f"\nHospital {i}/{len(hospitals)}: {hospital_name}")
        
        data_files, stats = search_and_crawl_hospital(hospital_name, state)
        
        # Add to results
        result = {
            "hospital": hospital_name,
            "location": location,
            "state": state,
            "stats": stats,
            "data_files_count": len(data_files),
            "matched_files_count": sum(1 for label, _ in data_files if "MATCHED" in label)
        }
        all_results.append(result)
        
        # Save interim results in case of crash
        with open("hospital_results.json", "w") as f:
            json.dump(all_results, f, indent=2)
    
    # Calculate overall statistics
    success_count = sum(1 for r in all_results if r['stats'].get('search_success', False))
    files_found_count = sum(r['data_files_count'] for r in all_results)
    matched_files_count = sum(r['matched_files_count'] for r in all_results)
    
    print(f"\n=== SUMMARY ===")
    print(f"Tested {len(all_results)} hospitals")
    print(f"Successful searches: {success_count} ({success_count/len(all_results)*100:.1f}%)")
    print(f"Total data files found: {files_found_count}")
    print(f"Matched files found: {matched_files_count}")
    
    # Save final results
    with open("hospital_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
        
    return all_results

def test_hospitals_from_master_db(master_db_file, states=None, sample_size=10):
    """Test the crawler on a sample of hospitals from the master hospital database."""
    hospitals = load_hospitals_by_state(master_db_file, states, sample_size)
    
    if not hospitals:
        print(f"Error: Could not load hospitals from {master_db_file}")
        return
    
    print(f"Testing price transparency crawler on {len(hospitals)} hospitals from master database")
    
    # Track results
    all_results = []
    
    for i, hospital in enumerate(hospitals, 1):
        hospital_name = hospital.get('hospital_name')
        location = hospital.get('location')
        state = hospital.get('state')
        
        if not hospital_name:
            continue
            
        print(f"\nHospital {i}/{len(hospitals)}: {hospital_name}")
        
        data_files, stats = search_and_crawl_hospital(hospital_name, state)
        
        # Add to results
        result = {
            "hospital": hospital_name,
            "location": location,
            "state": state,
            "stats": stats,
            "data_files_count": len(data_files),
            "matched_files_count": sum(1 for label, _ in data_files if "MATCHED" in label),
            "data_files": [{"label": label, "url": url} for label, url in data_files]
        }
        all_results.append(result)
        
        # Save interim results in case of crash
        with open("hospital_results.json", "w") as f:
            json.dump(all_results, f, indent=2)
    
    # Calculate overall statistics - use the deduplicated counts from the results
    success_count = sum(1 for r in all_results if r['stats'].get('search_success', False))
    files_found_count = sum(r['data_files_count'] for r in all_results)
    matched_files_count = sum(r['matched_files_count'] for r in all_results)
    
    print(f"\n=== SUMMARY ===")
    print(f"Tested {len(all_results)} hospitals")
    print(f"Successful searches: {success_count} ({success_count/len(all_results)*100:.1f}%)")
    print(f"Total unique data files found: {files_found_count}")
    print(f"Matched unique files found: {matched_files_count}")
    
    # Save final results
    with open("hospital_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
        
    return all_results

def parse_args():
    parser = argparse.ArgumentParser(description='Test price transparency crawler on multiple hospitals')
    parser.add_argument('--csv', help='CSV file containing hospital names')
    parser.add_argument('--master_db', help='JSON file containing hospital data')
    parser.add_argument('--states', help='Comma-separated list of state abbreviations to test')
    parser.add_argument('--sample', type=int, help='Number of hospitals to sample per state')
    parser.add_argument('--hospital', help='Test a specific hospital by name')
    parser.add_argument('--state', help='State for the specific hospital (when using --hospital)')
    return parser.parse_args()

def main():
    """
    Main test function
    """
    parser = argparse.ArgumentParser(description='Test hospital price transparency data discovery')
    parser.add_argument('--master_db', help='Path to master hospital database JSON file')
    parser.add_argument('--states', help='Comma-separated list of states to test')
    parser.add_argument('--sample', type=int, default=10, help='Number of hospitals to test per state')
    args = parser.parse_args()
    
    # Load master database if provided
    master_db = None
    if args.master_db:
        try:
            with open(args.master_db) as f:
                data = f.read()
                # Remove any % at the end
                data = data.rstrip('%')
                master_db = json.loads(data)
                if not isinstance(master_db, dict):
                    print(f"Error: Invalid master database format. Expected dict, got {type(master_db)}")
                    return
        except Exception as e:
            print(f"Error loading master database: {str(e)}")
            return
    
    # Get states to test
    states = [s.strip().upper() for s in args.states.split(',')] if args.states else ['CA']
    
    # Track overall results
    all_results = []
    total_hospitals = 0
    successful_searches = 0
    total_files = 0
    validated_files = 0
    
    print(f"\nTesting hospitals in states: {', '.join(states)}")
    
    # Test hospitals for each state
    for state in states:
        print(f"\n=== Testing hospitals in {state} ===")
        
        if master_db:
            # Get hospitals from master database for this state
            state_hospitals = master_db.get(state, [])
            
            if not state_hospitals:
                print(f"No hospitals found in {state}")
                continue
                
            print(f"Found {len(state_hospitals)} hospitals in {state}")
            
            if args.sample and args.sample < len(state_hospitals):
                state_hospitals = random.sample(state_hospitals, args.sample)
                print(f"Testing {len(state_hospitals)} sample hospitals")
        else:
            # Use dummy data for testing
            state_hospitals = [{'NAME': 'Test Hospital', 'STATE': state}]
            print("Using test data (no master database provided)")
            
        # Test each hospital
        for hospital in state_hospitals:
            total_hospitals += 1
            
            try:
                hospital_name = hospital.get('NAME', 'Unknown Hospital')
                print(f"\nTesting hospital {total_hospitals}: {hospital_name}")
                
                results = test_hospital(hospital_name, state, master_db)
                all_results.append(results)
                
                if results['search_success']:
                    successful_searches += 1
                total_files += results['data_files_found']
                validated_files += results.get('validated_files', 0)
                
            except Exception as e:
                print(f"Error testing hospital {hospital_name}: {str(e)}")
                logger.error(f"Error testing hospital {hospital_name}: {str(e)}")
                continue
            
    # Print summary
    print("\n=== SUMMARY ===")
    print(f"Tested {total_hospitals} hospitals")
    
    if total_hospitals > 0:
        success_rate = (successful_searches / total_hospitals) * 100
        print(f"Successful searches: {successful_searches} ({success_rate:.1f}%)")
        print(f"Total unique data files found: {total_files}")
        print(f"Validated files: {validated_files}")
    else:
        print("No hospitals were tested")

if __name__ == '__main__':
    main() 