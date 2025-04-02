#!/usr/bin/env python3
"""
Test script for running the price finder with detailed logging.
"""
import os
import sys
import asyncio
import logging
import traceback
from datetime import datetime

# Add the parent directory to the path so we can import from it
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Import the price finder function
from scripts.run_price_finder import update_database_from_price_finder

# Set up verbose logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

# Set module loggers to DEBUG
for logger_name in [
    "src.pipeline.orchestrator", 
    "src.searchers.serpapi_search",
    "src.searchers.web_crawler", 
    "src.llm.link_analyzer",
    "src.llm.content_analyzer",
    "src.validators.file_validator",
    "src.validators.hospital_matcher",
    "scripts.run_price_finder"
]:
    logging.getLogger(logger_name).setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

async def main():
    """Run the price finder with detailed logging."""
    logger.info("Starting test run of price finder with detailed logging...")
    
    # Run the price finder for a single hospital
    batch_size = 1
    state = None  # You can specify a state code here if you want to filter
    
    logger.info(f"Running price finder with batch_size={batch_size}, state={state}")
    
    try:
        result = await update_database_from_price_finder(batch_size, state)
        logger.info(f"Price finder completed with result: {result}")
    except Exception as e:
        logger.error(f"Error running price finder: {e}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main()) 