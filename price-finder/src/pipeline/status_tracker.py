import os
import json
import sqlite3
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from ..models.hospital import Hospital
from ..models.price_file import PriceFile

logger = logging.getLogger(__name__)

class StatusTracker:
    """Tracks the status of price transparency file searches."""
    
    # Status constants
    STATUS_PENDING = "pending"
    STATUS_SEARCHING = "searching"
    STATUS_FOUND = "found"
    STATUS_NOT_FOUND = "not_found"
    STATUS_ERROR = "error"
    
    def __init__(self, db_path: str = "data/price_finder.db"):
        """Initialize the status tracker.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize database
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize the SQLite database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create hospitals table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS hospitals (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            state TEXT NOT NULL,
            city TEXT,
            health_system_name TEXT,
            last_searched TIMESTAMP,
            search_status TEXT DEFAULT 'pending',
            search_attempts INTEGER DEFAULT 0,
            validation_date TIMESTAMP,
            updated_at TIMESTAMP
        )
        ''')
        
        # Create price_files table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id TEXT NOT NULL,
            url TEXT NOT NULL,
            file_type TEXT,
            validated BOOLEAN DEFAULT 0,
            validation_score REAL DEFAULT 0,
            validation_notes TEXT,
            file_size INTEGER,
            found_date TIMESTAMP,
            download_date TIMESTAMP,
            contains_prices BOOLEAN DEFAULT 0,
            contains_hospital_name BOOLEAN DEFAULT 0,
            coverage_period TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            FOREIGN KEY (hospital_id) REFERENCES hospitals (id)
        )
        ''')
        
        # Create search_logs table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hospital_id) REFERENCES hospitals (id)
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection.
        
        Returns:
            SQLite connection object
        """
        conn = sqlite3.connect(self.db_path)
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        # Set row factory to return dictionaries
        conn.row_factory = sqlite3.Row
        return conn
    
    def register_hospital(self, hospital: Hospital) -> bool:
        """Register a hospital for tracking.
        
        Args:
            hospital: Hospital object
            
        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if hospital already exists
            cursor.execute("SELECT id FROM hospitals WHERE id = ?", (hospital.id,))
            existing = cursor.fetchone()
            
            now = datetime.now().isoformat()
            
            if existing:
                # Update existing record
                cursor.execute('''
                UPDATE hospitals
                SET name = ?, state = ?, city = ?, health_system_name = ?, updated_at = ?
                WHERE id = ?
                ''', (
                    hospital.name,
                    hospital.state,
                    hospital.city,
                    hospital.health_system_name,
                    now,
                    hospital.id
                ))
            else:
                # Insert new record
                cursor.execute('''
                INSERT INTO hospitals
                (id, name, state, city, health_system_name, search_status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    hospital.id,
                    hospital.name,
                    hospital.state,
                    hospital.city,
                    hospital.health_system_name,
                    self.STATUS_PENDING,
                    now
                ))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error registering hospital {hospital.id}: {str(e)}")
            conn.rollback()
            return False
            
        finally:
            conn.close()
    
    def register_hospitals(self, hospitals: List[Hospital]) -> int:
        """Register multiple hospitals for tracking.
        
        Args:
            hospitals: List of Hospital objects
            
        Returns:
            Number of successfully registered hospitals
        """
        success_count = 0
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            now = datetime.now().isoformat()
            
            for hospital in hospitals:
                try:
                    # Check if hospital already exists
                    cursor.execute("SELECT id FROM hospitals WHERE id = ?", (hospital.id,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Update existing record
                        cursor.execute('''
                        UPDATE hospitals
                        SET name = ?, state = ?, city = ?, health_system_name = ?, updated_at = ?
                        WHERE id = ?
                        ''', (
                            hospital.name,
                            hospital.state,
                            hospital.city,
                            hospital.health_system_name,
                            now,
                            hospital.id
                        ))
                    else:
                        # Insert new record
                        cursor.execute('''
                        INSERT INTO hospitals
                        (id, name, state, city, health_system_name, search_status, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            hospital.id,
                            hospital.name,
                            hospital.state,
                            hospital.city,
                            hospital.health_system_name,
                            self.STATUS_PENDING,
                            now
                        ))
                    
                    success_count += 1
                    
                except Exception as e:
                    logger.error(f"Error registering hospital {hospital.id}: {str(e)}")
                    # Continue with next hospital
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Error in batch hospital registration: {str(e)}")
            conn.rollback()
            
        finally:
            conn.close()
            
        return success_count
    
    def start_search(self, hospital_id: str) -> bool:
        """Mark a hospital as currently being searched.
        
        Args:
            hospital_id: Hospital ID
            
        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            now = datetime.now().isoformat()
            
            # Update hospital status
            cursor.execute('''
            UPDATE hospitals
            SET search_status = ?, last_searched = ?, search_attempts = search_attempts + 1, updated_at = ?
            WHERE id = ?
            ''', (
                self.STATUS_SEARCHING,
                now,
                now,
                hospital_id
            ))
            
            # Log the search start
            cursor.execute('''
            INSERT INTO search_logs (hospital_id, status, message, timestamp)
            VALUES (?, ?, ?, ?)
            ''', (
                hospital_id,
                self.STATUS_SEARCHING,
                "Search started",
                now
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error starting search for hospital {hospital_id}: {str(e)}")
            conn.rollback()
            return False
            
        finally:
            conn.close()
    
    def mark_success(self, hospital_id: str, price_file: PriceFile) -> bool:
        """Mark a hospital search as successful with a found price file.
        
        Args:
            hospital_id: Hospital ID
            price_file: PriceFile object
            
        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            now = datetime.now().isoformat()
            
            # Update hospital status
            cursor.execute('''
            UPDATE hospitals
            SET search_status = ?, validation_date = ?, updated_at = ?
            WHERE id = ?
            ''', (
                self.STATUS_FOUND,
                now,
                now,
                hospital_id
            ))
            
            # Insert the price file
            cursor.execute('''
            INSERT INTO price_files
            (hospital_id, url, file_type, validated, validation_score, validation_notes,
             file_size, found_date, contains_prices, contains_hospital_name, 
             coverage_period, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                hospital_id,
                price_file.url,
                price_file.file_type,
                price_file.validated,
                price_file.validation_score,
                price_file.validation_notes,
                price_file.file_size,
                now,
                price_file.contains_prices,
                price_file.contains_hospital_name,
                price_file.coverage_period,
                now,
                now
            ))
            
            # Log the success
            cursor.execute('''
            INSERT INTO search_logs (hospital_id, status, message, timestamp)
            VALUES (?, ?, ?, ?)
            ''', (
                hospital_id,
                self.STATUS_FOUND,
                f"Found price file: {price_file.url}",
                now
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error marking success for hospital {hospital_id}: {str(e)}")
            conn.rollback()
            return False
            
        finally:
            conn.close()
    
    def mark_failure(self, hospital_id: str, reason: str = None) -> bool:
        """Mark a hospital search as failed.
        
        Args:
            hospital_id: Hospital ID
            reason: Optional failure reason
            
        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            now = datetime.now().isoformat()
            
            # Update hospital status
            cursor.execute('''
            UPDATE hospitals
            SET search_status = ?, updated_at = ?
            WHERE id = ?
            ''', (
                self.STATUS_NOT_FOUND,
                now,
                hospital_id
            ))
            
            # Log the failure
            message = f"Price file not found: {reason if reason else 'No suitable files'}"
            cursor.execute('''
            INSERT INTO search_logs (hospital_id, status, message, timestamp)
            VALUES (?, ?, ?, ?)
            ''', (
                hospital_id,
                self.STATUS_NOT_FOUND,
                message,
                now
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error marking failure for hospital {hospital_id}: {str(e)}")
            conn.rollback()
            return False
            
        finally:
            conn.close()
    
    def mark_error(self, hospital_id: str, error_message: str) -> bool:
        """Mark a hospital search as errored.
        
        Args:
            hospital_id: Hospital ID
            error_message: Error message
            
        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            now = datetime.now().isoformat()
            
            # Update hospital status
            cursor.execute('''
            UPDATE hospitals
            SET search_status = ?, updated_at = ?
            WHERE id = ?
            ''', (
                self.STATUS_ERROR,
                now,
                hospital_id
            ))
            
            # Log the error
            cursor.execute('''
            INSERT INTO search_logs (hospital_id, status, message, timestamp)
            VALUES (?, ?, ?, ?)
            ''', (
                hospital_id,
                self.STATUS_ERROR,
                f"Error during search: {error_message}",
                now
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error marking error for hospital {hospital_id}: {str(e)}")
            conn.rollback()
            return False
            
        finally:
            conn.close()
    
    def get_hospitals_to_search(self, limit: int = 100, states: List[str] = None) -> List[Hospital]:
        """Get a list of hospitals that need to be searched.
        
        Args:
            limit: Maximum number of hospitals to return
            states: Optional list of states to filter by
            
        Returns:
            List of Hospital objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            query = '''
            SELECT id, name, state, city, health_system_name,
                   last_searched, search_status, search_attempts, validation_date
            FROM hospitals
            WHERE search_status = ? OR search_status = ?
            '''
            params = [self.STATUS_PENDING, self.STATUS_ERROR]
            
            if states:
                placeholders = ', '.join(['?'] * len(states))
                query += f" AND state IN ({placeholders})"
                params.extend(states)
            
            query += " ORDER BY search_attempts ASC, validation_date ASC NULLS FIRST, last_searched ASC NULLS FIRST"
            query += f" LIMIT {limit}"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            hospitals = []
            for row in rows:
                hospital = Hospital(
                    id=row['id'],
                    name=row['name'],
                    state=row['state'],
                    city=row['city'],
                    health_system_name=row['health_system_name'],
                    last_search_date=self._parse_datetime(row['last_searched']),
                    search_status=row['search_status'],
                    search_attempts=row['search_attempts']
                )
                hospitals.append(hospital)
            
            return hospitals
            
        except Exception as e:
            logger.error(f"Error getting hospitals to search: {str(e)}")
            return []
            
        finally:
            conn.close()
    
    def get_hospital_status(self, hospital_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a hospital.
        
        Args:
            hospital_id: Hospital ID
            
        Returns:
            Dictionary with hospital status or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Get hospital data
            cursor.execute('''
            SELECT id, name, state, city, health_system_name,
                   last_searched, search_status, search_attempts, validation_date
            FROM hospitals
            WHERE id = ?
            ''', (hospital_id,))
            
            hospital_row = cursor.fetchone()
            if not hospital_row:
                return None
                
            hospital_data = dict(hospital_row)
            
            # Get latest price file if any
            cursor.execute('''
            SELECT id, url, file_type, validated, validation_score,
                   file_size, found_date, contains_prices, contains_hospital_name
            FROM price_files
            WHERE hospital_id = ?
            ORDER BY found_date DESC
            LIMIT 1
            ''', (hospital_id,))
            
            price_file_row = cursor.fetchone()
            if price_file_row:
                hospital_data['price_file'] = dict(price_file_row)
            
            # Get recent logs
            cursor.execute('''
            SELECT status, message, timestamp
            FROM search_logs
            WHERE hospital_id = ?
            ORDER BY timestamp DESC
            LIMIT 5
            ''', (hospital_id,))
            
            logs = [dict(row) for row in cursor.fetchall()]
            hospital_data['logs'] = logs
            
            return hospital_data
            
        except Exception as e:
            logger.error(f"Error getting status for hospital {hospital_id}: {str(e)}")
            return None
            
        finally:
            conn.close()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics for the price finder.
        
        Returns:
            Dictionary with statistics
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            stats = {}
            
            # Total hospitals
            cursor.execute("SELECT COUNT(*) as count FROM hospitals")
            stats['total_hospitals'] = cursor.fetchone()['count']
            
            # Count by status
            cursor.execute('''
            SELECT search_status, COUNT(*) as count
            FROM hospitals
            GROUP BY search_status
            ''')
            stats['status_counts'] = {row['search_status']: row['count'] for row in cursor.fetchall()}
            
            # Price files found
            cursor.execute("SELECT COUNT(*) as count FROM price_files")
            stats['total_price_files'] = cursor.fetchone()['count']
            
            # Validated price files
            cursor.execute("SELECT COUNT(*) as count FROM price_files WHERE validated = 1")
            stats['validated_price_files'] = cursor.fetchone()['count']
            
            # Recent activity
            cursor.execute('''
            SELECT h.name, h.state, l.status, l.message, l.timestamp
            FROM search_logs l
            JOIN hospitals h ON l.hospital_id = h.id
            ORDER BY l.timestamp DESC
            LIMIT 10
            ''')
            stats['recent_activity'] = [dict(row) for row in cursor.fetchall()]
            
            # Count by state
            cursor.execute('''
            SELECT state, COUNT(*) as count, 
                   SUM(CASE WHEN search_status = 'found' THEN 1 ELSE 0 END) as found_count
            FROM hospitals
            GROUP BY state
            ORDER BY count DESC
            ''')
            stats['state_counts'] = [dict(row) for row in cursor.fetchall()]
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting statistics: {str(e)}")
            return {}
            
        finally:
            conn.close()
    
    def export_results(self, output_file: str) -> bool:
        """Export search results to a JSON file.
        
        Args:
            output_file: Path to output file
            
        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Get all hospitals with price files
            cursor.execute('''
            SELECT h.id, h.name, h.state, h.city, h.health_system_name,
                   p.url as price_url, p.file_type, p.validation_score,
                   p.found_date, p.validation_notes
            FROM hospitals h
            LEFT JOIN (
                SELECT hospital_id, url, file_type, validation_score, found_date, validation_notes,
                       ROW_NUMBER() OVER (PARTITION BY hospital_id ORDER BY found_date DESC) as rn
                FROM price_files
                WHERE validated = 1
            ) p ON h.id = p.hospital_id AND p.rn = 1
            ORDER BY h.state, h.name
            ''')
            
            rows = cursor.fetchall()
            
            # Convert to list of dictionaries
            results = []
            for row in rows:
                hospital_data = dict(row)
                
                # Format dates for JSON
                if 'found_date' in hospital_data and hospital_data['found_date']:
                    try:
                        dt = self._parse_datetime(hospital_data['found_date'])
                        if dt:
                            hospital_data['found_date'] = dt.isoformat()
                    except:
                        pass
                
                results.append(hospital_data)
            
            # Write to file
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Error exporting results: {str(e)}")
            return False
            
        finally:
            conn.close()
    
    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse a datetime string from the database.
        
        Args:
            dt_str: Datetime string
            
        Returns:
            Datetime object or None
        """
        if not dt_str:
            return None
            
        try:
            return datetime.fromisoformat(dt_str)
        except:
            return None 