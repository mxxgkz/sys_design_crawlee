# Quick Start Guide for Content Categorization

## 🎯 Overview

This RAG application categorizes blog content by system design topics using multiple approaches. The system is designed to work with minimal dependencies and can be extended with advanced features.

## 📁 What We've Built

### Core Files

1. **`data_processing/content_categorizer.py`** - Main categorization system
2. **`test_basic_categorization.py`** - Basic test script (no external dependencies)
3. **`test_categorization.py`** - Full test script (requires scikit-learn)
4. **`analytics.py`** - Analytics and insights
5. **`requirements.txt`** - Basic dependencies
6. **`requirements-advanced.txt`** - Advanced features (LLMs, embeddings, etc.)

### Categorization Methods

1. **Keyword-Based**: Fast matching using predefined topic keywords
2. **TF-IDF**: Statistical similarity to topic descriptions (requires scikit-learn)
3. **Hybrid**: Combines both methods with company-specific weights

### System Design Topics

- **Distributed Systems**: Microservices, load balancing, consistency
- **Databases**: SQL/NoSQL, sharding, replication, indexing
- **Caching**: Redis, CDN, cache strategies
- **Messaging**: Kafka, pub/sub, event streaming
- **Monitoring**: Logging, metrics, tracing, observability
- **Security**: Authentication, authorization, encryption
- **Deployment**: CI/CD, Docker, Kubernetes, DevOps
- **Scalability**: Performance, throughput, optimization

## 🚀 Quick Start

### Option 1: Basic Categorization (No Dependencies)

```bash
# Test basic categorization (only uses built-in Python libraries)
python rag_app/test_basic_categorization.py
```

This will:
- Extract blog content from your database
- Categorize using keyword matching only
- Save results to `blog_topics` table
- Show analytics

### Option 2: Full Categorization (With Dependencies)

```bash
# Install basic dependencies
pip install -r rag_app/requirements.txt

# Run full categorization
python rag_app/test_categorization.py
```

This will:
- Use both keyword and TF-IDF methods
- Provide more accurate categorization
- Generate detailed analytics

### Option 3: Advanced Features (Heavy Dependencies)

```bash
# Install advanced dependencies (requires torch, etc.)
pip install -r rag_app/requirements-advanced.txt

# Run with advanced features
python rag_app/data_processing/content_categorizer.py
```

## 📊 Expected Output

### Categorization Results

```
📊 Categorization Results:
==================================================

🎯 Primary Topics:
  distributed_systems: 15 blogs (30.0%)
  databases: 12 blogs (24.0%)
  caching: 8 blogs (16.0%)
  monitoring: 7 blogs (14.0%)
  messaging: 5 blogs (10.0%)
  security: 3 blogs (6.0%)

🏢 Companies:
  Netflix: 8 blogs
  Uber: 6 blogs
  LinkedIn: 5 blogs
  Google: 4 blogs
  Amazon: 3 blogs

📝 Example Categorizations:

1. Building Pinterest Canvas, a text-to-image foundation...
   Company: Pinterest
   Primary Topic: distributed_systems
   Top Topics: distributed_systems (1.00), scalability (0.75), databases (0.50)
```

### Database Schema

The system creates a `blog_topics` table:

```sql
CREATE TABLE blog_topics (
    blog_id TEXT PRIMARY KEY,
    primary_topic TEXT,
    topic_scores TEXT,  -- JSON string
    top_topics TEXT,    -- JSON string
    FOREIGN KEY (blog_id) REFERENCES blog_content (blog_id)
);
```

## 🔧 Customization

### Add New Topics

Edit `content_categorizer.py`:

```python
self.system_design_topics = {
    "new_topic": [
        "keyword1", "keyword2", "keyword3"
    ],
    # ... existing topics
}
```

### Adjust Company Weights

```python
self.company_weights = {
    "YourCompany": {"distributed_systems": 1.2, "caching": 1.1},
    # ... existing companies
}
```

### Modify Categorization Logic

The hybrid method combines keyword and TF-IDF scores:

```python
# Adjust weights
combined_score = (keyword_score * 0.4) + (tfidf_score * 0.6)
```

## 📈 Analytics

### View Results

```bash
python rag_app/analytics.py
```

### Export Data

The system exports analytics to `blog_analytics.json`:

```json
{
  "summary": {
    "total_blogs": 50,
    "unique_companies": 8,
    "unique_topics": 6,
    "avg_content_length": 2500,
    "high_quality_percentage": 85.0
  },
  "topic_distribution": {
    "distributed_systems": 15,
    "databases": 12,
    "caching": 8
  }
}
```

## 🚨 Troubleshooting

### No Blog Data Found

Make sure you have:
1. Run the crawler first
2. Blog content in `storage/blogs/`
3. Database at `storage/table_data.db`

### Import Errors

For basic functionality, only built-in Python libraries are needed:
- `sqlite3` (built-in)
- `json` (built-in)
- `pathlib` (built-in)

For advanced features, install:
```bash
pip install -r rag_app/requirements.txt
```

### Memory Issues

For large datasets, process in batches:

```python
# In test_basic_categorization.py
blog_data = processor.extract_blog_content(limit=10)  # Process 10 at a time
```

## 🎯 Next Steps

1. **Test Basic Categorization**: Run `test_basic_categorization.py`
2. **Review Results**: Check the `blog_topics` table
3. **Customize Topics**: Add your own topic keywords
4. **Scale Up**: Process more blogs or add advanced features
5. **Build RAG**: Use categorized content for question-answering

## 📝 Notes

- The system works with text content only (images are ignored)
- Results are saved to the same database as crawler data
- Categorization is based on keyword matching and TF-IDF similarity
- Company-specific weights improve accuracy for known companies
- The system is designed to be extensible and customizable

