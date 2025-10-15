#!/usr/bin/env python3
"""
RAG (Retrieval-Augmented Generation) System for System Design Interview Prep.

This module implements the complete RAG system that combines vector search
with LLM generation for intelligent question answering.

Usage:
    python rag_system.py
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Change to project root directory so database paths work correctly
os.chdir(project_root)

# Setup enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('rag_system.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

from rag_app.embeddings_sentence_transformers import SentenceTransformersEmbeddingSystem


class RAGSystem:
    """Complete RAG system for system design interview preparation."""
    
    def __init__(self, 
                 embedding_system: Optional[SentenceTransformersEmbeddingSystem] = None,
                 max_context_chunks: int = 5,
                 context_window: int = 4000):
        """
        Initialize the RAG system.
        
        Args:
            embedding_system: Pre-initialized embedding system
            max_context_chunks: Maximum number of chunks to include in context
            context_window: Maximum context window size in characters
        """
        self.max_context_chunks = max_context_chunks
        self.context_window = context_window
        
        # Initialize embedding system
        if embedding_system:
            self.embedding_system = embedding_system
        else:
            logger.info("Initializing embedding system...")
            self.embedding_system = SentenceTransformersEmbeddingSystem()
        
        logger.info("RAG System initialized successfully")
    
    def retrieve_relevant_chunks(self, query: str, n_results: int = None) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks for a given query.
        
        Args:
            query: User's question
            n_results: Number of results to retrieve (defaults to max_context_chunks)
            
        Returns:
            List of relevant chunks with metadata
        """
        if n_results is None:
            n_results = self.max_context_chunks
            
        logger.info(f"Retrieving relevant chunks for query: '{query[:50]}...'")
        
        try:
            results = self.embedding_system.query_vectors(query, n_results=n_results)
            logger.info(f"Retrieved {len(results)} relevant chunks")
            return results
        except Exception as e:
            logger.error(f"Error retrieving chunks: {e}")
            return []
    
    def build_context(self, chunks: List[Dict[str, Any]]) -> str:
        """
        Build context string from retrieved chunks.
        
        Args:
            chunks: List of relevant chunks
            
        Returns:
            Formatted context string
        """
        if not chunks:
            return "No relevant context found."
        
        context_parts = []
        current_length = 0
        
        for i, chunk in enumerate(chunks):
            # Extract chunk information
            title = chunk.get('metadata', {}).get('title', 'Unknown')
            company = chunk.get('metadata', {}).get('company', 'Unknown')
            content = chunk.get('content', '')
            score = chunk.get('score', 0.0)
            
            # Format chunk
            chunk_text = f"""
            --- Source {i+1} (Relevance: {score:.3f}) ---
            Title: {title}
            Company: {company}
            Content: {content}
            """
            
            # Check if adding this chunk would exceed context window
            if current_length + len(chunk_text) > self.context_window:
                logger.warning(f"Context window limit reached, truncating at {i} chunks")
                break
            
            context_parts.append(chunk_text)
            current_length += len(chunk_text)
        
        context = "\n".join(context_parts)
        logger.info(f"Built context with {len(context_parts)} chunks ({current_length} characters)")
        return context
    
    def generate_prompt(self, query: str, context: str) -> str:
        """
        Generate a prompt for the LLM with context and query.
        
        Args:
            query: User's question
            context: Retrieved context
            
        Returns:
            Formatted prompt for the LLM
        """
        prompt = f"""You are an expert system design interviewer and technical mentor. Use the provided context to answer the user's question about system design, distributed systems, or software engineering.

        Context:
        {context}

        Question: {query}

        Instructions:
        1. Answer based on the provided context
        2. If the context doesn't contain enough information, say so
        3. Provide practical, actionable advice
        4. Include relevant technical details
        5. Structure your answer clearly
        6. If applicable, mention the source companies or technologies

        Answer:"""
        
        return prompt
    
    def answer_question(self, query: str, use_llm: bool = False) -> Dict[str, Any]:
        """
        Answer a question using the RAG system.
        
        Args:
            query: User's question
            use_llm: Whether to use LLM generation (requires OpenAI API key)
            
        Returns:
            Dictionary with answer and metadata
        """
        logger.info(f"Processing question: '{query[:50]}...'")
        
        # Step 1: Retrieve relevant chunks
        chunks = self.retrieve_relevant_chunks(query)
        
        if not chunks:
            return {
                'answer': "I couldn't find any relevant information to answer your question.",
                'sources': [],
                'context': "",
                'method': 'retrieval_only'
            }
        
        # Step 2: Build context
        context = self.build_context(chunks)
        
        # Step 3: Generate response
        if use_llm:
            # Use LLM for generation (requires OpenAI API)
            answer = self._generate_with_llm(query, context)
            method = 'rag_with_llm'
        else:
            # Use retrieval-only approach
            answer = self._generate_retrieval_only(query, chunks)
            method = 'retrieval_only'
        
        # Prepare sources
        sources = []
        for chunk in chunks:
            sources.append({
                'title': chunk.get('metadata', {}).get('title', 'Unknown'),
                'company': chunk.get('metadata', {}).get('company', 'Unknown'),
                'relevance_score': chunk.get('score', 0.0),
                'content_preview': chunk.get('content', '')[:200] + '...'
            })
        
        result = {
            'answer': answer,
            'sources': sources,
            'context': context,
            'method': method,
            'num_sources': len(sources)
        }
        
        logger.info(f"Generated answer using {method} with {len(sources)} sources")
        return result
    
    def _generate_retrieval_only(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        """Generate answer using only retrieved chunks (no LLM)."""
        if not chunks:
            return "No relevant information found."
        
        # Find the most relevant chunk
        best_chunk = max(chunks, key=lambda x: x.get('score', 0))
        
        answer = f"""Based on the available information:

                {best_chunk.get('content', '')}

                This information comes from {best_chunk.get('metadata', {}).get('company', 'an unknown company')} and is about {best_chunk.get('metadata', {}).get('title', 'the topic')}.

                For a more comprehensive answer, you might want to ask a more specific question or provide additional context."""
        
        return answer
    
    def _generate_with_llm(self, query: str, context: str) -> str:
        """Generate answer using LLM (requires OpenAI API key)."""
        try:
            from openai import OpenAI
            
            # Check for API key
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                logger.warning("OpenAI API key not found, falling back to retrieval-only")
                return self._generate_retrieval_only(query, [])
            
            # Initialize OpenAI client
            client = OpenAI(api_key=api_key)
            
            # Generate prompt
            prompt = self.generate_prompt(query, context)
            
            # Call OpenAI API
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert system design interviewer and technical mentor."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating with LLM: {e}")
            return "Error generating answer with LLM. Please try again."
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get statistics about the RAG system."""
        try:
            stats = self.embedding_system.get_collection_stats()
            stats.update({
                'max_context_chunks': self.max_context_chunks,
                'context_window': self.context_window,
                'system_type': 'sentence_transformers_rag'
            })
            return stats
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}


def main():
    """Main function to demonstrate the RAG system."""
    print("🚀 RAG System for System Design Interview Prep")
    print("=" * 60)
    
    try:
        # Initialize RAG system
        print("🔄 Initializing RAG system...")
        rag_system = RAGSystem()
        print("✅ RAG system initialized successfully!")
        
        # Show system stats
        stats = rag_system.get_system_stats()
        print(f"\n📊 System Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        # Test questions
        test_questions = [
            "How do you design a scalable web application?",
            "What are the key principles of distributed systems?",
            "How do you handle database scaling?",
            "What is microservices architecture?",
            "How do you implement caching in a system?"
        ]
        
        print(f"\n🔍 Testing RAG system with {len(test_questions)} questions...")
        
        for i, question in enumerate(test_questions, 1):
            print(f"\n{'='*60}")
            print(f"Question {i}: {question}")
            print(f"{'='*60}")
            
            # Get answer
            result = rag_system.answer_question(question)
            
            print(f"\n📝 Answer:")
            print(result['answer'])
            
            print(f"\n📚 Sources ({result['num_sources']}):")
            for j, source in enumerate(result['sources'][:3], 1):
                print(f"  {j}. {source['title']} ({source['company']}) - Score: {source['relevance_score']:.3f}")
                print(f"     {source['content_preview']}")
        
        print(f"\n🎉 RAG System Test Completed!")
        print(f"\n📋 Next steps:")
        print(f"   1. Set OPENAI_API_KEY for LLM-powered answers")
        print(f"   2. Create interactive interface")
        print(f"   3. Add more sophisticated retrieval strategies")
        
    except Exception as e:
        print(f"❌ Error in main: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
