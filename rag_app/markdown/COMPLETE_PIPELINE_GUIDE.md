# Complete RAG Pipeline Guide
**Date:** October 14, 2025  
**Status:** ✅ Complete - End-to-End RAG System

## 🎯 Overview

This guide covers the complete pipeline from data collection to running an interactive RAG system with LLM integration. The system processes engineering blogs, creates vector embeddings, and provides intelligent question-answering capabilities.

## 📋 Complete Pipeline Steps

### Phase 1: Data Collection & Processing
1. **Blog Crawling** - Extract content from engineering blogs
2. **Content Categorization** - AI-powered topic classification
3. **Text Chunking** - Break content into semantic chunks
4. **Vector Embeddings** - Create embeddings for similarity search

### Phase 2: RAG System Setup
5. **Vector Database** - Store embeddings in ChromaDB
6. **LLM Integration** - Set up OpenAI or Ollama models
7. **Interactive Interface** - Command-line RAG system

## 🚀 Quick Start - Complete Pipeline

### Prerequisites
```bash
# Ensure you're in the project root
cd /path/to/sys_design_crawlee

# Check if you have blog data
ls storage/table_data.db
```

### Step 1: Data Collection (If Not Done)
```bash
# Run the crawler to collect blog data
python test_scripts/test_full_crawler.py --max-blogs 50

# This will:
# - Extract blog URLs from main pages
# - Process individual blog posts
# - Save content to storage/blogs/
# - Store metadata in storage/table_data.db
```

### Step 2: Content Categorization
```bash
# Categorize blog content by topics
python rag_app/data_processing/content_categorizer.py

# This will:
# - Analyze blog content
# - Assign topics (AI/ML, Data Engineering, System Design)
# - Save results to blog_categories table
```

### Step 3: Text Chunking
```bash
# Create semantic chunks from blog content
python rag_app/data_processing/text_chunker.py

# This will:
# - Break content into semantic chunks
# - Apply different chunking strategies
# - Save chunks for embedding generation
```

### Step 4: Vector Embeddings Setup
```bash
# Set up Python 3.11 environment for sentence-transformers
conda create -n rag_app python=3.11
conda activate rag_app
pip install -r rag_app/requirements-py311.txt

# Generate embeddings
python rag_app/embeddings_sentence_transformers.py

# This will:
# - Load sentence-transformers model
# - Generate embeddings for all chunks
# - Store in ChromaDB vector database
```

### Step 5: RAG System Setup

#### Option A: Free LLM with Ollama
```bash
# Terminal 1: Start Ollama server
ollama serve

# Terminal 2: Pull a model
ollama pull llama2

# Run Ollama RAG system
python rag_app/ollama_interactive_rag.py
```

#### Option B: OpenAI API
```bash
# Set OpenAI API key
export OPENAI_API_KEY='your-key-here'

# Run OpenAI RAG system
python rag_app/improved_interactive_rag.py
```

## 🔧 Detailed Setup Instructions

### 1. Environment Setup

#### For Sentence Transformers (Required for Embeddings)
```bash
# Create Python 3.11 environment
conda create -n rag_app python=3.11
conda activate rag_app

# Install dependencies
pip install -r rag_app/requirements-py311.txt

# Fix NumPy compatibility (if needed)
bash rag_app/fix_numpy_warnings.sh
```

#### For OpenAI Integration (Optional)
```bash
# Install OpenAI dependencies
pip install openai

# Set API key
export OPENAI_API_KEY='your-openai-api-key'
```

#### For Ollama Integration (Free Alternative)
```bash
# Install Ollama (macOS)
brew install ollama

# Or download from: https://ollama.ai/download

# Pull a model
ollama pull llama2
# or
ollama pull mistral
```

### 2. Data Pipeline Execution

#### Complete Data Processing
```bash
# Run the complete pipeline
python rag_app/run_full_pipeline.py

# This script will:
# - Check for existing data
# - Run categorization if needed
# - Generate embeddings
# - Test the RAG system
```

#### Individual Steps
```bash
# Step 1: Categorization
python rag_app/data_processing/content_categorizer.py

# Step 2: Chunking
python rag_app/data_processing/text_chunker.py

# Step 3: Embeddings
python rag_app/embeddings_sentence_transformers.py

# Step 4: Test RAG
python rag_app/ollama_rag_system.py
```

### 3. RAG System Usage

#### Interactive Ollama RAG
```bash
# Start Ollama server (Terminal 1)
ollama serve

# Run interactive RAG (Terminal 2)
python rag_app/ollama_interactive_rag.py

# Example questions:
# - "How does Google's search ranking algorithm work?"
# - "What are the key principles of distributed systems?"
# - "How do companies handle machine learning at scale?"
```

