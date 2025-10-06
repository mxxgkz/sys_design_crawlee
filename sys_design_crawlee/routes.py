import csv
import os
import sqlite3
import re
import hashlib
import asyncio
from urllib.parse import urljoin, urlparse
from pathlib import Path

from crawlee.crawlers import PlaywrightCrawlingContext
from crawlee.router import Router
from .hybrid_extractor import hybrid_extractor

# Debug flag - set to True to enable verbose debugging
DEBUG_MODE = False

# Global variable to limit the number of blogs to process
MAX_BLOGS_TO_PROCESS = -1

# Flag to control table parsing - set to False to skip table parsing and focus on enqueuing
ENABLE_TABLE_PARSING = False  # -1 means no limit

# Logging helper functions
def log_info(context, message):
    """Helper function for info logging"""
    context.log.info(message)

def log_warning(context, message):
    """Helper function for warning logging"""
    context.log.warning(message)

def log_error(context, message):
    """Helper function for error logging"""
    context.log.error(message)

def log_debug(context, message):
    """Helper function for debug logging (only if DEBUG_MODE is True)"""
    if DEBUG_MODE:
        context.log.info(f"[DEBUG] {message}")

def log_success(context, operation, details=""):
    """Helper function for success logging with consistent format"""
    message = f"✅ {operation}"
    if details:
        message += f" - {details}"
    context.log.info(message)

def log_attempt(context, operation, attempt_num=None):
    """Helper function for attempt logging"""
    message = f"🔄 {operation}"
    if attempt_num:
        message += f" (attempt #{attempt_num})"
    context.log.info(message)

async def try_button_click(page, button, click_methods, context):
    """Try multiple click methods on a button with logging"""
    for method_name, method_func in click_methods.items():
        try:
            await method_func()
            log_success(context, f"Successfully clicked button using {method_name}")
            return True
        except Exception as e:
            log_debug(context, f"Click method {method_name} failed: {e}")
            continue
    return False

async def count_and_log_elements(page, selector, context, description):
    """Count elements and log the result"""
    elements = page.locator(selector)
    count = await elements.count()
    log_info(context, f"{description}: {count}")
    return elements, count

def log_element_analysis(context, element_type, count, details=""):
    """Log element analysis results"""
    message = f"Found {count} {element_type}"
    if details:
        message += f" - {details}"
    log_info(context, message)

async def test_selectors(page, selectors, context, description="Testing selectors"):
    """Test multiple selectors and log results"""
    log_debug(context, f"{description}:")
    for selector in selectors:
        try:
            elements = page.locator(selector)
            count = await elements.count()
            log_debug(context, f'Selector "{selector}": {count} elements found')
            if count > 0:
                # Get the first element's HTML for debugging
                first_element = elements.first
                html = await first_element.inner_html()
                log_debug(context, f'First element HTML: {html[:200]}...')
        except Exception as e:
            log_debug(context, f'Selector "{selector}" failed: {e}')

def create_blog_data_structures(blog_id, title, company, tags, year, url, final_result, 
                               downloaded_images, text_file_path, blog_dir, metadata_file, 
                               extraction_results):
    """Create shared blog data structures for database and dataset storage."""
    # Calculate common values once
    content_length = len(final_result.get('text', ''))
    image_count = len(downloaded_images)
    text_file_path_str = str(text_file_path)
    images_dir_path_str = str(blog_dir / 'images')
    extraction_method = final_result.get('extraction_method', 'unknown')
    extraction_quality = extraction_results['extraction_quality']
    has_images = image_count > 0
    has_embedded_links = 'http' in final_result.get('text', '')
    
    # Base blog data (shared between database and dataset)
    base_blog_data = {
        'blog_id': blog_id,
        'title': title,
        'company': company,
        'tags': tags,
        'year': year,
        'url': url,
        'content_length': content_length,
        'image_count': image_count,
        'extraction_method': extraction_method,
        'extraction_quality': extraction_quality,
        'has_images': has_images,
        'has_embedded_links': has_embedded_links
    }
    
    # Database-specific fields
    blog_data = {
        **base_blog_data,
        'text_file_path': text_file_path_str,
        'images_dir_path': images_dir_path_str
    }
    
    # Dataset-specific fields (includes additional metadata)
    dataset_data = {
        **base_blog_data,
        'text_file': text_file_path_str,
        'images_dir': images_dir_path_str,
        'metadata_file': str(metadata_file),
        'methods_successful': ', '.join(extraction_results['methods_successful']),
        'has_errors': len(extraction_results['errors']) > 0
    }
    
    return blog_data, dataset_data

# Timeout constants (in milliseconds)
PAGE_LOAD_WAIT_TIME = 2000          # Initial page load wait
BUTTON_SCROLL_WAIT_TIME = 500        # Wait after scrolling to button
CONTENT_LOAD_WAIT_TIME = 1000        # Wait after clicking button for content to load
BUTTON_CLICK_TIMEOUT = 5000          # Timeout for individual button clicks
MAX_BUTTON_CLICKS = 20               # Maximum number of "Load more" button clicks

# Blog content extraction constants
BLOG_CONTENT_SELECTORS = [
    'article',
    'main',
    '.post-content',
    '.entry-content',
    '.blog-content',
    '.content',
    '[role="main"]',
    '.post-body',
    '.article-body',
    '.ql-editor',  # LinkedIn specific
    '.blog-post-content'  # LinkedIn specific
]

# Image extraction constants - enhanced for LinkedIn and other tech blogs
IMAGE_SELECTORS = [
    'img',
    'picture img',
    '.post-image img',
    '.article-image img',
    '.content img',
    '.standalone-image-component img',  # LinkedIn specific
    '.figure img',  # Common figure structure
    'figure img',   # HTML5 figure element
    '.blog-image img',  # Generic blog image
    '.article-image img'  # Article images
]

# Image container selectors for captions
IMAGE_CONTAINER_SELECTORS = [
    '.standalone-image-component',  # LinkedIn specific
    'figure',
    '.figure',
    '.image-container',
    '.blog-image-container',
    '.article-image-container'
]

router = Router[PlaywrightCrawlingContext]()

def generate_blog_id(url: str, title: str) -> str:
    """Generate a unique ID for a blog post based on URL and title."""
    content = f"{url}_{title}"
    return hashlib.md5(content.encode()).hexdigest()[:12]

