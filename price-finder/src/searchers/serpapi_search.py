import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
from serpapi import GoogleSearch
import aiohttp
import json

from ..models.hospital import Hospital

logger = logging.getLogger(__name__)

class SerpAPISearcher:
    """Search engine for finding hospital price transparency files online."""
    
    def __init__(self, api_key: str = None, max_results: int = 10):
        """Initialize the SerpAPI searcher.
        
        Args:
            api_key: SerpAPI API key (if None, tries to get from SERPAPI_KEY env var)
            max_results: Maximum number of search results to return
        """
        self.api_key = api_key or os.environ.get('SERPAPI_KEY')
        if not self.api_key:
            raise ValueError("SerpAPI key is required. Set SERPAPI_KEY environment variable or pass api_key parameter.")
        
        self.max_results = max_results
        
    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Search for hospital price transparency files.
        
        Args:
            query: Search query string
            
        Returns:
            List of search result dictionaries
        """
        logger.info(f"Searching for: {query}")
        
        params = {
            "engine": "google",
            "q": query,
            "api_key": self.api_key,
            "num": self.max_results,
            "gl": "us",  # Country to search from (US)
            "hl": "en"   # Language
        }
        
        try:
            # Execute the search
            search = GoogleSearch(params)
            results = search.get_dict()
            
            # Extract organic search results
            organic_results = []
            if "organic_results" in results:
                for result in results["organic_results"]:
                    organic_results.append({
                        "position": result.get("position"),
                        "title": result.get("title"),
                        "link": result.get("link"),
                        "snippet": result.get("snippet"),
                        "source": "organic"
                    })
            
            # Also get "people also ask" results if available
            if "related_questions" in results:
                for i, question in enumerate(results["related_questions"]):
                    organic_results.append({
                        "position": i + 100,  # to distinguish from organic results
                        "title": question.get("question"),
                        "link": question.get("link"),
                        "snippet": question.get("snippet"),
                        "source": "related_question"
                    })
            
            logger.info(f"Found {len(organic_results)} results for query: {query}")
            return organic_results
            
        except Exception as e:
            logger.error(f"Error searching for {query}: {str(e)}")
            return []
    
    async def search_hospital_price_transparency(self, hospital: Hospital) -> List[Dict[str, Any]]:
        """Search for price transparency files for a specific hospital.
        
        Args:
            hospital: Hospital object
            
        Returns:
            List of search result dictionaries
        """
        # Create a single optimized query that's more likely to find price transparency files
        query = f"{hospital.search_query_base} price transparency standard charges"
        
        # Make a single search request
        results = await self.search(query)
        
        # Process results
        for result in results:
            result["hospital"] = hospital.name
            result["state"] = hospital.state
        
        # Already sorted by position from SerpAPI
        return results[:self.max_results]
        
    async def batch_search(self, hospitals: List[Hospital], concurrency: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """Search for multiple hospitals in parallel.
        
        Args:
            hospitals: List of Hospital objects
            concurrency: Number of concurrent searches
            
        Returns:
            Dictionary mapping hospital IDs to search results
        """
        logger.info(f"Batch searching for {len(hospitals)} hospitals with concurrency {concurrency}")
        
        results = {}
        sem = asyncio.Semaphore(concurrency)
        
        async def _search_with_semaphore(hospital):
            async with sem:
                hospital_results = await self.search_hospital_price_transparency(hospital)
                results[hospital.id] = hospital_results
                logger.info(f"Completed search for {hospital.name}, {hospital.state}")
                
        # Create tasks for all hospitals
        tasks = [_search_with_semaphore(hospital) for hospital in hospitals]
        
        # Wait for all tasks to complete
        await asyncio.gather(*tasks)
        
        return results 