import logging
import re
from typing import Dict, Any, Optional, Tuple, List, Set
from pathlib import Path
import pandas as pd
import json
import csv
import os
from difflib import SequenceMatcher

from ..models.hospital import Hospital
from ..llm.content_analyzer import LLMContentAnalyzer

logger = logging.getLogger(__name__)

class HospitalMatcher:
    """Validates that a price transparency file belongs to a specific hospital."""
    
    def __init__(self, confidence_threshold: float = 0.8):
        """Initialize the hospital matcher.
        
        Args:
            confidence_threshold: Minimum confidence score to consider a match valid
        """
        self.confidence_threshold = confidence_threshold
    
    async def validate(self, file_path: Path, hospital: Hospital, content_analyzer=None) -> Tuple[bool, float, str]:
        """Validate whether a file is a match for a hospital.
        
        Args:
            file_path: Path to the downloaded file
            hospital: Hospital to match
            content_analyzer: Optional ContentAnalyzer to use for LLM-based validation
            
        Returns:
            Tuple of (is_valid: bool, confidence: float, reasoning: str)
        """
        # First try rule-based validation (faster and cheaper)
        result, confidence, reasoning = self._rule_based_validation(file_path, hospital)
        
        # If high confidence in rule-based result, return it
        if confidence > 0.9:
            return result, confidence, reasoning
            
        # If we have a content analyzer, use LLM to validate
        if content_analyzer:
            try:
                # Extract a sample of the content to analyze
                content_sample = self._extract_content_sample(file_path)
                
                # Construct the validation prompt
                # Safely check for health_sys_name attribute
                health_sys_name = getattr(hospital, 'health_sys_name', '') if hasattr(hospital, 'health_sys_name') else ''
                hospital_system_info = f" It belongs to the {health_sys_name} health system." if health_sys_name else ""
                
                prompt = f"""
                I need to determine if this file is a hospital price transparency file for {hospital.name} in {hospital.city}, {hospital.state}.{hospital_system_info}
                
                The file may be a valid match if ANY of these are true:
                1. It explicitly mentions {hospital.name} or close variations
                2. It's a system-wide price file for {health_sys_name if health_sys_name else 'N/A'} that covers multiple facilities including this one
                3. It mentions both the city ({hospital.city}) and state ({hospital.state}) where this hospital is located
                
                Here's a sample of the file content:
                {content_sample}
                
                First, evaluate if this appears to be a hospital price transparency file containing standard charges.
                Then, determine if it's specifically for {hospital.name} or includes it as part of a system.
                
                Output your determination as: 
                - Valid: [true/false]
                - Confidence: [0.0-1.0]
                - Explanation: [your reasoning]
                """
                
                # Get LLM validation
                llm_result = await content_analyzer.validate_hospital_match(prompt)
                
                # Combine rule-based and LLM results
                # If rule-based found a match but LLM didn't, go with LLM (it's more reliable)
                # If LLM found a match but rule-based didn't, go with LLM
                # If both agree, go with the higher confidence
                if llm_result['valid'] and not result:
                    return True, llm_result['confidence'], llm_result['explanation']
                elif not llm_result['valid'] and result:
                    # If rule-based says valid but LLM disagrees, we trust LLM more
                    if llm_result['confidence'] > 0.8:
                        return False, llm_result['confidence'], llm_result['explanation']
                    else:
                        # If LLM isn't very confident in rejection, stick with rule-based
                        return True, confidence, reasoning + " (LLM was uncertain)"
                elif llm_result['valid'] and result:
                    # Both agree it's valid, use the higher confidence
                    return True, max(confidence, llm_result['confidence']), llm_result['explanation']
                else:
                    # Both agree it's invalid
                    return False, max(confidence, llm_result['confidence']), llm_result['explanation']
                    
            except Exception as e:
                logger.error(f"Error in LLM validation: {str(e)}")
                # Fall back to rule-based if LLM fails
                return result, confidence, reasoning + f" (LLM validation failed: {str(e)})"
        
        # If no content analyzer, just return rule-based result
        return result, confidence, reasoning
    
    def _rule_based_validation(self, file_path: Path, hospital: Hospital) -> Tuple[bool, float, str]:
        """Perform rule-based validation to check if file matches hospital.
        
        Args:
            file_path: Path to the file
            hospital: Hospital to match
            
        Returns:
            Tuple of (is_valid: bool, confidence: float, reasoning: str)
        """
        try:
            # Get basic file info
            file_name = file_path.name.lower()
            file_stem = file_path.stem.lower()
            file_size = file_path.stat().st_size
            
            # Extract hospital details
            hospital_name = hospital.name.lower()
            city = hospital.city.lower()
            state = hospital.state.lower()
            
            # Safely check for health system attribute
            health_sys_name = getattr(hospital, 'health_sys_name', '') if hasattr(hospital, 'health_sys_name') else ''
            system_name = health_sys_name.lower() if health_sys_name else ""
            
            # Generate variations of the hospital name for matching
            hospital_name_variations = self._generate_hospital_name_variations(hospital_name)
            
            # Generate variations of the system name if applicable
            system_name_variations = []
            if system_name:
                system_name_variations = self._generate_system_name_variations(system_name)
            
            # Check if file name contains hospital name or its variations
            has_hospital_name = any(variation in file_name for variation in hospital_name_variations)
            
            # Check if file name contains system name or its variations if applicable
            has_system_name = False
            if system_name:
                has_system_name = any(variation in file_name for variation in system_name_variations)
            
            # Check if file name contains city or state
            has_location = city in file_name or state in file_name
            
            # Try to read the first few KB of the file to check content
            content_sample = self._extract_content_sample(file_path)
            content_sample_lower = content_sample.lower()
            
            # Check if content contains hospital name or its variations using fuzzy matching for longer names
            content_has_hospital_name = False
            for variation in hospital_name_variations:
                if len(variation) > 5:  # Use fuzzy matching for longer names
                    # Check for fuzzy matches in content
                    if self._fuzzy_match_in_text(variation, content_sample_lower):
                        content_has_hospital_name = True
                        break
                else:  # Use exact matching for shorter names to avoid false positives
                    if variation in content_sample_lower:
                        content_has_hospital_name = True
                        break
            
            # Check if content contains system name or its variations
            content_has_system_name = False
            if system_name:
                for variation in system_name_variations:
                    if len(variation) > 5:  # Use fuzzy matching for longer names
                        if self._fuzzy_match_in_text(variation, content_sample_lower):
                            content_has_system_name = True
                            break
                    else:  # Use exact matching for shorter names
                        if variation in content_sample_lower:
                            content_has_system_name = True
                            break
            
            # Check if content contains city and state
            content_has_location = city in content_sample_lower and state in content_sample_lower
            
            # Determine if it's a match based on the checks
            is_match = False
            confidence = 0.0
            reasoning = ""
            
            # Direct hospital name match
            if has_hospital_name and (has_location or content_has_location):
                is_match = True
                confidence = 0.9
                reasoning = f"File name contains hospital name and location information. Hospital: {hospital_name}"
            elif content_has_hospital_name and (has_location or content_has_location):
                is_match = True
                confidence = 0.85
                reasoning = f"File content contains hospital name and location information. Hospital: {hospital_name}"
            
            # System-wide file match
            elif system_name and has_system_name and (has_location or content_has_location):
                is_match = True
                confidence = 0.8
                reasoning = f"File appears to be a system-wide price file for {system_name} that likely includes {hospital_name}"
            elif system_name and content_has_system_name and content_has_location:
                is_match = True
                confidence = 0.75
                reasoning = f"File content indicates a system-wide price file for {system_name} that may include {hospital_name}"
            
            # Location only match with price file indicators
            elif has_location and content_has_location and self._has_price_transparency_indicators(content_sample_lower):
                is_match = True
                confidence = 0.7
                reasoning = f"File contains location information matching {hospital.city}, {hospital.state} and price transparency indicators"
                
            # For ambiguous cases
            elif (has_hospital_name or content_has_hospital_name) and not (has_location or content_has_location):
                is_match = False
                confidence = 0.6
                reasoning = f"File references hospital name but lacks location confirmation for {hospital.city}, {hospital.state}"
            elif (has_system_name or content_has_system_name) and not (has_location or content_has_location):
                is_match = False
                confidence = 0.5
                reasoning = f"File references health system ({system_name}) but lacks location confirmation for {hospital.city}, {hospital.state}"
            else:
                is_match = False
                confidence = 0.7
                reasoning = f"No clear indicators that this file is for {hospital_name} in {hospital.city}, {hospital.state}"
            
            return is_match, confidence, reasoning
            
        except Exception as e:
            logger.error(f"Error in rule-based validation: {str(e)}")
            return False, 0.0, f"Error during validation: {str(e)}"
    
    def _generate_hospital_name_variations(self, hospital_name: str) -> List[str]:
        """Generate variations of the hospital name for matching.
        
        Args:
            hospital_name: Hospital name to generate variations for
            
        Returns:
            List of variations
        """
        variations = [hospital_name]
        
        # Remove common words
        for word in ['hospital', 'medical', 'center', 'health', 'regional', 'community', 'memorial']:
            clean_name = hospital_name.replace(f" {word}", "").replace(f"{word} ", "")
            if clean_name != hospital_name and len(clean_name) > 3:
                variations.append(clean_name)
        
        # Handle abbreviated forms
        words = hospital_name.split()
        if len(words) > 1:
            # Create acronym (first letter of each word)
            acronym = ''.join(word[0] for word in words if word[0].isalpha())
            if len(acronym) > 1:
                variations.append(acronym.lower())
            
            # For names like "Saint John's Hospital", also check for "St John's Hospital"
            if 'saint' in hospital_name:
                st_name = hospital_name.replace('saint', 'st')
                variations.append(st_name)
            
            # For names with "Saint" or "St", also try the full name
            if 'st ' in hospital_name and ' st ' not in hospital_name:
                saint_name = hospital_name.replace('st ', 'saint ')
                variations.append(saint_name)
        
        return variations
    
    def _generate_system_name_variations(self, system_name: str) -> List[str]:
        """Generate variations of the system name for matching.
        
        Args:
            system_name: System name to generate variations for
            
        Returns:
            List of variations
        """
        variations = [system_name]
        
        # Remove common words
        for word in ['health', 'system', 'network', 'partners', 'healthcare', 'hospital', 'hospitals', 'medical', 'group']:
            clean_name = system_name.replace(f" {word}", "").replace(f"{word} ", "")
            if clean_name != system_name and len(clean_name) > 3:
                variations.append(clean_name)
        
        # Handle abbreviated forms
        words = system_name.split()
        if len(words) > 1:
            # Create acronym (first letter of each word)
            acronym = ''.join(word[0] for word in words if word[0].isalpha())
            if len(acronym) > 1:
                variations.append(acronym.lower())
        
        return variations
    
    def _fuzzy_match_in_text(self, needle: str, haystack: str) -> bool:
        """Check if a string approximately appears in a text using fuzzy matching.
        
        Args:
            needle: String to search for
            haystack: Text to search in
            
        Returns:
            True if a fuzzy match is found, False otherwise
        """
        if len(needle) < 4:
            # For very short strings, require exact match to avoid false positives
            return needle in haystack
            
        # For longer strings, use fuzzy matching
        # Split haystack into chunks roughly the size of needle for more efficient comparison
        chunk_size = len(needle) * 2
        
        # Slide through text with overlapping chunks
        for i in range(0, len(haystack) - len(needle) + 1, chunk_size // 2):
            chunk = haystack[i:i + chunk_size]
            
            # If the needle is longer than our default chunk, adjust chunk size
            if len(needle) > chunk_size:
                chunk = haystack[i:i + len(needle) + 10]
                
            # Use SequenceMatcher to find close matches
            matcher = SequenceMatcher(None, needle, chunk)
            
            # If similarity is high enough, consider it a match
            # 0.8 threshold is high enough to avoid common false positives but allow for minor OCR errors
            if matcher.quick_ratio() > 0.7:
                # Compute more accurate ratio for promising candidates
                if matcher.ratio() > 0.7:
                    return True
                    
        return False
        
    def _has_price_transparency_indicators(self, content: str) -> bool:
        """Check if content has indicators of being a price transparency file.
        
        Args:
            content: Content to check
            
        Returns:
            True if price transparency indicators are found, False otherwise
        """
        indicators = [
            'standard charge', 'price list', 'chargemaster', 'machine readable',
            'negotiated rate', 'payer-specific', 'cash price', 'gross charge',
            'price transparency', 'cdm', 'charge description master'
        ]
        
        return any(indicator in content for indicator in indicators)
        
    def _extract_content_sample(self, file_path: Path, max_bytes: int = 10000) -> str:
        """Extract a sample of content from a file.
        
        Args:
            file_path: Path to the file
            max_bytes: Maximum number of bytes to read
            
        Returns:
            String with a sample of the content
        """
        try:
            # Handle different file types
            suffix = file_path.suffix.lower()
            
            if suffix in ['.csv', '.txt', '.dat', '.tsv']:
                with open(file_path, 'r', errors='ignore') as f:
                    return f.read(max_bytes)
            
            elif suffix == '.xlsx' or suffix == '.xls':
                # Try to read Excel files
                import pandas as pd
                # Read only the first sheet, first few rows
                df = pd.read_excel(file_path, sheet_name=0, nrows=100)
                return df.to_string(max_rows=50, max_cols=10)
                
            elif suffix == '.pdf':
                # Try to extract text from PDF
                try:
                    import pdfplumber
                    with pdfplumber.open(file_path) as pdf:
                        # Get text from first few pages
                        text = ""
                        for i, page in enumerate(pdf.pages[:3]):  # First 3 pages
                            text += page.extract_text() or ""
                            if len(text) > max_bytes:
                                break
                        return text[:max_bytes]
                except ImportError:
                    return f"PDF file: {file_path.name} (PDF text extraction not available)"
                except Exception as e:
                    return f"PDF file: {file_path.name} (Error: {str(e)})"
            
            elif suffix in ['.html', '.htm']:
                # Try to extract text from HTML
                try:
                    from bs4 import BeautifulSoup
                    with open(file_path, 'r', errors='ignore') as f:
                        html = f.read(max_bytes * 2)  # Read more to account for HTML tags
                    soup = BeautifulSoup(html, 'html.parser')
                    # Remove script and style tags
                    for script in soup(["script", "style"]):
                        script.extract()
                    # Get text
                    text = soup.get_text()
                    # Break into lines and remove leading/trailing whitespace
                    lines = (line.strip() for line in text.splitlines())
                    # Join lines
                    text = '\n'.join(line for line in lines if line)
                    return text[:max_bytes]
                except ImportError:
                    return f"HTML file: {file_path.name} (HTML parsing not available)"
                except Exception as e:
                    return f"HTML file: {file_path.name} (Error: {str(e)})"
            
            else:
                # Binary files or unsupported types
                return f"File: {file_path.name} (Unsupported format for content extraction)"
                    
        except Exception as e:
            logger.error(f"Error extracting content sample: {str(e)}")
            return f"Error reading file: {str(e)}" 