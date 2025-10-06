#!/usr/bin/env python3
"""
Test script for the full crawler with hybrid extraction and database storage
"""

import asyncio
import sys
import argparse
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from sys_design_crawlee.main import main


async def test_crawler_with_limit(max_blogs: int = 3):
    """Test the crawler with a limited number of blogs"""
    
    print(f"🚀 Testing Crawler with {max_blogs} Blog Limit")
    print("=" * 60)
    print("This will:")
    print("1. Run the crawler with limited blog processing")
    print("2. Extract blog URLs from the main page")
    print(f"3. Process only {max_blogs} individual blog posts with hybrid extraction")
    print("4. Save results to database and files")
    print("=" * 60)
    
    try:
        # Run the main crawler with limit
        await main(max_blogs=max_blogs)
        
        print(f"\n✅ Crawler completed with {max_blogs} blog limit!")
        print("📊 Check the following for results:")
        print("   - Database: storage/table_data.db (blog_content table)")
        print("   - Text files: storage/blogs/*/content.txt")
        print("   - Images: storage/blogs/*/images/")
        print("   - Logs: storage/extraction_logs/")
        
    except Exception as e:
        print(f"❌ Error running crawler: {e}")
        raise


async def test_full_crawler():
    """Test the full crawler with no limit"""
    
    print("🚀 Testing Full Crawler (No Limit)")
    print("=" * 60)
    print("This will process ALL blog URLs found")
    print("=" * 60)
    
    try:
        # Run the main crawler with no limit
        await main(max_blogs=-1)
        
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
    parser.add_argument('--max-blogs', type=int, default=3, 
                       help='Maximum number of blogs to process (default: 3, use -1 for no limit)')
    parser.add_argument('--full', action='store_true', 
                       help='Run full crawler with no limit')
    
    args = parser.parse_args()
    
    if args.full:
        print("🧪 Starting Full Crawler Test (No Limit)")
        asyncio.run(test_full_crawler())
    else:
        print(f"🧪 Starting Limited Crawler Test ({args.max_blogs} blogs)")
        asyncio.run(test_crawler_with_limit(args.max_blogs))
