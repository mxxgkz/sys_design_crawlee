#!/usr/bin/env python3
"""
Interactive RAG Interface with Ollama Integration.

This module provides an interactive interface for the Ollama RAG system
with free LLM models for intelligent answer generation.

Usage:
    python ollama_interactive_rag.py
"""

import os
import sys
from pathlib import Path

# Use common setup to avoid path issues
from common_setup import setup_environment

from ollama_rag_system import OllamaRAGSystem


def print_welcome():
    """Print welcome message and instructions."""
    print("🤖 Free LLM RAG System with Ollama")
    print("=" * 50)
    print("Ask me anything about system design, distributed systems, or software engineering!")
    print("Type 'quit', 'exit', or 'q' to stop.")
    print("Type 'help' for more commands.")
    print("=" * 50)


def print_help():
    """Print help information."""
    print("\n📋 Available Commands:")
    print("- 'help' or 'h': Show this help message")
    print("- 'quit', 'exit', or 'q': Exit the program")
    print("- 'status': Show system status")
    print("- 'sources': Show last answer sources")
    print("- 'models': Show available Ollama models")
    print("- Any other text: Ask a question")
    print("\n💡 Tips for better answers:")
    print("- Be specific in your questions")
    print("- Ask about specific technologies or concepts")
    print("- Use technical terms when possible")
    print("- Ask follow-up questions for deeper insights")


def print_status(rag_system):
    """Print system status."""
    print("\n🔍 System Status:")
    print(f"- Ollama Integration: {'✅ Enabled' if rag_system.ollama_available else '❌ Disabled'}")
    print(f"- Model: {rag_system.model_name}")
    print(f"- Max Context Chunks: {rag_system.max_context_chunks}")
    print(f"- Context Window: {rag_system.context_window} characters")
    print(f"- Embedding Model: {rag_system.embedding_system.model_name}")
    
    if not rag_system.ollama_available:
        print("\n💡 To enable free LLM integration:")
        print("   1. Install Ollama: curl -fsSL https://ollama.ai/install.sh | sh")
        print("   2. Start Ollama: ollama serve")
        print("   3. Download a model: ollama pull llama2")
        print("   4. Restart this program")


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


def print_models():
    """Print available Ollama models."""
    print("\n🤖 Available Ollama Models:")
    print("-" * 50)
    print("1. llama2 (7B) - Best for general RAG")
    print("2. mistral (7B) - Fast and efficient")
    print("3. codellama (7B) - Great for technical content")
    print("4. phi3 (3.8B) - Lightweight and fast")
    print("\n💡 To download a model:")
    print("   ollama pull <model-name>")
    print("\n💡 To see installed models:")
    print("   ollama list")


def main():
    """Main interactive loop."""
    print_welcome()
    
    # Initialize the Ollama RAG system
    print("\n🔄 Initializing Ollama RAG system...")
    try:
        rag_system = OllamaRAGSystem()
        print("✅ Ollama RAG system ready!")
        
        if not rag_system.ollama_available:
            print("ℹ️  Ollama not available - using retrieval-only mode")
            print("   Install Ollama for free LLM integration")
        
    except Exception as e:
        print(f"❌ Error initializing RAG system: {e}")
        return
    
    print("=" * 50)
    
    # Store last answer for source display
    last_sources = []
    
    # Interactive loop
    while True:
        try:
            # Get user input
            user_input = input("\n❓ Your question: ").strip()
            
            # Handle commands
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye! Thanks for using the free LLM RAG system!")
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
            
            elif user_input.lower() == 'models':
                print_models()
                continue
            
            elif not user_input:
                print("Please enter a question or command.")
                continue
            
            # Process question
            print(f"\n🔍 Processing: '{user_input}'")
            print("🔄 Searching for relevant information...")
            
            # Get answer from Ollama RAG system
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
            if metadata['ollama_available']:
                print(f"   LLM Model: {metadata['model_name']}")
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye! Thanks for using the free LLM RAG system!")
            break
        except Exception as e:
            print(f"\n❌ Error processing question: {e}")
            print("Please try again or type 'help' for assistance.")


if __name__ == "__main__":
    main()
