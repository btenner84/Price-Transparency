from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, DateTime, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class HealthSystem(Base):
    __tablename__ = 'health_systems'
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    city = Column(String)
    state = Column(String(2))
    corp_parent_name = Column(String)  # Added for corporate parent
    hospital_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    hospitals = relationship("Hospital", back_populates="health_system")
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('health_sys_name', ''),
            city=data.get('health_sys_city', ''),
            state=data.get('health_sys_state', ''),
            corp_parent_name=data.get('corp_parent_name', '')
        )
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "city": self.city,
            "state": self.state,
            "corp_parent_name": self.corp_parent_name,
            "hospital_count": self.hospital_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class Hospital(Base):
    __tablename__ = 'hospitals'
    
    id = Column(String, primary_key=True)
    # Basic information (from Excel)
    name = Column(String, nullable=False)       # NAME
    address = Column(String)                    # ADDRESS
    city = Column(String)                       # CITY
    state = Column(String(2))                   # STATE
    zip_code = Column(String)                   # ZIP
    hospital_type = Column(String)              # TYPE
    status = Column(String)                     # STATUS
    population = Column(Integer)                # POPULATION
    county = Column(String)                     # COUNTY
    latitude = Column(Float)                    # LATITUDE
    longitude = Column(Float)                   # LONGITUDE
    owner = Column(String)                      # OWNER
    helipad = Column(Boolean, default=False)    # HELIPAD
    
    # Health system information (from Excel)
    health_sys_id = Column(String, ForeignKey('health_systems.id'))
    health_sys_name = Column(String)            # health_sys_name
    health_sys_city = Column(String)            # health_sys_city
    health_sys_state = Column(String)           # health_sys_state
    corp_parent_name = Column(String)           # corp_parent_name
    
    # Additional fields
    website = Column(String)
    
    # Price transparency data
    price_transparency_url = Column(Text)
    price_file_found = Column(Boolean, default=False)
    search_status = Column(String, default="pending")  # pending, searching, found, not_found
    search_attempts = Column(Integer, default=0)
    last_search_date = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    health_system = relationship("HealthSystem", back_populates="hospitals")
    
    # Relationships
    price_files = relationship("HospitalPriceFile", back_populates="hospital")
    search_logs = relationship("HospitalSearchLog", back_populates="hospital")
    
    @classmethod
    def from_dict(cls, data):
        # Convert helipad to boolean
        helipad_val = False
        if 'HELIPAD' in data:
            helipad_str = str(data.get('HELIPAD', '')).strip().lower()
            helipad_val = helipad_str in ['y', 'yes', 'true', '1']
        
        # Convert population to integer
        population_val = None
        if 'POPULATION' in data:
            try:
                population_val = int(data.get('POPULATION', 0))
            except (ValueError, TypeError):
                population_val = None
        
        # Convert lat/long to float
        lat_val = None
        if 'LATITUDE' in data:
            try:
                lat_val = float(data.get('LATITUDE', 0))
            except (ValueError, TypeError):
                lat_val = None
                
        long_val = None
        if 'LONGITUDE' in data:
            try:
                long_val = float(data.get('LONGITUDE', 0))
            except (ValueError, TypeError):
                long_val = None
        
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('NAME', ''),
            address=data.get('ADDRESS', ''),
            city=data.get('CITY', ''),
            state=data.get('STATE', ''),
            zip_code=data.get('ZIP', ''),
            hospital_type=data.get('TYPE', ''),
            status=data.get('STATUS', ''),
            population=population_val,
            county=data.get('COUNTY', ''),
            latitude=lat_val,
            longitude=long_val,
            owner=data.get('OWNER', ''),
            helipad=helipad_val,
            health_sys_id=data.get('health_sys_id', ''),
            health_sys_name=data.get('health_sys_name', ''),
            health_sys_city=data.get('health_sys_city', ''),
            health_sys_state=data.get('health_sys_state', ''),
            corp_parent_name=data.get('corp_parent_name', ''),
            website=data.get('website', ''),
            price_transparency_url=data.get('price_transparency_url'),
            price_file_found=bool(data.get('price_transparency_url')),
            search_status=data.get('search_status', 'pending')
        )
    
    def to_dict(self):
        return {
            "id": self.id,
            "NAME": self.name,
            "ADDRESS": self.address,
            "CITY": self.city,
            "STATE": self.state,
            "ZIP": self.zip_code,
            "TYPE": self.hospital_type,
            "STATUS": self.status,
            "POPULATION": self.population,
            "COUNTY": self.county,
            "LATITUDE": self.latitude,
            "LONGITUDE": self.longitude,
            "OWNER": self.owner,
            "HELIPAD": self.helipad,
            "health_sys_id": self.health_sys_id,
            "health_sys_name": self.health_sys_name,
            "health_sys_city": self.health_sys_city,
            "health_sys_state": self.health_sys_state,
            "corp_parent_name": self.corp_parent_name,
            "website": self.website,
            "price_transparency_url": self.price_transparency_url,
            "price_file_found": self.price_file_found,
            "search_status": self.search_status,
            "search_attempts": self.search_attempts,
            "last_search_date": self.last_search_date.isoformat() if self.last_search_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        } 

class HospitalPriceFile(Base):
    __tablename__ = 'hospital_price_files'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hospital_id = Column(String, ForeignKey('hospitals.id'), nullable=False)
    file_url = Column(Text, nullable=False)
    file_type = Column(String)  # csv, json, xlsx, etc.
    found_date = Column(DateTime, default=datetime.utcnow)
    validated = Column(Boolean, default=False)
    validation_date = Column(DateTime)
    validation_method = Column(String)
    validation_details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    hospital = relationship("Hospital", back_populates="price_files")
    
    def to_dict(self):
        return {
            "id": self.id,
            "hospital_id": self.hospital_id,
            "file_url": self.file_url,
            "file_type": self.file_type,
            "found_date": self.found_date.isoformat() if self.found_date else None,
            "validated": self.validated,
            "validation_date": self.validation_date.isoformat() if self.validation_date else None,
            "validation_method": self.validation_method,
            "validation_details": self.validation_details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class HospitalSearchLog(Base):
    __tablename__ = 'hospital_search_logs'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hospital_id = Column(String, ForeignKey('hospitals.id'), nullable=False)
    search_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, nullable=False)  # pending, searching, found, not_found, error
    details = Column(Text)  # JSON string with search details
    created_at = Column(DateTime, default=datetime.utcnow)
    
    hospital = relationship("Hospital", back_populates="search_logs")
    
    def to_dict(self):
        return {
            "id": self.id,
            "hospital_id": self.hospital_id,
            "search_date": self.search_date.isoformat() if self.search_date else None,
            "status": self.status,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None
        } 