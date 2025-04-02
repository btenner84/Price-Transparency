#!/usr/bin/env python3
"""
Direct test script for the price finder with Mistral API only.
This script directly instantiates the pipeline with the correct provider.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# Add price finder directory to path
price_finder_dir = os.path.join(os.path.dirname(parent_dir), "price-finder")
sys.path.append(price_finder_dir)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Set debug level for relevant modules
for module in [
    'src.pipeline.orchestrator',
    'src.searchers.serpapi_search',
    'src.searchers.web_crawler',
    'src.llm.link_analyzer',
    'src.llm.content_analyzer',
    'src.validators.file_validator',
    'src.validators.hospital_matcher'
]:
    logging.getLogger(module).setLevel(logging.DEBUG)

# Import after setting up paths
from src.pipeline.orchestrator import PriceFinderPipeline
from src.models.hospital import Hospital

# Setup keys
SERP_API_KEY = "6d57e14bdf08c364978a63ccc98df618c8c033e2c9d572db667be74ad50c188a"
MISTRAL_API_KEY = "87QKmlS8vjw0woFXpLnUKVIqLkcMa8Lz"

async def main():
    """Run a direct test of the price finder with Mistral."""
    print("Starting direct test of price finder with Mistral API...")
    
    # Set environment variables
    os.environ["SERPAPI_KEY"] = SERP_API_KEY
    os.environ["MISTRAL_API_KEY"] = MISTRAL_API_KEY
    os.environ["LLM_PROVIDER"] = "mistral"
    
    # Create configuration
    config = {
        "serpapi_key": SERP_API_KEY,
        "mistral_key": MISTRAL_API_KEY,
        "llm_provider": "mistral",
        "download_dir": os.path.join(price_finder_dir, "downloads"),
        "db_path": os.path.join(price_finder_dir, "data", "price_finder.db")
    }
    
    # Initialize pipeline with explicit Mistral provider
    pipeline = PriceFinderPipeline(
        config=config,
        llm_provider="mistral"  # Explicit override
    )
    
    # Test with a sample hospital
    test_hospital = Hospital(
        id="test-001",
        name="Bibb Medical Center",
        state="AL",
        city="Centreville",
        website="https://www.bibbmed.com"
    )
    
    start_time = datetime.now()
    print(f"Searching for price file for {test_hospital.name} in {test_hospital.city}, {test_hospital.state}")
    
    try:
        result = await pipeline.find_price_file(test_hospital)
        
        if result:
            print(f"✅ Success! Found price file:")
            print(f"  URL: {result.url}")
            print(f"  File type: {result.file_type}")
            print(f"  Validated: {result.validated}")
        else:
            print(f"❌ No price file found for {test_hospital.name}")
            
    except Exception as e:
        print(f"Error during price finder execution: {e}")
        import traceback
        print(traceback.format_exc())
    
    elapsed = datetime.now() - start_time
    print(f"Test completed in {elapsed.total_seconds():.2f} seconds")

if __name__ == "__main__":
    asyncio.run(main()) 