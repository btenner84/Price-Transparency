"""
This file provides a proxy to the db.py module to maintain consistent import paths.
"""

from .db import get_db, create_tables, drop_tables, engine, SessionFactory
from .models import Base, Hospital, HealthSystem, HospitalPriceFile, HospitalSearchLog 