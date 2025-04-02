#!/usr/bin/env python3
"""
Reset placeholder price transparency URLs before running the real price finder.
"""
import sys
import os
from datetime import datetime

# Add the parent directory to the path so we can import from it
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import database models
from database import get_db
from database.models import Hospital, HospitalPriceFile, HospitalSearchLog

def reset_placeholder_urls():
    """
    Reset placeholder URLs that contain 'example.com' to NULL so we can run the real price finder.
    """
    db = next(get_db())
    try:
        # Find hospitals with placeholder URLs
        placeholder_hospitals = db.query(Hospital).filter(
            Hospital.price_transparency_url.like('%example.com%')
        ).all()
        
        print(f"Found {len(placeholder_hospitals)} hospitals with placeholder URLs")
        
        # Reset each hospital
        for hospital in placeholder_hospitals:
            print(f"Resetting hospital: {hospital.name} (ID: {hospital.id})")
            
            # Delete price file records
            price_files = db.query(HospitalPriceFile).filter(
                HospitalPriceFile.hospital_id == hospital.id
            ).all()
            
            for price_file in price_files:
                db.delete(price_file)
            
            # Reset hospital fields
            hospital.price_transparency_url = None
            hospital.price_file_found = False
            hospital.search_status = "pending"
            hospital.search_attempts = 0
            hospital.last_search_date = None
            
            # Add a search log entry
            search_log = HospitalSearchLog(
                hospital_id=hospital.id,
                search_date=datetime.now(),
                status="reset",
                details="Placeholder URL reset for real price finder run"
            )
            db.add(search_log)
        
        # Commit changes
        db.commit()
        print(f"Successfully reset {len(placeholder_hospitals)} hospitals with placeholder URLs")
        return True
    except Exception as e:
        db.rollback()
        print(f"Error resetting placeholder URLs: {str(e)}")
        return False

def reset_all_delaware_hospitals():
    """
    Reset all Delaware hospitals to prepare for a fresh price finder run.
    """
    db = next(get_db())
    try:
        # Get all Delaware hospitals
        hospitals = db.query(Hospital).filter(Hospital.state == "DE").all()
        print(f"Found {len(hospitals)} hospitals in Delaware")
        
        # Reset each hospital
        for hospital in hospitals:
            print(f"Resetting hospital: {hospital.name} (ID: {hospital.id})")
            
            # Delete price file records
            price_files = db.query(HospitalPriceFile).filter(
                HospitalPriceFile.hospital_id == hospital.id
            ).all()
            
            for price_file in price_files:
                db.delete(price_file)
            
            # Reset hospital fields
            hospital.price_transparency_url = None
            hospital.price_file_found = False
            hospital.search_status = "pending"
            hospital.search_attempts = 0
            hospital.last_search_date = None
        
        # Commit changes
        db.commit()
        print(f"Successfully reset {len(hospitals)} Delaware hospitals")
        return True
    except Exception as e:
        db.rollback()
        print(f"Error resetting Delaware hospitals: {str(e)}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Reset placeholder URLs before running the real price finder')
    parser.add_argument('--mode', choices=['placeholders', 'delaware', 'all'], 
                      default='placeholders', help='Reset mode')
    
    args = parser.parse_args()
    
    if args.mode == 'placeholders':
        reset_placeholder_urls()
    elif args.mode == 'delaware':
        reset_all_delaware_hospitals()
    elif args.mode == 'all':
        reset_placeholder_urls()
        reset_all_delaware_hospitals()