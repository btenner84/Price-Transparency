import os
import sys
import asyncio
import logging
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional
import json
import subprocess
import yaml
from sqlalchemy.orm import Session

# Add the price-finder directory to the path so we can import from it
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "price-finder"))

# Force Mistral as the LLM provider and set API keys
os.environ["SERPAPI_KEY"] = os.environ.get("SERPAPI_KEY", "6d57e14bdf08c364978a63ccc98df618c8c033e2c9d572db667be74ad50c188a")
# Set the OpenAI API key in the environment (as backup only)
os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "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")
# Set the Mistral API key in the environment
os.environ["MISTRAL_API_KEY"] = os.environ.get("MISTRAL_API_KEY", "87QKmlS8vjw0woFXpLnUKVIqLkcMa8Lz")
# Use Mistral as the default LLM provider
os.environ["LLM_PROVIDER"] = "mistral"

# Import after setting environment variables
from src.pipeline.orchestrator import PriceFinderPipeline
from src.models.hospital import Hospital as PipelineHospital
from src.models.price_file import PriceFile
from src.pipeline.status_tracker import StatusTracker

# Import our custom status tracker
from scripts.custom_status_tracker import MainDBStatusTracker

# Fix the import path for config_loader
try:
    from src.config.config_loader import load_config
except ImportError:
    # If the specific module doesn't exist, define a simple config loader
    def load_config():
        return {
            "serpapi_key": os.environ.get("SERPAPI_KEY"),
            "openai_key": os.environ.get("OPENAI_API_KEY"),
            "mistral_key": os.environ.get("MISTRAL_API_KEY"),
            "llm_provider": "mistral",  # Force mistral as provider
            "download_dir": "downloads"
        }

# Import database modules
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from database.database import get_db
from database.models import Hospital, HospitalPriceFile, HospitalSearchLog

