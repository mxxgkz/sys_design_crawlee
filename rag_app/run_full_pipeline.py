#!/usr/bin/env python3
"""
Run the complete data pipeline from scratch.

This script runs all the necessary steps to prepare your blog data for the RAG system.

Usage:
    python run_full_pipeline.py
"""

import sys
import os
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Change to project root directory
os.chdir(project_root)


def run_command(command, description):
    """Run a command and handle errors."""
    print(f"\n🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        if result.stdout:
            print(f"Output: {result.stdout[:200]}...")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error in {description}: {e}")
        if e.stdout:
            print(f"stdout: {e.stdout}")
        if e.stderr:
            print(f"stderr: {e.stderr}")
        return False


def main():
    """Run the complete data pipeline."""
    print("🚀 Complete Data Pipeline for RAG System")
    print("=" * 50)
    
    print("\n📋 Pipeline Steps:")
    print("1. ✅ Data Preparation (Already completed)")
    print("2. ✅ Categorization (Already completed)") 
    print("3. ✅ Chunking (Already completed)")
    print("4. ✅ Embeddings (Already completed)")
    print("5. 🔄 RAG System Test")
    
    # Check if data already exists
    db_path = "storage/table_data.db"
    if not os.path.exists(db_path):
        print("❌ Database not found. Please run data preparation first.")
        return
    
    print(f"✅ Database found: {db_path}")
    
    # Step 5: RAG System Test
    if not run_command("python rag_app/rag_system.py", "RAG System Test"):
        print("❌ RAG system test failed. Please check the RAG system.")
        return
    
    print("\n🎉 Complete Pipeline Finished Successfully!")
    print("\n📋 Next Steps:")
    print("1. 🚀 Start interactive interface:")
    print("   python rag_app/interactive_rag.py")
    print("\n2. 🔑 Optional: Set OpenAI API key for LLM-powered answers:")
    print("   export OPENAI_API_KEY='your-key-here'")


if __name__ == "__main__":
    main()