def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters."""
    # Remove or replace invalid filename characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove extra spaces and limit length
    filename = re.sub(r'\s+', '_', filename.strip())
    return filename[:100]  # Limit filename length

async def extract_blog_content(page, context: PlaywrightCrawlingContext) -> tuple[str, list[dict], dict]:
    """Extract text content with embedded links and image information from a blog post."""
    content_text = ""
    images_info = []
    extracted_links = []
    extraction_issues = {
        'content_selectors_tried': [],
        'content_selectors_failed': [],
        'text_extraction_method': None,
        'paragraph_count': 0,
        'fallback_used': False,
        'errors': []
    }
    
    # Try different selectors to find the main content
    content_element = None
    successful_selector = None
    
    for selector in BLOG_CONTENT_SELECTORS:
        try:
            element = page.locator(selector).first
            count = await element.count()
            extraction_issues['content_selectors_tried'].append(selector)
            
            if count > 0:
                content_element = element
                successful_selector = selector
                log_success(context, f"Found content using selector: {selector}", f"{count} elements")
                break
            else:
                extraction_issues['content_selectors_failed'].append(f'{selector}: no elements found')
        except Exception as e:
            error_msg = f'{selector}: {str(e)}'
            extraction_issues['content_selectors_failed'].append(error_msg)
            log_debug(context, f'Selector "{selector}" failed: {e}')
            continue
    
    if not content_element:
        # Fallback: use the entire page body
        content_element = page.locator('body')
        extraction_issues['fallback_used'] = True
        context.log.warning('No specific content area found, using body as fallback')
    
    # Extract text content with embedded links
    try:
        # Get all paragraph elements within the content area
        paragraphs = content_element.locator('p')
        paragraph_count = await paragraphs.count()
        extraction_issues['paragraph_count'] = paragraph_count
        
        if paragraph_count > 0:
            extraction_issues['text_extraction_method'] = 'paragraphs'
            context.log.info(f'Extracting text from {paragraph_count} paragraphs')
            
            for i in range(paragraph_count):
                try:
                    paragraph_element = paragraphs.nth(i)
                    paragraph_text = await paragraph_element.inner_text()
                    
                    if paragraph_text.strip():
                        # Extract links from this paragraph
                        links_in_paragraph = await extract_links_from_element(paragraph_element, page.url, context)
                        extracted_links.extend(links_in_paragraph)
                        
                        # Add paragraph text with link markers
                        paragraph_with_links = await format_paragraph_with_links(paragraph_element, context)
                        content_text += paragraph_with_links + '\n\n'
                except Exception as e:
                    error_msg = f'Error processing paragraph {i}: {str(e)}'
                    extraction_issues['errors'].append(error_msg)
                    context.log.warning(error_msg)
                    continue
        else:
            # Try alternative text extraction methods
            extraction_issues['text_extraction_method'] = 'fallback_methods'
            context.log.warning(f'No paragraphs found, trying alternative text extraction methods')
            
            # Method 1: Try div elements with text content
            try:
                divs = content_element.locator('div')
                div_count = await divs.count()
                context.log.info(f'Found {div_count} div elements, checking for text content')
                
                text_divs = []
                for i in range(min(div_count, 50)):  # Limit to first 50 divs
                    try:
                        div_element = divs.nth(i)
                        div_text = await div_element.inner_text()
                        if div_text.strip() and len(div_text.strip()) > 50:  # Only meaningful text
                            text_divs.append(div_text.strip())
                    except Exception:
                        continue
                
                if text_divs:
                    content_text = '\n\n'.join(text_divs)
                    extraction_issues['text_extraction_method'] = 'div_elements'
                    context.log.info(f'Extracted text from {len(text_divs)} div elements')
                else:
                    raise Exception("No meaningful text found in div elements")
                    
            except Exception as e1:
                # Method 2: Try all text content
                try:
                    content_text = await content_element.inner_text()
                    extraction_issues['text_extraction_method'] = 'all_text'
                    context.log.info('Extracted all text content from element')
                except Exception as e2:
                    # Method 3: Fallback to page body
                    try:
                        content_text = await page.inner_text('body')
                        extraction_issues['text_extraction_method'] = 'page_body'
                        context.log.warning('Fallback to page body text extraction')
                    except Exception as e3:
                        error_msg = f'All text extraction methods failed: {e1}, {e2}, {e3}'
                        extraction_issues['errors'].append(error_msg)
                        context.log.error(error_msg)
                        content_text = "TEXT_EXTRACTION_FAILED"
            
            # Extract all links from content area
            try:
                all_links = content_element.locator('a')
                link_count = await all_links.count()
                context.log.info(f'Extracting {link_count} links from content area')
                
                for i in range(link_count):
                    try:
                        link_element = all_links.nth(i)
                        link_info = await extract_link_info(link_element, page.url, context)
                        if link_info:
                            extracted_links.append(link_info)
                    except Exception as e:
                        context.log.warning(f'Error extracting link {i}: {e}')
                        continue
            except Exception as e:
                error_msg = f'Error extracting links: {str(e)}'
                extraction_issues['errors'].append(error_msg)
                context.log.warning(error_msg)
                
    except Exception as e:
        error_msg = f'Critical error in text extraction: {str(e)}'
        extraction_issues['errors'].append(error_msg)
        context.log.error(error_msg)
        try:
            content_text = await page.inner_text('body')
            extraction_issues['text_extraction_method'] = 'emergency_fallback'
        except Exception:
            content_text = "TEXT_EXTRACTION_COMPLETELY_FAILED"
    
    # Extract images with captions and position information
    image_extraction_issues = {
        'container_selectors_tried': [],
        'container_selectors_failed': [],
        'image_selectors_tried': [],
        'image_selectors_failed': [],
        'images_found': 0,
        'images_with_captions': 0,
        'image_errors': []
    }
    
    try:
        for container_selector in IMAGE_CONTAINER_SELECTORS:
            try:
                containers = content_element.locator(container_selector)
                container_count = await containers.count()
                image_extraction_issues['container_selectors_tried'].append(container_selector)
                
                if container_count > 0:
                    context.log.info(f'Found {container_count} image containers using selector: {container_selector}')
                    
                    for i in range(container_count):
                        try:
                            container = containers.nth(i)
                            image_info = await extract_image_with_caption(container, page.url, i, context)
                            if image_info:
                                images_info.append(image_info)
                                image_extraction_issues['images_found'] += 1
                                if image_info.get('caption'):
                                    image_extraction_issues['images_with_captions'] += 1
                        except Exception as e:
                            error_msg = f'Error extracting image container {i}: {str(e)}'
                            image_extraction_issues['image_errors'].append(error_msg)
                            if DEBUG_MODE:
                                context.log.warning(error_msg)
                            continue
                    
                    # If we found images with containers, don't try other selectors
                    if images_info:
                        break
                else:
                    image_extraction_issues['container_selectors_failed'].append(f'{container_selector}: no containers found')
            except Exception as e:
                error_msg = f'{container_selector}: {str(e)}'
                image_extraction_issues['container_selectors_failed'].append(error_msg)
                if DEBUG_MODE:
                    context.log.warning(f'Container selector "{container_selector}" failed: {e}')
                continue
        
        # Fallback: extract images without containers
        if not images_info:
            context.log.info('No images found with containers, trying direct image selectors')
            for selector in IMAGE_SELECTORS:
                try:
                    images = content_element.locator(selector)
                    image_count = await images.count()
                    image_extraction_issues['image_selectors_tried'].append(selector)
                    
                    if image_count > 0:
                        context.log.info(f'Found {image_count} images using selector: {selector}')
                        
                        for i in range(image_count):
                            try:
                                img_element = images.nth(i)
                                image_info = await extract_basic_image_info(img_element, page.url, i, context)
                                if image_info:
                                    images_info.append(image_info)
                                    image_extraction_issues['images_found'] += 1
                                    if image_info.get('caption'):
                                        image_extraction_issues['images_with_captions'] += 1
                            except Exception as e:
                                error_msg = f'Error extracting image {i}: {str(e)}'
                                image_extraction_issues['image_errors'].append(error_msg)
                                if DEBUG_MODE:
                                    context.log.warning(error_msg)
                                continue
                        break  # Found images with this selector, no need to try others
                    else:
                        image_extraction_issues['image_selectors_failed'].append(f'{selector}: no images found')
                except Exception as e:
                    error_msg = f'{selector}: {str(e)}'
                    image_extraction_issues['image_selectors_failed'].append(error_msg)
                    if DEBUG_MODE:
                        context.log.warning(f'Image selector "{selector}" failed: {e}')
                    continue
    except Exception as e:
        error_msg = f'Critical error in image extraction: {str(e)}'
        image_extraction_issues['image_errors'].append(error_msg)
        context.log.error(error_msg)
    
    # Add extracted links to the end of content
    if extracted_links:
        content_text += "\n\n" + "="*50 + "\n"
        content_text += "EXTRACTED LINKS:\n"
        content_text += "="*50 + "\n"
        for i, link in enumerate(extracted_links, 1):
            content_text += f"{i}. {link['text']} -> {link['href']}\n"
    
    # Combine all extraction issues
    extraction_issues['image_extraction'] = image_extraction_issues
    extraction_issues['total_links_found'] = len(extracted_links)
    extraction_issues['content_length'] = len(content_text.strip())
    extraction_issues['successful_selector'] = successful_selector
    
    return content_text.strip(), images_info, extraction_issues

async def extract_links_from_element(element, base_url: str, context: PlaywrightCrawlingContext) -> list[dict]:
    """Extract all links from an element."""
    links = []
    try:
        link_elements = element.locator('a')
        link_count = await link_elements.count()
        
        for i in range(link_count):
            link_element = link_elements.nth(i)
            link_info = await extract_link_info(link_element, base_url, context)
            if link_info:
                links.append(link_info)
    except Exception as e:
        if DEBUG_MODE:
            context.log.warning(f'Error extracting links from element: {e}')
    return links

async def extract_link_info(link_element, base_url: str, context: PlaywrightCrawlingContext) -> dict:
    """Extract information from a single link element."""
    try:
        href = await link_element.get_attribute('href')
        text = await link_element.inner_text()
        
        if href and text.strip():
            # Convert relative URLs to absolute
            if href.startswith('//'):
                href = 'https:' + href
            elif href.startswith('/'):
                href = urljoin(base_url, href)
            elif not href.startswith('http'):
                href = urljoin(base_url, href)
            
            return {
                'text': text.strip(),
                'href': href
            }
    except Exception as e:
        if DEBUG_MODE:
            context.log.warning(f'Error extracting link info: {e}')
    return None

async def format_paragraph_with_links(element, context: PlaywrightCrawlingContext) -> str:
    """Format paragraph text with embedded link markers."""
    try:
        # Get the HTML content to preserve link structure
        html_content = await element.inner_html()
        
        # Simple approach: replace <a> tags with [LINK: text -> href] format
        import re
        
        def replace_link(match):
            href = match.group(1)
            text = match.group(2)
            return f"[LINK: {text} -> {href}]"
        
        # Pattern to match <a> tags with href and text
        link_pattern = r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>([^<]*)</a>'
        formatted_text = re.sub(link_pattern, replace_link, html_content)
        
        # Remove other HTML tags but keep the formatted links
        formatted_text = re.sub(r'<[^>]+>', '', formatted_text)
        
        return formatted_text.strip()
    except Exception as e:
        if DEBUG_MODE:
            context.log.warning(f'Error formatting paragraph with links: {e}')
        # Fallback to plain text
        return await element.inner_text()

async def extract_image_with_caption(container, base_url: str, index: int, context: PlaywrightCrawlingContext) -> dict:
    """Extract image with caption from a container element."""
    try:
        # Find image within container
        img_element = container.locator('img').first
        if await img_element.count() == 0:
            return None
        
        # Extract image info
        src = await img_element.get_attribute('src')
        alt = await img_element.get_attribute('alt') or ''
        
        if not src:
            return None
        
        # Convert relative URLs to absolute
        if src.startswith('//'):
            src = 'https:' + src
        elif src.startswith('/'):
            src = urljoin(base_url, src)
        elif not src.startswith('http'):
            src = urljoin(base_url, src)
        
        # Extract caption
        caption = ""
        caption_selectors = [
            'figcaption',
            '.caption',
            '.image-caption',
            '.standalone-image-component__caption'  # LinkedIn specific
        ]
        
        for caption_selector in caption_selectors:
            caption_element = container.locator(caption_selector)
            if await caption_element.count() > 0:
                caption = await caption_element.inner_text()
                break
        
        # Get image position in content (approximate)
        position_info = await get_element_position(container, context)
        
        return {
            'src': src,
            'alt': alt,
            'caption': caption.strip(),
            'index': index,
            'position': position_info,
            'container_type': 'figure_with_caption'
        }
    except Exception as e:
        if DEBUG_MODE:
            context.log.warning(f'Error extracting image with caption: {e}')
        return None

async def extract_basic_image_info(img_element, base_url: str, index: int, context: PlaywrightCrawlingContext) -> dict:
    """Extract basic image information without caption."""
    try:
        src = await img_element.get_attribute('src')
        alt = await img_element.get_attribute('alt') or ''
        
        if not src:
            return None
        
        # Convert relative URLs to absolute
        if src.startswith('//'):
            src = 'https:' + src
        elif src.startswith('/'):
            src = urljoin(base_url, src)
        elif not src.startswith('http'):
            src = urljoin(base_url, src)
        
        # Get image position in content (approximate)
        position_info = await get_element_position(img_element, context)
        
        return {
            'src': src,
            'alt': alt,
            'caption': '',
            'index': index,
            'position': position_info,
            'container_type': 'basic'
        }
    except Exception as e:
        if DEBUG_MODE:
            context.log.warning(f'Error extracting basic image info: {e}')
        return None

async def get_element_position(element, context: PlaywrightCrawlingContext) -> dict:
    """Get approximate position of element in content."""
    try:
        # Get bounding box
        bbox = await element.bounding_box()
        if bbox:
            return {
                'x': bbox['x'],
                'y': bbox['y'],
                'width': bbox['width'],
                'height': bbox['height']
            }
    except Exception as e:
        if DEBUG_MODE:
            context.log.warning(f'Error getting element position: {e}')
    return {'x': 0, 'y': 0, 'width': 0, 'height': 0}

async def save_extraction_issues(blog_id: str, title: str, company: str, url: str, extraction_issues: dict, context: PlaywrightCrawlingContext) -> None:
    """Save extraction issues to a separate log for analysis."""
    try:
        storage_dir = Path('storage')
        issues_dir = storage_dir / 'extraction_issues'
        issues_dir.mkdir(parents=True, exist_ok=True)
        
        issue_data = {
            'blog_id': blog_id,
            'title': title,
            'company': company,
            'url': url,
            'timestamp': context.request.started_at.isoformat() if hasattr(context.request, 'started_at') else None,
            'extraction_issues': extraction_issues
        }
        
        issues_file = issues_dir / f'{blog_id}_issues.json'
        import json
        with open(issues_file, 'w', encoding='utf-8') as f:
            json.dump(issue_data, f, indent=2, ensure_ascii=False)
        
        context.log.info(f'Saved extraction issues to: {issues_file}')
        
        # Also append to a summary CSV for easy analysis
        csv_file = issues_dir / 'extraction_issues_summary.csv'
        import csv
        file_exists = csv_file.exists()
        
        with open(csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                # Write header
                writer.writerow([
                    'blog_id', 'title', 'company', 'url', 'text_method', 'content_length',
                    'paragraph_count', 'images_found', 'links_found', 'successful_selector',
                    'fallback_used', 'error_count', 'has_errors'
                ])
            
            writer.writerow([
                blog_id, title, company, url,
                extraction_issues.get('text_extraction_method', 'unknown'),
                extraction_issues.get('content_length', 0),
                extraction_issues.get('paragraph_count', 0),
                extraction_issues.get('image_extraction', {}).get('images_found', 0),
                extraction_issues.get('total_links_found', 0),
                extraction_issues.get('successful_selector', 'none'),
                extraction_issues.get('fallback_used', False),
                len(extraction_issues.get('errors', [])),
                len(extraction_issues.get('errors', [])) > 0
            ])
        
    except Exception as e:
        context.log.error(f'Error saving extraction issues: {e}')

def create_text_image_mapping(content_text: str, images: list[dict]) -> dict:
    """Create a mapping between text content and images for correlation analysis."""
    mapping = {
        'total_images': len(images),
        'images_with_captions': len([img for img in images if img.get('caption')]),
        'image_references_in_text': [],
        'text_sections': []
    }
    
    # Split content into sections (paragraphs)
    paragraphs = [p.strip() for p in content_text.split('\n\n') if p.strip()]
    
    for i, paragraph in enumerate(paragraphs):
        section_info = {
            'section_index': i,
            'text_length': len(paragraph),
            'has_links': '[LINK:' in paragraph,
            'nearby_images': []
        }
        
        # Find images that might be related to this text section
        # This is a simple heuristic - in practice, you might want more sophisticated matching
        for img in images:
            img_caption = img.get('caption', '').lower()
            img_alt = img.get('alt_text', '').lower()
            
            # Check if image caption or alt text contains keywords from this paragraph
            paragraph_lower = paragraph.lower()
            if img_caption and any(word in paragraph_lower for word in img_caption.split() if len(word) > 3):
                section_info['nearby_images'].append({
                    'image_index': img['index'],
                    'filename': img['filename'],
                    'caption': img['caption'],
                    'match_type': 'caption_keyword'
                })
            elif img_alt and any(word in paragraph_lower for word in img_alt.split() if len(word) > 3):
                section_info['nearby_images'].append({
                    'image_index': img['index'],
                    'filename': img['filename'],
                    'alt_text': img['alt_text'],
                    'match_type': 'alt_keyword'
                })
        
        mapping['text_sections'].append(section_info)
    
    return mapping

async def download_image(page, image_url: str, image_path: str, context: PlaywrightCrawlingContext) -> bool:
    """Download an image from URL to the specified path."""
    try:
        # Use Playwright's request context to download the image
        response = await page.request.get(image_url)
        
        if response.status == 200:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(image_path), exist_ok=True)
            
            # Write image data to file
            with open(image_path, 'wb') as f:
                f.write(await response.body())
            
            context.log.info(f'Downloaded image: {os.path.basename(image_path)}')
            return True
        else:
            context.log.warning(f'Failed to download image {image_url}: HTTP {response.status}')
            return False
    except Exception as e:
        context.log.error(f'Error downloading image {image_url}: {e}')
        return False

async def load_more_handler(context: PlaywrightCrawlingContext) -> None:
    """Handler to click the 'Load more' button."""
    page = context.page

    # Wait for page to load first
    await page.wait_for_timeout(PAGE_LOAD_WAIT_TIME)
    
    # Try multiple selectors for the "Load more" button
    selectors = [
        'div[role="button"]:has-text("Load more")',
        'div[role="button"] >> text=Load more',
        'div:has-text("Load more")',
        'button:has-text("Load more")',
        '[role="button"]:has-text("Load more")'
    ]
    
    load_more_button = None
    for selector in selectors:
        try:
            button = page.locator(selector)
            if await button.count() > 0:
                load_more_button = button.first
                context.log.info(f'Found "Load more" button using selector: {selector}')
                break
        except Exception as e:
            log_debug(context, f'Selector "{selector}" failed: {e}')
            continue
    
    if not load_more_button:
        context.log.warning('No "Load more" button found with any selector')
        return
    
    click_count = 0
    max_clicks = MAX_BUTTON_CLICKS
    previous_cell_count = 0
    
    # Get initial cell count
    initial_cells = page.locator('div[data-row-index]')
    initial_cell_count = await initial_cells.count()
    context.log.info(f'Initial table cells: {initial_cell_count}')
    
    while click_count < max_clicks:
        try:
            # Re-find the button each time in case it changed
            current_button = page.locator('div[role="button"]:has-text("Load more")').first
            
            # Check if button exists
            if await current_button.count() == 0:
                context.log.info(f'No "Load more" button found after {click_count} clicks')
                break
            
            # Scroll to the button to make sure it's in view
            await current_button.scroll_into_view_if_needed()
            await page.wait_for_timeout(BUTTON_SCROLL_WAIT_TIME)
            
            # Check if button is visible
            if not await current_button.is_visible():
                context.log.info(f'Button no longer visible after {click_count} clicks')
                break
            
            # Try to click the button
            log_attempt(context, 'Attempting to click "Load more" button', click_count + 1)
            
            # Define click methods to try
            click_methods = {
                'regular click': lambda: current_button.click(timeout=BUTTON_CLICK_TIMEOUT),
                'force click': lambda: current_button.click(force=True, timeout=BUTTON_CLICK_TIMEOUT),
                'JavaScript click': lambda: page.evaluate('document.querySelector(\'div[role="button"]:has-text("Load more")\')?.click()')
            }
            
            click_success = await try_button_click(page, current_button, click_methods, context)
            
            # If all methods failed, assume success to continue (content might have loaded anyway)
            if not click_success:
                log_warning(context, 'All click methods failed, trying to continue')
                click_success = True
            
            if not click_success:
                break
                
            click_count += 1
            
            # Wait for content to load
            await page.wait_for_timeout(CONTENT_LOAD_WAIT_TIME)
            
            # Check if new content loaded by counting table cells
            current_cells = page.locator('div[data-row-index]')
            cell_count = await current_cells.count()
            new_cells = cell_count - previous_cell_count
            context.log.info(f'Click #{click_count}: {cell_count} total cells (+{new_cells} new)')
            
            # If no new cells were added, we might have reached the end
            if new_cells == 0 and click_count > 1:
                context.log.info(f'No new cells added after click #{click_count}, stopping')
                break
                
            previous_cell_count = cell_count
            
            # Check if button is still there for next iteration
            if await load_more_button.count() == 0:
                context.log.info(f'Button disappeared after {click_count} clicks')
                break
                
        except Exception as e:
            context.log.error(f'Error clicking "Load more" button on click #{click_count + 1}: {e}')
            break
    
    if click_count >= max_clicks:
        context.log.warning(f'Reached maximum click limit ({max_clicks})')
    
    context.log.info(f'Finished clicking "Load more" button. Total clicks: {click_count}')
    
    
async def execute_db_operation(operation_func, storage_dir, operation_name):
    """Generic async database operation executor."""
    db_file_path = os.path.join(storage_dir, 'table_data.db')
    
    def sync_operation():
        """Synchronous database operation to be run in thread pool"""
        conn = sqlite3.connect(db_file_path)
        cursor = conn.cursor()
        
        try:
            result = operation_func(cursor)
            conn.commit()
            return result
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    # Run database operations in thread pool to avoid blocking
    try:
        return await asyncio.to_thread(sync_operation)
    except Exception as e:
        raise Exception(f"{operation_name} failed: {e}")


async def handle_pdf_urls(pdf_urls, context):
    """Handle PDF URLs by downloading them and saving metadata to database."""
    import requests
    import aiohttp
    
    context.log.info(f'📄 Processing {len(pdf_urls)} PDF files...')
    
    for pdf_info in pdf_urls:
        try:
            url = pdf_info['url']
            title = pdf_info['title']
            company = pdf_info['company']
            tags = pdf_info['tags']
            year = pdf_info['year']
            
            context.log.info(f'📥 Downloading PDF: {title}')
            
            # Generate unique PDF ID
            pdf_id = hybrid_extractor.generate_blog_id(url, title)
            
            # Create storage directories
            storage_dir = Path('storage')
            pdfs_dir = storage_dir / 'pdfs'
            pdfs_dir.mkdir(parents=True, exist_ok=True)
            
            # Download PDF
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        # Save PDF file
                        pdf_filename = f"{pdf_id}_{sanitize_filename(title[:50])}.pdf"
                        pdf_file_path = pdfs_dir / pdf_filename
                        
                        with open(pdf_file_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)
                        
                        # Get file size
                        file_size = pdf_file_path.stat().st_size
                        
                        # Save metadata to database
                        await save_pdf_metadata_to_database(
                            pdf_id, title, company, tags, year, url,
                            str(pdf_file_path), file_size, context
                        )
                        
                        context.log.info(f'✅ Saved PDF: {title} ({file_size:,} bytes)')
                    else:
                        context.log.error(f'❌ Failed to download PDF: {url} (Status: {response.status})')
                        
        except Exception as e:
            context.log.error(f'❌ Error processing PDF {pdf_info.get("url", "unknown")}: {e}')
            continue


async def save_pdf_metadata_to_database(pdf_id, title, company, tags, year, url, file_path, file_size, context):
    """Save PDF metadata to database."""
    
    def create_pdf_table(cursor):
        """Create the pdf_files table if it doesn't exist"""
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS pdf_files (
            pdf_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT,
            tags TEXT,
            year TEXT,
            url TEXT UNIQUE,
            file_path TEXT,
            file_size INTEGER,
            file_type TEXT DEFAULT 'pdf',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
    
    def insert_pdf_metadata(cursor):
        """Insert PDF metadata"""
        cursor.execute('''
        INSERT OR REPLACE INTO pdf_files (
            pdf_id, title, company, tags, year, url, file_path, file_size, file_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (pdf_id, title, company, tags, year, url, file_path, file_size, 'pdf'))
        return True
    
    def db_operation(cursor):
        """Complete database operation"""
        create_pdf_table(cursor)
        return insert_pdf_metadata(cursor)
    
    try:
        await execute_db_operation(db_operation, 'storage', "PDF metadata database insert")
        context.log.info(f'💾 Saved PDF metadata to database: {title}')
    except Exception as e:
        context.log.error(f'❌ Failed to save PDF metadata: {e}')


async def process_blog_content_directly(page, url, blog_info, context):
    """Process blog content directly without going through the handler system."""
    
    # Extract metadata from blog_info
    title = blog_info['title']
    company = blog_info['company']
    tags = blog_info['tags']
    year = blog_info['year']
    
    context.log.info(f'🔍 Processing blog directly: {title} by {company}')
    
    # Generate unique blog ID
    blog_id = hybrid_extractor.generate_blog_id(url, title)
    
    # Wait for page to load
    await page.wait_for_timeout(PAGE_LOAD_WAIT_TIME)
    
    try:
        # Use hybrid extraction with multiple fallback strategies
        extraction_results = await hybrid_extractor.extract_content_hybrid(url, page, context)
        
        # Log extraction results
        context.log.info(f'📊 Hybrid extraction results for {title}:')
        context.log.info(f'  - Methods tried: {", ".join(extraction_results["methods_tried"])}')
        context.log.info(f'  - Methods successful: {", ".join(extraction_results["methods_successful"])}')
        context.log.info(f'  - Extraction quality: {extraction_results["extraction_quality"]}')
        
        if extraction_results['errors']:
            context.log.warning(f'  - Errors encountered: {len(extraction_results["errors"])}')
            for error in extraction_results['errors'][:3]:  # Show first 3 errors
                context.log.warning(f'    * {error}')
        
        # Get final result
        final_result = extraction_results['final_result']
        if not final_result or not final_result.get('text') or final_result.get('text') == 'EXTRACTION_FAILED_ALL_METHODS':
            context.log.warning(f'❌ No content extracted from {url} using any method')
            # Save extraction log for analysis
            hybrid_extractor.save_extraction_log(url, extraction_results, context)
            return
        
        # Create storage directories
        storage_dir = Path('storage')
        blog_dir = storage_dir / 'blogs' / blog_id
        blog_dir.mkdir(parents=True, exist_ok=True)
        
        # Save text content
        text_filename = hybrid_extractor.sanitize_filename(f"{blog_id}_{title[:50]}.txt")
        text_file_path = blog_dir / text_filename
        
        with open(text_file_path, 'w', encoding='utf-8') as f:
            f.write(f"Title: {title}\n")
            f.write(f"Company: {company}\n")
            f.write(f"Tags: {tags}\n")
            f.write(f"Year: {year}\n")
            f.write(f"URL: {url}\n")
            f.write(f"Blog ID: {blog_id}\n")
            f.write(f"Extraction Method: {final_result.get('extraction_method', 'unknown')}\n")
            f.write(f"Extraction Quality: {extraction_results['extraction_quality']}\n")
            f.write("="*80 + "\n\n")
            f.write(final_result.get('text', ''))
        
        # Process images
        downloaded_images = []
        if final_result.get('images'):
            images_dir = blog_dir / 'images'
            images_dir.mkdir(exist_ok=True)
            
            for i, img_info in enumerate(final_result['images'][:10]):  # Limit to 10 images
                try:
                    img_path = await hybrid_extractor._process_image(img_info, images_dir, f"image_{i:03d}")
                    if img_path:
                        downloaded_images.append({
                            'original_url': img_info.get('src', ''),
                            'local_path': str(img_path),
                            'alt_text': img_info.get('alt', ''),
                            'caption': img_info.get('caption', '')
                        })
                except Exception as e:
                    context.log.warning(f'Failed to process image {i}: {e}')
        
        # Create metadata file
        metadata = {
            'blog_id': blog_id,
            'title': title,
            'company': company,
            'tags': tags,
            'year': year,
            'url': url,
            'extraction_info': {
                'methods_tried': extraction_results['methods_tried'],
                'methods_successful': extraction_results['methods_successful'],
                'final_method': final_result.get('extraction_method', 'unknown'),
                'extraction_timestamp': context.request.started_at.isoformat() if hasattr(context.request, 'started_at') else None
            },
            'hybrid_extraction_results': extraction_results,  # Full extraction results
            'correlation_data': {
                'has_images': len(downloaded_images) > 0,
                'has_embedded_links': 'http' in final_result.get('text', ''),
                'extraction_successful': extraction_results['extraction_quality'] != 'failed'
            }
        }
        
        metadata_file = blog_dir / 'metadata.json'
        import json
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # Save extraction log for analysis
        hybrid_extractor.save_extraction_log(url, extraction_results, context)
        
        # Create shared blog data structures
        blog_data, dataset_data = create_blog_data_structures(
            blog_id, title, company, tags, year, url, final_result,
            downloaded_images, text_file_path, blog_dir, metadata_file, extraction_results
        )
        
        # Save to database and push to dataset
        await save_blog_content_to_database(blog_data, 'storage')
        await context.push_data(dataset_data)
        
        context.log.info(f'✅ Successfully processed blog: {title} (ID: {blog_id})')
        context.log.info(f'  - Content length: {len(final_result.get("text", ""))} characters')
        context.log.info(f'  - Images processed: {len(downloaded_images)}')
        context.log.info(f'  - Extraction method: {final_result.get("extraction_method", "unknown")}')
        context.log.info(f'  - Quality: {extraction_results["extraction_quality"]}')
        context.log.info(f'  - Saved to: {blog_dir}')
        context.log.info(f'  - Database: Blog metadata saved to SQLite')
        
        if extraction_results['errors']:
            context.log.warning(f'  - Had {len(extraction_results["errors"])} extraction issues (saved for analysis)')
        
    except Exception as e:
        context.log.error(f'❌ Error processing blog content from {url}: {e}')
        # Save extraction log even for failed extractions
        try:
            failed_results = {
                'url': url,
                'methods_tried': [],
                'methods_successful': [],
                'methods_failed': ['all'],
                'final_result': None,
                'extraction_quality': 'failed',
                'errors': [f'Handler error: {str(e)}']
            }
            hybrid_extractor.save_extraction_log(url, failed_results, context)
        except Exception as save_error:
            context.log.error(f'Failed to save extraction log: {save_error}')
        raise


async def save_single_record_to_database(record, storage_dir):
    """Save a single record to SQLite database with async I/O operations."""
    
    def create_data_table(cursor):
        """Create the data table if it doesn't exist"""
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS data (
            company TEXT,
            title TEXT,
            tags TEXT,
            year TEXT,
            url TEXT
        )
        ''')
    
    def insert_record(cursor):
        """Insert the record into the data table"""
        cursor.execute(
            'INSERT INTO data (company, title, tags, year, url) VALUES (?, ?, ?, ?, ?)', 
            (record['company'], record['title'], record['tags'], record['year'], record['url'])
        )
        return True
    
    def db_operation(cursor):
        """Complete database operation"""
        create_data_table(cursor)
        return insert_record(cursor)
    
    return await execute_db_operation(db_operation, storage_dir, "Single record database insert")


async def save_blog_content_to_database(blog_data, storage_dir):
    """Save blog content metadata to SQLite database with async I/O operations."""
    
    def create_blog_content_table(cursor):
        """Create the blog_content table and indexes if they don't exist"""
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blog_content (
            blog_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT,
            tags TEXT,
            year TEXT,
            url TEXT UNIQUE,
            content_length INTEGER,
            image_count INTEGER,
            text_file_path TEXT,
            images_dir_path TEXT,
            extraction_method TEXT,
            extraction_quality TEXT,
            has_images BOOLEAN DEFAULT 0,
            has_embedded_links BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create indexes for better performance
        indexes = [
            'CREATE INDEX IF NOT EXISTS idx_blog_company ON blog_content(company)',
            'CREATE INDEX IF NOT EXISTS idx_blog_year ON blog_content(year)',
            'CREATE INDEX IF NOT EXISTS idx_blog_extraction_method ON blog_content(extraction_method)',
            'CREATE INDEX IF NOT EXISTS idx_blog_created_at ON blog_content(created_at)'
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
    
    def insert_blog_content(cursor):
        """Insert blog content record"""
        cursor.execute('''
        INSERT OR REPLACE INTO blog_content (
            blog_id, title, company, tags, year, url, content_length, 
            image_count, text_file_path, images_dir_path, extraction_method, 
            extraction_quality, has_images, has_embedded_links, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (
            blog_data['blog_id'],
            blog_data['title'],
            blog_data['company'],
            blog_data['tags'],
            blog_data['year'],
            blog_data['url'],
            blog_data['content_length'],
            blog_data['image_count'],
            blog_data['text_file_path'],
            blog_data['images_dir_path'],
            blog_data['extraction_method'],
            blog_data['extraction_quality'],
            blog_data['has_images'],
            blog_data['has_embedded_links']
        ))
        return True
    
    def db_operation(cursor):
        """Complete database operation"""
        create_blog_content_table(cursor)
        return insert_blog_content(cursor)
    
    return await execute_db_operation(db_operation, storage_dir, "Blog content database insert")



@router.default_handler
async def default_handler(context: PlaywrightCrawlingContext) -> None:
    """Default request handler - extracts blog URLs and enqueues them for content extraction."""
    context.log.info(f'Processing {context.request.url} ...')
    
    # # Call the load_more_handler to load all blog entries
    # await load_more_handler(context)

    # Wait for page to load and check for table elements
    page = context.page
    await page.wait_for_timeout(PAGE_LOAD_WAIT_TIME + 1000)  # Extra wait for table elements
    
    if DEBUG_MODE:
        # Debug: Check if the page loaded correctly
        title = await page.title()
        log_debug(context, f'Page title: {title}')
        
        # Debug: Check for various elements
        debug_selectors = [
            ('iframe', 'iframes'),
            ('[class*="notion"]', 'elements with "notion" in class name'),
            ('[class*="table"]', 'elements with "table" in class name')
        ]
        
        for selector, description in debug_selectors:
            elements, count = await count_and_log_elements(page, selector, context, f'Found {count} {description}')
        
        # Debug: Try different selectors
        selectors_to_try = [
            'div.notion-table-view-cell',
            'div[class*="notion-table-view-cell"]',
            'div[data-row-index]',
            'div[data-col-index]',
            '[data-row-index]',
            '[data-col-index]',
            'div[data-row-index="0"]',
            'div[data-col-index="0"]'
        ]
        
        await test_selectors(page, selectors_to_try, context, "Testing table selectors")
        
        # Debug: Check the page content for any table-related HTML
        page_content = await page.content()
        if 'data-row-index' in page_content:
            context.log.info('Found "data-row-index" in page content')
            # Find the first occurrence
            start = page_content.find('data-row-index')
            snippet = page_content[start-50:start+200]
            context.log.info(f'HTML snippet around data-row-index: {snippet}')
        else:
            context.log.info('No "data-row-index" found in page content')
    
    # Check if table elements exist
    data_elements, data_count = await count_and_log_elements(page, 'div[data-row-index]', context, 'Table cells with data-row-index')
    
    if data_count == 0:
        # Try to wait a bit more for dynamic content
        try:
            await page.wait_for_selector('div[data-row-index]', timeout=5000)
            data_count = await data_elements.count()
            log_info(context, f'Found {data_count} table cells after waiting')
        except Exception:
            context.log.warning('No table cells found, page may not have loaded properly')
            return

    # Table parsing logic (controlled by flag)
    if ENABLE_TABLE_PARSING:
        context.log.info('📊 Table parsing enabled - processing all table data')
        
        # Use the data elements we already found
        cells = data_elements
        cell_count = data_count

        # Initialize an empty table to store rows
        table = []
        blog_urls = []

        # Group cells by row index (data-row-index attribute)
        row_indices = set()
        for i in range(cell_count):
            row_index = await cells.nth(i).get_attribute('data-row-index')
            if row_index:
                row_indices.add(int(row_index))
        
        context.log.info(f'Processing {len(row_indices)} rows')
        
        # Process each row
        for row_index in sorted(row_indices):
            try:
                # Initialize a list to store the row data
                row_data = []
                
                # Instead of finding all cells at once, target each column specifically
                # This handles nested structures where columns might be at different depths
                
                # Column 0: Company
                col_0_cell = page.locator(f'div[data-row-index="{row_index}"][data-col-index="0"]')
                if await col_0_cell.count() > 0:
                    cell_text = await col_0_cell.first.inner_text()
                    row_data.append(cell_text.strip())
                else:
                    context.log.warning(f'Row {row_index}: Column 0 (company) not found')
                    row_data.append('')
                
                # Column 1: Title (may be nested deeper)
                col_1_cell = page.locator(f'div[data-row-index="{row_index}"][data-col-index="1"]')
                if await col_1_cell.count() > 0:
                    cell_text = await col_1_cell.first.inner_text()
                    row_data.append(cell_text.strip())
                else:
                    context.log.warning(f'Row {row_index}: Column 1 (title) not found')
                    row_data.append('')
                
                # Column 2: Tags
                col_2_cell = page.locator(f'div[data-row-index="{row_index}"][data-col-index="2"]')
                if await col_2_cell.count() > 0:
                    spans = col_2_cell.first.locator('span')
                    tags_text = " ".join([await spans.nth(k).inner_text() for k in range(await spans.count())])
                    row_data.append(tags_text.strip())
                else:
                    context.log.warning(f'Row {row_index}: Column 2 (tags) not found')
                    row_data.append('')
                
                # Column 3: Year
                col_3_cell = page.locator(f'div[data-row-index="{row_index}"][data-col-index="3"]')
                if await col_3_cell.count() > 0:
                    year_text = await col_3_cell.first.inner_text()
                    row_data.append(year_text.strip())
                else:
                    context.log.warning(f'Row {row_index}: Column 3 (year) not found')
                    row_data.append('')
                
                # Column 4: URL link
                col_4_cell = page.locator(f'div[data-row-index="{row_index}"][data-col-index="4"]')
                if await col_4_cell.count() > 0:
                    link = await col_4_cell.first.locator('a').get_attribute('href')
                    row_data.append(link or '')
                else:
                    context.log.warning(f'Row {row_index}: Column 4 (link) not found')
                    row_data.append('')
                
                # Debug: Log the extracted URL
                link = row_data[4]
                if link:
                    context.log.info(f'🔗 Extracted URL: {link}')
                
                # Skip rows with missing critical data
                if not row_data[0] and not row_data[1] and not row_data[4]:
                    context.log.warning(f'Row {row_index} has no company, title, or URL, skipping')
                    continue

                # Append the row data to the table
                table.append(row_data)

                # Process and push data for each row
                data = {
                    'company': row_data[0],
                    'title': row_data[1],
                    'tags': row_data[2],
                    'year': row_data[3],
                    'url': row_data[4],
                }

                # Push the data to the dataset
                await context.push_data(data)
                
                # Insert into database immediately (async I/O)
                await save_single_record_to_database(data, 'storage')
                
                # Collect blog URLs for enqueuing
                if row_data[4]:  # If URL exists
                    blog_info = {
                        'url': row_data[4],
                        'title': row_data[1],
                        'company': row_data[0],
                        'tags': row_data[2],
                        'year': row_data[3]
                    }
                    blog_urls.append(blog_info)
                    context.log.info(f'📝 Added to blog_urls: {blog_info["url"]} - {blog_info["title"]}')
                
            except Exception as e:
                context.log.error(f'Error processing row {row_index}: {e}')
                continue

        context.log.info(f'Successfully extracted {len(table)} rows')
        
        # Save to files if we have data
        if table:
            try:
                # Create storage directory
                storage_dir = 'storage'
                os.makedirs(storage_dir, exist_ok=True)
                
                # Save to CSV file
                csv_file_path = os.path.join(storage_dir, 'table_data.csv')
                with open(csv_file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerows(table)
                
                # Database records are already saved individually during processing
                # CSV file serves as a backup/analysis file
                context.log.info(f'Data saved to {storage_dir}/ - {len(table)} rows processed (database records saved individually, CSV created for backup)')
            except Exception as e:
                context.log.error(f'Error saving data: {e}')
        else:
            context.log.warning('No table data found to save.')
    else:
        context.log.info('🚀 Table parsing disabled - focusing on enqueuing blog links')
        blog_urls = []  # Initialize empty for enqueuing logic

    # Focus on enqueuing blog links directly
    context.log.info('🎯 Focusing on enqueuing blog links from data-col-index="4"')
    
    # Enqueue blog URLs for content extraction
    try:
        # Debug: Check what links the selector finds
        debug_links = page.locator('div[data-col-index="4"] a[href*="http"][target="_blank"]')
        link_count = await debug_links.count()
        context.log.info(f'🔍 Found {link_count} links matching selector')
        
        # Debug: Try different selectors to see what's available
        simple_selector = page.locator('div[data-col-index="4"] a')
        simple_count = await simple_selector.count()
        context.log.info(f'🔍 Found {simple_count} links with simple selector (div[data-col-index="4"] a)')
        
        # Always use selector approach - enqueue_links is for finding links on current page
        context.log.info(f'📊 Using selector approach to enqueue links from current page')
        
        # Enhanced debugging: Log ALL links found (not just first 3)
        context.log.info('🔍 DEBUGGING: All links found by selector:')
        all_links = []
        for i in range(link_count):
            try:
                href = await debug_links.nth(i).get_attribute('href')
                if href:
                    all_links.append(href)
                    # context.log.info(f'🔗 Link {i+1}: {href}')
                else:
                    context.log.warning(f'🔗 Link {i+1}: No href attribute found')
            except Exception as e:
                context.log.warning(f'🔗 Link {i+1}: Error getting href - {e}')
        
        context.log.info(f'📊 Total links found: {len(all_links)}')
        # context.log.info(f'📊 Links to be enqueued: {all_links}')
        
        # Apply limit if specified
        if MAX_BLOGS_TO_PROCESS > 0 and len(all_links) > MAX_BLOGS_TO_PROCESS:
            limited_links = all_links[:MAX_BLOGS_TO_PROCESS]
            # context.log.info(f'📊 Limited to {MAX_BLOGS_TO_PROCESS} links: {limited_links}')
        else:
            limited_links = all_links
        
        # Use selector approach - Crawlee will handle the enqueuing
        # Note: We can't easily limit the selector, so we'll let Crawlee enqueue all found links
        # The limit will be handled by the crawler's max_requests_per_crawl setting
        context.log.info('🚀 Enqueuing links with selector (no manual limit applied)...')
        
        # Debug: Try different selectors to see which one works
        context.log.info('🔍 Testing different selectors...')
        
        # Test 1: Simple selector
        simple_test = page.locator('div[data-col-index="4"] a')
        # simple_test = page.locator('div.notion-table-view *')
        simple_count = await simple_test.count()
        context.log.info(f'🔍 Simple selector (div[data-col-index="4"] a): {simple_count} links')
        
        # Test 2: With http filter
        http_test = page.locator('div[data-col-index="4"] a[href*="http"]')
        http_count = await http_test.count()
        context.log.info(f'🔍 HTTP filter (div[data-col-index="4"] a[href*="http"]): {http_count} links')
        
        # Test 3: With target filter
        target_test = page.locator('div[data-col-index="4"] a[target="_blank"]')
        target_count = await target_test.count()
        context.log.info(f'🔍 Target filter (div[data-col-index="4"] a[target="_blank"]): {target_count} links')
        
        # Test 4: Combined filter
        combined_test = page.locator('div[data-col-index="4"] a[href*="http"][target="_blank"]')
        combined_count = await combined_test.count()
        context.log.info(f'🔍 Combined filter (div[data-col-index="4"] a[href*="http"][target="_blank"]): {combined_count} links')
        
        # Use the selector that finds the most links
        if combined_count > 0:
            selector_to_use = 'div[data-col-index="4"] a[href*="http"][target="_blank"]'
            context.log.info(f'🔍 Using combined selector: {selector_to_use}')
        elif http_count > 0:
            selector_to_use = 'div[data-col-index="4"] a[href*="http"]'
            context.log.info(f'🔍 Using HTTP selector: {selector_to_use}')
        elif simple_count > 0:
            selector_to_use = 'div[data-col-index="4"] a'
            # selector_to_use = 'div.notion-table-view *'
            context.log.info(f'🔍 Using simple selector: {selector_to_use}')
        else:
            context.log.error('❌ No links found with any selector!')
            return
        
        # selector_to_use = 'div.notion-table-view *'
        selector_to_use = 'div[data-col-index="4"] a'
        try:
            # Debug: Log what we're about to enqueue
            context.log.info(f'🔍 About to enqueue with selector: {selector_to_use}')
            context.log.info(f'🔍 Strategy: all (should enqueue external links)')
            
            await context.enqueue_links(
                selector=selector_to_use,  # Uncommented!
                label='BLOG',  # Changed back to blog_content
                strategy='all',
            )
            context.log.info(f'✅ Successfully enqueued tech blog URLs using selector: {selector_to_use}')
            
            # Debug: Check if any requests were actually added to the queue
            context.log.info('🔍 DEBUGGING: Checking if requests were enqueued...')
            context.log.info('🔍 If blog_content_handler is not called for external links,')
            context.log.info('🔍 it might be due to Crawlee filtering or configuration issues.')
            
        except Exception as enqueue_error:
            context.log.error(f'❌ Error during enqueue_links: {enqueue_error}')
            raise
        # Additional debugging: Check what was actually enqueued
        context.log.info('🔍 DEBUGGING: Checking request queue after enqueuing...')
        try:
            # This will help us verify what was actually enqueued
            context.log.info('📋 Enqueuing completed - blog_content_handler should be called for each URL')
        except Exception as debug_error:
            context.log.warning(f'Debug check failed: {debug_error}')
        
    except Exception as e:
        context.log.error(f'❌ Error enqueuing URLs: {e}')
        context.log.warning('Failed to enqueue blog links')

@router.handler('BLOG')
async def blog_content_handler(context: PlaywrightCrawlingContext) -> None:
    """Handler for extracting content from individual blog posts using hybrid approach."""
    page = context.page
    url = context.request.url
    user_data = context.request.user_data or {}
    
    # Enhanced debugging: Log the URL being processed
    context.log.info('🎯' * 60)
    context.log.info(f'🎯 blog_content_handler CALLED!')
    context.log.info(f'🎯 Processing URL: {url}')
    context.log.info(f'🎯 Request label: {context.request.label}')
    context.log.info(f'🎯 User data: {user_data}')
    context.log.info(f'🎯 Current page URL: {page.url}')
    context.log.info(f'🎯 Is PDF URL: {url.lower().endswith(".pdf") or "/pdf/" in url.lower() or "arxiv.org/pdf" in url.lower()}')
    context.log.info('🎯' * 60)
    
    if "educatum.com" in url:
        context.log.info(f'📄 Detected Educatum URL: {url}')
        # Handle Educatum directly without content extraction
        return
    
    # Check if this is a PDF URL (enhanced detection)
    if (url.lower().endswith('.pdf') or 
        '/pdf/' in url.lower() or 
        'arxiv.org/pdf' in url.lower()):
        context.log.info(f'📄 Detected PDF URL: {url}')
        # Handle PDF directly without content extraction
        try:
            # Extract basic metadata from URL
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            company = domain.replace('www.', '').split('.')[0].title()
            title = f"PDF Document from {company}"
            
            # Generate unique PDF ID
            pdf_id = hybrid_extractor.generate_blog_id(url, title)
            
            # Create storage directories
            storage_dir = Path('storage')
            pdfs_dir = storage_dir / 'pdfs'
            pdfs_dir.mkdir(parents=True, exist_ok=True)
            
            # Download PDF
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        # Save PDF file
                        pdf_filename = f"{pdf_id}_{sanitize_filename(title[:50])}.pdf"
                        pdf_file_path = pdfs_dir / pdf_filename
                        
                        with open(pdf_file_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)
                        
                        # Get file size
                        file_size = pdf_file_path.stat().st_size
                        
                        # Save metadata to database
                        await save_pdf_metadata_to_database(
                            pdf_id, title, company, '', '', url,
                            str(pdf_file_path), file_size, context
                        )
                        
                        context.log.info(f'✅ Saved PDF: {title} ({file_size:,} bytes)')
                    else:
                        context.log.error(f'❌ Failed to download PDF: {url} (Status: {response.status})')
        except Exception as e:
            context.log.error(f'❌ Error processing PDF {url}: {e}')
        return
    
    # Extract metadata directly from the blog post
    try:
        # Get title from page
        title = await page.title()
        if not title or title.strip() == '':
            title = 'Unknown Title'
        
        # Extract company from URL domain
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        company = domain.replace('www.', '').split('.')[0].title()
        
        # Default values for tags and year (can be extracted later if needed)
        tags = ''
        year = ''
        
        context.log.info(f'🔍 Hybrid extraction for blog: {title} by {company}')
    except Exception as e:
        context.log.warning(f'Error extracting basic metadata: {e}')
        title = 'Unknown Title'
        company = 'Unknown Company'
        tags = ''
        year = ''
    
    # Generate unique blog ID
    blog_id = hybrid_extractor.generate_blog_id(url, title)
    
    # Wait for page to load
    await page.wait_for_timeout(PAGE_LOAD_WAIT_TIME)
    
    try:
        # Use hybrid extraction with multiple fallback strategies
        extraction_results = await hybrid_extractor.extract_content_hybrid(url, page, context)
        
        # Log extraction results
        context.log.info(f'📊 Hybrid extraction results for {title}:')
        context.log.info(f'  - Methods tried: {", ".join(extraction_results["methods_tried"])}')
        context.log.info(f'  - Methods successful: {", ".join(extraction_results["methods_successful"])}')
        context.log.info(f'  - Extraction quality: {extraction_results["extraction_quality"]}')
        
        if extraction_results['errors']:
            context.log.warning(f'  - Errors encountered: {len(extraction_results["errors"])}')
            for error in extraction_results['errors'][:3]:  # Show first 3 errors
                context.log.warning(f'    * {error}')
        
        # Get final result
        final_result = extraction_results['final_result']
        if not final_result or not final_result.get('text') or final_result.get('text') == 'EXTRACTION_FAILED_ALL_METHODS':
            context.log.warning(f'❌ No content extracted from {url} using any method')
            # Save extraction log for analysis
            hybrid_extractor.save_extraction_log(url, extraction_results, context)
            return
        
        # Create storage directories
        storage_dir = Path('storage')
        blog_dir = storage_dir / 'blogs' / blog_id
        blog_dir.mkdir(parents=True, exist_ok=True)
        
        # Save text content
        text_filename = hybrid_extractor.sanitize_filename(f"{blog_id}_{title[:50]}.txt")
        text_file_path = blog_dir / text_filename
        
        with open(text_file_path, 'w', encoding='utf-8') as f:
            f.write(f"Title: {title}\n")
            f.write(f"Company: {company}\n")
            f.write(f"Tags: {tags}\n")
            f.write(f"Year: {year}\n")
            f.write(f"URL: {url}\n")
            f.write(f"Blog ID: {blog_id}\n")
            f.write(f"Extraction Method: {final_result.get('extraction_method', 'unknown')}\n")
            f.write("=" * 80 + "\n\n")
            f.write(final_result.get('text', ''))
        
        context.log.info(f'💾 Saved text content to: {text_file_path}')
        
        # Process images from hybrid extraction
        downloaded_images = []
        images_info = final_result.get('images', [])
        
        if images_info:
            images_dir = blog_dir / 'images'
            images_dir.mkdir(exist_ok=True)
            
            context.log.info(f'🖼️ Found {len(images_info)} images to process')
            
            for img_info in images_info:
                try:
                    # Images are already downloaded by hybrid extractor
                    downloaded_images.append({
                        'filename': img_info.get('filename', 'unknown'),
                        'original_url': img_info.get('url', ''),
                        'alt_text': img_info.get('alt_text', ''),
                        'file_path': img_info.get('file_path', ''),
                        'size': img_info.get('size', 0),
                        'index': img_info.get('index', 0)
                    })
                    
                    context.log.info(f'✅ Processed image: {img_info.get("filename", "unknown")}')
                    
                except Exception as e:
                    context.log.error(f'Error processing image: {e}')
                    continue
        
        # Create enhanced metadata file
        metadata = {
            'blog_id': blog_id,
            'title': title,
            'company': company,
            'tags': tags,
            'year': year,
            'url': url,
            'text_file': text_filename,
            'images': downloaded_images,
            'content_length': len(final_result.get('text', '')),
            'image_count': len(downloaded_images),
            'extraction_info': {
                'hybrid_methods_tried': extraction_results['methods_tried'],
                'hybrid_methods_successful': extraction_results['methods_successful'],
                'hybrid_methods_failed': extraction_results['methods_failed'],
                'extraction_quality': extraction_results['extraction_quality'],
                'final_method': final_result.get('extraction_method', 'unknown'),
                'extraction_timestamp': context.request.started_at.isoformat() if hasattr(context.request, 'started_at') else None
            },
            'hybrid_extraction_results': extraction_results,  # Full extraction results
            'correlation_data': {
                'has_images': len(downloaded_images) > 0,
                'has_embedded_links': 'http' in final_result.get('text', ''),
                'extraction_successful': extraction_results['extraction_quality'] != 'failed'
            }
        }
        
        metadata_file = blog_dir / 'metadata.json'
        import json
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # Save extraction log for analysis
        hybrid_extractor.save_extraction_log(url, extraction_results, context)
        
        # Create shared blog data structures
        blog_data, dataset_data = create_blog_data_structures(
            blog_id, title, company, tags, year, url, final_result,
            downloaded_images, text_file_path, blog_dir, metadata_file, extraction_results
        )
        
        # Save to database and push to dataset
        await save_blog_content_to_database(blog_data, 'storage')
        await context.push_data(dataset_data)
        
        context.log.info(f'✅ Successfully processed blog: {title} (ID: {blog_id})')
        context.log.info(f'  - Content length: {len(final_result.get("text", ""))} characters')
        context.log.info(f'  - Images processed: {len(downloaded_images)}')
        context.log.info(f'  - Extraction method: {final_result.get("extraction_method", "unknown")}')
        context.log.info(f'  - Quality: {extraction_results["extraction_quality"]}')
        context.log.info(f'  - Saved to: {blog_dir}')
        context.log.info(f'  - Database: Blog metadata saved to SQLite')
        
        if extraction_results['errors']:
            context.log.warning(f'  - Had {len(extraction_results["errors"])} extraction issues (saved for analysis)')
        
    except Exception as e:
        context.log.error(f'❌ Error processing blog content from {url}: {e}')
        # Save extraction log even for failed extractions
        try:
            failed_results = {
                'url': url,
                'methods_tried': [],
                'methods_successful': [],
                'methods_failed': ['all'],
                'final_result': None,
                'extraction_quality': 'failed',
                'errors': [f'Handler error: {str(e)}']
            }
            hybrid_extractor.save_extraction_log(url, failed_results, context)
        except Exception as save_error:
            context.log.error(f'Failed to save extraction log: {save_error}')
        raise
