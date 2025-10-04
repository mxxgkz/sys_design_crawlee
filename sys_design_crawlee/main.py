import logging
from datetime import timedelta
from crawlee.crawlers import PlaywrightCrawler
from crawlee.http_clients import HttpxHttpClient
from .routes import router

# Configure logging to include line numbers
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)

async def main() -> None:
    """The crawler entry point."""
    crawler = PlaywrightCrawler(
        request_handler=router,
        headless=True,
        max_requests_per_crawl=500,  # Increased to handle all blog URLs + content extraction
        http_client=HttpxHttpClient(),
        # Increase timeout to prevent handler timeout
        request_handler_timeout=timedelta(minutes=5),  # 5 minutes
    )

    await crawler.run(
        [
            'https://www.educatum.com/engineering-blogs-in-ai-ml-system-design',
        ]
    )

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
