#!/usr/bin/env python3
"""
Test script for the full crawler with hybrid extraction and database storage

Example usage:
python test_full_crawler.py --max-blogs 3
python test_full_crawler.py --full
python test_full_crawler.py --max-blogs 3 --force-reextract
python test_full_crawler.py --full --force-reextract
python test_full_crawler.py --max-blogs 20 -r

python ./test_scripts/test_full_crawler.py --max-blogs 100 -r 2>&1 | tee logs/crawler_$(date +%Y%m%d_%H%M%S).log
python ./test_scripts/test_full_crawler.py -f -r 2>&1 | tee logs/crawler_$(date +%Y%m%d_%H%M%S).log
python ./test_scripts/test_full_crawler.py -l -f -r 2>&1 | tee logs/crawler_$(date +%Y%m%d_%H%M%S).log
"""

import asyncio
import sys
import argparse
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sys_design_crawlee.main import main


async def test_crawler_with_limit(max_blogs: int = 3, force_reextract: bool = False, load_more: bool = False, test_problematic: bool = False):
    """Test the crawler with a limited number of blogs"""
    
    print(f"🚀 Testing Crawler with {max_blogs} Blog Limit")
    if force_reextract:
        print("🔄 Force re-extract mode enabled - will re-extract all content")
    if test_problematic:
        print("🧪 Testing ONLY problematic domains (Zillow, AutoTrader, Medium, Etsy)")
    print("=" * 60)
    print("This will:")
    print("1. Run the crawler with limited blog processing")
    print("2. Extract blog URLs from the main page")
    print(f"3. Process only {max_blogs} individual blog posts with hybrid extraction")
    print("4. Save results to database and files")
    if force_reextract:
        print("5. Re-extract all content regardless of previous status")
    if load_more:
        print("6. Load more blogs from the main page")
    if test_problematic:
        print("6. ONLY process problematic domains for anti-bot testing")
    print("=" * 60)
    
    try:
        # Run the main crawler with limit
        await main(max_blogs=max_blogs, force_reextract=force_reextract, load_more=load_more, test_problematic=test_problematic)
        
        print(f"\n✅ Crawler completed with {max_blogs} blog limit!")
        print("📊 Check the following for results:")
        print("   - Database: storage/table_data.db (blog_content table)")
        print("   - Text files: storage/blogs/*/content.txt")
        print("   - Images: storage/blogs/*/images/")
        print("   - Logs: storage/extraction_logs/")
        
    except Exception as e:
        print(f"❌ Error running crawler: {e}")
        raise


async def test_full_crawler(force_reextract: bool = False, test_problematic: bool = False):
    """Test the full crawler with no limit"""
    
    print("🚀 Testing Full Crawler (No Limit)")
    if force_reextract:
        print("🔄 Force re-extract mode enabled - will re-extract all content")
    if test_problematic:
        print("🧪 Testing ONLY problematic URLs (failed extractions, low quality)")
    print("=" * 60)
    print("This will process ALL blog URLs found")
    if force_reextract:
        print("Will re-extract all content regardless of previous status")
    if test_problematic:
        print("Will ONLY process problematic URLs for anti-bot testing")
    print("=" * 60)
    
    try:
        # Run the main crawler with no limit
        await main(max_blogs=-1, force_reextract=force_reextract, test_problematic=test_problematic)
        
        print("\n✅ Full crawler completed!")
        print("📊 Check the following for results:")
        print("   - Database: storage/table_data.db (blog_content table)")
        print("   - Text files: storage/blogs/*/content.txt")
        print("   - Images: storage/blogs/*/images/")
        print("   - Logs: storage/extraction_logs/")
        
    except Exception as e:
        print(f"❌ Error running crawler: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test the crawler with blog limits')
    parser.add_argument('--max-blogs', '-m', type=int, default=3, 
                       help='Maximum number of blogs to process (default: 3, use -1 for no limit)')
    parser.add_argument('--full', '-f', action='store_true', 
                       help='Run full crawler with no limit')
    parser.add_argument('--force-reextract', '--force', '-r', action='store_true', 
                       help='Force re-extraction of all blog content regardless of previous status')
    parser.add_argument('--load-more', '-l', action='store_true', 
                       help='Load more blogs from the main page')
    parser.add_argument('--test-problematic', '-p', action='store_true', 
                       help='Test ONLY problematic URLs (failed extractions, low quality) to verify anti-bot improvements')
    
    args = parser.parse_args()
    
    if args.full:
        print("🧪 Starting Full Crawler Test (No Limit)")
        asyncio.run(test_full_crawler(force_reextract=args.force_reextract, test_problematic=args.test_problematic))
    else:
        print(f"🧪 Starting Limited Crawler Test ({args.max_blogs} blogs)")
        asyncio.run(test_crawler_with_limit(args.max_blogs, force_reextract=args.force_reextract, load_more=args.load_more, test_problematic=args.test_problematic))
