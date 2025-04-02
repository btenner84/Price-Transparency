#!/usr/bin/env python3
"""
Fix script to update hospital records with price transparency URLs
from successful searches that weren't properly saved.
"""
import sys
import os
import json
from datetime import datetime

# Add the parent directory to the path so we can import from it
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import database models
from database import get_db
from database.models import Hospital, HospitalPriceFile, HospitalSearchLog

def update_hospital_with_price_file(hospital_id, url, file_type="csv", validated=True, 
                                   validation_score=0.95, validation_notes=None):
    """
    Update a hospital record with price transparency file information.
    """
    db = next(get_db())
    try:
        # Get the hospital
        hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
        if not hospital:
            print(f"Hospital with ID {hospital_id} not found")
            return False
            
        print(f"Updating hospital: {hospital.name} (ID: {hospital_id})")
        
        # Update hospital fields
        hospital.price_transparency_url = url
        hospital.price_file_found = True
        hospital.search_status = "found"
        hospital.last_search_date = datetime.now()
        
        # Create or update price file record
        price_file = db.query(HospitalPriceFile).filter(
            HospitalPriceFile.hospital_id == hospital_id
        ).first()
        
        if not price_file:
            price_file = HospitalPriceFile(
                hospital_id=hospital_id,
                file_url=url,
                file_type=file_type,
                found_date=datetime.now(),
                validated=validated,
                validation_details=validation_notes
            )
            db.add(price_file)
        else:
            price_file.file_url = url
            price_file.file_type = file_type
            price_file.found_date = datetime.now()
            price_file.validated = validated
            price_file.validation_details = validation_notes
        
        # Create a search log entry
        search_log = HospitalSearchLog(
            hospital_id=hospital_id,
            search_date=datetime.now(),
            status="found",
            details=json.dumps({
                "url": url,
                "file_type": file_type,
                "validated": validated,
                "validation_score": validation_score
            })
        )
        db.add(search_log)
        
        # Commit changes
        db.commit()
        print(f"Successfully updated hospital {hospital.name} with URL: {url}")
        return True
    except Exception as e:
        db.rollback()
        print(f"Error updating hospital {hospital_id}: {str(e)}")
        return False

def update_from_logs():
    """
    Update database using specific results from logs.
    """
    # Known successful results from the logs
    results = [
        {
            "hospital_id": "f7ec5e5f-45c5-4212-972c-0811d12de61e",
            "name": "BAYHEALTH HOSPITAL KENT CAMPUS",
            "url": "https://www.bayhealth.org/-/media/files/patients-and-visitors/billing-financial-aid/price-transparency/2024/823462523-bayhealthemergencyphysicians-standardcharges.csv",
            "validation_score": 0.95,
            "validation_notes": "The file contains detailed pricing information with CPT codes, descriptions, and various payer rates. It also clearly mentions 'Bayhealth Hospital Kent Campus' in the hospital name field, matching the specified hospital. The header rows include standard charge, discounted cash price, and payer-specific negotiated charges, which are typical of valid hospital price transparency data."
        },
        {
            "hospital_id": "4c82ef31-3380-4a6b-9102-9df4a32ac950",
            "name": "CHRISTIANA CARE HEALTH SERVICES - CHRISTIANA HOSPITAL",
            "url": "https://documents.christianacare.org/Finance/510103684_christianacare_standardcharges.csv",
            "validation_score": 0.95,
            "validation_notes": "The file contains detailed pricing information including standard charges, discounted cash prices, and negotiated rates for various payers. It also includes service descriptions and procedure codes (APC codes). The hospital name 'Christianacare' and its locations, including 'Christianacare|Middletown Freestanding Emergency Department|Wilmington Hospital', are clearly mentioned, which matches the specified hospital."
        }
    ]
    
    for result in results:
        update_hospital_with_price_file(
            result["hospital_id"],
            result["url"],
            file_type="csv",
            validated=True,
            validation_score=result["validation_score"],
            validation_notes=result["validation_notes"]
        )

def update_delaware_hospitals():
    """
    Update all Delaware hospitals with a default URL to test the UI.
    """
    db = next(get_db())
    try:
        # Get all Delaware hospitals
        hospitals = db.query(Hospital).filter(Hospital.state == "DE").all()
        print(f"Found {len(hospitals)} hospitals in Delaware")
        
        for hospital in hospitals:
            # Update with a placeholder URL if no URL exists
            if not hospital.price_transparency_url:
                update_hospital_with_price_file(
                    hospital.id,
                    f"https://example.com/price-transparency/{hospital.id}.csv",
                    file_type="csv",
                    validated=True,
                    validation_score=0.9,
                    validation_notes="Test update for demonstration purposes."
                )
        return True
    except Exception as e:
        print(f"Error updating Delaware hospitals: {str(e)}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Update hospital price transparency URLs')
    parser.add_argument('--mode', choices=['logs', 'delaware', 'specific'], 
                        default='logs', help='Update mode')
    parser.add_argument('--hospital-id', help='Specific hospital ID to update')
    parser.add_argument('--url', help='Price transparency URL')
    
    args = parser.parse_args()
    
    if args.mode == 'logs':
        update_from_logs()
    elif args.mode == 'delaware':
        update_delaware_hospitals()
    elif args.mode == 'specific' and args.hospital_id and args.url:
        update_hospital_with_price_file(args.hospital_id, args.url)
    else:
        parser.print_help() 