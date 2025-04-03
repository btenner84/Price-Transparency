import os
import logging
import csv
import json
import pandas as pd
import re
import zipfile
import tempfile
from typing import Tuple, List, Dict, Any, Optional, Set
from pathlib import Path

logger = logging.getLogger(__name__)

class FileValidator:
    """Validates if files are valid price transparency files."""
    
    # File extensions that could contain price transparency data
    VALID_EXTENSIONS = ['.csv', '.json', '.xlsx', '.xls', '.xml', '.txt', '.pdf', '.html', '.htm', '.tsv', '.dat', '.zip']
    
    # Keywords likely to appear in price transparency headers
    PRICE_KEYWORDS = [
        'price', 'charge', 'rate', 'fee', 'cost', 'amount', '$', 'dollar',
        'payer', 'cash', 'negotiated', 'discount', 'payment', 'reimbursement',
        'gross', 'insurance', 'insurer', 'contracted', 'standard', 'charges',
        'pricing', 'rates', 'dollars', 'estimate', 'drg', 'ms-drg', 'billing'
    ]
    
    # Keywords likely to appear in procedure/service columns
    SERVICE_KEYWORDS = [
        'code', 'cpt', 'hcpcs', 'ms-drg', 'drg', 'procedure', 'service',
        'description', 'item', 'treatment', 'drug', 'medication', 'rev',
        'supplies', 'therapy', 'product', 'ndc', 'national drug code', 'visit',
        'imaging', 'lab', 'surgery', 'care', 'diagnostic', 'test'
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
        """Validate that a file has the correct format for a price transparency file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if valid format, False otherwise
        """
        # Check if file exists
        if not file_path.exists():
            logger.warning(f"File does not exist: {file_path}")
            return False
            
        # Check file size (must be non-empty, but not too large)
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            logger.info(f"File is empty: {file_path}")
            return False
        if file_size > 100 * 1024 * 1024:  # 100 MB limit
            logger.info(f"File too large: {file_path} ({file_size / (1024*1024):.2f} MB)")
            return False
            
        # Try to infer and validate the format for files without extensions
        if not file_path.suffix:
            return self._infer_and_validate_format(file_path)
            
        # Check file extension
        file_ext = file_path.suffix.lower()
        if file_ext not in self.VALID_EXTENSIONS:
            logger.info(f"Invalid file extension: {file_ext}")
            return False
        
        # If it's a .html or .htm file, check if it's likely a full webpage vs a data file
        if file_ext in ['.html', '.htm']:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read(4000)  # Read first 4KB
                    
                    # Check if it's a standard HTML page vs a data table
                    if '<!DOCTYPE html>' in content or '<html' in content:
                        # Skip pages with obvious indicators they're not price files
                        # like login pages, error pages, etc.
                        non_price_indicators = [
                            'login', 'signin', 'error', '404', 'not found', 'page not found',
                            '<form', 'password', 'username', 'log in', 'sign in'
                        ]
                        if any(indicator in content.lower() for indicator in non_price_indicators):
                            logger.info(f"Skipping HTML page that appears to be login/error: {file_path}")
                            return False
                            
                        # Look for table tags with price indicators
                        has_price_table = False
                        
                        # Read more content if needed for analysis
                        if len(content) < 4000:
                            content = f.read()
                            
                        # Check if there are price-related tables
                        price_indicators = ['price', 'charge', 'cost', 'rate', 'fee', 'cpt', 'hcpcs', 'procedure']
                        
                        # Simple check for tables with price columns
                        if '<table' in content and any(ind in content.lower() for ind in price_indicators):
                            # Check if there are actual tables with numerical data 
                            # (not just navigation or layout tables)
                            import re
                            # Look for patterns that suggest price data in tables
                            # Like: <td>$100.00</td> or <td>100.00</td>
                            price_patterns = [
                                r'<td[^>]*>\s*\$?\d+\.\d+\s*</td>',  # Price with decimals
                                r'<td[^>]*>\s*\$?\d+\s*</td>',        # Whole number price
                            ]
                            
                            for pattern in price_patterns:
                                if re.search(pattern, content):
                                    has_price_table = True
                                    break
                            
                        # Only accept HTML pages that have clear price tables
                        if not has_price_table:
                            logger.info(f"HTML file without price tables: {file_path}")
                            return False
            except Exception as e:
                logger.error(f"Error checking HTML content: {str(e)}")
                
        # If it's a ZIP file, extract and validate its contents
        if file_ext == '.zip':
            return self._validate_zip_file(file_path)
            
        # Basic content checks based on file type
        try:
            if file_ext in ['.csv', '.txt', '.tsv', '.dat']:
                return self._validate_csv(file_path)
            elif file_ext in ['.xlsx', '.xls']:
                return self._validate_excel(file_path)
            elif file_ext == '.json':
                return self._validate_json(file_path)
            elif file_ext == '.xml':
                # XML validation is complex, default to true and let LLM evaluate
                return True
            elif file_ext in ['.pdf', '.html', '.htm']:
                # For PDF and HTML files, assume they're valid if they have the right size
                # They'll be further validated during content analysis
                return file_size > 1000  # At least 1KB
            else:
                logger.warning(f"Unsupported file type: {file_ext}")
                return False
        except Exception as e:
            logger.error(f"Error validating file {file_path}: {str(e)}")
            return False
    
    def _validate_zip_file(self, zip_path: Path) -> bool:
        """Validate a zip file by extracting and checking its contents.
        
        Args:
            zip_path: Path to the zip file
            
        Returns:
            True if a valid price file is found within the zip, False otherwise
        """
        logger.info(f"Validating zip file: {zip_path}")
        
        try:
            # Create a temporary directory for extraction
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract the zip file
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # Check if any of the extracted files are valid price files
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        extracted_path = Path(os.path.join(root, file))
                        file_ext = extracted_path.suffix.lower()
                        
                        # Skip any nested zip files to avoid recursion issues
                        if file_ext == '.zip':
                            continue
                        
                        # Check if this file is a valid price file
                        if file_ext in self.VALID_EXTENSIONS and file_ext != '.zip':
                            logger.info(f"Checking extracted file: {file}")
                            
                            # Validate based on file type
                            try:
                                if file_ext in ['.csv', '.txt', '.tsv', '.dat']:
                                    if self._validate_csv(extracted_path):
                                        logger.info(f"Found valid CSV in zip: {file}")
                                        return True
                                elif file_ext in ['.xlsx', '.xls']:
                                    if self._validate_excel(extracted_path):
                                        logger.info(f"Found valid Excel in zip: {file}")
                                        return True
                                elif file_ext == '.json':
                                    if self._validate_json(extracted_path):
                                        logger.info(f"Found valid JSON in zip: {file}")
                                        return True
                                elif file_ext == '.xml':
                                    if self._validate_xml(extracted_path):
                                        logger.info(f"Found valid XML in zip: {file}")
                                        return True
                            except Exception as e:
                                logger.warning(f"Error validating extracted file {file}: {str(e)}")
                                continue
                
                logger.info(f"No valid price files found in zip: {zip_path}")
                return False
                
        except zipfile.BadZipFile:
            logger.warning(f"Invalid zip file: {zip_path}")
            return False
        except Exception as e:
            logger.error(f"Error processing zip file {zip_path}: {str(e)}")
            return False
    
    def _infer_and_validate_format(self, file_path: Path) -> bool:
        """Attempt to infer and validate the format of a file without an extension.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if valid format, False otherwise
        """
        # Try to read the first few bytes to detect file type
        try:
            with open(file_path, 'rb') as f:
                header = f.read(1024)
                
            # Check for CSV
            if b',' in header or b';' in header or b'\t' in header:
                return self._validate_csv(file_path)
                
            # Check for Excel
            if header.startswith(b'PK\x03\x04') or header.startswith(b'\xd0\xcf\x11\xe0'):
                return self._validate_excel(file_path)
                
            # Check for JSON
            if header.strip().startswith(b'{') or header.strip().startswith(b'['):
                return self._validate_json(file_path)
                
            # Check for XML
            if b'<?xml' in header or b'<root>' in header:
                return self._validate_xml(file_path)
                
            # Check for ZIP
            if header.startswith(b'PK\x03\x04'):
                return self._validate_zip_file(file_path)
                
            logger.warning(f"Could not infer format for file: {file_path}")
            return False
                
        except Exception as e:
            logger.error(f"Error inferring format for {file_path}: {str(e)}")
            return False
    
    def _validate_csv(self, file_path: Path) -> bool:
        """Validate a CSV file."""
        try:
            # Try different encodings and delimiters
            encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
            delimiters = [',', ';', '\t', '|']
            
            for encoding in encodings:
                for delimiter in delimiters:
                    try:
                        # Try to open and parse with this encoding and delimiter
                        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                            # First try to detect if this is a valid CSV with this delimiter
                            sample = f.read(2048)  # Read a sample to check
                            if delimiter not in sample:
                                continue  # Try next delimiter
                                
                            # Reset file pointer
                            f.seek(0)
                            
                            # Try to read the CSV file
                            csv_reader = csv.reader(f, delimiter=delimiter)
                            
                            # Get the header row
                            try:
                                headers = next(csv_reader)
                            except StopIteration:
                                logger.info(f"Empty CSV file: {file_path}")
                                return False
                            
                            # Check if headers suggest price data
                            if not self._headers_indicate_price_file(headers):
                                # Before giving up, check if the first row might be data not headers
                                # Some files might not have headers but still be price files
                                has_price_pattern = False
                                for cell in headers:
                                    if self.PRICE_PATTERN.match(cell):
                                        has_price_pattern = True
                                        break
                                        
                                if has_price_pattern:
                                    # This might be a headerless CSV with price data
                                    # Let it through for further validation
                                    return True
                                else:
                                    # Not a price file based on headers
                                    logger.info(f"Headers don't suggest price data: {headers}")
                                    continue  # Try next encoding/delimiter
                            
                            # Count rows and check for price-like data
                            row_count = 0
                            price_values_found = False
                            
                            for i, row in enumerate(csv_reader):
                                if not row or all(cell.strip() == '' for cell in row):
                                    continue  # Skip empty rows
                                    
                                row_count += 1
                                
                                if i < self.sample_size:
                                    # Check if any cells contain price-like values
                                    for cell in row:
                                        if self.PRICE_PATTERN.match(cell):
                                            price_values_found = True
                                            break
                                
                                if row_count >= self.min_rows and price_values_found:
                                    break
                            
                            # Special case: if we only have a few rows but they contain price data
                            # still consider it valid - some hospitals have small price lists
                            if row_count > 0 and price_values_found:
                                if row_count < self.min_rows:
                                    logger.info(f"Found only {row_count} rows but they contain price data")
                                    # Still valid if it has at least 3 rows and contains prices
                                    return row_count >= 3
                                return True
                            
                            if row_count < self.min_rows:
                                logger.info(f"Not enough data rows: {row_count} < {self.min_rows}")
                                continue  # Try next encoding/delimiter
                            
                            if not price_values_found:
                                logger.info(f"No price-like values found in sample")
                                continue  # Try next encoding/delimiter
                            
                            return True
                    except UnicodeDecodeError:
                        # Try next encoding
                        continue
                    except Exception as e:
                        logger.debug(f"Error with {encoding}/{delimiter}: {str(e)}")
                        continue
            
            # If we get here, we couldn't validate with any combination
            logger.info(f"Could not validate CSV with any encoding/delimiter: {file_path}")
            return False
                
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
    
    def _validate_xml(self, file_path: Path) -> bool:
        """Validate an XML file for price transparency data.
        
        Args:
            file_path: Path to the XML file
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Read the XML file
            df = pd.read_xml(file_path)
            
            # Check if empty
            if df.empty:
                logger.info(f"XML file is empty: {file_path}")
                return False
                
            # Ensure minimum row count
            if len(df) < self.min_rows:
                logger.info(f"XML file doesn't have enough rows: {file_path}")
                return False
                
            # Get headers
            headers = df.columns.tolist()
            
            # Check if headers indicate a price file
            if self._headers_indicate_price_file(headers):
                logger.info(f"Valid XML file: {file_path}")
                return True
                
            logger.info(f"XML file doesn't have price-related headers: {file_path}")
            return False
                
        except Exception as e:
            logger.error(f"Error validating XML file {file_path}: {str(e)}")
            return False
    
    def _headers_indicate_price_file(self, headers: List[str]) -> bool:
        """Check if headers indicate a price transparency file.
        
        Args:
            headers: List of header strings
            
        Returns:
            True if headers indicate a price file, False otherwise
        """
        if not headers:
            return False
            
        # Convert headers to lowercase for case-insensitive matching
        headers_lower = [str(h).lower() for h in headers]
        
        # Check for header patterns that MUST be present in price transparency files
        required_column_types = [
            # Price-related headers
            ['price', 'charge', 'rate', 'fee', 'cost', 'amount', 'dollar', 'payment'],
            
            # Code-related headers (at least one type of code should be present)
            ['cpt', 'hcpcs', 'drg', 'ms-drg', 'code', 'rev', 'procedure', 'service', 'ndc']
        ]
        
        # Count how many of the required column types are present
        present_types = 0
        for column_type in required_column_types:
            if any(any(keyword in header for keyword in column_type) for header in headers_lower):
                present_types += 1
        
        # For a valid price file, we need at least one price-related column AND 
        # either a code or service-related column
        sufficient_columns = present_types >= 2
        
        # Alternative check: look for very specific price transparency patterns
        price_transparency_patterns = [
            # Standard price transparency columns
            'standard charge', 'list price', 'cash price', 'discounted cash', 
            'negotiated rate', 'payer-specific', 'min price', 'max price',
            'gross charge', 'chargemaster', 'self-pay'
        ]
        
        has_transparency_pattern = any(
            any(pattern in header for pattern in price_transparency_patterns) 
            for header in headers_lower
        )
        
        # Also check if the headers include the string 'price'
        has_price = any('price' in header for header in headers_lower)
        
        # Check for common hospital data elements (useful when combined with price indicators)
        hospital_indicators = ['hospital', 'facility', 'provider', 'location', 'department']
        has_hospital_indicator = any(
            any(indicator in header for indicator in hospital_indicators)
            for header in headers_lower
        )
        
        # Return true if the file has sufficient columns OR specific price transparency patterns
        # OR has both price column and hospital indicator
        return sufficient_columns or has_transparency_pattern or (has_price and has_hospital_indicator)
    
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