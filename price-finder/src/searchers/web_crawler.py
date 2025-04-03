import os
import asyncio
import aiohttp
import logging
from urllib.parse import urljoin, urlparse
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import re
import time

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

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
    
    # Common selectors for price transparency links
    PRICE_TRANSPARENCY_SELECTORS = [
        'a:contains("Machine-Readable")', 
        'a:contains("Download")', 
        'a:contains("CSV")', 
        'a:contains("JSON")',
        'a:contains("Standard Charges")',
        'a:contains("Price List")',
        'a:contains("Chargemaster")'
    ]
    
    def __init__(self, download_dir: str = None):
        """Initialize the web crawler.
        
        Args:
            download_dir: Directory to save downloaded files
        """
        self.download_dir = download_dir or os.path.join(os.getcwd(), 'downloads')
        os.makedirs(self.download_dir, exist_ok=True)
        
        # Playwright components
        self.playwright = None
        self.browser = None
        self.context = None
        
        # Headers to mimic a browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }
    
    async def initialize_browser(self):
        """Initialize the Playwright browser if not already initialized."""
        if self.browser is None:
            try:
                logger.info("Initializing Playwright browser")
                self.playwright = await async_playwright().start()
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    args=['--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage']
                )
                self.context = await self.browser.new_context(
                    user_agent=self.headers['User-Agent'],
                    viewport={'width': 1280, 'height': 800}
                )
                logger.info("Playwright browser initialized successfully")
                return True
            except Exception as e:
                logger.error(f"Error initializing Playwright browser: {str(e)}")
                # Clean up any partially initialized resources
                await self.close_browser()
                return False
        return True
    
    async def close_browser(self):
        """Close Playwright browser and resources."""
        try:
            if self.context:
                await self.context.close()
                self.context = None
                
            if self.browser:
                await self.browser.close()
                self.browser = None
                
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
                
            logger.info("Playwright browser closed successfully")
        except Exception as e:
            logger.error(f"Error closing Playwright browser: {str(e)}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_browser()
    
    async def crawl(self, url: str) -> dict:
        """Crawl a webpage and extract relevant content.
        
        Args:
            url: URL to crawl
            
        Returns:
            dict: Page content, links, and potential price file links
        """
        logger.info(f"Crawling URL: {url}")
        
        # Initialize browser before everything else
        browser_ready = await self.initialize_browser()
        if not browser_ready:
            logger.warning(f"Failed to initialize browser, will use simple request for {url}")
        
        # Parse with basic request first
        html_content = await self._fetch_with_requests(url)
        
        # Try with Playwright if browser is ready
        js_content = ""
        if browser_ready:
            js_content = await self._fetch_with_playwright(url)
        
        # Use the content that has more information
        content = js_content if len(js_content) > len(html_content) else html_content
        
        # If we got no content from either method, return empty result
        if not content:
            logger.warning(f"Could not retrieve any content from {url}")
            return {
                'url': url,
                'content': "",
                'text_content': "",
                'links': [],
                'price_file_links': [],
                'crawl_date': datetime.now()
            }
        
        # Parse the HTML
        soup = BeautifulSoup(content, 'html.parser')
        
        # Extract links
        links = self._extract_links(soup, base_url=url)
        
        # Find potential price transparency file links
        price_file_links = self._find_price_file_links(links, soup, url)
        
        # Find special sections that might contain price transparency links
        machine_readable_links = self._find_machine_readable_sections(soup, url)
        if machine_readable_links:
            price_file_links.extend(machine_readable_links)
        
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
        if not self.browser or not self.context:
            logger.error("Browser or context not initialized")
            return ""
        
        page = None
        content = ""
        
        try:
            # Create a new page in our persistent context
            page = await self.context.new_page()
            
            # Set timeout for navigation
            page.set_default_timeout(30000)
            
            # Set additional headers to avoid detection
            await page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Ch-Ua": "\" Not A;Brand\";v=\"99\", \"Chromium\";v=\"96\"",
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": "\"Windows\"",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-User": "?1",
                "Sec-Fetch-Dest": "document"
            })
            
            # Navigate to the URL
            logger.debug(f"Navigating to {url} with Playwright")
            response = await page.goto(url, wait_until='domcontentloaded')
            
            # Check if navigation succeeded
            if not response:
                logger.warning(f"No response from {url}")
                return ""
                
            if response.status >= 400:
                logger.warning(f"Error status {response.status} when fetching {url}")
                return ""
            
            # Add more human-like behavior
            # Random wait time between 1 and 3 seconds
            await asyncio.sleep(1 + 2 * (time.time() % 1))
            
            # Wait for the page to be fully loaded
            try:
                await page.wait_for_load_state('networkidle', timeout=15000)
            except Exception as e:
                logger.warning(f"Page didn't reach networkidle state: {str(e)}")
            
            # Try to scroll down to load lazy content with more human-like behavior
            try:
                # Scroll down gradually instead of jumping to the bottom
                height = await page.evaluate("document.body.scrollHeight")
                viewport_height = await page.evaluate("window.innerHeight")
                steps = max(1, min(5, int(height / viewport_height)))
                
                for i in range(1, steps + 1):
                    scroll_position = int((i / steps) * height)
                    await page.evaluate(f"window.scrollTo(0, {scroll_position})")
                    # Random wait time between scroll actions
                    await asyncio.sleep(0.5 + (time.time() % 1))
            except Exception as e:
                logger.warning(f"Error scrolling page: {str(e)}")
            
            # Special handling for pages that might have expandable sections
            try:
                # Try to find and click elements that might expand to show download links
                for selector in [
                    'button:has-text("Machine-Readable")', 
                    'button:has-text("Standard Charges")',
                    'button:has-text("Price")',
                    'button:has-text("Download")',
                    'a:has-text("Machine-Readable")',
                    '[id*="price"]:not(a)',
                ]:
                    try:
                        elements = await page.query_selector_all(selector)
                        for element in elements:
                            try:
                                # Check if element is visible
                                is_visible = await element.is_visible()
                                if is_visible:
                                    await element.click()
                                    # Wait a moment for content to appear
                                    await asyncio.sleep(1)
                            except Exception as e:
                                # Just log and continue with next element
                                logger.debug(f"Error clicking element {selector}: {str(e)}")
                    except Exception as e:
                        logger.debug(f"Error finding elements with selector {selector}: {str(e)}")
                
                # Get updated content after potential interactions
                content = await page.content()
            except Exception as e:
                logger.warning(f"Error interacting with page elements: {str(e)}")
            
            # Final check - if we still have no content, try one more time with a screenshot
            if not content:
                try:
                    # Take a screenshot to force rendering
                    await page.screenshot(path=os.path.join(self.download_dir, f"screenshot_{int(time.time())}.png"))
                    # Try one more time to get content
                    content = await page.content()
                except Exception as e:
                    logger.warning(f"Error taking screenshot: {str(e)}")
            
            return content
            
        except Exception as e:
            logger.error(f"Error fetching {url} with Playwright: {str(e)}")
            return ""
            
        finally:
            # Close just the page, keeping the browser context
            if page:
                try:
                    await page.close()
                except Exception as e:
                    logger.warning(f"Error closing page: {str(e)}")
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Extract links from the page."""
        links = []
        
        # Standard link extraction - a tags with href
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            text = a_tag.get_text(strip=True)
            
            # Skip invalid or empty hrefs
            if not href or href.startswith('#') or href.startswith('javascript:'):
                continue
                
            # Make relative URLs absolute
            full_url = urljoin(base_url, href)
            
            links.append({
                'url': full_url,
                'text': text,
                'is_file': self._is_file_link(full_url),
                'file_type': self._get_file_type(full_url)
            })
        
        # ENHANCEMENT: Look for facility lists on price transparency pages
        
        # Phase 1: Look for sections with "Standard charges" or similar titles
        price_sections = []
        section_keywords = [
            "standard charges", "machine readable", "price transparency", 
            "chargemaster", "facility", "hospital", "charges by facility"
        ]
        
        # Find headings that might indicate price transparency sections
        for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            heading_text = heading.get_text(strip=True).lower()
            if any(keyword in heading_text for keyword in section_keywords):
                # Found a potential section - trace up to find the containing div/section
                parent = heading.parent
                section = None
                for i in range(4):  # Check up to 4 levels up
                    if parent and parent.name in ['section', 'div', 'article']:
                        section = parent
                        break
                    if parent:
                        parent = parent.parent
                
                # If we couldn't find a containing section, use all content after this heading
                if not section:
                    # Get all siblings after this heading
                    section = []
                    next_elem = heading.next_sibling
                    while next_elem and (not isinstance(next_elem, type(heading)) or 
                                        not next_elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                        if next_elem.name:  # Only add actual elements, not strings
                            section.append(next_elem)
                        next_elem = next_elem.next_sibling
                
                price_sections.append((heading_text, section))
                logger.debug(f"Found price transparency section: '{heading_text}'")
        
        # Phase 2: Process lists in price transparency sections
        for section_title, section in price_sections:
            # Handle both section as element and section as list
            if isinstance(section, list):
                elements = section
            else:
                elements = [section]
            
            # Process each element
            for element in elements:
                # Look for lists (both ul and ol)
                lists = element.find_all(['ul', 'ol']) if hasattr(element, 'find_all') else []
                
                for list_elem in lists:
                    # Extract all list items
                    list_items = list_elem.find_all('li')
                    
                    # Check if this list might be a facility list
                    facility_keywords = ['hospital', 'medical center', 'center', 'clinic', 'facility', 'health', 'system']
                    is_facility_list = len(list_items) >= 2 and any(
                        any(keyword in li.get_text().lower() for keyword in facility_keywords)
                        for li in list_items
                    )
                    
                    if is_facility_list:
                        logger.debug(f"Found potential facility list with {len(list_items)} items")
                        
                        # Process each list item as a potential facility
                        for li in list_items:
                            li_text = li.get_text(strip=True)
                            
                            # First, check if the list item itself is directly a link
                            li_links = li.find_all('a', href=True)
                            if li_links:
                                for a in li_links:
                                    href = a['href']
                                    if href and not href.startswith('#') and not href.startswith('javascript:'):
                                        full_url = urljoin(base_url, href)
                                        links.append({
                                            'url': full_url,
                                            'text': li_text,
                                            'is_file': self._is_file_link(full_url),
                                            'file_type': self._get_file_type(full_url),
                                            'facility': li_text
                                        })
                                        logger.debug(f"Found facility link: '{li_text}' -> {full_url}")
                            
                            # Next, look for links elsewhere in the page that might match this facility
                            # This addresses cases where facility names are listed as text but links are elsewhere
                            else:
                                # Skip items that are too short or don't look like facility names
                                if len(li_text) < 5 or not any(keyword in li_text.lower() for keyword in facility_keywords):
                                    continue
                                
                                # Get significant words from the facility name
                                facility_words = [w for w in li_text.lower().split() if len(w) > 3]
                                
                                # Look for files on the entire page that might match this facility
                                for a in soup.find_all('a', href=True):
                                    href = a['href']
                                    if not href or href.startswith('#') or href.startswith('javascript:'):
                                        continue
                                        
                                    # Check if this is a potential file link
                                    full_url = urljoin(base_url, href)
                                    
                                    # Only consider file links or links with price indicators
                                    href_lower = href.lower()
                                    price_indicators = ['price', 'charge', 'standard', 'transparency', 'csv', 'excel', 'json']
                                    
                                    is_price_related = any(indicator in href_lower for indicator in price_indicators)
                                    
                                    if not self._is_file_link(full_url) and not is_price_related:
                                        continue
                                    
                                    # Check if any significant words from the facility name appear in the URL
                                    facility_match = False
                                    for word in facility_words:
                                        if word in href_lower:
                                            facility_match = True
                                            break
                                    
                                    # If no direct match, try standardizing the facility name
                                    if not facility_match:
                                        # Convert facility name to standardized format
                                        std_name = self._standardize_facility_name(li_text)
                                        # Look for variations like "TMC-East-Alabama" for "Tanner Medical Center East Alabama"
                                        acronym_parts = [word[0] for word in std_name.split() if word.isalpha() and len(word) > 1]
                                        if acronym_parts:
                                            acronym = ''.join(acronym_parts)
                                            if acronym in href_lower:
                                                facility_match = True
                                    
                                    if facility_match or is_price_related:
                                        # If this URL is not already in our links, add it
                                        if not any(link['url'] == full_url for link in links):
                                            links.append({
                                                'url': full_url,
                                                'text': f"Price file for {li_text}",
                                                'is_file': self._is_file_link(full_url),
                                                'file_type': self._get_file_type(full_url),
                                                'facility': li_text
                                            })
                                            logger.debug(f"Found likely price file for '{li_text}': {full_url}")
        
        # Phase 3: Scan for standard charge files that match common naming patterns used by CMS
        common_patterns = [
            r'\d{9}_[\w\-]+_standardcharges\.csv',  # {tax_id}_{facility_name}_standardcharges.csv
            r'standardcharges.*\.csv',
            r'charges.*\.csv',
            r'.*chargemaster.*\.csv',
            r'machinereadable.*\.csv',
            r'price.*\.csv',
            r'.*_cdm_.*\.csv'
        ]
        
        all_links = soup.find_all('a', href=True)
        for a in all_links:
            href = a['href']
            if not href or href.startswith('#') or href.startswith('javascript:'):
                continue
                
            href_lower = href.lower()
            for pattern in common_patterns:
                if re.search(pattern, href_lower):
                    full_url = urljoin(base_url, href)
                    if not any(link['url'] == full_url for link in links):
                        links.append({
                            'url': full_url,
                            'text': a.get_text(strip=True) or "Standard Charges File",
                            'is_file': True,
                            'file_type': 'csv',
                            'pattern_match': pattern
                        })
                        logger.debug(f"Found standard charges file matching pattern '{pattern}': {full_url}")
                    break
        
        return links
    
    def _standardize_facility_name(self, name: str) -> str:
        """Standardize a facility name for better matching."""
        # Convert to lowercase
        name = name.lower()
        
        # Remove common words that don't help with identification
        common_words = ['the', 'and', 'of', 'at', 'in', 'by', 'for', 'a', 'an']
        words = [w for w in name.split() if w not in common_words]
        
        return ' '.join(words)
    
    def _find_price_file_links(self, links: List[Dict[str, str]], soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Find potential price transparency file links."""
        price_file_links = []
        
        # First pass: look for direct file links
        for link in links:
            url = link['url']
            text = link['text'].lower()
            
            # Check if URL is a file
            if link['is_file']:
                # Check if it's likely a price file
                if any(keyword in url.lower() for keyword in self.PRICE_FILE_KEYWORDS) or \
                   any(keyword in text for keyword in self.PRICE_FILE_KEYWORDS):
                    price_file_links.append(link)
                    continue
            
            # Check text for price transparency indicators
            if any(keyword in text for keyword in self.PRICE_FILE_KEYWORDS):
                price_file_links.append(link)
        
        # Second pass: look for special sections with downloads
        machine_readable_sections = self._find_machine_readable_sections(soup, base_url)
        price_file_links.extend(machine_readable_sections)
        
        return price_file_links
    
    def _find_machine_readable_sections(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Find special sections that might contain price transparency links."""
        special_links = []
        
        # Look for sections containing "Machine-Readable Files for Download" text
        special_section_keywords = [
            "Machine-Readable Files",
            "Machine Readable Files",
            "Machine-Readable File",
            "Download Machine",
            "Standard Charges",
            "Price Transparency"
        ]
        
        # Try to find these keywords in heading elements
        for keyword in special_section_keywords:
            for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                if keyword.lower() in heading.get_text().lower():
                    # Look for nearby links
                    section = None
                    
                    # Try to find enclosing section
                    parent = heading.parent
                    for _ in range(3):  # Check up to 3 levels up
                        if parent and parent.name in ['section', 'div', 'article']:
                            section = parent
                            break
                        parent = parent.parent if parent else None
                    
                    # If no section found, use siblings after heading
                    if not section:
                        section = heading
                    
                    # Find all links in or after this section
                    for a_tag in section.find_all('a', href=True):
                        href = a_tag['href']
                        text = a_tag.get_text(strip=True)
                        
                        # Skip invalid or empty hrefs
                        if not href or href.startswith('#') or href.startswith('javascript:'):
                            continue
                            
                        # Make relative URLs absolute
                        full_url = urljoin(base_url, href)
                        
                        # Add to list
                        special_links.append({
                            'url': full_url,
                            'text': text,
                            'is_file': self._is_file_link(full_url),
                            'file_type': self._get_file_type(full_url),
                            'section': keyword
                        })
                    
                    # If we found a section, break out of the loop
                    if special_links:
                        logger.debug(f"Found {len(special_links)} links in special section '{keyword}'")
                        break
        
        return special_links
    
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
    
    async def download_file(self, url: str, filename: str = None) -> Tuple[bytes, Optional[Path]]:
        """Download a file and return its content and path.
        
        Args:
            url: URL of the file to download
            filename: Optional filename to save as
            
        Returns:
            Tuple of (file content, file path)
        """
        try:
            # Check if this is a valid URL
            if not url or not url.startswith(('http://', 'https://')):
                logger.error(f"Error downloading file from {url}: Invalid URL")
                return b"", None
                
            # Configure aiohttp with proper settings - using the correct parameters to handle large headers
            timeout = aiohttp.ClientTimeout(total=60)
            connector = aiohttp.TCPConnector(
                limit=100, 
                limit_per_host=10,
                max_headers=32_000  # Increased from default 32KB to handle very large header sets
            )
            
            # Create a session with our headers
            async with aiohttp.ClientSession(
                headers=self.headers,
                timeout=timeout,
                connector=connector,
                skip_auto_headers=['User-Agent'],  # Avoid duplicate headers
            ) as session:
                try:
                    # Now the session will handle larger header sets properly
                    async with session.get(url) as response:
                        if response.status != 200:
                            # If we get 403 Forbidden, try with Playwright as fallback
                            if response.status == 403:
                                logger.warning(f"Got 403 Forbidden from {url}, trying with Playwright")
                                return await self._download_with_playwright(url, filename)
                            else:
                                logger.error(f"Failed to download file from {url}, status: {response.status}")
                                return b"", None
                    
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
                    
                    # Remove invalid characters from filename
                    filename = re.sub(r'[^\w\-\.]', '_', filename)
                    
                    # Ensure file path is valid
                    file_path = Path(self.download_dir) / filename
                    
                    # Read content
                    try:
                        content = await response.read()
                    except aiohttp.ClientPayloadError as e:
                        logger.warning(f"Payload error downloading {url}: {str(e)}, trying with Playwright")
                        return await self._download_with_playwright(url, filename)
                    
                    # Check content type for CSV/JSON detection
                    content_type = response.headers.get('Content-Type', '')
                    
                    # If file doesn't have an extension but content type is recognized, add extension
                    if '.' not in filename:
                        if 'csv' in content_type.lower():
                            file_path = Path(str(file_path) + '.csv')
                        elif 'json' in content_type.lower():
                            file_path = Path(str(file_path) + '.json')
                        elif 'excel' in content_type.lower() or 'spreadsheet' in content_type.lower():
                            file_path = Path(str(file_path) + '.xlsx')
                        elif 'xml' in content_type.lower():
                            file_path = Path(str(file_path) + '.xml')
                    
                    # Save file
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    
                    logger.info(f"Downloaded file from {url} to {file_path}")
                    return content, file_path
                        
                except aiohttp.ClientResponseError as e:
                    if "headers" in str(e).lower() or "header" in str(e).lower():
                        logger.warning(f"Header error downloading {url}: {str(e)}, trying with Playwright")
                        return await self._download_with_playwright(url, filename)
                    else:
                        logger.error(f"Response error downloading {url}: {str(e)}")
                        return b"", None
                except aiohttp.ClientPayloadError as e:
                    logger.warning(f"Payload error downloading {url}: {str(e)}, trying with Playwright")
                    return await self._download_with_playwright(url, filename)
                except aiohttp.ClientError as e:
                    logger.warning(f"Client error downloading {url}: {str(e)}, trying with Playwright")
                    return await self._download_with_playwright(url, filename)
                    
        except Exception as e:
            logger.error(f"Error downloading file from {url}: {str(e)}")
            return b"", None

    async def _download_with_playwright(self, url: str, filename: str = None) -> Tuple[bytes, Optional[Path]]:
        """Download a file using Playwright as fallback for blocked requests.
        
        Args:
            url: URL of the file to download
            filename: Optional filename to save as
            
        Returns:
            Tuple of (file content, file path)
        """
        # Close existing browser if any (we'll start a new one with headless=False to avoid bot detection)
        await self.close_browser()
        
        # Initialize a new browser with more human-like settings
        try:
            logger.info("Initializing anti-detection Playwright browser")
            self.playwright = await async_playwright().start()
            # Use non-headless mode to better avoid bot detection for difficult sites
            self.browser = await self.playwright.chromium.launch(
                headless=False,  # Set to False to better avoid detection
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-infobars',
                    '--window-size=1366,768'
                ]
            )
            
            # Create a more human-like context
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
                viewport={'width': 1366, 'height': 768},
                locale='en-US',
                timezone_id='America/New_York',
                has_touch=False,
                java_script_enabled=True,
                bypass_csp=True
            )
            
            # Add human-like behavior
            await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
            });
            """)
        except Exception as e:
            logger.error(f"Browser initialization failed: {str(e)}")
            return b"", None
        
        page = None
        try:
            # Create a new page
            page = await self.context.new_page()
            
            # Set up download behavior
            download_dir = Path(self.download_dir) / "temp_downloads"
            os.makedirs(download_dir, exist_ok=True)
            
            # Configure browser to download files
            await page.context.set_default_timeout(60000)
            
            # Configure more human-like headers and behavior
            await page.set_extra_http_headers({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "max-age=0"
            })
            
            # Add a random sleep before navigation (1-3 seconds)
            await asyncio.sleep(1 + 2 * (time.time() % 1))
            
            # Navigate to the page containing the download link
            logger.info(f"Navigating to {url} with anti-detection browser")
            await page.goto(url)
            
            # Wait for page to be at least partially loaded
            await page.wait_for_load_state("domcontentloaded")
            
            # Add human-like mouse movements
            viewport_size = page.viewport_size
            if viewport_size:
                # Move mouse randomly across page
                for _ in range(3):
                    x = int(viewport_size['width'] * (0.1 + 0.8 * (time.time() % 1)))
                    y = int(viewport_size['height'] * (0.1 + 0.8 * ((time.time() + 0.5) % 1)))
                    await page.mouse.move(x, y)
                    await asyncio.sleep(0.5 + (time.time() % 1))
            
            # Scroll down gradually
            await page.mouse.wheel(0, 300)
            await asyncio.sleep(0.7)
            await page.mouse.wheel(0, 500)
            await asyncio.sleep(0.5)
            
            # Wait for page to be fully loaded
            await page.wait_for_load_state("networkidle")
            
            # Try to click any download button if this is a download page
            download_buttons = await page.query_selector_all('a[href*="download"], button:has-text("Download"), a:has-text("Download")')
            if download_buttons and len(download_buttons) > 0:
                try:
                    # Click the first download button
                    await download_buttons[0].click()
                    # Wait a bit for the download to start
                    await asyncio.sleep(3)
                except Exception as e:
                    logger.warning(f"Failed to click download button: {str(e)}")
            
            # Get the content directly from the page
            response = await page.evaluate("""async () => {
                try {
                    const response = await fetch(window.location.href);
                    const blob = await response.blob();
                    return await new Promise((resolve) => {
                        const reader = new FileReader();
                        reader.onload = () => resolve(reader.result);
                        reader.readAsDataURL(blob);
                    });
                } catch (e) {
                    return null;
                }
            }""")
            
            if not response or not isinstance(response, str) or not response.startswith('data:'):
                logger.warning(f"Failed to get file content with Playwright: {url}")
                return b"", None
            
            # Parse the data URL
            content_type = response.split(';')[0].split(':')[1]
            base64_content = response.split(',')[1]
            import base64
            content = base64.b64decode(base64_content)
            
            # Determine filename if not provided
            if not filename:
                # Extract from URL or generate a default
                filename = os.path.basename(urlparse(url).path)
                if not filename or filename == '':
                    # Try to infer type from content_type
                    file_ext = '.dat'  # Default extension
                    if 'csv' in content_type.lower():
                        file_ext = '.csv'
                    elif 'json' in content_type.lower():
                        file_ext = '.json'
                    elif 'excel' in content_type.lower() or 'spreadsheet' in content_type.lower():
                        file_ext = '.xlsx'
                    elif 'xml' in content_type.lower():
                        file_ext = '.xml'
                    elif 'pdf' in content_type.lower():
                        file_ext = '.pdf'
                    
                    filename = f"download_pw_{datetime.now().strftime('%Y%m%d_%H%M%S')}{file_ext}"
            
            # Remove invalid characters from filename
            filename = re.sub(r'[^\w\-\.]', '_', filename)
            
            # Ensure file path is valid
            file_path = Path(self.download_dir) / filename
            
            # Save file to disk
            with open(file_path, 'wb') as f:
                f.write(content)
            
            logger.info(f"Downloaded file from {url} to {file_path} using Playwright")
            return content, file_path
            
        except Exception as e:
            logger.error(f"Error downloading file with Playwright from {url}: {str(e)}")
            return b"", None
        finally:
            if page:
                await page.close() 