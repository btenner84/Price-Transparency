import os
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
import asyncio
import pandas as pd
import csv
import io

from ..models.hospital import Hospital
from ..models.price_file import PriceFile

logger = logging.getLogger(__name__)

class LLMContentAnalyzer:
    """Uses LLMs to analyze and validate price transparency file content."""
    
    # LLM providers
    PROVIDER_OPENAI = "openai"
    PROVIDER_ANTHROPIC = "anthropic"
    PROVIDER_MISTRAL = "mistral"
    
    def __init__(self, 
                 provider: Optional[str] = None, 
                 model: Optional[str] = None,
                 api_key: Optional[str] = None,
                 validation_threshold: float = 0.7):
        """Initialize the LLM Content Analyzer.
        
        Args:
            provider: LLM provider (openai, anthropic, mistral)
            model: Model name to use
            api_key: API key for the LLM provider
            validation_threshold: Minimum validation score to consider a file valid
        """
        # Check environment for provider preference
        if provider is None:
            provider = os.environ.get("LLM_PROVIDER", self.PROVIDER_OPENAI)
            
        self.provider = provider.lower()
        self.validation_threshold = validation_threshold
        
        # Set up the appropriate client based on the provider
        # (Similar to LLMLinkAnalyzer, but we'll focus on file content analysis)
        # This would typically be initialized with specific models and API keys
        # For now, we'll reuse the link analyzer implementation
        from .link_analyzer import LLMLinkAnalyzer
        self.analyzer = LLMLinkAnalyzer(
            provider=provider,
            model=model,
            api_key=api_key
        )
    
    async def analyze_file_content(self, 
                                  file_path: str, 
                                  hospital: Hospital) -> Dict[str, Any]:
        """Analyze file content to verify it's a valid price transparency file.
        
        Args:
            file_path: Path to downloaded file
            hospital: Hospital object the file should belong to
            
        Returns:
            Dict with validation results
        """
        # First determine file type and extract sample content
        file_type = os.path.splitext(file_path)[1].lower()
        
        # Extract a sample of the file content for analysis
        sample = self._extract_file_sample(file_path, file_type)
        
        if not sample:
            return {
                "is_valid": False,
                "validation_score": 0.0,
                "contains_prices": False,
                "contains_hospital_name": False,
                "reasoning": "Could not extract file content"
            }
        
        # Construct prompt for the LLM
        system_prompt = f"""
        You are an expert in hospital price transparency data.
        
        You need to analyze a sample from a potential price transparency file and validate:
        1. That it actually contains hospital pricing data
        2. That it belongs to the specified hospital
        
        Hospital: {hospital.name}
        Location: {hospital.city}, {hospital.state if hospital.city else hospital.state}
        
        Valid hospital price transparency data should contain:
        - Service descriptions or procedure codes
        - Pricing information (dollars, rates, charges)
        - Could use CPT codes, DRG codes, or service descriptions
        - May have different payer rates, cash prices, or min/max prices
        
        Examples of valid header rows in price transparency files:
        - "Code, Procedure, Description, Charge"
        - "MS-DRG, Service Description, Gross Charge, Discounted Cash Price, Payer-Specific Negotiated Charge"
        - "CPT/HCPCS, Item/Service Description, Standard Charge, Cash Price, Min, Max"
        """
        
        user_message = f"""
        Please analyze this sample from a potential price transparency file:
        
        ```
        {sample}
        ```
        
        Determine if this is a valid price transparency file for {hospital.name}.
        
        Respond in JSON format with:
        - is_valid: true/false
        - validation_score: float between 0 and 1
        - contains_prices: true/false
        - contains_hospital_name: true/false
        - reasoning: explanation for your decision
        
        Example:
        ```json
        {{
          "is_valid": true,
          "validation_score": 0.92,
          "contains_prices": true,
          "contains_hospital_name": true,
          "reasoning": "File contains CPT codes with corresponding prices and clearly mentions the hospital name."
        }}
        ```
        """
        
        # Call the LLM for analysis
        if self.provider == self.PROVIDER_OPENAI:
            response = await self.analyzer._analyze_with_openai(system_prompt, user_message)
        elif self.provider == self.PROVIDER_ANTHROPIC:
            response = await self.analyzer._analyze_with_anthropic(system_prompt, user_message)
        elif self.provider == self.PROVIDER_MISTRAL:
            response = await self.analyzer._analyze_with_mistral(system_prompt, user_message)
        else:
            return {
                "is_valid": False,
                "validation_score": 0.0,
                "contains_prices": False,
                "contains_hospital_name": False,
                "reasoning": f"Unsupported LLM provider: {self.provider}"
            }
        
        # Parse the response
        analysis = self.analyzer._extract_json_from_text(response)
        
        # Default values in case of parsing errors
        result = {
            "is_valid": False,
            "validation_score": 0.0,
            "contains_prices": False,
            "contains_hospital_name": False,
            "reasoning": "Failed to analyze content"
        }
        
        try:
            result["is_valid"] = analysis.get("is_valid", False)
            result["validation_score"] = float(analysis.get("validation_score", 0.0))
            result["contains_prices"] = analysis.get("contains_prices", False)
            result["contains_hospital_name"] = analysis.get("contains_hospital_name", False)
            result["reasoning"] = analysis.get("reasoning", "No reasoning provided")
        except (ValueError, AttributeError, TypeError) as e:
            logger.error(f"Error parsing LLM response: {e}, response: {response}")
        
        return result
    
    def _extract_file_sample(self, file_path: str, file_type: str, max_rows: int = 20) -> str:
        """Extract a sample of the file content for analysis.
        
        Args:
            file_path: Path to the file
            file_type: File extension
            max_rows: Maximum number of rows to extract
            
        Returns:
            String representation of file sample
        """
        try:
            # For CSV files
            if file_type in ['.csv', '.txt']:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    lines = []
                    csv_reader = csv.reader(f)
                    for i, row in enumerate(csv_reader):
                        if i >= max_rows:
                            break
                        lines.append(','.join(row))
                    return '\n'.join(lines)
            
            # For Excel files
            elif file_type in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path, nrows=max_rows)
                return df.to_csv(index=False)
            
            # For JSON files
            elif file_type == '.json':
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    data = json.load(f)
                    # If it's an array, take first few items
                    if isinstance(data, list):
                        sample = data[:min(max_rows, len(data))]
                    # If it's an object, take it as is
                    else:
                        sample = data
                    return json.dumps(sample, indent=2)
            
            # For XML files
            elif file_type == '.xml':
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()[:max_rows]
                    return ''.join(lines)
            
            # For unknown file types
            else:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    return f.read(8000)  # Read first 8KB
                    
        except Exception as e:
            logger.error(f"Error extracting sample from {file_path}: {str(e)}")
            return ""
    
    async def extract_price_file_metadata(self, 
                                         file_path: str, 
                                         hospital: Hospital,
                                         url: str) -> PriceFile:
        """Extract metadata for a price transparency file.
        
        Args:
            file_path: Path to downloaded file
            hospital: Hospital object
            url: URL where the file was found
            
        Returns:
            PriceFile object with metadata
        """
        file_type = os.path.splitext(file_path)[1].lower().lstrip('.')
        
        # Analyze the file content
        analysis = await self.analyze_file_content(file_path, hospital)
        
        # Create a PriceFile object
        price_file = PriceFile(
            hospital_id=hospital.id,
            url=url,
            file_type=file_type,
            validated=analysis["is_valid"],
            validation_score=analysis["validation_score"],
            validation_notes=analysis["reasoning"],
            file_size=os.path.getsize(file_path),
            download_date=None,  # Will be set by caller
            contains_prices=analysis["contains_prices"],
            contains_hospital_name=analysis["contains_hospital_name"]
        )
        
        return price_file
    
    async def find_file_links(self, page_content: str, hospital: Hospital) -> List[str]:
        """Find links to price transparency files in page content.
        
        Args:
            page_content: HTML content of a webpage
            hospital: Hospital object
            
        Returns:
            List of URLs that likely point to price transparency files
        """
        # Extract a sample of the page content
        content_sample = page_content[:10000]  # First 10KB to avoid overloading LLM
        
        system_prompt = f"""
        You are an expert at finding hospital price transparency information online.
        
        Your task is to analyze HTML content and identify links that are likely to lead 
        to price transparency files (CSV, Excel, JSON) for a specific hospital.
        
        Hospital: {hospital.name}
        Location: {hospital.city}, {hospital.state if hospital.city else hospital.state}
        
        Look for:
        1. Links with keywords like "price list", "chargemaster", "standard charges"
        2. Links to files with extensions .csv, .xlsx, .xls, .json
        3. Links that mention "machine-readable" or similar terms
        """
        
        user_message = f"""
        Extract ALL URLs from the HTML content below that might lead to price transparency files for {hospital.name}.
        
        HTML content sample:
        ```
        {content_sample}
        ```
        
        For each potential link, include these details:
        - url: The full URL
        - confidence: How confident you are that this leads to a price transparency file (0.0-1.0)
        - reasoning: Brief explanation why you think this is a price transparency link
        
        Return your answer in JSON format as an array of objects:
        ```json
        [
          {{
            "url": "https://example.com/prices.csv",
            "confidence": 0.9,
            "reasoning": "Direct link to CSV file with 'standard charges' in the anchor text"
          }},
          ...
        ]
        ```
        
        If no links are found, return an empty array.
        """
        
        # Call the LLM for analysis
        if self.provider == self.PROVIDER_OPENAI:
            response = await self.analyzer._analyze_with_openai(system_prompt, user_message)
        elif self.provider == self.PROVIDER_ANTHROPIC:
            response = await self.analyzer._analyze_with_anthropic(system_prompt, user_message)
        elif self.provider == self.PROVIDER_MISTRAL:
            response = await self.analyzer._analyze_with_mistral(system_prompt, user_message)
        else:
            return []
        
        # Parse the response
        try:
            json_data = self.analyzer._extract_json_from_text(response)
            
            if not isinstance(json_data, list):
                logger.error(f"Expected JSON list but got {type(json_data)}")
                return []
            
            # Extract URLs with confidence above threshold
            urls = [
                item.get("url") 
                for item in json_data 
                if item.get("url") and item.get("confidence", 0) >= 0.6
            ]
            
            return urls
            
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}, response: {response}")
            return [] 