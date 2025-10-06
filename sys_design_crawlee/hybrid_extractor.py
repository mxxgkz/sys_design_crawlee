"""
Hybrid Content Extraction Module
Combines multiple mature strategies for robust blog content extraction
"""

import asyncio
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urljoin, urlparse
import aiohttp
from newspaper import Article
from readability import Document
import requests
from playwright.async_api import Page
from bs4 import BeautifulSoup


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
        context = None
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
            
            newspaper_result = await self._extract_with_newspaper(url)
            if newspaper_result and newspaper_result.get('text'):
                extraction_results['methods_tried'].append('newspaper3k')
                extraction_results['methods_successful'].append('newspaper3k')
                extraction_results['final_result'] = newspaper_result
                extraction_results['extraction_quality'] = 'high'
                
                if context:
                    context.log.info(f"✅ Newspaper3k successful: {len(newspaper_result.get('text', ''))} chars, {len(newspaper_result.get('images', []))} images")
                
                return extraction_results
            else:
                extraction_results['methods_tried'].append('newspaper3k')
                extraction_results['methods_failed'].append('newspaper3k')
                extraction_results['errors'].append('Newspaper3k: No content extracted')
                
        except Exception as e:
            extraction_results['methods_tried'].append('newspaper3k')
            extraction_results['methods_failed'].append('newspaper3k')
            extraction_results['errors'].append(f'Newspaper3k: {str(e)}')
            
            if context:
                context.log.warning(f"❌ Newspaper3k failed: {e}")
        
        # Method 2: Readability-lxml (Secondary - for clean content)
        try:
            if context:
                context.log.info(f"Trying Readability extraction for {url}")
            
            readability_result = await self._extract_with_readability(url)
            if readability_result and readability_result.get('text') and len(readability_result.get('text', '')) > 50:
                extraction_results['methods_tried'].append('readability')
                extraction_results['methods_successful'].append('readability')
                extraction_results['final_result'] = readability_result
                extraction_results['extraction_quality'] = 'medium'
                
                if context:
                    context.log.info(f"✅ Readability successful: {len(readability_result.get('text', ''))} chars")
                
                return extraction_results
            else:
                extraction_results['methods_tried'].append('readability')
                extraction_results['methods_failed'].append('readability')
                extraction_results['errors'].append('Readability: No content extracted')
                
        except Exception as e:
            extraction_results['methods_tried'].append('readability')
            extraction_results['methods_failed'].append('readability')
            extraction_results['errors'].append(f'Readability: {str(e)}')
            
            if context:
                context.log.warning(f"❌ Readability failed: {e}")
        
        # Method 3: Custom Playwright extraction (Fallback)
        if page:
            try:
                if context:
                    context.log.info(f"Trying custom Playwright extraction for {url}")
                
                custom_result = await self._extract_with_playwright(page, url, context)
                if custom_result and custom_result.get('text'):
                    extraction_results['methods_tried'].append('playwright')
                    extraction_results['methods_successful'].append('playwright')
                    extraction_results['final_result'] = custom_result
                    extraction_results['extraction_quality'] = 'low'
                    
                    if context:
                        context.log.info(f"✅ Custom Playwright successful: {len(custom_result.get('text', ''))} chars")
                    
                    return extraction_results
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
    
    async def _extract_with_newspaper(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract content using Newspaper3k"""
        try:
            print(f"🔍 Trying Newspaper3k extraction for: {url}")
            article = Article(url)
            article.download()
            article.parse()
            
            # Check if we got any content
            if not article.text or len(article.text.strip()) < 50:
                print(f"⚠️ Newspaper3k: Insufficient content ({len(article.text)} chars)")
                return None
            
            print(f"✅ Newspaper3k: Found {len(article.text)} characters of content")
            
            # Download and process images
            images = []
            if article.images:
                # Convert set to list and limit to 10 images
                image_list = list(article.images)[:10]
                print(f"📸 Processing {len(image_list)} images...")
                for i, img_url in enumerate(image_list):
                    try:
                        img_info = await self._process_image(img_url, url, i)
                        if img_info:
                            images.append(img_info)
                    except Exception as e:
                        print(f"Error processing image {img_url}: {e}")
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
            print(f"❌ Newspaper3k extraction failed: {e}")
            return None
    
    async def _extract_with_readability(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract content using Readability-lxml"""
        try:
            print(f"🔍 Trying Readability extraction for: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            doc = Document(response.text)
            
            # Get the main content
            content_html = doc.content()
            title = doc.title()
            summary = doc.summary()
            
            print(f"📄 Readability: HTML content length: {len(content_html)} chars")
            
            # Extract text from HTML content
            soup = BeautifulSoup(content_html, 'html.parser')
            text_content = soup.get_text(separator='\n', strip=True)
            
            # Clean up the text
            text_content = re.sub(r'\n\s*\n', '\n\n', text_content)  # Remove excessive newlines
            text_content = text_content.strip()
            
            print(f"📄 Readability: Text content length: {len(text_content)} chars")
            
            # Check if we got sufficient content
            if len(text_content) < 50:
                print(f"⚠️ Readability: Insufficient content ({len(text_content)} chars)")
                return None
            
            print(f"✅ Readability: Found {len(text_content)} characters of content")
            
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
            print(f"❌ Readability extraction failed: {e}")
            return None
    
    async def _extract_with_playwright(self, page: Page, url: str, context) -> Optional[Dict[str, Any]]:
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
            
            # Extract images
            images = []
            try:
                img_elements = await page.locator('img').all()
                for i, img in enumerate(img_elements[:10]):  # Limit to 10 images
                    try:
                        src = await img.get_attribute('src')
                        alt = await img.get_attribute('alt') or ""
                        if src:
                            img_info = await self._process_image(src, url, i, alt)
                            if img_info:
                                images.append(img_info)
                    except Exception:
                        continue
            except Exception:
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
            print(f"Playwright extraction failed: {e}")
            return None
    
    async def _process_image(self, img_url: str, base_url: str, index: int, alt_text: str = "") -> Optional[Dict[str, Any]]:
        """Process and download an image"""
        try:
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
                        
                        # Save image
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
            print(f"Error processing image {img_url}: {e}")
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
