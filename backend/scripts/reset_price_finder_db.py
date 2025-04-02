"""
Reset the price finder database and validate the main database integration.

This script deletes the old price_finder.db file to ensure we're using 
the main database going forward. It also validates the changes by checking
if there are any records in the HospitalPriceFile table.
"""

import os
import sys
import logging
from pathlib import Path
from sqlalchemy.sql import func

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Import database modules
from database.database import get_db
from database.models import Hospital, HospitalPriceFile

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def reset_price_finder_db():
    """
    Delete the old price_finder.db file and validate the main database integration.
    """
    # Path to the old price_finder.db file
    price_finder_db_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) / "price-finder" / "data" / "price_finder.db"
    
    logger.info(f"Checking for old price finder database at {price_finder_db_path}")
    
    # Check if the file exists
    if price_finder_db_path.exists():
        # Backup the file first
        backup_path = price_finder_db_path.with_suffix(".db.bak")
        logger.info(f"Backing up old database to {backup_path}")
        os.rename(price_finder_db_path, backup_path)
        logger.info(f"Successfully backed up old database to {backup_path}")
    else:
        logger.info("Old price finder database not found, no need to reset")
    
    # Now validate the main database
    logger.info("Validating main database...")
    db = next(get_db())
    
    # Check hospital count
    hospital_count = db.query(func.count(Hospital.id)).scalar()
    logger.info(f"Found {hospital_count} hospitals in main database")
    
    # Check hospitals with price files
    hospitals_with_files = db.query(func.count(Hospital.id)).filter(Hospital.price_file_found == True).scalar()
    logger.info(f"Found {hospitals_with_files} hospitals with price files")
    
    # Check hospital price file records
    price_file_count = db.query(func.count(HospitalPriceFile.id)).scalar()
    logger.info(f"Found {price_file_count} price file records")
    
    # Check validated price files
    validated_files = db.query(func.count(HospitalPriceFile.id)).filter(HospitalPriceFile.validated == True).scalar()
    logger.info(f"Found {validated_files} validated price files")
    
    logger.info("Main database validation complete")
    
    return {
        "hospital_count": hospital_count,
        "hospitals_with_files": hospitals_with_files,
        "price_file_count": price_file_count,
        "validated_files": validated_files
    }

if __name__ == "__main__":
    logger.info("Starting price finder database reset...")
    stats = reset_price_finder_db()
    logger.info(f"Price finder database reset complete. Stats: {stats}") 