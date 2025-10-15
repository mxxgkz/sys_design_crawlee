#!/usr/bin/env python3
"""
Test script for the Sentence Transformers embedding system.

Usage:
    python test_sentence_transformers.py
"""

import sys
import logging
from pathlib import Path
import os

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Change to project root directory so database paths work correctly
os.chdir(project_root)

# Setup enhanced logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('rag_app_test.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

from rag_app.embeddings_sentence_transformers import SentenceTransformersEmbeddingSystem
from rag_app.data_processing.text_chunker import TextChunker


def test_sentence_transformers():
    """Test sentence-transformers embedding generation and similarity search."""
    print("🧪 Testing Sentence Transformers Embedding System")
    print("=" * 50)

    try:
        # Initialize embedding system
        print("🔄 Initializing embedding system...")
        embedding_system = SentenceTransformersEmbeddingSystem()
        print("✅ Embedding system initialized successfully!")
        
    except Exception as e:
        print(f"❌ Error initializing embedding system: {e}")
        return

    # Load some chunks for testing
    print("\n📊 Loading blog chunks for testing...")
    chunker = TextChunker()
    
    try:
        blog_data = chunker.load_categorized_blogs()
    except Exception as e:
        print(f"❌ Error loading blog data: {e}")
        print("\n🔧 You need to run data preparation first:")
        print("   1. Run: python rag_app/data_preparation.py")
        print("   2. Run: python rag_app/categorization.py") 
        print("   3. Run: python rag_app/test_chunking.py")
        print("   4. Then run this test again")
        return

    if not blog_data:
        print("❌ No blog data found. Make sure you have run categorization and chunking first.")
        print("\n🔧 Setup steps:")
        print("   1. Run: python rag_app/data_preparation.py")
        print("   2. Run: python rag_app/categorization.py")
        print("   3. Run: python rag_app/test_chunking.py")
        return

    # Use a small subset for testing
    test_blogs = blog_data[:1]  # Use only 1 blog for quick testing
    all_chunks = []
    
    for blog in test_blogs:
        print(f"  Processing: {blog['title'][:50]}...")
        chunks = chunker.chunk_blog(blog, strategy="semantic")
        
        # Debug logging for chunks
        logger.debug(f"Generated {len(chunks)} chunks")
        if chunks:
            logger.debug(f"First chunk type: {type(chunks[0])}")
            logger.debug(f"First chunk keys: {chunks[0].keys() if isinstance(chunks[0], dict) else 'Not a dict'}")
            logger.debug(f"First chunk content preview: {str(chunks[0])[:100]}...")
        
        all_chunks.extend(chunks)

    if not all_chunks:
        print("❌ No chunks generated for testing.")
        return

    print(f"✅ Loaded {len(all_chunks)} chunks for testing.")

    # Generate and store embeddings
    print("\n🔄 Generating and storing embeddings...")
    try:
        embedding_system.store_embeddings(all_chunks)
        print("✅ Embeddings stored in ChromaDB.")
    except Exception as e:
        print(f"❌ Error storing embeddings: {e}")
        return

    # Test similarity search
    print("\n🔍 Testing similarity search...")
    test_queries = [
        "How to scale a distributed system?",
        "Machine learning algorithms",
        "Data engineering best practices",
        "AI and LLM systems"
    ]
    
    for query in test_queries:
        print(f"\n📝 Query: '{query}'")
        results = embedding_system.query_vectors(query, n_results=3)

        if results:
            print(f"✅ Found {len(results)} similar chunks:")
            for i, res in enumerate(results):
                print(f"\n--- Result {i+1} (Score: {res['score']:.4f}) ---")
                print(f"Title: {res['metadata'].get('title', 'N/A')}")
                print(f"Company: {res['metadata'].get('company', 'N/A')}")
                print(f"Chunk Type: {res['chunk_type']}")
                print(f"Content: {res['content'][:150]}...")
        else:
            print("❌ No similar chunks found.")

    # Show collection stats
    print("\n📊 Collection Statistics:")
    stats = embedding_system.get_collection_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n🎉 Sentence Transformers Embedding System Test Completed!")


if __name__ == "__main__":
    test_sentence_transformers()
