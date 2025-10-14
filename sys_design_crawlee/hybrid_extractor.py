"""
Hybrid Content Extraction Module
Combines multiple mature strategies for robust blog content extraction
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import urllib3
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urljoin, urlparse
import aiohttp
from newspaper import Article
from readability import Document
import requests
from playwright.async_api import Page
from bs4 import BeautifulSoup
from .logging_utils import log_with_emoji

# Disable SSL warnings since we're bypassing verification for problematic sites
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class HybridContentExtractor:
    """
    Hybrid content extractor that combines multiple mature strategies:
    1. Newspaper3k (primary) - handles most blog structures automatically
    2. Readability-lxml (secondary) - for clean content extraction
    3. Custom Playwright extraction (fallback) - for complex cases
    """
    
    def __init__(self, storage_dir: str = "storage"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        (self.storage_dir / "blogs").mkdir(exist_ok=True)
        (self.storage_dir / "images").mkdir(exist_ok=True)
        (self.storage_dir / "extraction_logs").mkdir(exist_ok=True)
    
    async def extract_content_hybrid(
        self, 
        url: str, 
        page: Optional[Page] = None,
        context = None,
        blog_images_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Extract content using hybrid approach with multiple fallback strategies
        
        Args:
            url: Blog URL to extract content from
            page: Optional Playwright page (for custom extraction fallback)
            context: Optional Crawlee context for logging
            
        Returns:
            Dictionary containing extracted content and metadata
        """
        extraction_results = {
            'url': url,
            'methods_tried': [],
            'methods_successful': [],
            'methods_failed': [],
            'final_result': None,
            'extraction_quality': 'unknown',
            'errors': []
        }
        
        # Method 1: Newspaper3k (Primary - handles 90% of blog structures)
        try:
            if context:
                context.log.info(f"Trying Newspaper3k extraction for {url}")
            
            newspaper_result = await self._extract_with_newspaper(url, context, blog_images_dir)
            if newspaper_result and newspaper_result.get('text'):
                content_length = len(newspaper_result.get('text', ''))
                # Always enhance with comprehensive image extraction, regardless of content length
                enhanced_result = await self._enhance_with_comprehensive_images(newspaper_result, url, page, blog_images_dir)
                
                # Check if content is sufficient (minimum 500 characters for a meaningful blog post)
                if content_length >= 500:
                    extraction_results['methods_tried'].append('newspaper3k')
                    extraction_results['methods_successful'].append('newspaper3k')
                    extraction_results['final_result'] = enhanced_result
                    extraction_results['extraction_quality'] = 'high'
                    
                    if context:
                        context.log.info(f"✅ Newspaper3k successful: {content_length} chars, {len(enhanced_result.get('images', []))} images")
                    
                    return extraction_results
                else:
                    # Content too short, but we still have comprehensive images
                    extraction_results['methods_tried'].append('newspaper3k')
                    extraction_results['methods_failed'].append('newspaper3k')
                    extraction_results['errors'].append(f'Newspaper3k: Insufficient content ({content_length} chars)')
                    
                    if context:
                        context.log.warning(f"⚠️ Newspaper3k: Insufficient content ({content_length} chars) - trying other methods")
            else:
                extraction_results['methods_tried'].append('newspaper3k')
                extraction_results['methods_failed'].append('newspaper3k')
                extraction_results['errors'].append('Newspaper3k: No content extracted')
                
        except Exception as e:
            extraction_results['methods_tried'].append('newspaper3k')
            extraction_results['methods_failed'].append('newspaper3k')
            extraction_results['errors'].append(f'Newspaper3k: {str(e)}')
            
            if context:
                if "406" in str(e) or "Not Acceptable" in str(e):
                    context.log.warning(f"❌ Newspaper3k failed: 406 Not Acceptable - site may be blocking automated requests")
                elif "SSL" in str(e) or "certificate" in str(e).lower():
                    context.log.warning(f"❌ Newspaper3k failed: SSL certificate issue - {e}")
                else:
                    context.log.warning(f"❌ Newspaper3k failed: {e}")
        
        # Method 2: Readability-lxml (Secondary - for clean content)
        try:
            if context:
                context.log.info(f"Trying Readability extraction for {url}")
            
            readability_result = await self._extract_with_readability(url, context)
            if readability_result and readability_result.get('text'):
                content_length = len(readability_result.get('text', ''))
                # Always enhance with comprehensive image extraction, regardless of content length
                enhanced_result = await self._enhance_with_comprehensive_images(readability_result, url, page, blog_images_dir)
                
                if content_length >= 500:
                    extraction_results['methods_tried'].append('readability')
                    extraction_results['methods_successful'].append('readability')
                    extraction_results['final_result'] = enhanced_result
                    extraction_results['extraction_quality'] = 'medium'
                    
                    if context:
                        context.log.info(f"✅ Readability successful: {content_length} chars, {len(enhanced_result.get('images', []))} images")
                    
                    return extraction_results
                else:
                    # Content too short, try other methods
                    extraction_results['methods_tried'].append('readability')
                    extraction_results['methods_failed'].append('readability')
                    extraction_results['errors'].append(f'Readability: Insufficient content ({content_length} chars)')
                    
                    if context:
                        context.log.warning(f"⚠️ Readability: Insufficient content ({content_length} chars) - trying other methods")
            else:
                extraction_results['methods_tried'].append('readability')
                extraction_results['methods_failed'].append('readability')
                extraction_results['errors'].append('Readability: No content extracted')
                
        except Exception as e:
            extraction_results['methods_tried'].append('readability')
            extraction_results['methods_failed'].append('readability')
            extraction_results['errors'].append(f'Readability: {str(e)}')
            
            if context:
                if "406" in str(e) or "Not Acceptable" in str(e):
                    context.log.warning(f"❌ Readability failed: 406 Not Acceptable - site may be blocking automated requests")
                elif "SSL" in str(e) or "certificate" in str(e).lower():
                    context.log.warning(f"❌ Readability failed: SSL certificate issue - {e}")
                else:
                    context.log.warning(f"❌ Readability failed: {e}")
        
        # Method 3: Custom Playwright extraction (Fallback)
        if page:
            try:
                if context:
                    context.log.info(f"Trying custom Playwright extraction for {url}")
                
                custom_result = await self._extract_with_playwright(page, url, context, blog_images_dir)
                if custom_result and custom_result.get('text'):
                    content_length = len(custom_result.get('text', ''))
                    # Always enhance with comprehensive image extraction, regardless of content length
                    enhanced_result = await self._enhance_with_comprehensive_images(custom_result, url, page, blog_images_dir)
                    
                    if content_length >= 500:
                        extraction_results['methods_tried'].append('playwright')
                        extraction_results['methods_successful'].append('playwright')
                        extraction_results['final_result'] = enhanced_result
                        extraction_results['extraction_quality'] = 'low'
                        
                        if context:
                            context.log.info(f"✅ Custom Playwright successful: {content_length} chars, {len(enhanced_result.get('images', []))} images")
                        
                        return extraction_results
                    else:
                        # Content too short, try other methods
                        extraction_results['methods_tried'].append('playwright')
                        extraction_results['methods_failed'].append('playwright')
                        extraction_results['errors'].append(f'Playwright: Insufficient content ({content_length} chars)')
                        
                        if context:
                            context.log.warning(f"⚠️ Playwright: Insufficient content ({content_length} chars) - trying other methods")
                else:
                    extraction_results['methods_tried'].append('playwright')
                    extraction_results['methods_failed'].append('playwright')
                    extraction_results['errors'].append('Playwright: No content extracted')
                    
            except Exception as e:
                extraction_results['methods_tried'].append('playwright')
                extraction_results['methods_failed'].append('playwright')
                extraction_results['errors'].append(f'Playwright: {str(e)}')
                
                if context:
                    context.log.warning(f"❌ Custom Playwright failed: {e}")
        
        # All methods failed
        extraction_results['final_result'] = {
            'text': 'EXTRACTION_FAILED_ALL_METHODS',
            'title': 'Extraction Failed',
            'images': [],
            'extraction_method': 'none'
        }
        extraction_results['extraction_quality'] = 'failed'
        
        if context:
            context.log.error(f"❌ All extraction methods failed for {url}")
        
        return extraction_results
    
    async def _enhance_with_comprehensive_images(self, result: Dict[str, Any], url: str, page=None, blog_images_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Enhance any extraction result with comprehensive image extraction.
        This ensures ALL images are captured regardless of which method succeeded.
        
        Args:
            result: The extraction result from any method
            url: The URL being processed
            page: Optional Playwright page for getting rendered content
            blog_images_dir: Directory to save images to
            
        Returns:
            Enhanced result with comprehensive image list
        """
        try:
            # If we have a Playwright page, use it to get the fully rendered content
            if page:
                html_content = await page.content()
            else:
                # Fallback to aiohttp if no page available
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=self._get_standard_headers(), ssl=False) as response:
                        if response.status == 200:
                            html_content = await response.text()
                        else:
                            return result
            
            # Extract ALL images from the HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            all_img_tags = soup.find_all('img')
            
            # Get existing downloaded images from the result
            existing_images = result.get('images', [])
            existing_urls = {img.get('url', img.get('original_url', '')) for img in existing_images if img.get('url') or img.get('original_url')}
            
            # Process new images that weren't already downloaded
            new_images = []
            for i, img in enumerate(all_img_tags):
                src = img.get('src')
                alt = img.get('alt', '')
                if src and src not in existing_urls:
                    try:
                        # Download the new image
                        img_info = await self._process_image(src, url, len(existing_images) + i, alt, blog_images_dir)
                        if img_info:
                            new_images.append(img_info)
                    except Exception as e:
                        log_with_emoji("⚠️", f"Error processing additional image {src}", str(e), None)
                        continue
            
            # Combine existing and new images
            enhanced_result = result.copy()
            enhanced_result['images'] = existing_images + new_images
            enhanced_result['image_count'] = len(existing_images) + len(new_images)
            enhanced_result['comprehensive_images'] = True
            
            return enhanced_result
        except Exception as e:
            # If enhancement fails, return original result
            return result
    
    def _create_ssl_bypass_session(self) -> requests.Session:
        """Create a requests session with SSL verification disabled"""
        session = requests.Session()
        session.verify = False
        return session
    
    def _get_standard_headers(self) -> Dict[str, str]:
        """Get standard headers for HTTP requests"""
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def _extract_content_manually(self, html_content: str, context=None) -> Optional[Dict[str, Any]]:
        """
        Manually extract content from HTML using BeautifulSoup when automated methods fail.
        
        Args:
            html_content: Raw HTML content as string
            
        Returns:
            Dictionary with text content and images, or None if extraction fails
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # First, extract ALL images from the document (comprehensive search)
            all_images = []
            all_img_tags = soup.find_all('img')
            for img in all_img_tags:
                src = img.get('src')
                alt = img.get('alt', '')
                if src:
                    all_images.append({
                        'src': src,
                        'alt': alt,
                        'width': img.get('width', ''),
                        'height': img.get('height', '')
                    })
            
            # Try different content selectors in order of preference
            content_selectors = [
                'main', '.post-content', '.entry-content', 
                '.blog-content', '.content', '[role="main"]', 
                '.post-body', '.article-body', '.blog-post', 
                '.post', '.entry', '.markdown-body', '.blog-article',
                '.post-content-wrapper', '.content-wrapper',
                'article',  # Move article later as it might be too broad
                '.blog-post-content', '.article-content',
                '.post-text', '.entry-text', '.content-text'
            ]
            
            # Add generic selectors for obfuscated class names (like Ramp's random classes)
            generic_selectors = [
                'div[class*="content"]',  # Any div with "content" in class name
                'div[class*="post"]',     # Any div with "post" in class name
                'div[class*="article"]',  # Any div with "article" in class name
                'div[class*="text"]',     # Any div with "text" in class name
                'div[class*="body"]',     # Any div with "body" in class name
                'div[class*="main"]',     # Any div with "main" in class name
                'section[class*="content"]',  # Any section with "content" in class name
                'section[class*="post"]',     # Any section with "post" in class name
            ]
            
            # Combine all selectors
            all_selectors = content_selectors + generic_selectors
            
            for selector in all_selectors:
                elements = soup.select(selector)
                if elements:
                    text_content = ' '.join([elem.get_text(strip=True) for elem in elements])
                    if len(text_content) > 100:
                        log_with_emoji("🔍", f"Found content with selector '{selector}'", f"{len(text_content)} chars", context)
                        return {
                            'text': text_content,
                            'images': all_images,
                            'content_length': len(text_content),
                            'image_count': len(all_images)
                        }
            
            # If no specific selectors work, try to extract from common text containers
            text_containers = soup.find_all(['div', 'section'], class_=re.compile(r'(content|post|article|blog|entry)', re.I))
            if text_containers:
                text_content = ' '.join([elem.get_text(strip=True) for elem in text_containers])
                if len(text_content) > 100:
                    log_with_emoji("🔍", "Found content with text containers", f"{len(text_content)} chars", context)
                    return {
                        'text': text_content,
                        'images': all_images,
                        'content_length': len(text_content),
                        'image_count': len(all_images)
                    }
            
            # Last resort: try to find the largest text block
            all_text_elements = soup.find_all(['p', 'div', 'span'], string=True)
            if all_text_elements:
                # Filter out very short text (likely navigation/meta)
                meaningful_texts = [elem.get_text(strip=True) for elem in all_text_elements 
                                 if len(elem.get_text(strip=True)) > 20]
                if meaningful_texts:
                    text_content = ' '.join(meaningful_texts)
                    if len(text_content) > 500:  # Only if we get substantial content
                        log_with_emoji("🔍", "Found content with text elements", f"{len(text_content)} chars", context)
                        return {
                            'text': text_content,
                            'images': all_images,
                            'content_length': len(text_content),
                            'image_count': len(all_images)
                        }
            
            # Ultra-aggressive fallback: extract all text from the body and filter
            log_with_emoji("🔍", "Trying ultra-aggressive text extraction...", "", context)
            body = soup.find('body')
            if body:
                # Remove script, style, nav, header, footer elements
                for element in body(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                    element.decompose()
                
                # Get all text content
                all_text = body.get_text(separator='\n', strip=True)
                
                # Split into paragraphs and filter
                paragraphs = [p.strip() for p in all_text.split('\n') if p.strip()]
                meaningful_paragraphs = [p for p in paragraphs if len(p) > 50]  # Only substantial paragraphs
                
                if meaningful_paragraphs:
                    text_content = '\n\n'.join(meaningful_paragraphs)
                    if len(text_content) > 500:
                        log_with_emoji("🔍", "Found content with ultra-aggressive extraction", f"{len(text_content)} chars", context)
                        return {
                            'text': text_content,
                            'images': all_images,
                            'content_length': len(text_content),
                            'image_count': len(all_images)
                        }
            
            return None
            
        except Exception as e:
            log_with_emoji("⚠️", "Manual extraction failed", str(e), context)
            return None
    
    def _extract_images_from_elements(self, elements) -> List[Dict[str, Any]]:
        """Extract images from BeautifulSoup elements"""
        images = []
        try:
            for element in elements:
                # Find all img tags within the element
                img_tags = element.find_all('img')
                for img in img_tags:
                    src = img.get('src')
                    alt = img.get('alt', '')
                    if src:
                        images.append({
                            'src': src,
                            'alt': alt,
                            'width': img.get('width', ''),
                            'height': img.get('height', '')
                        })
        except Exception as e:
            log_with_emoji("⚠️", "Image extraction from elements failed", str(e))
        return images

    async def _extract_with_newspaper(self, url: str, context=None, blog_images_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
        """Extract content using Newspaper3k with SSL bypass"""
        try:
            log_with_emoji("🔍", "Trying Newspaper3k extraction", url, context)
            
            session = self._create_ssl_bypass_session()
            headers = self._get_standard_headers()
            
            # Try direct download approach first
            try:
                response = session.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                html_content = response.text
                
                log_with_emoji("📄", "Downloaded HTML content", f"{len(html_content)} chars", context)
                
                # Create article and set HTML content directly
                article = Article(url)
                article.set_html(html_content)
                article.parse()
                
            except Exception as download_error:
                log_with_emoji("⚠️", "Direct download failed", str(download_error), context)
                log_with_emoji("🔄", "Falling back to standard newspaper3k method...", "", context)
                
                # Fallback to standard method
                article = Article(url)
                article.config.headers = headers
                article.config.verify_ssl = False
                
                if hasattr(article.config, 'session'):
                    article.config.session = session
                
                article.download()
                article.parse()
            
            # Check if we got any content
            if not article.text or len(article.text.strip()) < 50:
                log_with_emoji("⚠️", "Newspaper3k: Insufficient content", f"{len(article.text)} chars", context)
                log_with_emoji("🔍", "Debug: Article title", str(article.title), context)
                log_with_emoji("🔍", "Debug: Article authors", str(article.authors), context)
                log_with_emoji("🔍", "Debug: Article publish_date", str(article.publish_date), context)
                log_with_emoji("🔍", "Debug: Article top_image", str(article.top_image), context)
                log_with_emoji("🔍", "Debug: Article images count", str(len(article.images) if article.images else 0), context)
                
                # Try to extract content manually from HTML
                manual_result = self._extract_content_manually(html_content, context)
                if manual_result and manual_result.get('text'):
                    article.text = manual_result['text']
                    # Add manual images to the article images
                    if manual_result.get('images'):
                        for img_info in manual_result['images']:
                            if img_info.get('src'):
                                article.images.add(img_info['src'])
                    log_with_emoji("✅", "Manual extraction successful", f"{len(article.text)} chars, {len(manual_result.get('images', []))} images", context)
                else:
                    log_with_emoji("⚠️", "Manual extraction also failed", "", context)
                    return None
            
            log_with_emoji("✅", "Newspaper3k: Found content", f"{len(article.text)} characters", context)
            
            # Download and process images
            images = []
            if article.images:
                # Convert set to list and limit to 10 images
                image_list = list(article.images)[:10]
                log_with_emoji("📸", "Processing images", f"{len(image_list)} images", context)
                for i, img_url in enumerate(image_list):
                    try:
                        img_info = await self._process_image(img_url, url, i, blog_images_dir=blog_images_dir)
                        if img_info:
                            images.append(img_info)
                    except Exception as e:
                        log_with_emoji("⚠️", f"Error processing image {img_url}", str(e), context)
                        continue
            
            return {
                'text': article.text,
                'title': article.title,
                'authors': article.authors,
                'publish_date': str(article.publish_date) if article.publish_date else None,
                'images': images,
                'top_image': article.top_image,
                'keywords': article.keywords,
                'summary': article.summary,
                'extraction_method': 'newspaper3k',
                'content_length': len(article.text),
                'image_count': len(images)
            }
            
        except Exception as e:
            log_with_emoji("❌", "Newspaper3k extraction failed", str(e), context)
            return None
    
    async def _extract_with_readability(self, url: str, context=None) -> Optional[Dict[str, Any]]:
        """Extract content using Readability-lxml"""
        try:
            log_with_emoji("🔍", "Trying Readability extraction", url, context)
            
            session = self._create_ssl_bypass_session()
            headers = self._get_standard_headers()
            headers['DNT'] = '1'  # Add DNT header for readability
            
            response = session.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            doc = Document(response.text)
            
            # Get the main content
            content_html = doc.content()
            title = doc.title()
            summary = doc.summary()
            
            log_with_emoji("📄", "Readability: HTML content length", f"{len(content_html)} chars", context)
            
            # Extract text from HTML content
            soup = BeautifulSoup(content_html, 'html.parser')
            text_content = soup.get_text(separator='\n', strip=True)
            
            # Clean up the text
            text_content = re.sub(r'\n\s*\n', '\n\n', text_content)  # Remove excessive newlines
            text_content = text_content.strip()
            
            log_with_emoji("📄", "Readability: Text content length", f"{len(text_content)} chars", context)
            
            # Check if we got sufficient content
            if len(text_content) < 50:
                log_with_emoji("⚠️", "Readability: Insufficient content", f"{len(text_content)} chars", context)
                return None
            
            log_with_emoji("✅", "Readability: Found content", f"{len(text_content)} characters", context)
            
            return {
                'text': text_content,
                'title': title,
                'summary': summary,
                'content_html': content_html,
                'extraction_method': 'readability',
                'content_length': len(text_content),
                'image_count': 0,  # Readability doesn't extract images
                'images': []  # Empty images list for consistency
            }
            
        except Exception as e:
            log_with_emoji("❌", "Readability extraction failed", str(e), context)
            return None
    
    async def _extract_with_playwright(self, page: Page, url: str, context, blog_images_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
        """Extract content using custom Playwright selectors (fallback)"""
        try:
            # Wait for page to load
            await page.wait_for_timeout(2000)
            
            # Try to extract text using common selectors
            text_selectors = [
                'article p',
                'div.post-content p',
                'div.content p',
                'div.entry-content p',
                'main p',
                'div.blog-content p',
                'p'
            ]
            
            content_text = ""
            successful_selector = None
            
            for selector in text_selectors:
                try:
                    elements = await page.locator(selector).all()
                    if elements:
                        texts = []
                        for element in elements:
                            text = await element.text_content()
                            if text and text.strip():
                                texts.append(text.strip())
                        
                        if texts:
                            content_text = '\n\n'.join(texts)
                            successful_selector = selector
                            break
                except Exception:
                    continue
            
            if not content_text:
                # Fallback: get all text from body
                body = await page.locator('body')
                content_text = await body.text_content() or ""
            
            # Extract images with enhanced selectors for obfuscated class names
            images = []
            try:
                # Try multiple image selectors to handle obfuscated class names
                image_selectors = [
                    'img',  # Standard img tag
                    'img[class*="image"]',  # Any img with "image" in class name
                    'img[class*="img"]',    # Any img with "img" in class name
                    'img[class*="photo"]',  # Any img with "photo" in class name
                    'img[class*="picture"]', # Any img with "picture" in class name
                    'img[class*="media"]',  # Any img with "media" in class name
                    'img[class*="asset"]',  # Any img with "asset" in class name
                    'img[class*="banner"]', # Any img with "banner" in class name
                    'img[class*="hero"]',   # Any img with "hero" in class name
                    'img[class*="cover"]',  # Any img with "cover" in class name
                ]
                
                all_images = set()  # Use set to avoid duplicates
                
                for selector in image_selectors:
                    try:
                        img_elements = await page.locator(selector).all()
                        for img in img_elements:
                            try:
                                src = await img.get_attribute('src')
                                if src and src not in all_images:
                                    all_images.add(src)
                            except Exception:
                                continue
                    except Exception:
                        continue
                
                # Process all unique images
                for i, img_src in enumerate(list(all_images)[:10]):  # Limit to 10 images
                    try:
                        # Get alt text from the first matching element
                        alt = ""
                        for selector in image_selectors:
                            try:
                                img_element = page.locator(f'{selector}[src="{img_src}"]').first
                                if await img_element.count() > 0:
                                    alt = await img_element.get_attribute('alt') or ""
                                    break
                            except Exception:
                                continue
                        
                        img_info = await self._process_image(img_src, url, i, alt, blog_images_dir=blog_images_dir)
                        if img_info:
                            images.append(img_info)
                    except Exception:
                        continue
                        
            except Exception as e:
                log_with_emoji("⚠️", "Image extraction failed", str(e), context)
                pass
            
            return {
                'text': content_text,
                'title': await page.title(),
                'images': images,
                'extraction_method': 'playwright',
                'successful_selector': successful_selector,
                'content_length': len(content_text),
                'image_count': len(images)
            }
            
        except Exception as e:
            log_with_emoji("❌", "Playwright extraction failed", str(e), context)
            return None
    
    async def _process_image(self, img_url: str, base_url: str, index: int, alt_text: str = "", blog_images_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
        """Process and download an image"""
        try:
            # Skip data URLs (inline images like SVG, base64, etc.)
            if img_url.startswith('data:'):
                log_with_emoji("⏭️", "Skipping data URL image", f"{img_url[:50]}...", None)
                return None
            
            # Make URL absolute
            if img_url.startswith('//'):
                img_url = 'https:' + img_url
            elif img_url.startswith('/'):
                img_url = urljoin(base_url, img_url)
            elif not img_url.startswith('http'):
                img_url = urljoin(base_url, img_url)
            
            # Generate filename
            parsed_url = urlparse(img_url)
            file_ext = os.path.splitext(parsed_url.path)[1] or '.jpg'
            filename = f"image_{index:03d}{file_ext}"
            
            # Download image
            async with aiohttp.ClientSession() as session:
                async with session.get(img_url, timeout=30) as response:
                    if response.status == 200:
                        content = await response.read()
                        
                        # Save image to blog images directory (default behavior)
                        if blog_images_dir:
                            blog_images_dir.mkdir(parents=True, exist_ok=True)
                            img_path = blog_images_dir / filename
                        else:
                            # Fallback to global images directory
                            img_path = self.storage_dir / "images" / filename
                        
                        with open(img_path, 'wb') as f:
                            f.write(content)
                        
                        return {
                            'url': img_url,
                            'filename': filename,
                            'alt_text': alt_text,
                            'file_path': str(img_path),
                            'size': len(content),
                            'index': index
                        }
            
        except Exception as e:
            log_with_emoji("⚠️", f"Error processing image {img_url}", str(e), None)
            return None
    
    def generate_blog_id(self, url: str, title: str) -> str:
        """Generate unique blog ID"""
        content = f"{url}_{title}".encode('utf-8')
        return hashlib.md5(content).hexdigest()[:12]
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage"""
        # Remove or replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = re.sub(r'\s+', '_', filename)
        return filename[:100]  # Limit length
    
    def save_extraction_log(self, url: str, extraction_results: Dict[str, Any], context = None):
        """Save detailed extraction log for analysis"""
        try:
            log_data = {
                'url': url,
                'timestamp': context.request.started_at.isoformat() if hasattr(context, 'request') and hasattr(context.request, 'started_at') else None,
                'extraction_results': extraction_results
            }
            
            blog_id = self.generate_blog_id(url, extraction_results.get('final_result', {}).get('title', 'Unknown'))
            log_file = self.storage_dir / "extraction_logs" / f"{blog_id}_extraction_log.json"
            
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
            
            if context:
                context.log.info(f"Saved extraction log to: {log_file}")
                
        except Exception as e:
            if context:
                context.log.error(f"Error saving extraction log: {e}")


# Global instance for easy import
hybrid_extractor = HybridContentExtractor()
