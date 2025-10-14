#!/usr/bin/env python3
"""
Test script for content categorization system.

Usage:
    python test_categorization.py
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rag_app.data_processing.content_categorizer import BlogContentProcessor


def test_categorization():
    """Test the categorization system."""
    print("🧪 Testing Content Categorization System")
    print("=" * 50)
    
    # Initialize processor
    processor = BlogContentProcessor()
    
    # Test with a small sample first
    print("📊 Extracting blog content...")
    blog_data = processor.extract_blog_content()
    
    if not blog_data:
        print("❌ No blog data found. Make sure you have run the crawler first.")
        return
    
    print(f"✅ Found {len(blog_data)} blogs to categorize")
    
    # Test categorization on first 5 blogs
    print("\n🔍 Testing categorization on first 5 blogs:")
    print("-" * 50)
    
    for i, blog in enumerate(blog_data[:5]):
        print(f"\n📝 Blog {i+1}: {blog['title'][:60]}...")
        print(f"🏢 Company: {blog['company']}")
        print(f"📏 Content Length: {blog['content_length']:,} chars")
        
        # Categorize this blog
        topic_scores = processor.categorizer.categorize_hybrid(
            blog['content'], 
            blog['title'], 
            blog['company']
        )
        
        primary_topic = processor.categorizer.get_primary_topic(topic_scores)
        top_topics = processor.categorizer.get_top_topics(topic_scores, 3)
        
        print(f"🎯 Primary Topic: {primary_topic}")
        print(f"📈 Top Topics: {', '.join([f'{topic} ({score:.2f})' for topic, score in top_topics])}")
    
    # Ask if user wants to run full categorization
    print(f"\n🤔 Do you want to categorize all {len(blog_data)} blogs? (y/n): ", end="")
    response = input().strip().lower()
    
    if response == 'y':
        print("\n🚀 Running full categorization...")
        categorized_blogs = processor.categorize_all_blogs()
        processor.save_categorized_data(categorized_blogs)
        processor.analyze_categorization_results()
    else:
        print("✅ Test completed. Use the full script to categorize all blogs.")


if __name__ == "__main__":
    test_categorization()
