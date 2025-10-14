import sys
# local_crawler_path = "/Users/karlzhang/Library/CloudStorage/OneDrive-Personal/Other/Live_Courses/BitTiger/Alg_Practice/Ind_Proj/crawlee-python-exp/src"
# sys.path.insert(0, local_crawler_path)

import logging
from datetime import timedelta
from crawlee.crawlers import PlaywrightCrawler
from crawlee.http_clients import HttpxHttpClient
from .routes import router

# Clear any existing handlers
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Set up logging with line numbers
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s-%(levelname)s-%(filename)s:%(lineno)d-%(message)s',
    stream=sys.stdout,
    force=True
)

# Configure all loggers to use the same format with line numbers
def configure_logger_with_line_numbers(logger_name):
    """Configure a specific logger to include line numbers"""
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create a new handler with line number format
    handler = logging.StreamHandler(sys.stdout)
    # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    formatter = logging.Formatter('%(asctime)s-%(levelname)s-%(filename)s:%(lineno)d-%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Prevent propagation to root logger to avoid duplicate messages
    logger.propagate = False

# Configure all relevant loggers
configure_logger_with_line_numbers('crawlee')
configure_logger_with_line_numbers('crawlee.crawlers')
configure_logger_with_line_numbers('crawlee.crawlers._playwright')
configure_logger_with_line_numbers('crawlee.crawlers._playwright._playwright_crawler')
configure_logger_with_line_numbers('sys_design_crawlee')

import crawlee
logging.info(f'Crawlee version: {crawlee.__version__} and path: {crawlee.__path__}')

async def main(max_blogs: int = -1, force_reextract: bool = False, load_more: bool = False, test_problematic: bool = False) -> None:
    """The crawler entry point.
    
    Args:
        max_blogs: Maximum number of blog URLs to process. -1 means no limit.
        force_reextract: If True, re-extract all blog content even if previously extracted successfully.
        test_problematic: If True, only process problematic domains for testing anti-bot improvements.
    """
    # Set the global limit for blog processing
    import sys_design_crawlee.routes as routes_module
    routes_module.MAX_BLOGS_TO_PROCESS = max_blogs
    routes_module.FORCE_REEXTRACT_BLOGS = force_reextract
    routes_module.LOAD_MORE = load_more
    routes_module.TEST_ONLY_PROBLEMATIC_DOMAINS = test_problematic
    
    if force_reextract:
        print("🔄 FORCE_REEXTRACT_BLOGS=True - Will re-extract all blog content regardless of previous status")
    else:
        print("✅ FORCE_REEXTRACT_BLOGS=False - Will skip previously extracted content")
        
    if load_more:
        print("🔄 LOAD_MORE=True - Will load more blogs")
    else:
        print("✅ LOAD_MORE=False - Will not load more blogs")
    
    if test_problematic:
        print("🧪 TEST_ONLY_PROBLEMATIC_DOMAINS=True - Will ONLY process problematic URLs (failed extractions, low quality)")
    else:
        print("✅ TEST_ONLY_PROBLEMATIC_DOMAINS=False - Will process all URLs normally")
    
    # Calculate max_requests_per_crawl based on max_blogs
    if max_blogs > 0:
        # Add some buffer: 1 for initial page + max_blogs for content extraction + 2 for safety
        max_requests = max_blogs + 3
        print(f"📊 Setting max_requests_per_crawl to {max_requests} (based on max_blogs={max_blogs})")
    else:
        # No limit - use a high number
        max_requests = 500
        print(f"📊 Setting max_requests_per_crawl to {max_requests} (no limit)")
    
    crawler = PlaywrightCrawler(
        request_handler=router,
        headless=True,
        max_requests_per_crawl=max_requests,  # Dynamic based on max_blogs parameter
        http_client=HttpxHttpClient(),
        # Increase timeout to prevent handler timeout
        request_handler_timeout=timedelta(minutes=10),  # 10 minutes
    )

    await crawler.run(
        [
            'https://www.educatum.com/engineering-blogs-in-ai-ml-system-design',
        ]
    )

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
