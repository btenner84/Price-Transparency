import asyncio
import logging
import sys
import os
import time
import random
from datetime import datetime

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Import our integration script
from scripts.run_price_finder import update_database_from_price_finder

# Create logs directory if it doesn't exist
logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(logs_dir, exist_ok=True)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, "scheduler.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def scheduled_runner():
    """
    Run the price finder periodically, with randomized batch sizes and intervals
    """
    logger.info("Starting scheduled price finder runner")
    
    while True:
        try:
            # Randomize batch size between 5 and 15
            batch_size = random.randint(5, 15)
            
            # Get current time for logging
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[{now}] Running scheduled price finder with batch size {batch_size}")
            
            # Run the price finder
            result = await update_database_from_price_finder(batch_size=batch_size)
            
            # Log the results
            logger.info(f"Completed run: processed {result['hospitals_processed']} hospitals, " 
                        f"found {result['files_found']} files, "
                        f"validated {result['files_validated']} files, "
                        f"errors: {result['errors']}")
            
            # Randomize wait time between 2 and 5 minutes
            wait_time = random.randint(120, 300)
            logger.info(f"Waiting for {wait_time} seconds until next run")
            
            # Wait before next run
            await asyncio.sleep(wait_time)
            
        except Exception as e:
            logger.error(f"Error in scheduled runner: {str(e)}")
            # Wait 5 minutes before trying again after an error
            logger.info("Waiting 5 minutes before next attempt after error")
            await asyncio.sleep(300)

if __name__ == "__main__":
    logger.info("=== Starting Price Finder Scheduler ===")
    # Run the scheduler
    try:
        asyncio.run(scheduled_runner())
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Scheduler stopped due to error: {str(e)}") 