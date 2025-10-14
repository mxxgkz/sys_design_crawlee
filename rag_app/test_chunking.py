#!/usr/bin/env python3
"""
Test script for text chunking system.

Usage:
    python test_chunking.py
"""

import sys
import signal
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rag_app.data_processing.text_chunker import TextChunker


class TimeoutError(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")


def run_with_timeout(func, timeout_seconds=30):
    """Run a function with a timeout."""
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)
    try:
        result = func()
        signal.alarm(0)
        return result
    except TimeoutError:
        print(f"⏰ Operation timed out after {timeout_seconds} seconds")
        return None


def test_chunking_strategies():
    """Test different chunking strategies."""
    print("🧪 Testing Text Chunking Strategies")
    print("=" * 50)
    
    chunker = TextChunker()
    
    # Load a few blogs for testing
    print("📊 Loading blog data...")
    blog_data = chunker.load_categorized_blogs()
    
    if not blog_data:
        print("❌ No blog data found. Make sure you have run categorization first.")
        return
    
    print(f"✅ Found {len(blog_data)} blogs")
    
    # Test with first 3 blogs
    test_blogs = blog_data[:3]
    
    strategies = ["semantic", "hierarchical", "fixed_size"]
    
    for strategy in strategies:
        print(f"\n🔍 Testing {strategy} chunking:")
        print("-" * 30)
        
        all_chunks = []
        
        for i, blog in enumerate(test_blogs):
            print(f"\n📝 Blog {i+1}: {blog['title'][:50]}...")
            print(f"🏢 Company: {blog['company']}")
            print(f"🎯 Primary Topic: {blog['primary_topic']}")
            print(f"📏 Content Length: {blog['content_length']:,} chars")
            
            try:
                print(f"  🔄 Processing {strategy} chunking...")
                
                # Use timeout for fixed_size chunking
                if strategy == "fixed_size":
                    def chunk_blog_func():
                        return chunker.chunk_blog(blog, strategy)
                    
                    chunks = run_with_timeout(chunk_blog_func, timeout_seconds=60)
                    if chunks is None:
                        print(f"  ⏰ {strategy} chunking timed out, skipping...")
                        continue
                else:
                    chunks = chunker.chunk_blog(blog, strategy)
                
                all_chunks.extend(chunks)
                
                print(f"  ✅ Created {len(chunks)} chunks")
                
                # Show first chunk as example
                if chunks:
                    first_chunk = chunks[0]
                    print(f"  📄 First chunk ({first_chunk.chunk_type}): {first_chunk.content[:100]}...")
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
        
        # Analyze results
        if all_chunks:
            print(f"\n📊 {strategy.title()} Results:")
            chunker.analyze_chunks(all_chunks)
    
    # Ask if user wants to run full chunking
    print(f"\n🤔 Do you want to chunk all {len(blog_data)} blogs? (y/n): ", end="")
    response = input().strip().lower()
    
    if response == 'y':
        print("\n🚀 Running full chunking...")
        
        # Choose strategy
        print("\nChoose chunking strategy:")
        print("1. Semantic (recommended for technical content)")
        print("2. Hierarchical (blog → sections → paragraphs)")
        print("3. Fixed-size (512 tokens with overlap)")
        
        choice = input("Enter choice (1-3): ").strip()
        
        strategy_map = {"1": "semantic", "2": "hierarchical", "3": "fixed_size"}
        strategy = strategy_map.get(choice, "semantic")
        
        print(f"\n📊 Chunking all blogs using {strategy} strategy...")
        all_chunks = chunker.chunk_all_blogs(strategy=strategy)
        
        if all_chunks:
            chunker.analyze_chunks(all_chunks)
            chunker.save_chunks_to_database(all_chunks)
            print(f"\n✅ Chunking completed! Created {len(all_chunks)} chunks.")
        else:
            print("❌ No chunks created.")
    else:
        print("✅ Test completed. Use the full script to chunk all blogs.")


if __name__ == "__main__":
    test_chunking_strategies()
