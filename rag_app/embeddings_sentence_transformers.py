#!/usr/bin/env python3
"""
Sentence Transformers Embedding System for RAG App.

This module provides embedding generation and vector storage using sentence-transformers
and ChromaDB for the RAG application.

Usage:
    python embeddings_sentence_transformers.py
"""
import sys
import logging
from typing import List, Dict, Any, Optional
import numpy as np
from tqdm import tqdm

# Use common setup to avoid path issues
from rag_app.common_setup import setup_environment, get_database_path, get_vector_db_path

# Setup enhanced logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('rag_app_embeddings.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from rag_app.data_processing.text_chunker import TextChunker


class SentenceTransformersEmbeddingSystem:
    """Embedding system using sentence-transformers and ChromaDB."""
    
    def __init__(self,
                 model_name: str = "all-MiniLM-L6-v2",
                 db_path: str = None,
                 vector_db_path: str = None,
                 collection_name: str = "blog_chunks"):
        """
        Initialize the embedding system.
        
        Args:
            model_name: Sentence transformer model name
            db_path: Path to SQLite database
            vector_db_path: Path to ChromaDB storage
            collection_name: Name of the ChromaDB collection
        """
        self.model_name = model_name
        self.db_path = db_path or str(get_database_path())
        self.vector_db_path = vector_db_path or str(get_vector_db_path())
        self.collection_name = collection_name
        
        # Initialize sentence transformer model
        print(f"🔄 Loading sentence transformer model: {model_name}")
        self.model = SentenceTransformer(model_name)
        print(f"✅ Model loaded successfully!")
        
        # Initialize ChromaDB
        print(f"🔄 Initializing ChromaDB...")
        self.client = chromadb.PersistentClient(
            path=vector_db_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Create or get collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        print(f"✅ ChromaDB initialized with collection: {collection_name}")
    
    def generate_embeddings(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            batch_size: Batch size for processing
            
        Returns:
            List of embedding vectors
        """
        print(f"🔄 Generating embeddings for {len(texts)} texts...")
        
        embeddings = []
        for i in tqdm(range(0, len(texts), batch_size), desc="Generating embeddings"):
            batch_texts = texts[i:i + batch_size]
            try:
                batch_embeddings = self.model.encode(
                    batch_texts,
                    convert_to_tensor=False,
                    show_progress_bar=False
                )
                embeddings.extend(batch_embeddings.tolist())
            except Exception as e:
                print(f"❌ Error generating embeddings for batch {i//batch_size + 1}: {e}")
                # Add zero embeddings as fallback
                embedding_dim = self.model.get_sentence_embedding_dimension()
                embeddings.extend([[0.0] * embedding_dim for _ in batch_texts])
        
        print(f"✅ Generated {len(embeddings)} embeddings")
        return embeddings
    
    def store_embeddings(self, chunks: List[Dict[str, Any]], batch_size: int = 1000) -> None:
        """
        Store chunks and their embeddings in ChromaDB with batch processing.

        Args:
            chunks: List of chunk dictionaries with content and metadata
            batch_size: Maximum number of chunks to process at once
        """
        logger.info(f"Storing {len(chunks)} chunks in ChromaDB with batch size {batch_size}...")

        try:
            # Extract texts and metadata with detailed logging
            texts = []
            metadatas = []
            ids = []

            for i, chunk in enumerate(chunks):
                logger.debug(f"Processing chunk {i}: {type(chunk)}")

                # Handle different chunk formats
                if isinstance(chunk, dict):
                    # Handle dictionary chunks
                    content = chunk.get('content', '')
                    title = chunk.get('title', '')
                    company = chunk.get('company', '')
                    url = chunk.get('url', '')
                    chunk_type = chunk.get('chunk_type', '')
                    topic = chunk.get('topic', '')
                else:
                    # Handle TextChunk objects
                    try:
                        content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                        title = chunk.title if hasattr(chunk, 'title') else ''
                        company = chunk.company if hasattr(chunk, 'company') else ''
                        url = chunk.url if hasattr(chunk, 'url') else ''
                        chunk_type = chunk.chunk_type if hasattr(chunk, 'chunk_type') else ''
                        topic = chunk.topic if hasattr(chunk, 'topic') else ''
                    except Exception as e:
                        logger.error(f"Error accessing chunk {i} attributes: {e}")
                        continue

                if not content:
                    logger.warning(f"Chunk {i} has no content, skipping")
                    continue

                texts.append(content)

                metadata = {
                    'title': title,
                    'company': company,
                    'url': url,
                    'chunk_type': chunk_type,
                    'chunk_index': i,
                    'topic': topic,
                    'chunk_size': len(content)
                }
                metadatas.append(metadata)
                ids.append(f"chunk_{i}")

            logger.info(f"Extracted {len(texts)} texts for embedding")

            if not texts:
                logger.warning("No valid texts found for embedding")
                return

            # Process in batches to avoid ChromaDB batch size limits
            total_batches = (len(texts) + batch_size - 1) // batch_size
            logger.info(f"Processing {len(texts)} chunks in {total_batches} batches of {batch_size}")

            for batch_idx in range(0, len(texts), batch_size):
                batch_end = min(batch_idx + batch_size, len(texts))
                batch_texts = texts[batch_idx:batch_end]
                batch_metadatas = metadatas[batch_idx:batch_end]
                batch_ids = ids[batch_idx:batch_end]
                
                logger.info(f"Processing batch {batch_idx//batch_size + 1}/{total_batches} ({len(batch_texts)} chunks)")
                
                # Generate embeddings for this batch
                batch_embeddings = self.generate_embeddings(batch_texts)
                
                # Store this batch in ChromaDB
                self.collection.add(
                    embeddings=batch_embeddings,
                    documents=batch_texts,
                    metadatas=batch_metadatas,
                    ids=batch_ids
                )
                logger.info(f"Successfully stored batch {batch_idx//batch_size + 1}/{total_batches}")

            logger.info(f"Successfully stored all {len(texts)} chunks in ChromaDB")

        except Exception as e:
            logger.error(f"Error storing embeddings: {e}", exc_info=True)
            raise
    
    def query_vectors(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Query the vector database for similar chunks.
        
        Args:
            query: Query string
            n_results: Number of results to return
            
        Returns:
            List of similar chunks with scores
        """
        print(f"🔍 Querying: '{query}'")
        
        try:
            # Generate query embedding
            query_embedding = self.model.encode([query], convert_to_tensor=False)
            
            # Query ChromaDB
            results = self.collection.query(
                query_embeddings=query_embedding.tolist(),
                n_results=n_results
            )
            
            # Format results
            formatted_results = []
            if results['documents'] and results['documents'][0]:
                for i in range(len(results['documents'][0])):
                    result = {
                        'content': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'score': 1 - results['distances'][0][i],  # Convert distance to similarity
                        'chunk_type': results['metadatas'][0][i].get('chunk_type', ''),
                        'title': results['metadatas'][0][i].get('title', ''),
                        'company': results['metadatas'][0][i].get('company', '')
                    }
                    formatted_results.append(result)
            
            print(f"✅ Found {len(formatted_results)} similar chunks")
            return formatted_results
            
        except Exception as e:
            print(f"❌ Error querying vectors: {e}")
            return []
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection."""
        try:
            count = self.collection.count()
            return {
                'total_chunks': count,
                'model_name': self.model_name,
                'collection_name': self.collection_name
            }
        except Exception as e:
            print(f"❌ Error getting collection stats: {e}")
            return {}


def main():
    """Main function to demonstrate the embedding system."""
    print("🚀 Sentence Transformers Embedding System")
    print("=" * 50)
    
    try:
        # Initialize embedding system
        embedding_system = SentenceTransformersEmbeddingSystem()
        
        # Load blog chunks
        print("\n📊 Loading blog chunks...")
        chunker = TextChunker()
        blog_data = chunker.load_categorized_blogs()
        
        if not blog_data:
            print("❌ No blog data found. Please run data preparation and chunking first.")
            return
        
        print(f"✅ Loaded {len(blog_data)} blogs")
        
        # Generate chunks for a few blogs (for testing)
        print("\n🔄 Generating chunks for testing...")
        test_blogs = blog_data[:2]  # Use first 2 blogs for testing
        all_chunks = []
        
        for i, blog in enumerate(test_blogs):
            print(f"  Processing blog {i+1}: {blog['title'][:50]}...")
            chunks = chunker.chunk_blog(blog, strategy="semantic")
            all_chunks.extend(chunks)
        
        if not all_chunks:
            print("❌ No chunks generated.")
            return
        
        print(f"✅ Generated {len(all_chunks)} chunks")
        
        # Store embeddings
        print("\n🔄 Storing embeddings...")
        embedding_system.store_embeddings(all_chunks)
        
        # Test query
        print("\n🔍 Testing similarity search...")
        query = "How to scale distributed systems?"
        results = embedding_system.query_vectors(query, n_results=3)
        
        if results:
            print(f"\n📋 Query Results for: '{query}'")
            for i, result in enumerate(results):
                print(f"\n--- Result {i+1} (Score: {result['score']:.4f}) ---")
                print(f"Title: {result['title']}")
                print(f"Company: {result['company']}")
                print(f"Content: {result['content'][:200]}...")
        else:
            print("❌ No results found")
        
        # Show collection stats
        stats = embedding_system.get_collection_stats()
        print(f"\n📊 Collection Stats:")
        print(f"  Total chunks: {stats.get('total_chunks', 0)}")
        print(f"  Model: {stats.get('model_name', 'N/A')}")
        
        print("\n🎉 Sentence Transformers Embedding System Test Completed!")
        
    except Exception as e:
        print(f"❌ Error in main: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
