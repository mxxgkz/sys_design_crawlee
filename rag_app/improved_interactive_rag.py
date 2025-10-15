#!/usr/bin/env python3
"""
Improved Interactive RAG Interface with Enhanced Answer Generation.

This module provides an interactive interface for the improved RAG system
with better context building, LLM integration, and source attribution.

Usage:
    python improved_interactive_rag.py
"""

import os
import sys
from pathlib import Path

# Use common setup to avoid path issues
from common_setup import setup_environment

from improved_rag_system import ImprovedRAGSystem


def print_welcome():
    """Print welcome message and instructions."""
    print("🤖 Improved RAG System for System Design Interview Prep")
    print("=" * 60)
    print("Ask me anything about system design, distributed systems, or software engineering!")
    print("Type 'quit', 'exit', or 'q' to stop.")
    print("Type 'help' for more commands.")
    print("=" * 60)


def print_help():
    """Print help information."""
    print("\n📋 Available Commands:")
    print("- 'help' or 'h': Show this help message")
    print("- 'quit', 'exit', or 'q': Exit the program")
    print("- 'status': Show system status")
    print("- 'sources': Show last answer sources")
    print("- Any other text: Ask a question")
    print("\n💡 Tips for better answers:")
    print("- Be specific in your questions")
    print("- Ask about specific technologies or concepts")
    print("- Use technical terms when possible")
    print("- Ask follow-up questions for deeper insights")


def print_status(rag_system):
    """Print system status."""
    print("\n🔍 System Status:")
    print(f"- OpenAI Integration: {'✅ Enabled' if rag_system.use_openai else '❌ Disabled'}")
    print(f"- Max Context Chunks: {rag_system.max_context_chunks}")
    print(f"- Context Window: {rag_system.context_window} characters")
    print(f"- Embedding Model: {rag_system.embedding_system.model_name}")
    
    if not rag_system.use_openai:
        print("\n💡 To enable enhanced answers:")
        print("   export OPENAI_API_KEY='your-key-here'")
        print("   Then restart this program")


def print_sources(sources):
    """Print sources from last answer."""
    if not sources:
        print("No sources available from last answer.")
        return
    
    print(f"\n📚 Sources ({len(sources)}):")
    print("-" * 50)
    for source in sources:
        print(f"{source['index']}. {source['title']}")
        if source['company'] != 'Unknown Company':
            print(f"   Company: {source['company']}")
        if source['url']:
            print(f"   URL: {source['url']}")
        print(f"   Relevance: {source['relevance']:.3f}")
        print(f"   Preview: {source['preview']}")
        print()


def main():
    """Main interactive loop."""
    print_welcome()
    
    # Initialize the improved RAG system
    print("\n🔄 Initializing improved RAG system...")
    try:
        rag_system = ImprovedRAGSystem()
        print("✅ Improved RAG system ready!")
        
        if not rag_system.use_openai:
            print("ℹ️  No OpenAI API key - using retrieval-only mode")
            print("   Set OPENAI_API_KEY for enhanced answers")
        
    except Exception as e:
        print(f"❌ Error initializing RAG system: {e}")
        return
    
    print("=" * 60)
    
    # Store last answer for source display
    last_sources = []
    
    # Interactive loop
    while True:
        try:
            # Get user input
            user_input = input("\n❓ Your question: ").strip()
            
            # Handle commands
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye! Thanks for using the RAG system!")
                break
            
            elif user_input.lower() in ['help', 'h']:
                print_help()
                continue
            
            elif user_input.lower() == 'status':
                print_status(rag_system)
                continue
            
            elif user_input.lower() == 'sources':
                print_sources(last_sources)
                continue
            
            elif not user_input:
                print("Please enter a question or command.")
                continue
            
            # Process question
            print(f"\n🔍 Processing: '{user_input}'")
            print("🔄 Searching for relevant information...")
            
            # Get answer from improved RAG system
            result = rag_system.answer_question(user_input)
            
            # Display answer
            print(f"\n🤖 Answer:")
            print("-" * 40)
            print(result['answer'])
            
            # Display sources
            if result['sources']:
                print(f"\n📚 Sources ({len(result['sources'])}):")
                print("-" * 40)
                for source in result['sources'][:3]:  # Show top 3 sources
                    print(f"{source['index']}. {source['title']} ({source['company']})")
                    print(f"   Relevance: {source['relevance']:.3f}")
                    if source['url']:
                        print(f"   URL: {source['url']}")
                    print()
                
                if len(result['sources']) > 3:
                    print(f"   ... and {len(result['sources']) - 3} more sources")
            
            # Store sources for later display
            last_sources = result['sources']
            
            # Show metadata
            metadata = result['metadata']
            print(f"\n📊 Answer generated using: {metadata['method']}")
            print(f"   Retrieved {metadata['chunks_retrieved']} relevant chunks")
            print(f"   Context length: {metadata['context_length']} characters")
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye! Thanks for using the RAG system!")
            break
        except Exception as e:
            print(f"\n❌ Error processing question: {e}")
            print("Please try again or type 'help' for assistance.")


if __name__ == "__main__":
    main()
