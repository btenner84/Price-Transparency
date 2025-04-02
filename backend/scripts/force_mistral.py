#!/usr/bin/env python3
"""
Script to test the price finder with detailed logging to console, forcing Mistral as the LLM provider.
"""

import os
import sys
import asyncio
import logging
import traceback
from datetime import datetime

# Add the parent directory to the path to allow importing modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# Add price-finder directory to path
price_finder_dir = os.path.join(os.path.dirname(parent_dir), "price-finder")
sys.path.append(price_finder_dir)

from scripts.run_price_finder import update_database_from_price_finder

# Set up detailed logging to console
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Set debug level for all relevant modules
for module in [
    'src.pipeline.orchestrator',
    'src.searchers.serpapi_search',
    'src.searchers.web_crawler',
    'src.llm.link_analyzer',
    'src.llm.content_analyzer',
    'src.validators.file_validator',
    'src.validators.hospital_matcher',
    'scripts.run_price_finder'
]:
    logging.getLogger(module).setLevel(logging.DEBUG)

async def main():
    """Run the price finder with a single hospital and detailed logging, using Mistral."""
    print("Starting test run of price finder with detailed logging...")
    
    # Force using Mistral by setting environment variables
    os.environ['LLM_PROVIDER'] = 'mistral'
    os.environ["SERPAPI_KEY"] = "6d57e14bdf08c364978a63ccc98df618c8c033e2c9d572db667be74ad50c188a"
    os.environ["MISTRAL_API_KEY"] = "87QKmlS8vjw0woFXpLnUKVIqLkcMa8Lz"
    
    print(f"Environment variables set:")
    print(f"- LLM_PROVIDER: {os.environ.get('LLM_PROVIDER')}")
    print(f"- SERPAPI_KEY: {os.environ.get('SERPAPI_KEY')[:10]}...")
    print(f"- MISTRAL_API_KEY: {os.environ.get('MISTRAL_API_KEY')[:10]}...")
    
    start_time = datetime.now()
    print(f"Running price finder with batch_size=1, state=None")
    
    try:
        result = await update_database_from_price_finder(batch_size=1, state=None)
        print(f"Price finder completed with result: {result}")
    except Exception as e:
        print(f"Error running price finder: {e}")
        print(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main()) 