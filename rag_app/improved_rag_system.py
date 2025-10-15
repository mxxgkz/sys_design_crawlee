#!/usr/bin/env python3
"""
Improved RAG System with Better Context Building and LLM Integration.

This module implements an enhanced RAG system that:
1. Retrieves relevant chunks with better ranking
2. Builds comprehensive context with metadata
3. Integrates with OpenAI for intelligent answer generation
4. Provides proper source attribution

Usage:
    python improved_rag_system.py
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import re

# Use common setup to avoid path issues
from common_setup import setup_environment, get_database_path, get_vector_db_path

# Setup enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('improved_rag_system.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

from embeddings_sentence_transformers import SentenceTransformersEmbeddingSystem

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI not available. Install with: pip install openai")


class ImprovedRAGSystem:
    """Enhanced RAG system with better context building and LLM integration."""
    
    def __init__(self, 
                 embedding_system: Optional[SentenceTransformersEmbeddingSystem] = None,
                 max_context_chunks: int = 8,
                 context_window: int = 6000,
                 use_openai: bool = True):
        """
        Initialize the improved RAG system.
        
        Args:
            embedding_system: Pre-initialized embedding system
            max_context_chunks: Maximum number of chunks to retrieve
            context_window: Maximum context window size
            use_openai: Whether to use OpenAI for answer generation
        """
        self.max_context_chunks = max_context_chunks
        self.context_window = context_window
        self.use_openai = use_openai and OPENAI_AVAILABLE
        
        # Initialize embedding system
        if embedding_system:
            self.embedding_system = embedding_system
        else:
            logger.info("Initializing embedding system...")
            self.embedding_system = SentenceTransformersEmbeddingSystem()
        
        # Initialize OpenAI if available
        if self.use_openai:
            api_key = os.getenv('OPENAI_API_KEY')
            if api_key:
                openai.api_key = api_key
                logger.info("OpenAI API key found - enhanced answers enabled")
            else:
                logger.warning("No OpenAI API key found - using retrieval-only mode")
                self.use_openai = False
        
        logger.info("Improved RAG System initialized successfully")
    
    def retrieve_relevant_chunks(self, query: str, n_results: int = None) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks with improved ranking and filtering.
        
        Args:
            query: User query
            n_results: Number of results to retrieve (defaults to max_context_chunks)
            
        Returns:
            List of relevant chunks with metadata
        """
        if n_results is None:
            n_results = self.max_context_chunks
        
        logger.info(f"Retrieving relevant chunks for query: '{query[:50]}...'")
        
        # Get initial results
        results = self.embedding_system.query_vectors(query, n_results * 2)  # Get more for filtering
        
        if not results:
            logger.warning("No relevant chunks found")
            return []
        
        # Enhanced ranking and filtering
        improved_results = self._enhance_chunk_ranking(results, query)
        
        # Select top chunks that fit context window
        selected_chunks = self._select_chunks_for_context(improved_results)
        
        logger.info(f"Retrieved {len(selected_chunks)} relevant chunks")
        return selected_chunks
    
    def _enhance_chunk_ranking(self, chunks: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """
        Enhance chunk ranking with query-specific scoring.
        
        Args:
            chunks: Retrieved chunks
            query: User query
            
        Returns:
            Enhanced and ranked chunks
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        enhanced_chunks = []
        
        for chunk in chunks:
            # Extract content and metadata
            content = chunk.get('content', '')
            metadata = chunk.get('metadata', {})
            score = chunk.get('score', 0.0)
            
            # Calculate additional relevance factors
            content_lower = content.lower()
            
            # Keyword matching bonus
            keyword_matches = sum(1 for word in query_words if word in content_lower)
            keyword_bonus = keyword_matches / len(query_words) * 0.1
            
            # Title relevance bonus
            title = metadata.get('title', '')
            title_matches = sum(1 for word in query_words if word in title.lower())
            title_bonus = title_matches / len(query_words) * 0.2
            
            # Content length penalty (prefer concise, relevant chunks)
            length_penalty = min(len(content) / 1000, 0.1)  # Penalty for very long chunks
            
            # Enhanced score
            enhanced_score = score + keyword_bonus + title_bonus - length_penalty
            
            # Add enhanced metadata
            enhanced_chunk = {
                **chunk,
                'enhanced_score': enhanced_score,
                'keyword_matches': keyword_matches,
                'title_matches': title_matches,
                'content_length': len(content)
            }
            
            enhanced_chunks.append(enhanced_chunk)
        
        # Sort by enhanced score
        enhanced_chunks.sort(key=lambda x: x['enhanced_score'], reverse=True)
        
        return enhanced_chunks
    
    def _select_chunks_for_context(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Select chunks that fit within the context window.
        
        Args:
            chunks: Ranked chunks
            
        Returns:
            Selected chunks for context
        """
        selected_chunks = []
        current_length = 0
        
        for chunk in chunks:
            content_length = len(chunk.get('content', ''))
            
            # Check if adding this chunk would exceed context window
            if current_length + content_length > self.context_window:
                break
            
            selected_chunks.append(chunk)
            current_length += content_length
            
            # Stop if we have enough chunks
            if len(selected_chunks) >= self.max_context_chunks:
                break
        
        return selected_chunks
    
    def build_comprehensive_context(self, chunks: List[Dict[str, Any]], query: str) -> str:
        """
        Build comprehensive context with metadata and source information.
        
        Args:
            chunks: Selected chunks
            query: User query
            
        Returns:
            Formatted context string
        """
        if not chunks:
            return "No relevant information found."
        
        context_parts = []
        
        # Add query context
        context_parts.append(f"Question: {query}")
        context_parts.append("")
        context_parts.append("Relevant Information:")
        context_parts.append("=" * 50)
        
        # Add each chunk with proper attribution
        for i, chunk in enumerate(chunks, 1):
            content = chunk.get('content', '')
            metadata = chunk.get('metadata', {})
            score = chunk.get('enhanced_score', chunk.get('score', 0.0))
            
            # Extract source information
            title = metadata.get('title', 'Unknown Title')
            company = metadata.get('company', 'Unknown Company')
            url = metadata.get('url', '')
            chunk_type = metadata.get('chunk_type', 'paragraph')
            
            # Format source attribution
            source_info = f"Source {i}: {title}"
            if company and company != 'Unknown Company':
                source_info += f" ({company})"
            if url:
                source_info += f" - {url}"
            
            context_parts.append(f"[{i}] {source_info}")
            context_parts.append(f"Relevance: {score:.3f} | Type: {chunk_type}")
            context_parts.append("")
            context_parts.append(content)
            context_parts.append("")
            context_parts.append("-" * 30)
            context_parts.append("")
        
        return "\n".join(context_parts)
    
    def generate_answer_with_llm(self, query: str, context: str) -> str:
        """
        Generate intelligent answer using OpenAI.
        
        Args:
            query: User query
            context: Retrieved context
            
        Returns:
            Generated answer
        """
        if not self.use_openai:
            return self._generate_simple_answer(query, context)
        
        try:
            # Create a comprehensive prompt
            prompt = f"""You are an expert system design consultant with access to a comprehensive knowledge base of engineering blog posts from top tech companies.

                    Context Information:
                    {context}

                    Instructions:
                    1. Answer the user's question based on the provided context
                    2. Synthesize information from multiple sources when relevant
                    3. Provide specific examples and practical insights
                    4. If the context doesn't contain enough information, say so clearly
                    5. Focus on actionable advice and real-world applications
                    6. Cite specific sources when making claims

                    User Question: {query}

                    Please provide a comprehensive, well-structured answer:"""

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert system design consultant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            answer = response.choices[0].message.content.strip()
            return answer
            
        except Exception as e:
            logger.error(f"Error generating answer with OpenAI: {e}")
            return self._generate_simple_answer(query, context)
    
    def _generate_simple_answer(self, query: str, context: str) -> str:
        """
        Generate a simple answer without LLM.
        
        Args:
            query: User query
            context: Retrieved context
            
        Returns:
            Simple answer
        """
        return f"""Based on the available information:

                {context}

                For a more comprehensive answer, you might want to ask a more specific question or provide additional context."""
    
    def answer_question(self, query: str) -> Dict[str, Any]:
        """
        Answer a question using the improved RAG system.
        
        Args:
            query: User question
            
        Returns:
            Dictionary with answer, sources, and metadata
        """
        logger.info(f"Processing question: '{query[:50]}...'")
        
        # Step 1: Retrieve relevant chunks
        chunks = self.retrieve_relevant_chunks(query)
        
        if not chunks:
            return {
                'answer': "I couldn't find relevant information to answer your question.",
                'sources': [],
                'metadata': {'chunks_retrieved': 0, 'method': 'no_results'}
            }
        
        # Step 2: Build comprehensive context
        context = self.build_comprehensive_context(chunks, query)
        
        # Step 3: Generate answer
        if self.use_openai:
            answer = self.generate_answer_with_llm(query, context)
            method = 'llm_enhanced'
        else:
            answer = self._generate_simple_answer(query, context)
            method = 'retrieval_only'
        
        # Step 4: Prepare sources
        sources = []
        for i, chunk in enumerate(chunks, 1):
            metadata = chunk.get('metadata', {})
            sources.append({
                'index': i,
                'title': metadata.get('title', 'Unknown Title'),
                'company': metadata.get('company', 'Unknown Company'),
                'url': metadata.get('url', ''),
                'relevance': chunk.get('enhanced_score', chunk.get('score', 0.0)),
                'preview': chunk.get('content', '')[:200] + '...'
            })
        
        return {
            'answer': answer,
            'sources': sources,
            'metadata': {
                'chunks_retrieved': len(chunks),
                'method': method,
                'context_length': len(context),
                'use_openai': self.use_openai
            }
        }


def main():
    """Test the improved RAG system."""
    print("🚀 Improved RAG System for System Design Interview Prep")
    print("=" * 60)
    
    # Initialize the system
    rag_system = ImprovedRAGSystem()
    
    # Test questions
    test_questions = [
        "How do you handle database scaling?",
        "What is microservices architecture?",
        "How do you implement caching in a system?",
        "What are the best practices for system design?",
        "How do companies integrate LLMs into their systems?"
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n{'='*60}")
        print(f"Question {i}: {question}")
        print('='*60)
        
        result = rag_system.answer_question(question)
        
        print(f"\n🤖 Answer:")
        print("-" * 40)
        print(result['answer'])
        
        print(f"\n📚 Sources ({len(result['sources'])}):")
        print("-" * 40)
        for source in result['sources']:
            print(f"{source['index']}. {source['title']} ({source['company']})")
            print(f"   Relevance: {source['relevance']:.3f}")
            print(f"   Preview: {source['preview']}")
            print()
        
        print(f"📊 Metadata: {result['metadata']}")
    
    print(f"\n🎉 Improved RAG System Test Completed!")


if __name__ == "__main__":
    main()
