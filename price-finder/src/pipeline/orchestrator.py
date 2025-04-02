import os
import logging
import asyncio
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path

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
            hospital: Hospital to search for
            
        Returns:
            PriceFile object if found, None otherwise
        """
        start_time = datetime.now()
        hospital_id = hospital.id
        
        try:
            logger.info(f"Starting price file search for {hospital.name} ({hospital.state})")
            
            # Update status
            self.status_tracker.start_search(hospital_id)
            
            # Step 1: Search for the hospital's price transparency data
            logger.info(f"Searching for price transparency files for {hospital.name}")
            search_results = await self.serpapi_searcher.search_hospital_price_transparency(hospital)
            
            if not search_results:
                logger.warning(f"No search results found for {hospital.name}")
                self.status_tracker.mark_failure(hospital_id, "No search results")
                log_execution_time(logger, start_time, f"Search for {hospital.name}")
                return None
            
            # Step 2: Analyze search results with LLM
            logger.info(f"Analyzing {len(search_results)} search results for {hospital.name}")
            analyzed_results = await self.link_analyzer.analyze_search_results(search_results, hospital)
            
            if not analyzed_results:
                logger.warning(f"No relevant links found for {hospital.name}")
                self.status_tracker.mark_failure(hospital_id, "No relevant links")
                log_execution_time(logger, start_time, f"Search for {hospital.name}")
                return None
            
            # Step 3: Crawl only the top 3 most promising links
            valid_files = []
            
            # Sort results by confidence/relevance if not already sorted
            analyzed_results.sort(key=lambda x: x.get("confidence", 0), reverse=True)
            
            for i, result in enumerate(analyzed_results[:3]):  # Only check top 3 results
                url = result.get("link")
                if not url:
                    continue
                    
                logger.info(f"Crawling {url} for {hospital.name} (#{i+1} of top 3)")
                page_data = await self.crawler.crawl(url)
                
                # Use LLM to find potential price file links in the page
                potential_links = await self.content_analyzer.find_file_links(page_data['text_content'], hospital)
                
                # Add direct links from crawler's analysis
                potential_links.extend([link['url'] for link in page_data['price_file_links'][:3]])
                
                # Remove duplicates
                potential_links = list(set(potential_links))
                
                logger.info(f"Found {len(potential_links)} potential price file links for {hospital.name}")
                
                # Only check up to 2 files per promising link to limit API usage
                for file_link in potential_links[:2]:
                    try:
                        # Download and analyze the file
                        logger.info(f"Downloading file from {file_link}")
                        content, file_path = await self.crawler.download_file(file_link)
                        
                        if not file_path:
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
                        
                        if not is_valid:
                            logger.info(f"File from {file_link} is not a match for {hospital.name}: {reasoning}")
                            continue
                        
                        # Extract metadata
                        price_file = await self.content_analyzer.extract_price_file_metadata(
                            file_path, hospital, file_link
                        )
                        
                        logger.info(f"Found valid price file for {hospital.name}: {file_link}, confidence: {confidence}")
                        valid_files.append(price_file)
                        
                        # No need to check more files if we found a high-confidence match
                        if confidence > 0.9:
                            break
                            
                    except Exception as e:
                        logger.error(f"Error processing file {file_link}: {str(e)}")
                
                # If we found valid files, no need to check more search results
                if valid_files:
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