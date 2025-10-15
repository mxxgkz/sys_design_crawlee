#!/usr/bin/env python3
"""
Setup script for the Sentence Transformers embedding system.
Generates embeddings and runs tests.

Usage:
    python setup_sentence_transformers.py
"""

import sys
from pathlib import Path
import os

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rag_app.embeddings_sentence_transformers import SentenceTransformersEmbeddingSystem
from rag_app.data_processing.text_chunker import TextChunker
from rag_app.test_sentence_transformers import test_sentence_transformers


def main():
    """Main function to run the sentence-transformers embedding setup."""
    print("🚀 RAG App - Sentence Transformers Embedding System Setup")
    print("=" * 60)

    # Check if we're in the right environment
    try:
        from sentence_transformers import SentenceTransformer
        print("✅ Sentence transformers is available")
    except ImportError:
        print("❌ Sentence transformers not found. Please activate the rag_app environment:")
        print("   conda activate rag_app")
        return

    try:
        import chromadb
        print("✅ ChromaDB is available")
    except ImportError:
        print("❌ ChromaDB not found. Please install it:")
        print("   pip install chromadb")
        return

    # Generate and store embeddings
    print("\n🔄 Initializing embedding system and generating embeddings...")
    try:
        embedding_system = SentenceTransformersEmbeddingSystem()
        chunker = TextChunker()
        all_blogs = chunker.load_categorized_blogs()

        if not all_blogs:
            print("❌ No blog data found. Please ensure data preparation and chunking are complete.")
            return

        # Chunk all blogs using semantic strategy
        print(f"📊 Chunking {len(all_blogs)} blogs for embedding...")
        all_chunks = []
        for i, blog in enumerate(all_blogs):
            print(f"  Processing blog {i+1}/{len(all_blogs)}: {blog['title'][:50]}...")
            chunks = chunker.chunk_blog(blog, strategy="semantic")
            all_chunks.extend(chunks)

        if not all_chunks:
            print("❌ No chunks generated for embedding.")
            return

        print(f"✅ Total {len(all_chunks)} chunks generated.")
        
        # Store embeddings
        print("\n🔄 Storing embeddings in ChromaDB...")
        embedding_system.store_embeddings(all_chunks)
        print("✅ All embeddings generated and stored in ChromaDB.")

        # Show collection stats
        stats = embedding_system.get_collection_stats()
        print(f"\n📊 Collection Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

    except Exception as e:
        print(f"❌ Error during embedding generation: {e}")
        import traceback
        traceback.print_exc()
        return

    # Run tests
    print("\n🔄 Running embedding system tests...")
    test_sentence_transformers()

    print("\n🎉 Sentence Transformers Embedding System Setup Completed!")
    print("\n📋 Next steps:")
    print("   1. Test queries: python rag_app/test_sentence_transformers.py")
    print("   2. Move to Phase 3: RAG System Architecture")


if __name__ == "__main__":
    main()
