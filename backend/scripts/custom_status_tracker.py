"""
Custom StatusTracker implementation that uses the main application database
instead of the separate price_finder.db database.
"""

import os
import sys
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import traceback

# Add the price-finder directory to the path so we can import from it
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "price-finder"))

# Import the original status tracker
from src.pipeline.status_tracker import StatusTracker
from src.models.hospital import Hospital
from src.models.price_file import PriceFile

# Import database modules
from database.database import get_db
from database.db import SessionFactory
from database.models import Hospital as DBHospital, HospitalPriceFile, HospitalSearchLog

logger = logging.getLogger(__name__)

class MainDBStatusTracker(StatusTracker):
    """
    A custom StatusTracker that uses the main application database 
    instead of the separate price_finder.db database.
    
    This class overrides the database operations to use the main database
    while maintaining compatibility with the price finder pipeline.
    """
    
    def __init__(self, db_session):
        """
        Initialize the tracker with a database session from the main application.
        
        Args:
            db_session: SQLAlchemy database session from the main application
        """
        super().__init__()
        self.db_session = db_session
        # We don't need to initialize a database as we're using the existing one
        logger.info("Initialized MainDBStatusTracker with main application database")
    
    def register_hospital(self, hospital: Hospital) -> bool:
        """
        Register a hospital for tracking in the main database.
        
        Args:
            hospital: Hospital object from the price finder
            
        Returns:
            True if successful
        """
        try:
            # Check if hospital already exists in the main DB
            db_hospital = self.db_session.query(DBHospital).filter(DBHospital.id == hospital.id).first()
            
            if db_hospital:
                logger.debug(f"Hospital {hospital.id} already exists in main database")
                return True
            else:
                logger.warning(f"Hospital {hospital.id} not found in main database - this shouldn't happen")
                return False
                
        except Exception as e:
            logger.error(f"Error registering hospital {hospital.id}: {str(e)}")
            return False
    
    def start_search(self, hospital_id: str) -> bool:
        """
        Mark a hospital as being searched in the main database.
        
        Args:
            hospital_id: ID of the hospital to update
            
        Returns:
            True if successful
        """
        try:
            # Update the hospital in the main database
            db_hospital = self.db_session.query(DBHospital).filter(DBHospital.id == hospital_id).first()
            
            if db_hospital:
                db_hospital.search_status = "searching"
                db_hospital.last_search_date = datetime.now()
                db_hospital.search_attempts = (db_hospital.search_attempts or 0) + 1
                
                # Create a search log entry
                search_log = HospitalSearchLog(
                    hospital_id=hospital_id,
                    search_date=datetime.now(),
                    status="searching",
                    details="Started price transparency search"
                )
                self.db_session.add(search_log)
                self.db_session.commit()
                
                return True
            else:
                logger.warning(f"Hospital {hospital_id} not found in main database")
                return False
                
        except Exception as e:
            logger.error(f"Error starting search for hospital {hospital_id}: {str(e)}")
            self.db_session.rollback()
            return False
    
    def mark_success(self, hospital_id: str, price_file: PriceFile) -> bool:
        """
        Mark a hospital search as successful and store the price file in the main database.
        
        Args:
            hospital_id: ID of the hospital to update
            price_file: PriceFile object with file details
            
        Returns:
            True if successful
        """
        try:
            # Update the hospital in the main database
            db_hospital = self.db_session.query(DBHospital).filter(DBHospital.id == hospital_id).first()
            
            if db_hospital:
                # Update hospital record
                db_hospital.search_status = "found"
                db_hospital.last_search_date = datetime.now()
                db_hospital.price_transparency_url = price_file.url
                db_hospital.price_file_found = True
                
                # Create a search log entry - but don't add it yet
                search_log = HospitalSearchLog(
                    hospital_id=hospital_id,
                    search_date=datetime.now(),
                    status="found",
                    details=f"Found price file: {price_file.url}"
                )
                
                # First commit hospital updates to avoid foreign key issues
                try:
                    self.db_session.commit()
                    logger.info(f"Successfully updated hospital {hospital_id} status")
                    
                    # Now handle the price file
                    try:
                        # Check if price file record already exists
                        db_price_file = self.db_session.query(HospitalPriceFile).filter(
                            HospitalPriceFile.hospital_id == hospital_id,
                            HospitalPriceFile.file_url == price_file.url
                        ).first()
                        
                        if db_price_file:
                            # Update existing price file record
                            db_price_file.file_type = price_file.file_type
                            db_price_file.validated = price_file.validated
                            
                            # Convert validation_score and validation_notes to validation_details JSON
                            validation_details = {
                                "score": getattr(price_file, "validation_score", 0.0),
                                "notes": getattr(price_file, "validation_notes", "")
                            }
                            db_price_file.validation_details = json.dumps(validation_details)
                            
                            # Set validation date if validated
                            if price_file.validated and not db_price_file.validation_date:
                                db_price_file.validation_date = datetime.now()
                                
                            db_price_file.updated_at = datetime.now()
                        else:
                            # Create new price file record with proper fields
                            validation_details = {
                                "score": getattr(price_file, "validation_score", 0.0),
                                "notes": getattr(price_file, "validation_notes", "")
                            }
                            
                            db_price_file = HospitalPriceFile(
                                hospital_id=hospital_id,
                                file_url=price_file.url,
                                file_type=price_file.file_type or "unknown",
                                validated=price_file.validated,
                                validation_details=json.dumps(validation_details),
                                validation_date=datetime.now() if price_file.validated else None,
                                validation_method="price_finder_v1",
                                found_date=datetime.now()
                            )
                            self.db_session.add(db_price_file)
                        
                        # Add search log
                        self.db_session.add(search_log)
                        
                        self.db_session.commit()
                        logger.info(f"Successfully added price file for hospital {hospital_id}")
                    except Exception as pf_error:
                        logger.error(f"Error updating price file for hospital {hospital_id}: {str(pf_error)}")
                        self.db_session.rollback()
                        # Don't return False yet, we did update the hospital status
                except Exception as db_error:
                    logger.error(f"Error committing hospital update for {hospital_id}: {str(db_error)}")
                    self.db_session.rollback()
                    return False
                
                return True
            else:
                logger.warning(f"Hospital {hospital_id} not found in main database")
                return False
                
        except Exception as e:
            logger.error(f"Error marking success for hospital {hospital_id}: {str(e)}")
            self.db_session.rollback()
            return False
    
    def mark_failure(self, hospital_id: str, reason: str = None) -> bool:
        """
        Mark a hospital search as failed in the main database.
        
        Args:
            hospital_id: ID of the hospital to update
            reason: Optional reason for failure
            
        Returns:
            True if successful
        """
        try:
            # Update the hospital in the main database
            db_hospital = self.db_session.query(DBHospital).filter(DBHospital.id == hospital_id).first()
            
            if db_hospital:
                db_hospital.search_status = "not_found"
                db_hospital.last_search_date = datetime.now()
                
                # First commit hospital updates to avoid foreign key issues
                try:
                    self.db_session.commit()
                    logger.info(f"Successfully updated hospital {hospital_id} with not_found status")
                    
                    # Then try to add the search log
                    try:
                        # Create a search log entry
                        search_log = HospitalSearchLog(
                            hospital_id=hospital_id,
                            search_date=datetime.now(),
                            status="not_found",
                            details=reason or "No price file found"
                        )
                        self.db_session.add(search_log)
                        self.db_session.commit()
                    except Exception as log_error:
                        logger.error(f"Error adding search log for hospital {hospital_id}: {str(log_error)}")
                        self.db_session.rollback()
                        # Don't return False as we did update the hospital status
                except Exception as db_error:
                    logger.error(f"Error committing hospital update for {hospital_id}: {str(db_error)}")
                    self.db_session.rollback()
                    return False
                
                return True
            else:
                logger.warning(f"Hospital {hospital_id} not found in main database")
                return False
                
        except Exception as e:
            logger.error(f"Error marking failure for hospital {hospital_id}: {str(e)}")
            self.db_session.rollback()
            return False
    
    def mark_error(self, hospital_id: str, error_message: str) -> bool:
        """
        Mark a hospital search as errored in the main database.
        
        Args:
            hospital_id: ID of the hospital to update
            error_message: Error message to store
            
        Returns:
            True if successful
        """
        try:
            # Update the hospital in the main database
            db_hospital = self.db_session.query(DBHospital).filter(DBHospital.id == hospital_id).first()
            
            if db_hospital:
                db_hospital.search_status = "error"
                db_hospital.last_search_date = datetime.now()
                
                # First commit hospital updates to avoid foreign key issues
                try:
                    self.db_session.commit()
                    logger.info(f"Successfully updated hospital {hospital_id} with error status")
                    
                    # Then try to add the search log
                    try:
                        # Create a search log entry
                        search_log = HospitalSearchLog(
                            hospital_id=hospital_id,
                            search_date=datetime.now(),
                            status="error",
                            details=error_message or "Unknown error occurred"
                        )
                        self.db_session.add(search_log)
                        self.db_session.commit()
                    except Exception as log_error:
                        logger.error(f"Error adding search log for hospital {hospital_id}: {str(log_error)}")
                        self.db_session.rollback()
                        # Don't return False as we did update the hospital status
                except Exception as db_error:
                    logger.error(f"Error committing hospital update for {hospital_id}: {str(db_error)}")
                    self.db_session.rollback()
                    return False
                
                return True
            else:
                logger.warning(f"Hospital {hospital_id} not found in main database")
                return False
                
        except Exception as e:
            logger.error(f"Error marking error for hospital {hospital_id}: {str(e)}")
            self.db_session.rollback()
            return False
    
    def get(self, hospital_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current status of a hospital from the main database.
        
        Args:
            hospital_id: ID of the hospital to get status for
            
        Returns:
            Dictionary with hospital status info, or None if not found
        """
        try:
            # Query the hospital from the main database
            db_hospital = self.db_session.query(DBHospital).filter(DBHospital.id == hospital_id).first()
            
            if db_hospital:
                return {
                    "id": hospital_id,
                    "status": db_hospital.search_status or "pending",
                    "last_updated": db_hospital.last_search_date.isoformat() if db_hospital.last_search_date else None,
                    "price_transparency_url": db_hospital.price_transparency_url,
                    "price_file_found": db_hospital.price_file_found
                }
            else:
                logger.warning(f"Hospital {hospital_id} not found in main database")
                return None
                
        except Exception as e:
            logger.error(f"Error getting status for hospital {hospital_id}: {str(e)}")
            return None
    
    def get_hospitals_to_search(self, limit: int = 100, states: List[str] = None) -> List[Hospital]:
        """
        Get hospitals to search from the main database.
        
        Args:
            limit: Maximum number of hospitals to return
            states: Optional list of state codes to filter by
            
        Returns:
            List of Hospital objects
        """
        try:
            # Query hospitals from the main database
            query = self.db_session.query(DBHospital)
            
            # Apply state filter if provided
            if states:
                query = query.filter(DBHospital.state.in_([s.upper() for s in states]))
            
            # Order by search date (oldest first) and limit results
            hospitals = query.order_by(
                DBHospital.last_search_date.asc().nullsfirst()
            ).limit(limit).all()
            
            # Convert to Pipeline Hospital objects
            pipeline_hospitals = []
            for hospital in hospitals:
                pipeline_hospital = Hospital(
                    id=hospital.id,
                    name=hospital.name,
                    state=hospital.state,
                    city=hospital.city,
                    address=hospital.address,
                    website=hospital.website,
                    health_system_name=hospital.health_sys_name,
                    price_transparency_url=hospital.price_transparency_url,
                    url_validated=bool(hospital.price_file_found),
                    validation_date=hospital.updated_at,
                    last_search_date=hospital.last_search_date,
                    search_status=hospital.search_status or "pending",
                    search_attempts=hospital.search_attempts or 0
                )
                pipeline_hospitals.append(pipeline_hospital)
            
            return pipeline_hospitals
                
        except Exception as e:
            logger.error(f"Error getting hospitals to search: {str(e)}")
            return [] 