#### Interactive OpenAI RAG
```bash
# Set API key
export OPENAI_API_KEY='your-key-here'

# Run interactive RAG
python rag_app/improved_interactive_rag.py
```

## 📊 Expected Results

### Data Processing Output
```
📊 Categorization Results:
  Total blogs: 100+
  Topics: AI/ML (40%), Data Engineering (35%), System Design (25%)
  
📊 Chunking Results:
  Total chunks: 11,573+
  Average chunk size: 474 characters
  
📊 Embeddings Results:
  Vector database: ChromaDB
  Embedding dimensions: 384
  Model: all-MiniLM-L6-v2
```

### RAG System Output
```
🤖 Answer:
----------------------------------------
Based on the provided engineering blogs, we can identify several key takeaways regarding business use cases and their development.

Firstly, there are various business use cases that have been built for different industries and purposes...

📚 Sources (8):
----------------------------------------
1. Google Search Ranking (Google)
   Relevance: 0.615
2. Netflix Microservices (Netflix)
   Relevance: 0.468
   ... and 6 more sources
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. Database Path Errors
```bash
# Ensure you're in the project root
pwd
# Should show: /path/to/sys_design_crawlee

# Check database exists
ls storage/table_data.db
```

#### 2. Python Environment Issues
```bash
# Activate correct environment
conda activate rag_app

# Check Python version
python --version
# Should show: Python 3.11.x
```

#### 3. Ollama Connection Issues
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if needed
ollama serve
```

#### 4. Missing Dependencies
```bash
# Install missing packages
pip install -r rag_app/requirements-py311.txt

# For OpenAI
pip install openai
```

### Performance Optimization

#### Large Dataset Handling
```bash
# Process in batches
python rag_app/embeddings_sentence_transformers.py --batch-size 500

# Use timeout for chunking
python rag_app/test_chunking.py --timeout 60
```

#### Memory Management
```bash
# Monitor memory usage
python rag_app/embeddings_sentence_transformers.py --batch-size 1000

# Use smaller models if needed
# Change model in embeddings_sentence_transformers.py
```

## 📈 Performance Metrics

### System Performance
- **Blog Processing**: ~100 blogs in 10 minutes
- **Chunking**: 11,573+ chunks in 5 minutes
- **Embeddings**: 11,573+ embeddings in 15 minutes
- **Query Response**: <2 seconds per question

### Resource Usage
- **Database Size**: ~50MB SQLite + ~200MB ChromaDB
- **Memory Usage**: ~2GB for embeddings generation
- **Storage**: ~500MB total (including models)

## 🎯 Example Workflow

### Complete End-to-End Example
```bash
# 1. Start fresh
conda activate rag_app
cd /path/to/sys_design_crawlee

# 2. Collect data (if needed)
python test_scripts/test_full_crawler.py --max-blogs 20

# 3. Process data
python rag_app/data_processing/content_categorizer.py
python rag_app/data_processing/text_chunker.py
python rag_app/embeddings_sentence_transformers.py

# 4. Start Ollama (Terminal 1)
ollama serve

# 5. Run RAG system (Terminal 2)
python rag_app/ollama_interactive_rag.py

# 6. Ask questions
# "How do companies design scalable systems?"
# "What are the challenges in machine learning at scale?"
# "How does Google handle search ranking?"
```

## 📝 Next Steps

### Immediate Actions
1. **Test the System**: Run through the complete pipeline
2. **Ask Questions**: Try different types of system design questions
3. **Evaluate Results**: Check answer quality and source attribution

### Future Enhancements
1. **Add More Content**: Crawl additional engineering blogs
2. **Improve Models**: Try different embedding models or LLMs
3. **Add Features**: Conversation memory, web interface
4. **Optimize Performance**: Caching, batch processing

## 🔗 Key Files

### Core Pipeline
- `test_scripts/test_full_crawler.py` - Data collection
- `rag_app/data_processing/content_categorizer.py` - Categorization
- `rag_app/data_processing/text_chunker.py` - Text chunking
- `rag_app/embeddings_sentence_transformers.py` - Embeddings

### RAG System
- `rag_app/ollama_rag_system.py` - Ollama RAG system
- `rag_app/ollama_interactive_rag.py` - Interactive Ollama interface
- `rag_app/improved_rag_system.py` - OpenAI RAG system
- `rag_app/improved_interactive_rag.py` - Interactive OpenAI interface

### Utilities
- `rag_app/common_setup.py` - Path resolution
- `rag_app/run_full_pipeline.py` - Complete pipeline runner

---

**🎉 Congratulations!** You now have a complete RAG system for system design interview preparation!
