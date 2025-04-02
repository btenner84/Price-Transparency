#!/usr/bin/env python3
"""
Import hospital data from Excel to PostgreSQL database.
"""
import os
import sys
import pandas as pd
import uuid
from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError
import argparse
from tqdm import tqdm

# Add the parent directory to the path so we can import from it
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import database models
from database import SessionFactory, create_tables, drop_tables, Hospital, HealthSystem


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Import hospital data to PostgreSQL database')
    parser.add_argument('--excel', default='../Master Hospitals Dataset.xlsx',
                        help='Path to Master Hospitals Dataset.xlsx file')
    parser.add_argument('--reset', action='store_true',
                        help='Drop existing tables before import')
    parser.add_argument('--chunksize', type=int, default=100,
                        help='Batch size for database inserts')
    return parser.parse_args()


def create_health_system_id(system_name, city=None, state=None):
    """Create a unique ID for a health system based on its name and location."""
    if not system_name or pd.isna(system_name) or system_name.strip() == '':
        return None
    
    # Clean system name
    clean_name = system_name.strip().lower().replace(' ', '_')
    
    # Add location if available
    location_parts = []
    if city and not pd.isna(city) and city.strip() != '':
        location_parts.append(city.strip().lower())
    
    if state and not pd.isna(state) and state.strip() != '':
        location_parts.append(state.strip().lower())
    
    # Create a deterministic ID based on the cleaned name
    system_id = f"sys_{clean_name.replace(',', '').replace('.', '')}"
    if location_parts:
        system_id += "_" + "_".join(location_parts)
    
    # Add a hash to make it unique
    return system_id[:50]  # Limit size to avoid issues


