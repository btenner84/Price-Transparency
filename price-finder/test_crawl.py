import os
import json
import logging
import time
from test_search import crawl_for_data_files, is_data_file_url

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("crawler_test.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def test_crawl_price_transparency_page():
    """Test crawling on a known hospital price transparency page."""
    # URL for Providence's price transparency page
    url = "https://www.providence.org/billing-support/pricing-transparency"
    logger.info(f"======== STARTING CRAWL TEST ON {url} ========")
    
    print(f"Starting crawl test on: {url}")
    print("Crawling with increased depth to find actual data files...")
    
    # Try with deeper crawl (3 levels) to have a better chance of finding files
    start_time = time.time()
    found_files = crawl_for_data_files(url, max_depth=3)
    elapsed_time = time.time() - start_time
    
    logger.info(f"Crawl completed in {elapsed_time:.2f} seconds")
    logger.info(f"Found {len(found_files)} potential data files")
    
    print(f"\nCrawl completed in {elapsed_time:.2f} seconds")
    print(f"Found {len(found_files)} potential data files:")
    
    if found_files:
        for i, file_url in enumerate(found_files, 1):
            logger.info(f"DATA FILE #{i}: {file_url}")
            print(f"{i}. {file_url}")
    else:
        logger.warning("NO DATA FILES FOUND")
        print("No data files found. The crawler may need adjustments to detect files on this site.")
    
    logger.info("======== CRAWL TEST COMPLETED ========")

if __name__ == "__main__":
    test_crawl_price_transparency_page() 