from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List

@dataclass
class PriceFile:
    """Data model for price transparency file information."""
    hospital_id: str
    url: str
    file_type: str  # csv, json, xlsx, etc.
    
    # Validation information
    validated: bool = False
    validation_date: Optional[datetime] = None
    validation_score: float = 0.0  # 0-1 confidence score
    validation_notes: Optional[str] = None
    
    # File metadata
    file_size: Optional[int] = None  # in bytes
    last_modified: Optional[datetime] = None
    download_date: Optional[datetime] = None
    
    # Content validation
    contains_prices: bool = False
    contains_hospital_name: bool = False
    coverage_period: Optional[str] = None
    
    # Processing status
    processed: bool = False
    processing_date: Optional[datetime] = None
    processing_errors: List[str] = None
    
    def __post_init__(self):
        if self.processing_errors is None:
            self.processing_errors = []
    
    @property
    def is_valid(self) -> bool:
        """Check if file is valid based on validation criteria."""
        return (self.validated and 
                self.validation_score > 0.8 and
                self.contains_prices and 
                self.contains_hospital_name)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "hospital_id": self.hospital_id,
            "url": self.url,
            "file_type": self.file_type,
            "validated": self.validated,
            "validation_date": self.validation_date.isoformat() if self.validation_date else None,
            "validation_score": self.validation_score,
            "validation_notes": self.validation_notes,
            "file_size": self.file_size,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
            "download_date": self.download_date.isoformat() if self.download_date else None,
            "contains_prices": self.contains_prices,
            "contains_hospital_name": self.contains_hospital_name,
            "coverage_period": self.coverage_period,
            "processed": self.processed,
            "processing_date": self.processing_date.isoformat() if self.processing_date else None,
            "processing_errors": self.processing_errors
        } 