import os
import logging
import csv
import json
import pandas as pd
import re
from typing import Tuple, List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class FileValidator:
    """Validates if files are valid price transparency files."""
    
    # File extensions that could contain price transparency data
    VALID_EXTENSIONS = ['.csv', '.json', '.xlsx', '.xls', '.xml', '.txt']
    
    # Keywords likely to appear in price transparency headers
    PRICE_KEYWORDS = [
        'price', 'charge', 'rate', 'fee', 'cost', 'amount', '$', 'dollar',
        'payer', 'cash', 'negotiated', 'discount'
    ]
    
    # Keywords likely to appear in procedure/service columns
    SERVICE_KEYWORDS = [
        'code', 'cpt', 'hcpcs', 'ms-drg', 'drg', 'procedure', 'service',
        'description', 'item', 'treatment'
    ]
    
    # Regular expression for identifying price-like values (currency)
    PRICE_PATTERN = re.compile(r'^\s*\$?\s*\d+(?:[,.]\d+)?\s*$')
    
    def __init__(self, min_price_columns: int = 1, min_rows: int = 10, sample_size: int = 100):
        """Initialize the file validator.
        
        Args:
            min_price_columns: Minimum number of price columns required
            min_rows: Minimum number of data rows required
            sample_size: Number of rows to sample for validation
        """
        self.min_price_columns = min_price_columns
        self.min_rows = min_rows
        self.sample_size = sample_size
    
    def is_valid_format(self, file_path: Path) -> bool:
        """Check if the file format is supported and likely to be a price file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if the file format is valid
        """
        # Check file extension
        file_ext = os.path.splitext(str(file_path))[1].lower()
        if file_ext not in self.VALID_EXTENSIONS:
            logger.info(f"Invalid file extension: {file_ext}")
            return False
        
        # Check file size (must be non-empty, but not too large)
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            logger.info(f"File is empty: {file_path}")
            return False
        
        if file_size > 1024 * 1024 * 100:  # 100 MB
            logger.warning(f"File is very large ({file_size / (1024*1024):.2f} MB): {file_path}")
            # Don't reject based on size alone, but log a warning
        
        # Basic content checks based on file type
        try:
            if file_ext == '.csv':
                return self._validate_csv(file_path)
            elif file_ext in ['.xlsx', '.xls']:
                return self._validate_excel(file_path)
            elif file_ext == '.json':
                return self._validate_json(file_path)
            elif file_ext == '.xml':
                # XML validation is complex, default to true and let LLM evaluate
                return True
            elif file_ext == '.txt':
                # Try to parse as CSV first
                if self._validate_csv(file_path):
                    return True
                # If that fails, do basic content checks
                return self._validate_text(file_path)
            
            return False
        except Exception as e:
            logger.error(f"Error validating file {file_path}: {str(e)}")
            return False
    
    def _validate_csv(self, file_path: Path) -> bool:
        """Validate a CSV file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                # Try to read the CSV file
                csv_reader = csv.reader(f)
                
                # Get the header row
                try:
                    headers = next(csv_reader)
                except StopIteration:
                    logger.info(f"Empty CSV file: {file_path}")
                    return False
                
                # Check if headers suggest price data
                if not self._headers_indicate_price_file(headers):
                    logger.info(f"Headers don't suggest price data: {headers}")
                    return False
                
                # Count rows and check for price-like data
                row_count = 0
                price_values_found = False
                
                for i, row in enumerate(csv_reader):
                    row_count += 1
                    
                    if i < self.sample_size:
                        # Check if any cells contain price-like values
                        for cell in row:
                            if self.PRICE_PATTERN.match(cell):
                                price_values_found = True
                                break
                    
                    if row_count >= self.min_rows and price_values_found:
                        break
                
                if row_count < self.min_rows:
                    logger.info(f"Not enough data rows: {row_count} < {self.min_rows}")
                    return False
                
                if not price_values_found:
                    logger.info(f"No price-like values found in sample")
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"Error reading CSV {file_path}: {str(e)}")
            return False
    
    def _validate_excel(self, file_path: Path) -> bool:
        """Validate an Excel file."""
        try:
            # Read first sheet of Excel file
            df = pd.read_excel(file_path, nrows=self.sample_size)
            
            if df.empty:
                logger.info(f"Empty Excel file: {file_path}")
                return False
            
            # Check headers
            headers = df.columns.tolist()
            if not self._headers_indicate_price_file(headers):
                logger.info(f"Headers don't suggest price data: {headers}")
                return False
            
            # Check row count
            if len(df) < self.min_rows:
                logger.info(f"Not enough data rows: {len(df)} < {self.min_rows}")
                return False
            
            # Check for price-like values
            price_values_found = False
            for col in df.columns:
                # Convert column to string for pattern matching
                if df[col].dtype in ['float64', 'int64'] or 'float' in str(df[col].dtype) or 'int' in str(df[col].dtype):
                    price_values_found = True
                    break
                
                # Check string columns for price patterns
                for val in df[col].astype(str).head(self.sample_size):
                    if self.PRICE_PATTERN.match(str(val)):
                        price_values_found = True
                        break
            
            if not price_values_found:
                logger.info(f"No price-like values found in sample")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error reading Excel {file_path}: {str(e)}")
            return False
    
    def _validate_json(self, file_path: Path) -> bool:
        """Validate a JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                data = json.load(f)
            
            # Check if it's an empty object or array
            if not data:
                logger.info(f"Empty JSON data: {file_path}")
                return False
            
            # If it's an array, check number of items
            if isinstance(data, list):
                if len(data) < self.min_rows:
                    logger.info(f"Not enough data items: {len(data)} < {self.min_rows}")
                    return False
                
                # Check first item for price-related keys
                if data:
                    first_item = data[0]
                    if isinstance(first_item, dict):
                        keys = list(first_item.keys())
                        if not self._headers_indicate_price_file(keys):
                            logger.info(f"Keys don't suggest price data: {keys}")
                            return False
                        
                        # Check for price-like values
                        price_values_found = self._json_contains_price_values(data[:self.sample_size])
                        if not price_values_found:
                            logger.info(f"No price-like values found in JSON sample")
                            return False
            
            # If it's an object, check for price-related keys and nested arrays
            elif isinstance(data, dict):
                keys = list(data.keys())
                
                # Look for arrays in the object
                arrays_found = False
                for key, value in data.items():
                    if isinstance(value, list) and len(value) >= self.min_rows:
                        arrays_found = True
                        # Check if this array contains price data
                        if value and isinstance(value[0], dict):
                            subkeys = list(value[0].keys())
                            if self._headers_indicate_price_file(subkeys):
                                # Check for price-like values
                                price_values_found = self._json_contains_price_values(value[:self.sample_size])
                                if price_values_found:
                                    return True
                
                if not arrays_found:
                    logger.info(f"No suitable arrays found in JSON")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error reading JSON {file_path}: {str(e)}")
            return False
    
    def _validate_text(self, file_path: Path) -> bool:
        """Validate a plain text file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                # Read a sample of the file
                lines = [next(f) for _ in range(self.sample_size + 1) if f]
            
            if not lines:
                logger.info(f"Empty text file: {file_path}")
                return False
            
            # Check if it contains price-like patterns
            price_pattern_count = 0
            for line in lines:
                # Count occurrences of price patterns ($100, 100.00, etc.)
                matches = re.findall(r'\$?\s*\d+(?:[,.]\d+)?', line)
                price_pattern_count += len(matches)
            
            # If there are many price-like patterns, it's likely a price file
            if price_pattern_count > len(lines) * 2:  # At least 2 prices per line on average
                return True
                
            # Also check for price-related keywords
            keyword_count = 0
            for keyword in self.PRICE_KEYWORDS + self.SERVICE_KEYWORDS:
                for line in lines:
                    if re.search(r'\b' + re.escape(keyword) + r'\b', line.lower()):
                        keyword_count += 1
            
            # If many price-related keywords found, likely a price file
            if keyword_count >= 5:
                return True
            
            logger.info(f"Text file doesn't appear to contain price data")
            return False
            
        except Exception as e:
            logger.error(f"Error reading text file {file_path}: {str(e)}")
            return False
    
    def _headers_indicate_price_file(self, headers: List[str]) -> bool:
        """Check if headers suggest a price transparency file."""
        # Convert headers to lowercase for case-insensitive matching
        headers_lower = [h.lower() if isinstance(h, str) else str(h).lower() for h in headers]
        
        # Count price-related and service-related headers
        price_header_count = 0
        service_header_count = 0
        
        for header in headers_lower:
            for keyword in self.PRICE_KEYWORDS:
                if keyword in header:
                    price_header_count += 1
                    break
                    
            for keyword in self.SERVICE_KEYWORDS:
                if keyword in header:
                    service_header_count += 1
                    break
        
        # Need at least one price column and one service column
        return price_header_count >= self.min_price_columns and service_header_count >= 1
    
    def _json_contains_price_values(self, data: List[Dict]) -> bool:
        """Check if JSON data contains price-like values."""
        # Recursively check all values in the JSON for price patterns
        def check_value(value):
            if isinstance(value, (str, int, float)):
                # Check if it's a number or a string with a price pattern
                if isinstance(value, (int, float)) and value > 0:
                    return True
                elif isinstance(value, str) and self.PRICE_PATTERN.match(value):
                    return True
            elif isinstance(value, dict):
                return any(check_value(v) for v in value.values())
            elif isinstance(value, list):
                return any(check_value(v) for v in value)
            return False
        
        return any(check_value(item) for item in data) 