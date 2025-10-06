#!/usr/bin/env python3
"""
Test script for the hybrid content extraction approach
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from sys_design_crawlee.hybrid_extractor import hybrid_extractor


async def test_hybrid_extraction():
    """Test the hybrid extraction with sample blog URLs"""
    
    # Sample blog URLs from different companies/platforms
    test_urls = [
        "https://engineering.linkedin.com/blog/2020/building-a-heterogeneous-social-network-recommendation-system",
        "https://tech.scribd.com/blog/2021/identifying-document-types.html",
        "https://medium.com/oda-product-tech/how-we-went-from-zero-insight-to-predicting-service-time-with-a-machine-learning-model-part-1-516b9545d02f"
    ]
    
    print("🧪 Testing Hybrid Content Extraction")
    print("=" * 50)
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n📝 Test {i}: {url}")
        print("-" * 30)
        
        try:
            # Test hybrid extraction (without Playwright page for now)
            results = await hybrid_extractor.extract_content_hybrid(url, page=None, context=None)
            
            print(f"✅ Extraction completed")
            print(f"   Methods tried: {', '.join(results['methods_tried'])}")
            print(f"   Methods successful: {', '.join(results['methods_successful'])}")
            print(f"   Quality: {results['extraction_quality']}")
            
            if results['final_result']:
                final = results['final_result']
                print(f"   Content length: {len(final.get('text', ''))} chars")
                print(f"   Images found: {len(final.get('images', []))}")
                print(f"   Method used: {final.get('extraction_method', 'unknown')}")
                
                # Show first 200 chars of content
                text = final.get('text', '')
                if text:
                    preview = text[:200] + "..." if len(text) > 200 else text
                    print(f"   Content preview: {preview}")
            
            if results['errors']:
                print(f"   ⚠️ Errors: {len(results['errors'])}")
                for error in results['errors'][:2]:  # Show first 2 errors
                    print(f"     - {error}")
            
        except Exception as e:
            print(f"❌ Error testing {url}: {e}")
    
    print(f"\n🎯 Hybrid extraction test completed!")
    print(f"📁 Check 'storage/extraction_logs/' for detailed logs")


async def test_single_url():
    """Test with a single URL for detailed analysis"""
    
    url = "https://engineering.linkedin.com/blog/2020/building-a-heterogeneous-social-network-recommendation-system"
    
    print(f"\n🔍 Detailed test for: {url}")
    print("=" * 60)
    
    try:
        results = await hybrid_extractor.extract_content_hybrid(url, page=None, context=None)
        
        print(f"📊 Detailed Results:")
        print(f"   URL: {results['url']}")
        print(f"   Methods tried: {results['methods_tried']}")
        print(f"   Methods successful: {results['methods_successful']}")
        print(f"   Methods failed: {results['methods_failed']}")
        print(f"   Quality: {results['extraction_quality']}")
        
        if results['final_result']:
            final = results['final_result']
            print(f"\n📄 Final Result:")
            print(f"   Title: {final.get('title', 'N/A')}")
            print(f"   Content length: {len(final.get('text', ''))} chars")
            print(f"   Images: {len(final.get('images', []))}")
            print(f"   Method: {final.get('extraction_method', 'unknown')}")
            
            # Show more content
            text = final.get('text', '')
            if text:
                print(f"\n📝 Content (first 500 chars):")
                print(text[:500] + "..." if len(text) > 500 else text)
        
        if results['errors']:
            print(f"\n⚠️ Errors encountered:")
            for error in results['errors']:
                print(f"   - {error}")
                
    except Exception as e:
        print(f"❌ Error in detailed test: {e}")


if __name__ == "__main__":
    print("🚀 Starting Hybrid Extraction Tests")
    
    # Run basic tests
    asyncio.run(test_hybrid_extraction())
    
    # Run detailed test
    asyncio.run(test_single_url())
    
    print("\n✅ All tests completed!")
    print("💡 To run the full crawler with hybrid extraction:")
    print("   python -m sys_design_crawlee.main")