def load_hospital_data(file_path, chunksize=100):
    """Load hospital data from Excel file and import into the database."""
    print(f"Loading data from {file_path}...")
    
    # Read the Excel file
    try:
        df = pd.read_excel(file_path)
        total_rows = len(df)
        print(f"Read {total_rows} rows from Excel file")
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return False
    
    # Process health systems first
    health_systems = {}
    systems_created = 0
    hospitals_created = 0
    
    print("Processing health systems...")
    session = SessionFactory()
    
    try:
        # Create "Independent" health system for hospitals without a system
        independent_id = "sys_independent"
        independent_system = HealthSystem(
            id=independent_id,
            name="Independent",
            city=None,
            state=None,
            corp_parent_name=None
        )
        session.add(independent_system)
        session.commit()
        health_systems[independent_id] = {"id": independent_id, "name": "Independent", "hospital_count": 0}
        systems_created += 1
        
        # Track unique health systems
        for _, row in tqdm(df.iterrows(), total=len(df)):
            sys_name = row.get('health_sys_name')
            if pd.isna(sys_name) or not sys_name or sys_name.strip() == '':
                # Skip independent hospitals in this step
                continue
                
            sys_city = row.get('health_sys_city')
            sys_state = row.get('health_sys_state')
            sys_id = create_health_system_id(sys_name, sys_city, sys_state)
            
            if sys_id and sys_id not in health_systems:
                health_systems[sys_id] = {
                    'id': sys_id,
                    'name': sys_name,
                    'city': sys_city if not pd.isna(sys_city) else None,
                    'state': sys_state if not pd.isna(sys_state) else None,
                    'corp_parent_name': row.get('corp_parent_name') if not pd.isna(row.get('corp_parent_name')) else None,
                    'hospital_count': 0
                }
        
        # Insert health systems
        print(f"Inserting {len(health_systems) - 1} additional health systems...")
        for sys_id, system_data in tqdm(health_systems.items()):
            # Skip the Independent system since we've already added it
            if sys_id == independent_id:
                continue
                
            health_system = HealthSystem(
                id=system_data['id'],
                name=system_data['name'],
                city=system_data['city'],
                state=system_data['state'],
                corp_parent_name=system_data['corp_parent_name']
            )
            session.add(health_system)
            systems_created += 1
            
            # Commit in batches
            if systems_created % 100 == 0:
                session.commit()
                
        # Final commit for health systems
        session.commit()
        print(f"Created {systems_created} health systems")
        
        # Process hospitals in chunks to avoid memory issues
        print("Processing hospitals...")
        for index, chunk_df in enumerate(tqdm([df[i:i+chunksize] for i in range(0, len(df), chunksize)])):
            # Process each hospital
            hospitals_batch = []
            for _, row in chunk_df.iterrows():
                # Generate a unique ID
                hospital_id = str(uuid.uuid4())
                
                # Get or assign health system ID
                sys_name = row.get('health_sys_name')
                sys_city = row.get('health_sys_city')
                sys_state = row.get('health_sys_state')
                
                if pd.isna(sys_name) or not sys_name or sys_name.strip() == '':
                    # If no health system, assign to "Independent"
                    sys_id = independent_id
                    health_systems[independent_id]['hospital_count'] += 1
                else:
                    sys_id = create_health_system_id(sys_name, sys_city, sys_state)
                    if sys_id in health_systems:
                        health_systems[sys_id]['hospital_count'] += 1
                    else:
                        # This should not happen but provide a fallback
                        sys_id = independent_id
                        health_systems[independent_id]['hospital_count'] += 1
                
                # Create Hospital object with appropriate values for each column
                hospital = Hospital(
                    id=hospital_id,
                    name=row.get('NAME', ''),
                    address=row.get('ADDRESS', '') if not pd.isna(row.get('ADDRESS')) else None,
                    city=row.get('CITY', '') if not pd.isna(row.get('CITY')) else None,
                    state=row.get('STATE', '') if not pd.isna(row.get('STATE')) else None,
                    zip_code=str(row.get('ZIP', '')) if not pd.isna(row.get('ZIP')) else None,
                    hospital_type=row.get('TYPE', '') if not pd.isna(row.get('TYPE')) else None,
                    status=row.get('STATUS', '') if not pd.isna(row.get('STATUS')) else None,
                    population=int(row.get('POPULATION')) if not pd.isna(row.get('POPULATION')) else None,
                    county=row.get('COUNTY', '') if not pd.isna(row.get('COUNTY')) else None,
                    latitude=float(row.get('LATITUDE')) if not pd.isna(row.get('LATITUDE')) else None,
                    longitude=float(row.get('LONGITUDE')) if not pd.isna(row.get('LONGITUDE')) else None,
                    owner=row.get('OWNER', '') if not pd.isna(row.get('OWNER')) else None,
                    helipad=str(row.get('HELIPAD')).lower() in ['y', 'yes', 'true', '1'] if not pd.isna(row.get('HELIPAD')) else False,
                    health_sys_id=sys_id,
                    health_sys_name=sys_name if not pd.isna(sys_name) else 'Independent',
                    health_sys_city=sys_city if not pd.isna(sys_city) else None,
                    health_sys_state=sys_state if not pd.isna(sys_state) else None,
                    corp_parent_name=row.get('corp_parent_name') if not pd.isna(row.get('corp_parent_name')) else None,
                    website=None,  # No website in dataset
                    price_transparency_url=None,  # No transparency URL in dataset
                    price_file_found=False,
                    search_status='pending',
                    search_attempts=0
                )
                session.add(hospital)
                hospitals_created += 1
            
            # Commit each chunk
            session.commit()
            print(f"Processed chunk {index+1}, total hospitals: {hospitals_created}")
        
        # Update hospital counts for health systems
        print("Updating hospital counts for health systems...")
        for sys_id, system_data in health_systems.items():
            health_system = session.query(HealthSystem).filter_by(id=sys_id).first()
            if health_system:
                health_system.hospital_count = system_data['hospital_count']
        
        session.commit()
        print(f"Import complete. Created {systems_created} health systems and {hospitals_created} hospitals.")
        return True
        
    except SQLAlchemyError as e:
        session.rollback()
        print(f"Database error: {e}")
        return False
    except Exception as e:
        session.rollback()
        print(f"Error during import: {e}")
        return False
    finally:
        session.close()


def main():
    """Main entry point for the script."""
    # Load environment variables
    load_dotenv()
    
    # Parse arguments
    args = parse_args()
    
    # Reset database if requested
    if args.reset:
        print("Creating database tables...")
        create_tables()
    
    # Import data
    success = load_hospital_data(args.excel, args.chunksize)
    
    if success:
        print("Hospital data import completed successfully.")
    else:
        print("Hospital data import failed.")


if __name__ == "__main__":
    main() 