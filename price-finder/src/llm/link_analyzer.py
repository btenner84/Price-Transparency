import os
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
import asyncio
import re

import openai
from openai import AsyncOpenAI
import anthropic

from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

from ..models.hospital import Hospital

logger = logging.getLogger(__name__)

class LLMLinkAnalyzer:
    """Uses LLMs to analyze search results and identify relevant price transparency links."""
    
    # LLM providers
    PROVIDER_OPENAI = "openai"
    PROVIDER_ANTHROPIC = "anthropic"
    PROVIDER_MISTRAL = "mistral"
    
    def __init__(self, 
                provider: Optional[str] = None, 
                model: Optional[str] = None,
                api_key: Optional[str] = None,
                confidence_threshold: float = 0.7):
        """Initialize the link analyzer.
        
        Args:
            provider: LLM provider (openai, anthropic, mistral)
            model: Model name to use for the provider
            api_key: API key for the provider
            confidence_threshold: Minimum relevance score to consider a URL as relevant
        """
        # Check environment for provider preference
        if provider is None:
            provider = os.environ.get("LLM_PROVIDER", self.PROVIDER_OPENAI)
            
        self.provider = provider.lower()
        self.confidence_threshold = confidence_threshold
        
        # Set up the appropriate client based on the provider
        if self.provider == self.PROVIDER_OPENAI:
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
            
            self.model = model or "gpt-4o"
            self.client = AsyncOpenAI(api_key=self.api_key)
            
        elif self.provider == self.PROVIDER_ANTHROPIC:
            self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not self.api_key:
                raise ValueError("Anthropic API key is required. Set ANTHROPIC_API_KEY environment variable or pass api_key parameter.")
            
            self.model = model or "claude-3-sonnet-20240229"
            self.client = anthropic.Anthropic(api_key=self.api_key)
            
        elif self.provider == self.PROVIDER_MISTRAL:
            self.api_key = api_key or os.environ.get("MISTRAL_API_KEY")
            if not self.api_key:
                raise ValueError("Mistral API key is required. Set MISTRAL_API_KEY environment variable or pass api_key parameter.")
            
            self.model = model or "mistral-large-latest"
            self.client = MistralClient(api_key=self.api_key)
            
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
        
        logger.info(f"Initialized LLMLinkAnalyzer with provider={self.provider}, model={self.model}")
    
    async def analyze_search_results(self, 
                                    search_results: List[Dict[str, Any]], 
                                    hospital: Hospital) -> List[Dict[str, Any]]:
        """Analyze search results to identify the most relevant links for price transparency.
        
        Args:
            search_results: List of search result dictionaries
            hospital: Hospital object
            
        Returns:
            List of search results with added relevance scores
        """
        if not search_results:
            return []
            
        # Create a batch of all results for efficiency
        system_prompt = f"""
        You are an expert at finding hospital price transparency information online.
        
        Your task is to analyze search results and determine which links are most likely to contain 
        price transparency information for a specific hospital.
        
        Hospital: {hospital.name}
        Location: {hospital.city}, {hospital.state} (if city available, otherwise just state)
        
        A good price transparency link should:
        1. Lead directly to a hospital's official price list, chargemaster, or standard charges
        2. Be from the hospital's official website (preferred) or a trusted healthcare portal
        3. Contain machine-readable pricing data (CSVs, spreadsheets, or structured data)
        4. Be specific to the exact hospital, not just the parent health system
        5. Contain recent (within last 12 months) pricing information
        
        Bad links include:
        1. News articles about price transparency
        2. General information pages without actual pricing data
        3. Links for different hospitals or healthcare systems
        4. Academic or research papers about price transparency
        5. Government policy pages without hospital-specific data
        
        For each link, provide a relevance score from 0.0 to 1.0, where:
        - 0.0-0.2: Definitely not relevant
        - 0.3-0.5: Possibly relevant but unclear
        - 0.6-0.8: Likely relevant
        - 0.9-1.0: Almost certainly relevant
        
        Also provide a brief reasoning for your score.
        """
        
        # For each batch of results, create a user message
        user_message = "Analyze these search results and determine which are most likely to contain price transparency data:\n\n"
        
        # Truncate to reasonable number for LLM context
        MAX_RESULTS = 10
        results_to_analyze = search_results[:MAX_RESULTS]
        
        for i, result in enumerate(results_to_analyze):
            user_message += f"Result {i+1}:\n"
            user_message += f"Title: {result.get('title', 'N/A')}\n"
            user_message += f"URL: {result.get('link', 'N/A')}\n"
            user_message += f"Snippet: {result.get('snippet', 'N/A')}\n\n"
        
        # Add instructions for output format
        user_message += """
        Respond in JSON format with an array of objects, each containing:
        - result_index: index of the result (1-based)
        - url: the URL
        - relevance_score: float between 0 and 1
        - reasoning: brief explanation for the score
        
        Example:
        ```json
        [
          {
            "result_index": 1,
            "url": "https://example.com/prices",
            "relevance_score": 0.9,
            "reasoning": "Official hospital website with direct link to machine-readable files"
          },
          ...
        ]
        ```
        """
        
        # Call the appropriate LLM provider
        analyzed_results = []
        
        if self.provider == self.PROVIDER_OPENAI:
            analysis = await self._analyze_with_openai(system_prompt, user_message)
            analyzed_results = self._parse_openai_response(analysis, results_to_analyze)
            
        elif self.provider == self.PROVIDER_ANTHROPIC:
            analysis = await self._analyze_with_anthropic(system_prompt, user_message)
            analyzed_results = self._parse_anthropic_response(analysis, results_to_analyze)
            
        elif self.provider == self.PROVIDER_MISTRAL:
            analysis = await self._analyze_with_mistral(system_prompt, user_message)
            analyzed_results = self._parse_mistral_response(analysis, results_to_analyze)
        
        # Filter results by confidence threshold
        relevant_results = [
            result for result in analyzed_results 
            if result.get('relevance_score', 0) >= self.confidence_threshold
        ]
        
        # Sort by relevance score
        relevant_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return relevant_results
    
    async def is_relevant(self, url: str, title: str, snippet: str, hospital: Hospital) -> Tuple[bool, float, str]:
        """Determine if a URL is likely to lead to price transparency information.
        
        Args:
            url: URL to analyze
            title: Title of the page
            snippet: Snippet from the search result
            hospital: Hospital object
            
        Returns:
            Tuple of (is_relevant, confidence_score, reasoning)
        """
        system_prompt = f"""
        You are an expert at finding hospital price transparency information online.
        
        Your task is to analyze a search result and determine if it's likely to contain 
        price transparency information for a specific hospital.
        
        Hospital: {hospital.name}
        Location: {hospital.city}, {hospital.state if hospital.city else hospital.state}
        """
        
        user_message = f"""
        Please analyze this search result:
        
        Title: {title}
        URL: {url}
        Snippet: {snippet}
        
        Determine if this link is likely to lead to price transparency information for {hospital.name}.
        
        A good price transparency link should:
        1. Lead directly to a hospital's official price list, chargemaster, or standard charges
        2. Be from the hospital's official website or a trusted healthcare portal
        3. Contain machine-readable pricing data (CSVs, spreadsheets, or structured data)
        4. Be specific to this exact hospital, not just the parent health system
        5. Contain recent pricing information
        
        Respond in JSON format with:
        - is_relevant: true/false
        - confidence_score: float between 0 and 1
        - reasoning: brief explanation for your decision
        
        Example:
        ```json
        {
          "is_relevant": true,
          "confidence_score": 0.85,
          "reasoning": "Official hospital website with direct link to machine-readable files"
        }
        ```
        """
        
        if self.provider == self.PROVIDER_OPENAI:
            response = await self._analyze_with_openai(system_prompt, user_message)
            analysis = self._extract_json_from_text(response)
        elif self.provider == self.PROVIDER_ANTHROPIC:
            response = await self._analyze_with_anthropic(system_prompt, user_message)
            analysis = self._extract_json_from_text(response)
        
        # Default values in case of parsing errors
        is_relevant = False
        confidence_score = 0.0
        reasoning = "Failed to analyze"
        
        try:
            is_relevant = analysis.get("is_relevant", False)
            confidence_score = float(analysis.get("confidence_score", 0.0))
            reasoning = analysis.get("reasoning", "No reasoning provided")
        except (ValueError, AttributeError, TypeError) as e:
            logger.error(f"Error parsing LLM response: {e}, response: {response}")
        
        return is_relevant, confidence_score, reasoning
    
    async def _analyze_with_openai(self, system_prompt: str, user_message: str) -> str:
        """Analyze text using OpenAI API."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.1,  # Low temperature for more deterministic outputs
                max_tokens=2000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            return ""
    
    async def _analyze_with_anthropic(self, system_prompt: str, user_message: str) -> str:
        """Analyze text using Anthropic API."""
        try:
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Error calling Anthropic API: {str(e)}")
            return ""
    
    async def _analyze_with_mistral(self, system_prompt: str, user_message: str) -> str:
        """Analyze with Mistral AI.
        
        Args:
            system_prompt: System prompt for the LLM
            user_message: User message to send to the LLM
            
        Returns:
            The raw response text
        """
        try:
            # Create chat messages in Mistral format
            messages = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_message)
            ]
            
            # Since Mistral's client is synchronous, we need to run it in a thread
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat(
                    model=self.model,
                    messages=messages
                )
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error calling Mistral AI API: {e}")
            raise
    
    def _parse_openai_response(self, response: str, original_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse OpenAI response to extract structured data."""
        if not response:
            return []
            
        try:
            # Extract JSON from the response text
            json_data = self._extract_json_from_text(response)
            
            if not isinstance(json_data, list):
                logger.error(f"Expected JSON list but got {type(json_data)}")
                return []
            
            analyzed_results = []
            
            for item in json_data:
                if 'result_index' not in item or not isinstance(item['result_index'], (int, str)):
                    continue
                    
                # Convert string to int if needed
                if isinstance(item['result_index'], str):
                    try:
                        item['result_index'] = int(item['result_index'])
                    except ValueError:
                        continue
                
                # Adjust for 1-based indexing in the prompt
                idx = item['result_index'] - 1
                
                if idx < 0 or idx >= len(original_results):
                    continue
                
                # Merge with original result
                merged_result = original_results[idx].copy()
                merged_result.update({
                    'relevance_score': float(item.get('relevance_score', 0.0)),
                    'reasoning': item.get('reasoning', 'No reasoning provided')
                })
                
                analyzed_results.append(merged_result)
            
            return analyzed_results
            
        except Exception as e:
            logger.error(f"Error parsing OpenAI response: {e}, response: {response}")
            return []
    
    def _parse_anthropic_response(self, response: str, original_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse Anthropic response to extract structured data."""
        # Same parsing logic as OpenAI for now
        return self._parse_openai_response(response, original_results)
    
    def _parse_mistral_response(self, response: str, original_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse the Mistral response into a structured format.
        
        Args:
            response: Raw response from Mistral
            original_results: Original search results
            
        Returns:
            List of analyzed results
        """
        try:
            # Extract JSON from the response
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON without code blocks
                json_match = re.search(r'\[\s*{.*}\s*\]', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    json_str = response
            
            # Parse the JSON
            data = json.loads(json_str)
            
            # Process the results
            results = []
            for item in data:
                result_index = item.get('result_index', 0) - 1  # Convert to 0-based
                
                if 0 <= result_index < len(original_results):
                    # Add analysis to the original result
                    result = original_results[result_index].copy()
                    result['relevance_score'] = item.get('relevance_score', 0)
                    result['reasoning'] = item.get('reasoning', '')
                    results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Error parsing Mistral response: {e}")
            logger.debug(f"Raw response: {response}")
            return []
    
    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """Extract JSON from text that might contain other content."""
        try:
            # Try to parse the entire text as JSON first
            return json.loads(text)
        except json.JSONDecodeError:
            # If that fails, look for JSON within markdown code blocks
            json_match = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            
            # If that fails too, look for JSON without code blocks
            json_match = re.search(r'(\{.*?\}|\[.*?\])', text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
                    
            logger.error(f"Could not extract JSON from text: {text}")
            return {} 