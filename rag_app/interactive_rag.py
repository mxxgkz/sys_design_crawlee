#!/usr/bin/env python3
"""
Interactive RAG System Interface.

This provides a command-line interface for asking questions to the RAG system.

Usage:
    python interactive_rag.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Change to project root directory
os.chdir(project_root)

from rag_app.rag_system import RAGSystem


def print_welcome():
    """Print welcome message."""
    print("🤖 RAG System for System Design Interview Prep")
    print("=" * 60)
    print("Ask me anything about system design, distributed systems, or software engineering!")
    print("Type 'quit', 'exit', or 'q' to stop.")
    print("Type 'help' for more commands.")
    print("=" * 60)


def print_help():
    """Print help message."""
    print("\n📋 Available Commands:")
    print("  help, h          - Show this help message")
    print("  stats, s         - Show system statistics")
    print("  quit, exit, q    - Exit the program")
    print("  clear, c         - Clear the screen")
    print("\n💡 Example Questions:")
    print("  - How do you design a scalable web application?")
    print("  - What are microservices?")
    print("  - How do you handle database scaling?")
    print("  - What is load balancing?")


def print_answer(result):
    """Print formatted answer."""
    print(f"\n🤖 Answer:")
    print("-" * 40)
    print(result['answer'])
    
    if result['sources']:
        print(f"\n📚 Sources ({result['num_sources']}):")
        print("-" * 40)
        for i, source in enumerate(result['sources'][:3], 1):
            print(f"{i}. {source['title']} ({source['company']})")
            print(f"   Relevance: {source['relevance_score']:.3f}")
            print(f"   Preview: {source['content_preview']}")
            print()


def main():
    """Main interactive loop."""
    print_welcome()
    
    try:
        # Initialize RAG system
        print("🔄 Initializing RAG system...")
        rag_system = RAGSystem()
        print("✅ RAG system ready!")
        
        # Check for OpenAI API key
        has_openai = bool(os.getenv('OPENAI_API_KEY'))
        if has_openai:
            print("🔑 OpenAI API key detected - LLM-powered answers available!")
        else:
            print("ℹ️  No OpenAI API key - using retrieval-only mode")
            print("   Set OPENAI_API_KEY for enhanced answers")
        
        print("\n" + "="*60)
        
        # Interactive loop
        while True:
            try:
                # Get user input
                user_input = input("\n❓ Your question: ").strip()
                
                # Handle commands
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Goodbye! Happy system design learning!")
                    break
                
                elif user_input.lower() in ['help', 'h']:
                    print_help()
                    continue
                
                elif user_input.lower() in ['stats', 's']:
                    stats = rag_system.get_system_stats()
                    print(f"\n📊 System Statistics:")
                    for key, value in stats.items():
                        print(f"  {key}: {value}")
                    continue
                
                elif user_input.lower() in ['clear', 'c']:
                    os.system('clear' if os.name == 'posix' else 'cls')
                    print_welcome()
                    continue
                
                elif not user_input:
                    print("Please enter a question or command.")
                    continue
                
                # Process question
                print(f"\n🔍 Processing: '{user_input}'")
                print("🔄 Searching for relevant information...")
                
                # Get answer (use LLM if available)
                result = rag_system.answer_question(user_input, use_llm=has_openai)
                
                # Print formatted answer
                print_answer(result)
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye! Happy system design learning!")
                break
            except Exception as e:
                print(f"\n❌ Error processing question: {e}")
                print("Please try again or type 'help' for assistance.")
    
    except Exception as e:
        print(f"❌ Error initializing RAG system: {e}")
        print("Make sure you have run the embedding setup first:")
        print("  python rag_app/test_sentence_transformers.py")


if __name__ == "__main__":
    main()