# Create logs directory if it doesn't exist
logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(logs_dir, exist_ok=True)

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG level for more detailed logs
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, "price_finder_integration.log")),
        logging.FileHandler(os.path.join(logs_dir, "price_finder_debug.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def update_database_from_price_finder(batch_size: int = 10, state: Optional[str] = None) -> Dict[str, Any]:
    """
    Run the price finder on hospitals that need updates and update the database with results.
    
    Args:
        batch_size: Number of hospitals to process in this batch
        state: Optional state to filter hospitals by
    
    Returns:
        Dictionary with statistics about the operation
    """
    logger.info(f"Starting price finder integration - batch size: {batch_size}, state: {state}")
    
    # Initialize statistics
    stats = {
        "hospitals_processed": 0,
        "files_found": 0,
        "files_validated": 0,
        "errors": 0,
        "start_time": datetime.now().isoformat(),
        "end_time": None
    }
    
    try:
        # Initialize the price finder pipeline
        config = load_config()
        # Ensure Mistral is set as the provider
        config["llm_provider"] = "mistral"
        logger.debug(f"Config loaded: {config}")
        
        # Create data directory for the status tracker database
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "price-finder", "data")
        os.makedirs(data_dir, exist_ok=True)
        
        # Get a database session
        db = next(get_db())
        
        # Initialize our custom MainDBStatusTracker with the main database session
        status_tracker = MainDBStatusTracker(db)
        logger.info("Status tracker initialized with main application database")
        
        # Initialize the pipeline with our custom status tracker and explicit Mistral provider
        pipeline = PriceFinderPipeline(
            config=config,
            llm_provider="mistral"  # Explicitly set the LLM provider here
        )
        
        # Replace the default status tracker with our custom one
        pipeline.status_tracker = status_tracker
        logger.info("PriceFinderPipeline initialized successfully with custom status tracker")
        
        # Query for hospitals that need processing
        query = db.query(Hospital)
        
        # If state is provided, filter by state
        if state:
            query = query.filter(Hospital.state == state)
        
        # Prioritize hospitals with no search attempts or older searches
        hospitals = query.order_by(
            Hospital.last_search_date.asc().nullsfirst()
        ).limit(batch_size).all()
        
        if not hospitals:
            logger.info("No hospitals found for processing")
            stats["end_time"] = datetime.now().isoformat()
            return stats
        
        logger.info(f"Found {len(hospitals)} hospitals to process")
        
        # Process each hospital
        for hospital in hospitals:
            stats["hospitals_processed"] += 1
            hospital_data = {
                "id": hospital.id,
                "name": hospital.name,
                "website": hospital.website or f"https://www.{hospital.name.lower().replace(' ', '')}.org",  # Provide a fallback URL
                "city": hospital.city or "",
                "state": hospital.state or "",
                "health_system_name": hospital.health_sys_name or "Independent"
            }
            
            logger.debug(f"Hospital object fields: {vars(hospital)}")
            logger.info(f"Searching for price file for hospital: {hospital_data}")
            
            try:
                logger.info(f"Processing hospital: {hospital.name} (ID: {hospital.id})")
                
                # Update the hospital status to searching
                hospital.search_status = "searching"
                hospital.search_attempts = (hospital.search_attempts or 0) + 1
                db.commit()
                
                # Use the price finder to search for price transparency files
                try:
                    # Convert dictionary to Hospital object for the pipeline
                    pipeline_hospital = PipelineHospital(
                        id=hospital_data["id"],
                        name=hospital_data["name"],
                        state=hospital_data["state"],
                        city=hospital_data.get("city", ""),
                        website=hospital_data["website"]
                    )
                    logger.debug(f"Created pipeline hospital object: {pipeline_hospital}")
                    
                    # No need to register hospital with status tracker - our custom tracker handles this
                    
                    # Convert the find_price_file coroutine to a regular function
                    result = await pipeline.find_price_file(pipeline_hospital)
                    
                    if result:
                        logger.info(f"Price finder result: {result.to_dict()}")
                        result_dict = result.to_dict()
                        stats["files_found"] += 1
                        if result.validated:
                            stats["files_validated"] += 1
                    else:
                        logger.warning("Price finder returned None")
                        result_dict = {"status": "not_found"}
                        
                except Exception as pipeline_error:
                    logger.error(f"Error in price finder pipeline: {str(pipeline_error)}")
                    logger.error(f"Pipeline error details: {traceback.format_exc()}")
                    result_dict = {"status": "error", "error": str(pipeline_error)}
                    stats["errors"] += 1
                
                # Update the hospital with the search date and status
                hospital.last_search_date = datetime.now()
                
                # Set the appropriate status based on the result
                if result_dict.get("url"):
                    hospital.search_status = "found"
                    hospital.price_transparency_url = result_dict.get("url")
                    hospital.price_file_found = True
                else:
                    hospital.search_status = "not_found"
                
                # Create a search log entry
                search_log = HospitalSearchLog(
                    hospital_id=hospital.id,
                    search_date=datetime.now(),
                    status=result_dict.get("status", "unknown"),
                    details=json.dumps(result_dict)
                )
                db.add(search_log)
                
                # If we have a price file result with validation info, create/update a HospitalPriceFile record
                if result_dict.get("url") and result_dict.get("validated"):
                    # Check if a price file record already exists
                    existing_price_file = db.query(HospitalPriceFile).filter(
                        HospitalPriceFile.hospital_id == hospital.id,
                        HospitalPriceFile.file_url == result_dict.get("url")
                    ).first()
                    
                    if existing_price_file:
                        # Update existing record
                        existing_price_file.validated = result_dict.get("validated", False)
                        existing_price_file.validation_details = json.dumps({
                            "score": result_dict.get("validation_score", 0.0),
                            "notes": result_dict.get("validation_notes", "")
                        })
                        if result_dict.get("validated", False):
                            existing_price_file.validation_date = datetime.now()
                        existing_price_file.updated_at = datetime.now()
                    else:
                        # Create new record
                        validation_details_json = json.dumps({
                            "score": result_dict.get("validation_score", 0.0),
                            "notes": result_dict.get("validation_notes", "")
                        })
                        
                        price_file = HospitalPriceFile(
                            hospital_id=hospital.id,
                            file_url=result_dict.get("url"),
                            file_type=result_dict.get("file_type", "unknown"),
                            validated=result_dict.get("validated", False),
                            validation_details=validation_details_json,
                            validation_date=datetime.now() if result_dict.get("validated", False) else None,
                            validation_method="price_finder_v1",
                            found_date=datetime.now()
                        )
                        db.add(price_file)
                
                # Commit changes to the database
                try:
                    db.commit()
                    logger.info(f"Successfully updated database for hospital {hospital.name}")
                except Exception as db_error:
                    logger.error(f"Database error while committing changes: {str(db_error)}")
                    db.rollback()
                    
                    # Try a more minimal update to ensure at least the search date gets recorded
                    try:
                        # Create a fresh session
                        new_db = SessionFactory()
                        hospital_update = new_db.query(Hospital).filter(Hospital.id == hospital.id).first()
                        if hospital_update:
                            hospital_update.last_search_date = datetime.now()
                            hospital_update.search_status = result_dict.get("status", "unknown")
                            new_db.commit()
                            logger.info(f"Minimal update succeeded for hospital {hospital.name}")
                        new_db.close()
                    except Exception as minimal_error:
                        logger.error(f"Even minimal update failed: {str(minimal_error)}")
                    
                    stats["errors"] += 1
                
            except Exception as e:
                logger.error(f"Error processing hospital {hospital.id}: {str(e)}")
                logger.error(traceback.format_exc())
                db.rollback()
                
                # Still try to update the last_search_date to prevent hospital from being constantly reprocessed
                try:
                    hospital.last_search_date = datetime.now()
                    hospital.search_status = "error"
                    db.commit()
                except:
                    db.rollback()
                
                stats["errors"] += 1
            
            logger.info(f"Successfully processed hospital {hospital.name}")
            
        # Update statistics with end time
        stats["end_time"] = datetime.now().isoformat()
        return stats
        
    except Exception as e:
        logger.error(f"Error in price finder integration: {str(e)}")
        logger.error(traceback.format_exc())
        stats["errors"] += 1
        stats["end_time"] = datetime.now().isoformat()
        return stats

async def run_price_finder_task(batch_size: int = 10, state: Optional[str] = None) -> Dict[str, Any]:
    """
    Task wrapper for the update_database_from_price_finder function.
    """
    return await update_database_from_price_finder(batch_size, state) 