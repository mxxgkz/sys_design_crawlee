#!/usr/bin/env python3
"""
RAG System with Ollama Integration for Free LLM Models.

This module integrates free LLM models via Ollama for intelligent answer generation.
Supports models like Llama 2, Mistral, CodeLlama, and Phi-3.

Usage:
    python ollama_rag_system.py
"""

import os
import sys
import logging
import requests
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

# Use common setup to avoid path issues
from common_setup import setup_environment, get_database_path, get_vector_db_path

# Setup enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('ollama_rag_system.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

from embeddings_sentence_transformers import SentenceTransformersEmbeddingSystem


class OllamaRAGSystem:
    """RAG system with Ollama integration for free LLM models."""
    
    def __init__(self, 
                 embedding_system: Optional[SentenceTransformersEmbeddingSystem] = None,
                 model_name: str = "llama2",
                 ollama_url: str = "http://localhost:11434",
                 max_context_chunks: int = 8,
                 context_window: int = 6000):
        """
        Initialize the Ollama RAG system.
        
        Args:
            embedding_system: Pre-initialized embedding system
            model_name: Ollama model name (llama2, mistral, codellama, phi3)
            ollama_url: Ollama server URL
            max_context_chunks: Maximum number of chunks to retrieve
            context_window: Maximum context window size
        """
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.max_context_chunks = max_context_chunks
        self.context_window = context_window
        
        # Initialize embedding system
        if embedding_system:
            self.embedding_system = embedding_system
        else:
            logger.info("Initializing embedding system...")
            self.embedding_system = SentenceTransformersEmbeddingSystem()
        
        # Check Ollama availability
        self.ollama_available = self._check_ollama_availability()
        
        if self.ollama_available:
            logger.info(f"Ollama available with model: {model_name}")
        else:
            logger.warning("Ollama not available - using retrieval-only mode")
        
        logger.info("Ollama RAG System initialized successfully")
    
    def _check_ollama_availability(self) -> bool:
        """Check if Ollama is running and available."""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [model['name'] for model in models]
                if any(self.model_name in name for name in model_names):
                    return True
                else:
                    logger.warning(f"Model {self.model_name} not found. Available models: {model_names}")
                    return False
            return False
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            return False
    
    def retrieve_relevant_chunks(self, query: str, n_results: int = None) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks with improved ranking.
        
        Args:
            query: User query
            n_results: Number of results to retrieve
            
        Returns:
            List of relevant chunks with metadata
        """
        if n_results is None:
            n_results = self.max_context_chunks
        
        logger.info(f"Retrieving relevant chunks for query: '{query[:50]}...'")
        
        # Get initial results
        results = self.embedding_system.query_vectors(query, n_results * 2)
        
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
        """Enhance chunk ranking with query-specific scoring."""
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        enhanced_chunks = []
        
        for chunk in chunks:
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
            
            # Content length penalty
            length_penalty = min(len(content) / 1000, 0.1)
            
            # Enhanced score
            enhanced_score = score + keyword_bonus + title_bonus - length_penalty
            
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
        """Select chunks that fit within the context window."""
        selected_chunks = []
        current_length = 0
        
        for chunk in chunks:
            content_length = len(chunk.get('content', ''))
            
            if current_length + content_length > self.context_window:
                break
            
            selected_chunks.append(chunk)
            current_length += content_length
            
            if len(selected_chunks) >= self.max_context_chunks:
                break
        
        return selected_chunks
    
    def build_comprehensive_context(self, chunks: List[Dict[str, Any]], query: str) -> str:
        """Build comprehensive context with metadata."""
        if not chunks:
            return "No relevant information found."
        
        context_parts = []
        context_parts.append(f"Question: {query}")
        context_parts.append("")
        context_parts.append("Relevant Information:")
        context_parts.append("=" * 50)
        
        for i, chunk in enumerate(chunks, 1):
            content = chunk.get('content', '')
            metadata = chunk.get('metadata', {})
            score = chunk.get('enhanced_score', chunk.get('score', 0.0))
            
            title = metadata.get('title', 'Unknown Title')
            company = metadata.get('company', 'Unknown Company')
            url = metadata.get('url', '')
            chunk_type = metadata.get('chunk_type', 'paragraph')
            
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
    
    def generate_answer_with_ollama(self, query: str, context: str) -> str:
        """
        Generate intelligent answer using Ollama.
        
        Args:
            query: User query
            context: Retrieved context
            
        Returns:
            Generated answer
        """
        if not self.ollama_available:
            return self._generate_simple_answer(query, context)
        
        try:
            # Create a comprehensive prompt
            prompt = f"""You are an expert system design consultant. Based on the provided context from engineering blogs, provide a comprehensive answer that synthesizes information and offers practical insights.

                    Context Information:
                    {context}

                    Instructions:
                    1. Write a clear, comprehensive answer that synthesizes the information from the context
                    2. Don't just copy chunks - explain concepts in your own words and connect ideas
                    3. Provide practical insights and real-world applications
                    4. Connect different pieces of information to form a coherent response
                    5. If information is incomplete, acknowledge limitations
                    6. Focus on actionable advice and system design principles
                    7. Use specific examples from the context to illustrate points
                    8. Structure your answer with clear sections and logical flow

                    User Question: {query}

                    Please provide a comprehensive, well-structured answer that synthesizes the information:"""

            # Call Ollama API
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.8,  # Higher creativity for more generative responses
                        "top_p": 0.9,
                        "num_predict": 1200,  # More tokens for comprehensive answers (Ollama uses num_predict, not max_tokens)
                        "repeat_penalty": 1.1,  # Avoid repetition
                        "num_ctx": 4096  # Larger context window
                    }
                },
                timeout=180  # 3 minutes for first model load
            )
            
            if response.status_code == 200:
                result = response.json()
                answer = result.get('response', '').strip()
                return answer
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return self._generate_simple_answer(query, context)
                
        except Exception as e:
            logger.error(f"Error generating answer with Ollama: {e}")
            return self._generate_simple_answer(query, context)
    
    def _generate_simple_answer(self, query: str, context: str) -> str:
        """Generate a simple answer without LLM."""
        return f"""Based on the available information:

{context}

For a more comprehensive answer, you might want to ask a more specific question or provide additional context."""
    
    def answer_question(self, query: str) -> Dict[str, Any]:
        """
        Answer a question using the Ollama RAG system.
        
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
        if self.ollama_available:
            answer = self.generate_answer_with_ollama(query, context)
            method = 'ollama_enhanced'
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
                'ollama_available': self.ollama_available,
                'model_name': self.model_name
            }
        }


def main():
    """Test the Ollama RAG system."""
    print("🚀 Ollama RAG System for System Design Interview Prep")
    print("=" * 60)
    
    # Initialize the system
    rag_system = OllamaRAGSystem()
    
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
    
    print(f"\n🎉 Ollama RAG System Test Completed!")


if __name__ == "__main__":
    main()
