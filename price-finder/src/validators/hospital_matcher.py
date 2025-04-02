import logging
import re
from typing import Dict, Any, Optional, Tuple, List, Set
from pathlib import Path
import pandas as pd
import json
import csv
import os

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
    
    async def validate(self, 
                     file_path: Path, 
                     hospital: Hospital,
                     content_analyzer: LLMContentAnalyzer) -> Tuple[bool, float, str]:
        """Validate that a file belongs to a specific hospital.
        
        Args:
            file_path: Path to the file
            hospital: Hospital object the file should belong to
            content_analyzer: LLM-based content analyzer
            
        Returns:
            Tuple of (is_valid, confidence_score, reasoning)
        """
        # First, do a basic rule-based check
        rule_match, rule_confidence, rule_evidence = self._rule_based_validation(file_path, hospital)
        
        # If rule-based validation is very confident either way, we can skip LLM
        if rule_confidence > 0.9:
            return rule_match, rule_confidence, rule_evidence
            
        # For uncertain cases, use LLM to validate
        analysis = await content_analyzer.analyze_file_content(file_path, hospital)
        
        # Combine rule-based and LLM-based validation
        combined_confidence = (rule_confidence + analysis['validation_score']) / 2
        
        # If the LLM is very confident, prioritize its decision
        if analysis['validation_score'] > 0.9:
            combined_confidence = analysis['validation_score']
            
        is_valid = combined_confidence >= self.confidence_threshold
        
        reasoning = f"Rule-based: {rule_evidence}. LLM: {analysis['reasoning']}"
        
        return is_valid, combined_confidence, reasoning
    
    def _rule_based_validation(self, file_path: Path, hospital: Hospital) -> Tuple[bool, float, str]:
        """Perform rule-based validation without using LLM.
        
        Args:
            file_path: Path to the file
            hospital: Hospital object the file should belong to
            
        Returns:
            Tuple of (is_valid, confidence_score, evidence)
        """
        # Extract hospital name variations
        hospital_name_variations = self._get_hospital_name_variations(hospital)
        
        # Extract sample content based on file type
        file_ext = os.path.splitext(str(file_path))[1].lower()
        sample_text = self._extract_text_sample(file_path, file_ext)
        
        # Look for hospital name in the content
        matched_variations = []
        for name_var in hospital_name_variations:
            pattern = r'\b' + re.escape(name_var) + r'\b'
            if re.search(pattern, sample_text, re.IGNORECASE):
                matched_variations.append(name_var)
        
        # Calculate confidence based on matches
        if matched_variations:
            # Exact hospital name match is strongest evidence
            if hospital.name.lower() in [var.lower() for var in matched_variations]:
                confidence = 0.95
                evidence = f"Found exact hospital name match: {hospital.name}"
            else:
                # Variation matches are good but not as strong
                confidence = 0.8
                evidence = f"Found hospital name variations: {', '.join(matched_variations)}"
                
            # Also check for location match to increase confidence
            if hospital.city and re.search(r'\b' + re.escape(hospital.city) + r'\b', sample_text, re.IGNORECASE):
                confidence = min(confidence + 0.1, 1.0)
                evidence += f" and city match: {hospital.city}"
                
            if re.search(r'\b' + re.escape(hospital.state) + r'\b', sample_text, re.IGNORECASE):
                confidence = min(confidence + 0.05, 1.0)
                evidence += f" and state match: {hospital.state}"
                
            return True, confidence, evidence
        
        # Basic location matching can be suggestive but not conclusive
        location_match = False
        location_evidence = []
        
        if hospital.city and re.search(r'\b' + re.escape(hospital.city) + r'\b', sample_text, re.IGNORECASE):
            location_match = True
            location_evidence.append(f"city: {hospital.city}")
        
        if re.search(r'\b' + re.escape(hospital.state) + r'\b', sample_text, re.IGNORECASE):
            location_match = True
            location_evidence.append(f"state: {hospital.state}")
            
        if location_match:
            confidence = 0.5  # Location alone is only moderately confident
            evidence = f"Found location matches: {', '.join(location_evidence)}, but no hospital name match"
            return False, confidence, evidence
        
        # No clear evidence found
        return False, 0.1, "No hospital name or location matches found"
    
    def _get_hospital_name_variations(self, hospital: Hospital) -> Set[str]:
        """Generate variations of a hospital name for matching.
        
        Args:
            hospital: Hospital object
            
        Returns:
            Set of name variations
        """
        variations = set([hospital.name])
        
        # Full name
        variations.add(hospital.name)
        
        # Name without common suffixes
        for suffix in ['Hospital', 'Medical Center', 'Health', 'Healthcare', 'Health System', 'Center', 'Clinic']:
            if hospital.name.endswith(suffix):
                variations.add(hospital.name[:-len(suffix)].strip())
        
        # Name with location prefix removed
        if hospital.city:
            if hospital.name.startswith(hospital.city):
                variations.add(hospital.name[len(hospital.city):].strip())
        
        # Abbreviated versions
        words = hospital.name.split()
        if len(words) > 2:
            # First letters of each word
            abbrev = ''.join(word[0] for word in words if word[0].isupper())
            if len(abbrev) >= 2:
                variations.add(abbrev)
            
            # First letter of words except last word
            if len(words) > 3:
                abbrev_except_last = ''.join(word[0] for word in words[:-1] if word[0].isupper()) + ' ' + words[-1]
                variations.add(abbrev_except_last)
        
        # Handle "Saint" vs "St." variations
        if "Saint" in hospital.name:
            variations.add(hospital.name.replace("Saint", "St"))
            variations.add(hospital.name.replace("Saint", "St."))
        elif "St " in hospital.name:
            variations.add(hospital.name.replace("St ", "Saint "))
        elif "St. " in hospital.name:
            variations.add(hospital.name.replace("St. ", "Saint "))
        
        # Name plus location
        if hospital.city:
            variations.add(f"{hospital.name} {hospital.city}")
            variations.add(f"{hospital.name} {hospital.city}, {hospital.state}")
        
        return variations
    
    def _extract_text_sample(self, file_path: Path, file_ext: str, max_sample: int = 10000) -> str:
        """Extract a text sample from the file for matching.
        
        Args:
            file_path: Path to the file
            file_ext: File extension
            max_sample: Maximum sample size in characters
            
        Returns:
            Text sample from the file
        """
        try:
            # For CSV files
            if file_ext in ['.csv', '.txt']:
                sample = ""
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    for _ in range(100):  # Read first 100 lines or until EOF
                        line = f.readline()
                        if not line:
                            break
                        sample += line
                    return sample[:max_sample]
            
            # For Excel files
            elif file_ext in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path, nrows=100)
                sample = df.to_string()
                return sample[:max_sample]
            
            # For JSON files
            elif file_ext == '.json':
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    data = json.load(f)
                    sample = json.dumps(data)[:max_sample]
                    return sample
            
            # For XML files
            elif file_ext == '.xml':
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    sample = f.read(max_sample)
                    return sample
            
            # Default case
            else:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    return f.read(max_sample)
                    
        except Exception as e:
            logger.error(f"Error extracting text sample from {file_path}: {str(e)}")
            return "" 