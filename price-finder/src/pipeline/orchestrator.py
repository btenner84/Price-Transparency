import os
import logging
import asyncio
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from ..models.hospital import Hospital
from ..models.price_file import PriceFile
from ..searchers.serpapi_search import SerpAPISearcher
from ..searchers.web_crawler import WebCrawler
from ..llm.link_analyzer import LLMLinkAnalyzer
from ..llm.content_analyzer import LLMContentAnalyzer
from ..validators.file_validator import FileValidator
from ..validators.hospital_matcher import HospitalMatcher
from .status_tracker import StatusTracker
from ..utils.logger import log_execution_time, log_exception, StatsTracker

logger = logging.getLogger(__name__)

class PriceFinderPipeline:
    """Main orchestrator for finding hospital price transparency files."""
    
    def __init__(self, 
                 config: Dict[str, Any] = None,
                 serpapi_key: str = None,
                 openai_key: str = None,
                 download_dir: str = "downloads",
                 llm_provider: str = "openai"):
        """Initialize the price finder pipeline.
        
        Args:
            config: Pipeline configuration
            serpapi_key: SerpAPI API key
            openai_key: OpenAI API key
            download_dir: Directory for downloaded files
            llm_provider: LLM provider name
        """
        self.config = config or {}
        
        # Set up environment variables if provided
        if serpapi_key:
            os.environ["SERPAPI_KEY"] = serpapi_key
        if openai_key:
            os.environ["OPENAI_API_KEY"] = openai_key
            
        # Ensure download directory exists
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
        
        # Initialize components
        logger.info("Initializing pipeline components...")
        
        # Search components
        self.serpapi_searcher = SerpAPISearcher(
            max_results=self.config.get("max_search_results", 10)
        )
        
        self.crawler = WebCrawler(
            download_dir=self.download_dir
        )
        
        # LLM-based analyzers
        self.link_analyzer = LLMLinkAnalyzer(
            provider=llm_provider,
            model=self.config.get("link_analyzer_model"),
            confidence_threshold=self.config.get("link_confidence_threshold", 0.6)
        )
        
        self.content_analyzer = LLMContentAnalyzer(
            provider=llm_provider,
            model=self.config.get("content_analyzer_model"),
            validation_threshold=self.config.get("content_validation_threshold", 0.8)
        )
        
        # Validators
        self.file_validator = FileValidator(
            min_price_columns=self.config.get("min_price_columns", 1),
            min_rows=self.config.get("min_rows", 10)
        )
        
        self.hospital_matcher = HospitalMatcher(
            confidence_threshold=self.config.get("hospital_match_threshold", 0.8)
        )
        
        # Status tracking
        self.status_tracker = StatusTracker(
            db_path=self.config.get("db_path", "data/price_finder.db")
        )
        
        # Stats tracking
        self.stats = StatsTracker(logger)
        
        logger.info("Pipeline initialization complete")
    
    async def find_price_file(self, hospital: Hospital) -> Optional[PriceFile]:
        """Find a price transparency file for a hospital.
        
        Args:
            hospital: Hospital object
            
        Returns:
            PriceFile object if found, None otherwise
        """
        hospital_id = hospital.id
        start_time = datetime.now()
        
        try:
            logger.info(f"Starting price file search for {hospital.name} ({hospital.state})")
            
            # Update status to searching
            self.status_tracker.start_search(hospital_id)
            
            # Step 1: Search for price transparency files using SerpAPI
            search_query = f"{hospital.name} {hospital.city}, {hospital.state} price transparency standard charges"
            logger.info(f"Searching for: {search_query}")
            search_results = await self.serpapi_searcher.search(search_query)
            
            if not search_results:
                logger.warning(f"No search results for {hospital.name}")
                self.status_tracker.mark_failure(hospital_id, "No search results found")
                return None
            
            logger.info(f"Found {len(search_results)} results for query: {search_query}")
            
            # Keep only top 10 results for analysis
            top_results = search_results[:10]
            
            # Step 2: Analyze search results with LLM to identify promising links
            logger.info(f"Analyzing {len(top_results)} search results for {hospital.name}")
            analyzed_results = await self.link_analyzer.analyze_search_results(top_results, hospital)
            
            # Sort by relevance score
            analyzed_results.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            # Keep only top N most relevant links
            top_links = analyzed_results[:3] if analyzed_results else []
            
            valid_files = []
            
            # Check if this is part of a known hospital system that might have combined price files
            # Safely check for health_sys_name attribute
            has_health_sys_attr = hasattr(hospital, 'health_sys_name')
            health_sys_name = getattr(hospital, 'health_sys_name', '') if has_health_sys_attr else ''
            is_system_hospital = bool(health_sys_name and health_sys_name.strip() != '')
            
            # Check for Noland hospital - safely handle different Hospital implementations
            hospital_name_lower = hospital.name.lower() if hasattr(hospital, 'name') else ''
            health_sys_lower = health_sys_name.lower() if health_sys_name else ''
            is_noland_hospital = ('noland' in hospital_name_lower or 
                                 ('noland' in health_sys_lower))
            
            # Step 3: Crawl and validate top links
            for link_data in top_links:
                # Crawl the page for price file links
                link_url = link_data['link']
                # Safely get rank or use index+1
                link_rank = link_data.get('rank', top_links.index(link_data) + 1)
                logger.info(f"Crawling {link_url} for {hospital.name} (#{link_rank} of top {len(top_links)})")
                
                # Special handling for system hospitals, especially Noland 
                if is_noland_hospital and ('nolandhospitals.com' in link_url or 'nolandhealth.com' in link_url):
                    logger.info(f"Special handling for Noland hospital system URL: {link_url}")
                    # Be more lenient with validation for system-wide price files for Noland
                
                # Use the existing crawl method instead of the non-existent find_price_file_links
                page_data = await self.crawler.crawl(link_url)
                
                # Extract potential file links
                file_links = []
                facility_links = {}  # Dictionary to store facility-specific links
                
                # Check for direct price file links from crawler
                if 'price_file_links' in page_data:
                    for link_info in page_data['price_file_links']:
                        if 'url' in link_info:
                            url = link_info['url']
                            # Store facility information if available
                            if 'facility' in link_info:
                                facility = link_info['facility']
                                if facility not in facility_links:
                                    facility_links[facility] = []
                                facility_links[facility].append(url)
                            file_links.append(url)
                
                # Also check for direct file links that match common file types
                if 'links' in page_data:
                    # Define strict extensions for price files
                    price_file_extensions = ['.csv', '.xlsx', '.xls', '.json', '.xml']
                    # Price file indicators in URL path or text
                    price_indicators = ['price', 'charge', 'standard', 'chargemaster', 'transparency', 
                                        'cdm', 'machine-readable', 'rates', 'negotiated']
                    
                    for link_info in page_data['links']:
                        if 'url' in link_info:
                            url = link_info['url'].lower()
                            text = link_info.get('text', '').lower()
                            
                            # Check if it's a direct file link with approved extension
                            is_price_file_ext = any(url.endswith(ext) for ext in price_file_extensions)
                            
                            # Check for zip files with price indicators
                            is_zip_with_price = url.endswith('.zip') and any(indicator in url or indicator in text 
                                                                            for indicator in price_indicators)
                            
                            # Check for price indicators in URL path or link text
                            has_price_indicator = any(indicator in url or indicator in text 
                                                     for indicator in price_indicators)
                            
                            # Filter more strictly - must have either approved extension or strong indicators
                            if is_price_file_ext or is_zip_with_price or (
                                    has_price_indicator and link_info.get('is_file', False)):
                                # Store facility information if available
                                if 'facility' in link_info:
                                    facility = link_info['facility']
                                    if facility not in facility_links:
                                        facility_links[facility] = []
                                    facility_links[facility].append(link_info['url'])
                                file_links.append(link_info['url'])
                
                # Filter out duplicate links
                file_links = list(dict.fromkeys(file_links))
                
                # Prioritize links for the specific hospital if available
                prioritized_links = []
                
                # Step 1: First, check if we have facility-specific links that match this hospital
                if facility_links:
                    # Standardize all facility names and hospital name for better matching
                    hospital_std = self._standardize_facility_name(hospital.name)
                    hospital_words = set(hospital_std.split())
                    
                    best_match = None
                    best_match_score = 0
                    
                    for facility, urls in facility_links.items():
                        # Standardize facility name
                        facility_std = self._standardize_facility_name(facility)
                        facility_words = set(facility_std.split())
                        
                        # Calculate word overlap as a score
                        common_words = hospital_words.intersection(facility_words)
                        total_words = hospital_words.union(facility_words)
                        match_score = len(common_words) / max(1, len(total_words))
                        
                        # Boost score if facility contains hospital location
                        if hasattr(hospital, 'city') and hospital.city and hospital.city.lower() in facility_std:
                            match_score += 0.3
                            
                        if hasattr(hospital, 'state') and hospital.state and hospital.state.lower() in facility_std:
                            match_score += 0.2
                        
                        # Track best match
                        if match_score > best_match_score:
                            best_match_score = match_score
                            best_match = facility
                    
                    # If we found a good match (>40% similarity), prioritize those links
                    if best_match_score > 0.4:
                        logger.info(f"Found facility match for {hospital.name}: '{best_match}' (score: {best_match_score:.2f})")
                        prioritized_links = facility_links[best_match]
                        
                        # Add remaining links as fallbacks
                        for url in file_links:
                            if url not in prioritized_links:
                                prioritized_links.append(url)
                    else:
                        # No good facility match, use all links
                        prioritized_links = file_links
                else:
                    # No facility links found, use all links
                    prioritized_links = file_links
                
                # Limit links to check
                max_links_to_check = 5
                prioritized_links = prioritized_links[:max_links_to_check]
                
                # If we found potential links, log them
                if prioritized_links:
                    logger.info(f"Found {len(prioritized_links)} potential price file links on {link_url}")
                else:
                    logger.info(f"No price file links found on {link_url}")
                    continue
                
                # Download and validate each potential file
                temp_valid_files = []  # Store all valid files for this page, we'll pick the best later
                for file_link in prioritized_links:
                    try:
                        # Skip PDFs unless they have strong price transparency indicators
                        if file_link.lower().endswith('.pdf'):
                            # Check if the URL or filename contains price indicators
                            pdf_price_indicators = ['price', 'charge', 'chargemaster', 'cdm', 'standard-charges']
                            has_price_indicator = any(indicator in file_link.lower() for indicator in pdf_price_indicators)
                            
                            # Skip generic PDFs that don't seem to be price files
                            if not has_price_indicator:
                                logger.info(f"Skipping generic PDF that lacks price indicators: {file_link}")
                                continue
                                
                            # Also check for common non-price PDF patterns
                            skip_indicators = ['patient', 'rights', 'notice', 'form', 'policy', 'privacy', 'consent']
                            should_skip = any(indicator in file_link.lower() for indicator in skip_indicators)
                            
                            if should_skip and not has_price_indicator:
                                logger.info(f"Skipping PDF that appears to be non-price document: {file_link}")
                                continue
                        
                        # Download the file
                        result = await self.crawler.download_file(file_link)
                        
                        # Check if result is a tuple (content, file_path)
                        if isinstance(result, tuple) and len(result) == 2:
                            content, file_path = result
                        else:
                            # If it's not a tuple, assume it's just the file path
                            file_path = result
                            
                        if not file_path or not isinstance(file_path, Path) or not file_path.exists():
                            logger.warning(f"Failed to download file from {file_link}")
                            continue
                        
                        # Validate the file format
                        if not self.file_validator.is_valid_format(file_path):
                            logger.info(f"File from {file_link} is not a valid price transparency file format")
                            continue
                        
                        # Match the file to the hospital
                        is_valid, confidence, reasoning = await self.hospital_matcher.validate(
                            file_path, hospital, self.content_analyzer
                        )
                        
                        # Special handling for system hospitals like Noland
                        if not is_valid and is_system_hospital:
                            # If it's a system hospital, check if the file might be a system-wide price file
                            if is_noland_hospital and ('birmingham' in file_path.name.lower() or 'anniston' in file_path.name.lower()):
                                # For Noland specifically, we know they use combined price files
                                logger.info(f"Potential system-wide price file detected for Noland: {file_path.name}")
                                
                                # Extract the hospital's state from the content to verify it's for the right region
                                if hospital.state.lower() in reasoning.lower():
                                    logger.info(f"System file contains reference to hospital state {hospital.state}")
                                    is_valid = True
                                    confidence = 0.75
                                    reasoning += f" System-wide price file: May cover multiple Noland facilities including {hospital.name}."
                        
                        # Store this file and validation info for later selection
                        price_file = await self.content_analyzer.extract_price_file_metadata(
                            file_path, hospital, file_link
                        )
                        
                        # Add validation info
                        price_file.validated = is_valid
                        price_file.validation_score = confidence
                        price_file.validation_notes = reasoning
                        
                        # Track all valid files
                        if is_valid:
                            logger.info(f"Found valid price file for {hospital.name}: {file_link}, confidence: {confidence}")
                            temp_valid_files.append(price_file)
                        else:
                            logger.info(f"File from {file_link} is not a match for {hospital.name}: {reasoning}")
                            
                    except Exception as e:
                        logger.error(f"Error processing file {file_link}: {str(e)}")
                
                # Add any valid files from this page to the overall list
                valid_files.extend(temp_valid_files)
                
                # If we found a high-confidence file, we can move on
                if any(f.validation_score > 0.9 for f in temp_valid_files):
                    logger.info(f"Found high-confidence match for {hospital.name}, stopping search")
                    break
            
            # Step 4: Update status and return results
            if valid_files:
                # Sort by validation score
                valid_files.sort(key=lambda x: x.validation_score, reverse=True)
                best_file = valid_files[0]
                
                self.status_tracker.mark_success(hospital_id, best_file)
                
                log_execution_time(logger, start_time, f"Successful search for {hospital.name}")
                return best_file
            else:
                self.status_tracker.mark_failure(hospital_id, "No valid files found")
                log_execution_time(logger, start_time, f"Failed search for {hospital.name}")
                return None
                
        except Exception as e:
            log_exception(logger, e, f"Error in find_price_file for {hospital.name}")
            self.status_tracker.mark_error(hospital_id, str(e))
            return None
    
    async def batch_process(self, 
                          hospitals: List[Hospital], 
                          concurrency: int = 5,
                          save_results: bool = True) -> Dict[str, Any]:
        """Process multiple hospitals in parallel.
        
        Args:
            hospitals: List of Hospital objects
            concurrency: Number of concurrent searches
            save_results: Whether to save results to a file
            
        Returns:
            Dictionary with results summary
        """
        logger.info(f"Starting batch processing of {len(hospitals)} hospitals with concurrency {concurrency}")
        
        start_time = datetime.now()
        self.stats.reset()
        self.stats.total_hospitals = len(hospitals)
        
        # Set up a semaphore to limit concurrency
        sem = asyncio.Semaphore(concurrency)
        results = {}
        
        async def _process_hospital(hospital):
            """Process a single hospital with semaphore."""
            async with sem:
                try:
                    logger.info(f"Processing hospital: {hospital.name}, {hospital.state}")
                    price_file = await self.find_price_file(hospital)
                    results[hospital.id] = price_file
                    self.stats.record_hospital_processed(price_file is not None)
                    self.stats.log_progress()
                except Exception as e:
                    log_exception(logger, e, f"Error processing hospital {hospital.name}")
                    self.stats.record_hospital_processed(False, had_error=True)
                    self.stats.log_progress()
        
        # Create tasks for all hospitals
        tasks = [_process_hospital(hospital) for hospital in hospitals]
        
        # Wait for all tasks to complete
        await asyncio.gather(*tasks)
        
        # Log final stats
        self.stats.log_final_stats()
        
        # Save results to file if requested
        if save_results:
            result_file = f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            self.status_tracker.export_results(result_file)
            logger.info(f"Results exported to {result_file}")
        
        log_execution_time(logger, start_time, "Batch processing")
        
        return {
            "total": self.stats.total_hospitals,
            "processed": self.stats.hospitals_processed,
            "found": self.stats.hospitals_with_price_files,
            "not_found": self.stats.hospitals_without_price_files,
            "errors": self.stats.search_errors,
        }
    
    def get_hospitals_to_process(self, limit: int = 100, states: List[str] = None) -> List[Hospital]:
        """Get a list of hospitals that need to be processed.
        
        Args:
            limit: Maximum number of hospitals to return
            states: Optional list of states to filter by
            
        Returns:
            List of Hospital objects
        """
        return self.status_tracker.get_hospitals_to_search(limit=limit, states=states)
    
    def load_hospitals_from_file(self, file_path: str) -> List[Hospital]:
        """Load hospitals from a JSON file.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            List of Hospital objects
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            hospitals = []
            
            # If it's a dictionary with state codes as keys
            if isinstance(data, dict):
                for state_code, state_hospitals in data.items():
                    for h in state_hospitals:
                        hospital = Hospital(
                            id=h.get('id') or f"{h.get('NAME')}_{h.get('STATE')}_{h.get('CITY')}",
                            name=h.get('NAME'),
                            state=h.get('STATE'),
                            city=h.get('CITY'),
                            health_system_name=h.get('health_sys_name')
                        )
                        hospitals.append(hospital)
            
            # If it's a list of hospitals
            elif isinstance(data, list):
                for h in data:
                    hospital = Hospital(
                        id=h.get('id') or f"{h.get('NAME')}_{h.get('STATE')}_{h.get('CITY')}",
                        name=h.get('NAME'),
                        state=h.get('STATE'),
                        city=h.get('CITY'),
                        health_system_name=h.get('health_sys_name')
                    )
                    hospitals.append(hospital)
            
            # Register all hospitals in the status tracker
            self.status_tracker.register_hospitals(hospitals)
            
            logger.info(f"Loaded {len(hospitals)} hospitals from {file_path}")
            return hospitals
            
        except Exception as e:
            log_exception(logger, e, f"Error loading hospitals from {file_path}")
            return []
    
    def update_master_dataset(self, output_file: str) -> bool:
        """Update the master hospitals dataset with price transparency URLs.
        
        Args:
            output_file: Path to output JSON file
            
        Returns:
            True if successful
        """
        try:
            # Get all results from the database
            conn = self.status_tracker._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT h.id, h.name, h.state, h.city, h.health_system_name,
                   p.url as price_transparency_url, p.validation_score,
                   p.validated, p.validation_date
            FROM hospitals h
            LEFT JOIN (
                SELECT hospital_id, url, validation_score, validated, found_date as validation_date,
                       ROW_NUMBER() OVER (PARTITION BY hospital_id ORDER BY found_date DESC) as rn
                FROM price_files
                WHERE validated = 1
            ) p ON h.id = p.hospital_id AND p.rn = 1
            ORDER BY h.state, h.name
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            # Create a dictionary with state codes as keys
            result_data = {}
            
            for row in rows:
                hospital_data = dict(row)
                state = hospital_data['state']
                
                if state not in result_data:
                    result_data[state] = []
                
                del hospital_data['state']  # Remove duplicate state field
                result_data[state].append(hospital_data)
            
            # Write to file
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, indent=2)
            
            logger.info(f"Master dataset updated and saved to {output_file}")
            return True
            
        except Exception as e:
            log_exception(logger, e, f"Error updating master dataset")
            return False

    def _standardize_facility_name(self, name: str) -> str:
        """Standardize a facility name for better matching."""
        if not name:
            return ""
            
        # Convert to lowercase
        name = name.lower()
        
        # Remove common punctuation and normalize spacing
        name = name.replace('-', ' ').replace('|', ' ').replace('/', ' ').replace(',', ' ')
        name = ' '.join(name.split())  # Normalize spaces
        
        # Handle special cases for hospital naming patterns
        # Replace common hospital type indicators with standard forms
        name = name.replace('medical center', 'hospital')
        name = name.replace('med center', 'hospital')
        name = name.replace('medical ctr', 'hospital')
        name = name.replace('med ctr', 'hospital')
        name = name.replace('health center', 'hospital')
        name = name.replace('health system', '')
        name = name.replace('healthcare', '')
        name = name.replace('health care', '')
        
        # Extract key identifying words from the hospital name
        # Remove common words that don't help with identification
        common_words = [
            'the', 'and', 'of', 'at', 'in', 'by', 'for', 'a', 'an', 'to', 'with',
            'hospital', 'medical', 'center', 'health', 'regional', 'community',
            'memorial', 'general', 'system', 'care', 'saint', 'st', 'university'
        ]
        words = []
        location_words = []
        
        # Process each word and categorize as identifying word or location indicator
        for word in name.split():
            # Skip common words unless they're likely part of a proper name
            if word not in common_words or (len(word) > 2 and word[0].isupper()):
                # Check if this might be a location indicator
                # Locations often come after a dash or at the end of a name
                if name.find(' ' + word) > name.find(' - ') > 0:
                    location_words.append(word)
                else:
                    words.append(word)
        
        # Combine the words, giving preference to identifying words first, then location words
        result = ' '.join(words)
        if location_words:
            # If we found location indicators, add them with higher weight
            result = result + ' ' + ' '.join(location_words)
            
        return result 