from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime, timedelta

@dataclass
class Hospital:
    """Data model for hospital information."""
    id: str
    name: str
    state: str
    city: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    health_system_name: Optional[str] = None
    
    # Price transparency tracking
    price_transparency_url: Optional[str] = None
    url_validated: bool = False
    validation_date: Optional[datetime] = None
    
    # Search status
    last_search_date: Optional[datetime] = None
    search_status: str = "pending"  # pending, searching, found, not_found
    search_attempts: int = 0
    
    @property
    def search_query_base(self) -> str:
        """Base query for searching."""
        location = f"{self.city}, {self.state}" if self.city else self.state
        return f"{self.name} {location}"
    
    def needs_update(self) -> bool:
        """Check if hospital needs price file update."""
        # If we don't have a validated URL
        if not self.url_validated or not self.price_transparency_url:
            return True
            
        # If validation is older than 3 months
        if self.validation_date:
            three_months_ago = datetime.now() - timedelta(days=90)
            if self.validation_date < three_months_ago:
                return True
                
        return False 