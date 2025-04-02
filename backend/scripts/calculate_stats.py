#!/usr/bin/env python3
"""
Calculate price transparency statistics directly from the main database.
"""
import sys
import os
from sqlalchemy import func
from datetime import datetime

# Add the parent directory to the path so we can import from it
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import database models
from database import get_db
from database.models import Hospital, HospitalPriceFile, HospitalSearchLog

def calculate_transparency_stats():
    """
    Calculate price transparency statistics directly from the database.
    """
    db = next(get_db())
    try:
        # Get total number of hospitals
        total_hospitals = db.query(func.count(Hospital.id)).scalar() or 0
        
        # Get count of hospitals with price files found
        found_files = db.query(func.count(Hospital.id)).filter(
            Hospital.price_file_found == True
        ).scalar() or 0
        
        # Get count of hospitals with validated price files
        validated_files = db.query(func.count(HospitalPriceFile.id)).filter(
            HospitalPriceFile.validated == True
        ).scalar() or 0
        
        # Calculate percentages
        percent_found = round(found_files / total_hospitals * 100, 1) if total_hospitals > 0 else 0
        percent_validated = round(validated_files / total_hospitals * 100, 1) if total_hospitals > 0 else 0
        
        stats = {
            "total_hospitals": total_hospitals,
            "found_files": found_files,
            "validated_files": validated_files,
            "percent_found": percent_found,
            "percent_validated": percent_validated,
            "last_updated": datetime.now().isoformat()
        }
        
        print(f"Transparency Statistics:")
        print(f"  Total Hospitals: {total_hospitals}")
        print(f"  Found Files: {found_files} ({percent_found}%)")
        print(f"  Validated Files: {validated_files} ({percent_validated}%)")
        print(f"  Last Updated: {stats['last_updated']}")
        
        return stats
    except Exception as e:
        print(f"Error calculating statistics: {e}")
        return None

if __name__ == "__main__":
    calculate_transparency_stats() 