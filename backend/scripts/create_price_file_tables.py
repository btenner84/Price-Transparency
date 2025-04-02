import sys
import os
import logging
from sqlalchemy import create_engine

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

from database.config import DATABASE_URL
from database.models import Base, HospitalPriceFile, HospitalSearchLog

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/db_migrations.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def create_price_file_tables():
    """
    Create the tables required for tracking price files and search logs.
    """
    try:
        logger.info("Creating database engine...")
        engine = create_engine(DATABASE_URL)
        
        logger.info("Creating tables for price files and search logs...")
        # This will create the tables if they don't exist
        Base.metadata.create_all(engine, tables=[
            HospitalPriceFile.__table__,
            HospitalSearchLog.__table__
        ])
        
        logger.info("Successfully created tables!")
        return True
    except Exception as e:
        logger.error(f"Error creating tables: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Starting table creation script...")
    success = create_price_file_tables()
    if success:
        logger.info("Tables created successfully!")
    else:
        logger.error("Failed to create tables.") 