import csv
import os
import sqlite3
import re
import hashlib
from urllib.parse import urljoin, urlparse
from pathlib import Path

from crawlee.crawlers import PlaywrightCrawlingContext
from crawlee.router import Router

# Debug flag - set to True to enable verbose debugging
DEBUG_MODE = False

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
                context.log.info(f'Found content using selector: {selector} ({count} elements)')
                break
            else:
                extraction_issues['content_selectors_failed'].append(f'{selector}: no elements found')
        except Exception as e:
            error_msg = f'{selector}: {str(e)}'
            extraction_issues['content_selectors_failed'].append(error_msg)
            if DEBUG_MODE:
                context.log.info(f'Selector "{selector}" failed: {e}')
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
            if DEBUG_MODE:
                context.log.info(f'Selector "{selector}" failed: {e}')
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
            context.log.info(f'Attempting to click "Load more" button (click #{click_count + 1})...')
            
            # Try different click methods with shorter timeouts
            click_success = False
            try:
                # Try regular click with timeout
                await current_button.click(timeout=BUTTON_CLICK_TIMEOUT)
                context.log.info(f'Successfully clicked button using .click()')
                click_success = True
            except Exception as e1:
                try:
                    # Try force click with timeout
                    await current_button.click(force=True, timeout=BUTTON_CLICK_TIMEOUT)
                    context.log.info(f'Successfully clicked button using .click(force=True)')
                    click_success = True
                except Exception as e2:
                    try:
                        # Try JavaScript click
                        await page.evaluate('document.querySelector(\'div[role="button"]:has-text("Load more")\')?.click()')
                        context.log.info(f'Successfully clicked button using JavaScript')
                        click_success = True
                    except Exception as e3:
                        context.log.warning(f'All click methods failed, trying to continue: {e1}, {e2}, {e3}')
                        # Don't break, just continue to see if content loaded anyway
                        click_success = True  # Assume success to continue
            
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
    
    
def save_to_database(table, storage_dir):
    """Save the extracted table data to an SQLite database."""
    # Connect to SQLite database (or create it if it doesn't exist)
    db_file_path = os.path.join(storage_dir, 'table_data.db')
    conn = sqlite3.connect(db_file_path)
    cursor = conn.cursor()

    # Create a table if it doesn't already exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS data (
        company TEXT,
        title TEXT,
        tags TEXT,
        year TEXT,
        url TEXT
    )
    ''')

    # Insert the data into the database
    cursor.executemany('INSERT INTO data (company, title, tags, year, url) VALUES (?, ?, ?, ?, ?)', table)

    # Commit changes and close the connection
    conn.commit()
    conn.close()


@router.default_handler
async def default_handler(context: PlaywrightCrawlingContext) -> None:
    """Default request handler - extracts blog URLs and enqueues them for content extraction."""
    context.log.info(f'Processing {context.request.url} ...')
    
    # Call the load_more_handler to load all blog entries
    await load_more_handler(context)

    # Wait for page to load and check for table elements
    page = context.page
    await page.wait_for_timeout(PAGE_LOAD_WAIT_TIME + 1000)  # Extra wait for table elements
    
    if DEBUG_MODE:
        # Debug: Check if the page loaded correctly
        title = await page.title()
        context.log.info(f'Page title: {title}')
        
        # Debug: Check for iframes
        iframes = page.locator('iframe')
        iframe_count = await iframes.count()
        context.log.info(f'Found {iframe_count} iframes on the page')
        
        # Debug: Check for any notion-related elements
        notion_elements = page.locator('[class*="notion"]')
        notion_count = await notion_elements.count()
        context.log.info(f'Found {notion_count} elements with "notion" in class name')
        
        # Debug: Check for table-related elements
        table_elements = page.locator('[class*="table"]')
        table_count = await table_elements.count()
        context.log.info(f'Found {table_count} elements with "table" in class name')
        
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
        
        for selector in selectors_to_try:
            elements = page.locator(selector)
            count = await elements.count()
            context.log.info(f'Selector "{selector}": {count} elements found')
            if count > 0:
                # Get the first element's HTML for debugging
                first_element = elements.first
                html = await first_element.inner_html()
                context.log.info(f'First element HTML: {html[:200]}...')
        
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
    data_elements = page.locator('div[data-row-index]')
    data_count = await data_elements.count()
    context.log.info(f'Found {data_count} table cells with data-row-index')
    
    if data_count == 0:
        # Try to wait a bit more for dynamic content
        try:
            await page.wait_for_selector('div[data-row-index]', timeout=5000)
            data_count = await data_elements.count()
            context.log.info(f'Found {data_count} table cells after waiting')
        except Exception:
            context.log.warning('No table cells found, page may not have loaded properly')
            return

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
            # Get all cells for this row
            row_cells = page.locator(f'div[data-row-index="{row_index}"]')
            cell_count_for_row = await row_cells.count()
            
            if cell_count_for_row < 5:
                context.log.warning(f'Row {row_index} has only {cell_count_for_row} cells, skipping')
                continue

            # Initialize a list to store the row data
            row_data = []

            # Extract text content for the first 2 cells (company and title)
            for j in range(2):
                cell_text = await row_cells.nth(j).inner_text()
                row_data.append(cell_text.strip())

            # Extract tags from the 3rd cell (index 2)
            third_cell = row_cells.nth(2)
            spans = third_cell.locator('span')
            tags_text = " ".join([await spans.nth(k).inner_text() for k in range(await spans.count())])
            row_data.append(tags_text.strip())

            # Extract year from the 4th cell
            year_text = await row_cells.nth(3).inner_text()
            row_data.append(year_text.strip())

            # Extract the href link from the last cell
            last_cell = row_cells.nth(4)
            link = await last_cell.locator('a').get_attribute('href')
            row_data.append(link or '')

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
            
            # Collect blog URLs for enqueuing
            if row_data[4]:  # If URL exists
                blog_urls.append({
                    'url': row_data[4],
                    'title': row_data[1],
                    'company': row_data[0],
                    'tags': row_data[2],
                    'year': row_data[3]
                })
            
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
            
            # Save to database
            save_to_database(table, storage_dir)
            context.log.info(f'Data saved to {storage_dir}/')
        except Exception as e:
            context.log.error(f'Error saving data: {e}')
    else:
        context.log.warning('No table data found to save.')
    
    # Enqueue blog URLs for content extraction
    if blog_urls:
        context.log.info(f'Enqueuing {len(blog_urls)} blog URLs for content extraction...')
        for blog_info in blog_urls:
            try:
                await context.enqueue_request({
                    'url': blog_info['url'],
                    'label': 'blog_content',
                    'userData': {
                        'title': blog_info['title'],
                        'company': blog_info['company'],
                        'tags': blog_info['tags'],
                        'year': blog_info['year']
                    }
                })
            except Exception as e:
                context.log.error(f'Error enqueuing blog URL {blog_info["url"]}: {e}')
                continue
        
        context.log.info(f'Successfully enqueued {len(blog_urls)} blog URLs')
    else:
        context.log.warning('No blog URLs found to enqueue')

@router.add_handler('blog_content')
async def blog_content_handler(context: PlaywrightCrawlingContext) -> None:
    """Handler for extracting content from individual blog posts."""
    page = context.page
    url = context.request.url
    user_data = context.request.user_data or {}
    
    # Extract metadata from user_data
    title = user_data.get('title', 'Unknown Title')
    company = user_data.get('company', 'Unknown Company')
    tags = user_data.get('tags', '')
    year = user_data.get('year', '')
    
    context.log.info(f'Extracting content from blog: {title} by {company}')
    
    # Generate unique blog ID
    blog_id = generate_blog_id(url, title)
    
    # Wait for page to load
    await page.wait_for_timeout(PAGE_LOAD_WAIT_TIME)
    
    try:
        # Extract content and images
        content_text, images_info, extraction_issues = await extract_blog_content(page, context)
        
        # Log extraction issues for analysis
        context.log.info(f'Extraction summary for {title}:')
        context.log.info(f'  - Text method: {extraction_issues.get("text_extraction_method", "unknown")}')
        context.log.info(f'  - Content length: {extraction_issues.get("content_length", 0)} chars')
        context.log.info(f'  - Paragraphs found: {extraction_issues.get("paragraph_count", 0)}')
        context.log.info(f'  - Images found: {extraction_issues.get("image_extraction", {}).get("images_found", 0)}')
        context.log.info(f'  - Links found: {extraction_issues.get("total_links_found", 0)}')
        context.log.info(f'  - Successful selector: {extraction_issues.get("successful_selector", "none")}')
        
        if extraction_issues.get('errors'):
            context.log.warning(f'  - Errors encountered: {len(extraction_issues["errors"])}')
            for error in extraction_issues['errors'][:3]:  # Show first 3 errors
                context.log.warning(f'    * {error}')
        
        if not content_text or content_text == "TEXT_EXTRACTION_FAILED" or content_text == "TEXT_EXTRACTION_COMPLETELY_FAILED":
            context.log.warning(f'No content extracted from {url}')
            # Still save the extraction issues for analysis
            await save_extraction_issues(blog_id, title, company, url, extraction_issues, context)
            return
        
        # Create storage directories
        storage_dir = Path('storage')
        blog_dir = storage_dir / 'blogs' / blog_id
        blog_dir.mkdir(parents=True, exist_ok=True)
        
        # Save text content
        text_filename = sanitize_filename(f"{blog_id}_{title[:50]}.txt")
        text_file_path = blog_dir / text_filename
        
        with open(text_file_path, 'w', encoding='utf-8') as f:
            f.write(f"Title: {title}\n")
            f.write(f"Company: {company}\n")
            f.write(f"Tags: {tags}\n")
            f.write(f"Year: {year}\n")
            f.write(f"URL: {url}\n")
            f.write(f"Blog ID: {blog_id}\n")
            f.write("=" * 80 + "\n\n")
            f.write(content_text)
        
        context.log.info(f'Saved text content to: {text_file_path}')
        
        # Download and save images with enhanced metadata
        downloaded_images = []
        if images_info:
            images_dir = blog_dir / 'images'
            images_dir.mkdir(exist_ok=True)
            
            context.log.info(f'Found {len(images_info)} images to download')
            
            for i, img_info in enumerate(images_info):
                try:
                    # Generate image filename
                    img_url = img_info['src']
                    img_alt = img_info['alt']
                    img_caption = img_info.get('caption', '')
                    img_position = img_info.get('position', {})
                    container_type = img_info.get('container_type', 'basic')
                    
                    # Get file extension from URL
                    parsed_url = urlparse(img_url)
                    file_ext = os.path.splitext(parsed_url.path)[1] or '.jpg'
                    
                    # Create filename with more descriptive naming
                    caption_snippet = sanitize_filename(img_caption[:30]) if img_caption else f"img_{i:03d}"
                    img_filename = f"{blog_id}_{caption_snippet}_{i:03d}{file_ext}"
                    img_path = images_dir / img_filename
                    
                    # Download image
                    success = await download_image(page, img_url, str(img_path), context)
                    
                    if success:
                        downloaded_images.append({
                            'filename': img_filename,
                            'original_url': img_url,
                            'alt_text': img_alt,
                            'caption': img_caption,
                            'index': i,
                            'position': img_position,
                            'container_type': container_type,
                            'file_path': str(img_path)
                        })
                        
                        context.log.info(f'Downloaded image {i+1}/{len(images_info)}: {img_filename}')
                        if img_caption:
                            context.log.info(f'  Caption: {img_caption[:100]}...')
                        
                except Exception as e:
                    context.log.error(f'Error downloading image {i}: {e}')
                    continue
        
        # Create enhanced metadata file linking text and images
        metadata = {
            'blog_id': blog_id,
            'title': title,
            'company': company,
            'tags': tags,
            'year': year,
            'url': url,
            'text_file': text_filename,
            'images': downloaded_images,
            'content_length': len(content_text),
            'image_count': len(downloaded_images),
            'extraction_info': {
                'content_selectors_used': BLOG_CONTENT_SELECTORS,
                'image_selectors_used': IMAGE_SELECTORS,
                'image_container_selectors_used': IMAGE_CONTAINER_SELECTORS,
                'extraction_timestamp': context.request.started_at.isoformat() if hasattr(context.request, 'started_at') else None
            },
            'extraction_issues': extraction_issues,  # Include detailed extraction issues
            'correlation_data': {
                'text_image_mapping': create_text_image_mapping(content_text, downloaded_images),
                'image_positions': [img['position'] for img in downloaded_images],
                'has_captions': any(img['caption'] for img in downloaded_images),
                'has_embedded_links': 'EXTRACTED LINKS:' in content_text
            }
        }
        
        metadata_file = blog_dir / 'metadata.json'
        import json
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # Save extraction issues for analysis (even for successful extractions)
        await save_extraction_issues(blog_id, title, company, url, extraction_issues, context)
        
        # Push data to dataset
        await context.push_data({
            'blog_id': blog_id,
            'title': title,
            'company': company,
            'tags': tags,
            'year': year,
            'url': url,
            'content_length': len(content_text),
            'image_count': len(downloaded_images),
            'text_file': str(text_file_path),
            'images_dir': str(blog_dir / 'images'),
            'metadata_file': str(metadata_file),
            'extraction_method': extraction_issues.get('text_extraction_method', 'unknown'),
            'successful_selector': extraction_issues.get('successful_selector', 'none'),
            'has_errors': len(extraction_issues.get('errors', [])) > 0
        })
        
        context.log.info(f'Successfully processed blog: {title} (ID: {blog_id})')
        context.log.info(f'  - Content length: {len(content_text)} characters')
        context.log.info(f'  - Images downloaded: {len(downloaded_images)}')
        context.log.info(f'  - Text method: {extraction_issues.get("text_extraction_method", "unknown")}')
        context.log.info(f'  - Successful selector: {extraction_issues.get("successful_selector", "none")}')
        context.log.info(f'  - Saved to: {blog_dir}')
        
        if extraction_issues.get('errors'):
            context.log.warning(f'  - Had {len(extraction_issues["errors"])} extraction issues (saved for analysis)')
        
    except Exception as e:
        context.log.error(f'Error processing blog content from {url}: {e}')
        # Try to save extraction issues even if processing failed
        try:
            failed_issues = {
                'content_selectors_tried': [],
                'content_selectors_failed': [],
                'text_extraction_method': 'processing_failed',
                'paragraph_count': 0,
                'fallback_used': False,
                'errors': [f'Processing failed: {str(e)}'],
                'image_extraction': {'images_found': 0, 'image_errors': [f'Processing failed: {str(e)}']},
                'total_links_found': 0,
                'content_length': 0,
                'successful_selector': None
            }
            await save_extraction_issues(blog_id, title, company, url, failed_issues, context)
        except Exception as save_error:
            context.log.error(f'Failed to save extraction issues: {save_error}')
        raise
