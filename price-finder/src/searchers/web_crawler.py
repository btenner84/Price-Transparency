import os
import asyncio
import aiohttp
import logging
from urllib.parse import urljoin, urlparse
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import re

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from ..models.hospital import Hospital

logger = logging.getLogger(__name__)

class WebCrawler:
    """Web crawler for fetching and parsing web pages and downloading files."""
    
    # File extensions that could contain price transparency data
    PRICE_FILE_EXTENSIONS = ['.csv', '.json', '.xlsx', '.xls', '.xml', '.txt']
    
    # Keywords likely to appear in price transparency filenames
    PRICE_FILE_KEYWORDS = [
        'price', 'transparency', 'chargemaster', 'charge', 'cdm', 
        'standard-charge', 'machine-readable', 'pricelist'
    ]
    
    def __init__(self, download_dir: str = None):
        """Initialize the web crawler.
        
        Args:
            download_dir: Directory to save downloaded files
        """
        self.download_dir = download_dir or os.path.join(os.getcwd(), 'downloads')
        os.makedirs(self.download_dir, exist_ok=True)
        
        # Headers to mimic a browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }
    
    async def crawl(self, url: str) -> dict:
        """Crawl a webpage and extract relevant content.
        
        Args:
            url: URL to crawl
            
        Returns:
            dict: Page content, links, and potential price file links
        """
        logger.info(f"Crawling URL: {url}")
        
        # Parse with both methods for redundancy
        html_content = await self._fetch_with_requests(url)
        js_content = await self._fetch_with_playwright(url)
        
        # Use the content that has more information
        content = js_content if len(js_content) > len(html_content) else html_content
        
        # Parse the HTML
        soup = BeautifulSoup(content, 'html.parser')
        
        # Extract links
        links = self._extract_links(soup, base_url=url)
        
        # Find potential price transparency file links
        price_file_links = self._find_price_file_links(links)
        
        # Extract text content for LLM analysis
        text_content = self._extract_text_content(soup)
        
        return {
            'url': url,
            'content': content,
            'text_content': text_content,
            'links': links,
            'price_file_links': price_file_links,
            'crawl_date': datetime.now()
        }
    
    async def _fetch_with_requests(self, url: str) -> str:
        """Fetch a webpage using aiohttp."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=30) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        logger.warning(f"Failed to fetch {url} with status {response.status}")
                        return ""
        except Exception as e:
            logger.error(f"Error fetching {url} with aiohttp: {str(e)}")
            return ""
    
    async def _fetch_with_playwright(self, url: str) -> str:
        """Fetch a webpage using Playwright (handles JavaScript)."""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Set timeout and user agent
                await page.set_default_timeout(60000)
                await page.set_extra_http_headers(self.headers)
                
                # Navigate to the page
                await page.goto(url, wait_until='networkidle')
                
                # Get the content
                content = await page.content()
                
                await browser.close()
                return content
        except Exception as e:
            logger.error(f"Error fetching {url} with Playwright: {str(e)}")
            return ""
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Extract links from the page."""
        links = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            text = a_tag.get_text(strip=True)
            
            # Make relative URLs absolute
            full_url = urljoin(base_url, href)
            
            links.append({
                'url': full_url,
                'text': text,
                'is_file': self._is_file_link(full_url),
                'file_type': self._get_file_type(full_url)
            })
        
        return links
    
    def _find_price_file_links(self, links: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Find links that might point to price transparency files."""
        price_file_links = []
        
        for link in links:
            url = link['url']
            text = link['text'].lower()
            
            # Check if the link points to a file
            if link['is_file']:
                # Check file extension
                if any(url.lower().endswith(ext) for ext in self.PRICE_FILE_EXTENSIONS):
                    score = 0.5  # Base score for matching file extension
                    
                    # Check for keywords in the URL path
                    url_path = urlparse(url).path.lower()
                    for keyword in self.PRICE_FILE_KEYWORDS:
                        if keyword in url_path:
                            score += 0.1
                            
                    # Check for keywords in the link text
                    for keyword in self.PRICE_FILE_KEYWORDS:
                        if keyword in text:
                            score += 0.2
                    
                    if 'price' in text and 'transparency' in text:
                        score += 0.3
                        
                    link['score'] = min(score, 1.0)  # Cap at 1.0
                    if score > 0.5:  # Threshold for considering it a potential match
                        price_file_links.append(link)
            # For directory links, check if they might contain price info
            elif any(keyword in url.lower() for keyword in ['price', 'billing', 'financial', 'charge']):
                link['score'] = 0.3  # Lower score for directories
                price_file_links.append(link)
        
        # Sort by score
        return sorted(price_file_links, key=lambda x: x.get('score', 0), reverse=True)
    
    def _is_file_link(self, url: str) -> bool:
        """Check if a URL points to a file."""
        path = urlparse(url).path.lower()
        return any(path.endswith(ext) for ext in self.PRICE_FILE_EXTENSIONS)
    
    def _get_file_type(self, url: str) -> Optional[str]:
        """Get the file type from a URL."""
        path = urlparse(url).path.lower()
        for ext in self.PRICE_FILE_EXTENSIONS:
            if path.endswith(ext):
                return ext[1:]  # Remove the dot
        return None
    
    def _extract_text_content(self, soup: BeautifulSoup) -> str:
        """Extract the main text content from a page for LLM analysis."""
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.extract()
        
        # Get text
        text = soup.get_text(separator=" ", strip=True)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    async def download_file(self, url: str, filename: str = None) -> Tuple[str, Optional[Path]]:
        """Download a file and return its content and path.
        
        Args:
            url: URL of the file to download
            filename: Optional filename to save as
            
        Returns:
            Tuple of (file content, file path)
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status != 200:
                        logger.error(f"Failed to download file from {url}, status: {response.status}")
                        return "", None
                    
                    # Determine filename if not provided
                    if not filename:
                        content_disposition = response.headers.get('Content-Disposition')
                        if content_disposition:
                            filename_match = re.search(r'filename="?([^"]+)"?', content_disposition)
                            if filename_match:
                                filename = filename_match.group(1)
                        
                        if not filename:
                            # Use URL path as filename
                            filename = os.path.basename(urlparse(url).path)
                            
                        if not filename or filename == '':
                            # Last resort: generate a filename
                            file_type = self._get_file_type(url) or 'dat'
                            filename = f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_type}"
                    
                    # Ensure file path is valid
                    file_path = Path(self.download_dir) / filename
                    
                    # Read content
                    content = await response.read()
                    
                    # Save file
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    
                    logger.info(f"Downloaded file from {url} to {file_path}")
                    return content, file_path
                    
        except Exception as e:
            logger.error(f"Error downloading file from {url}: {str(e)}")
            return "", None 