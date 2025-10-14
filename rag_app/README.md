# RAG Application for System Design Interview Preparation

This RAG (Retrieval-Augmented Generation) application is designed to help with system design interview preparation by categorizing and analyzing engineering blog content.

## 🎯 Overview

The application processes blog content extracted by the crawler and categorizes it by system design topics, enabling intelligent retrieval and question-answering for interview preparation.

## 📁 Project Structure

```
rag_app/
├── data_processing/
│   └── content_categorizer.py    # Content categorization system
├── models/                       # ML models and embeddings
├── utils/                        # Utility functions
├── requirements.txt              # Python dependencies
├── test_categorization.py        # Test categorization system
├── analytics.py                 # Analytics and insights
└── README.md                    # This file
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd rag_app
pip install -r requirements.txt
```

### 2. Run Content Categorization

```bash
# Test categorization on a few blogs
python test_categorization.py

# Run full categorization
python data_processing/content_categorizer.py
```

### 3. View Analytics

```bash
python analytics.py
```

## 🔧 Features

### Content Categorization

The system categorizes blog content into system design topics:

- **Distributed Systems**: Microservices, load balancing, consistency
- **Databases**: SQL/NoSQL, sharding, replication, indexing
- **Caching**: Redis, CDN, cache strategies
- **Messaging**: Kafka, pub/sub, event streaming
- **Monitoring**: Logging, metrics, tracing, observability
- **Security**: Authentication, authorization, encryption
- **Deployment**: CI/CD, Docker, Kubernetes, DevOps
- **Scalability**: Performance, throughput, optimization
- **Machine Learning**: Model training, MLOps, feature engineering
- **AI/LLM Systems**: Large language models, RAG, embeddings, transformers
- **Data Engineering**: ETL/ELT, data pipelines, data warehouses

### Categorization Methods

1. **Keyword-Based**: Fast matching using predefined topic keywords
2. **TF-IDF**: Statistical similarity to topic descriptions
3. **Hybrid**: Combines both methods with company-specific weights

### Analytics

- Topic distribution analysis
- Company-specific topic trends
- Content quality metrics
- Similar blog recommendations
- Export capabilities

## 📊 Usage Examples

### Categorize Blog Content

```python
from rag_app.data_processing.content_categorizer import BlogContentProcessor

# Initialize processor
processor = BlogContentProcessor()

# Categorize all blogs
categorized_blogs = processor.categorize_all_blogs()

# Save results
processor.save_categorized_data(categorized_blogs)
```

### Analyze Results

```python
from rag_app.analytics import BlogAnalytics

# Initialize analytics
analytics = BlogAnalytics()

# View topic distribution
analytics.topic_distribution()

# Find similar blogs
analytics.find_similar_blogs("blog_id_123", n=5)
```

## 🎯 System Design Topics

The categorization system focuses on these key system design areas:

1. **Distributed Systems**: Architecture patterns, consistency models
2. **Databases**: Data modeling, query optimization, scaling
3. **Caching**: Performance optimization, cache strategies
4. **Messaging**: Asynchronous communication, event-driven architecture
5. **Monitoring**: Observability, performance tracking
6. **Security**: Authentication, authorization, data protection
7. **Deployment**: Infrastructure, automation, DevOps
8. **Scalability**: Performance optimization, capacity planning

## 🔍 Categorization Algorithm

### Hybrid Approach

1. **Keyword Matching**: Count topic-specific keywords in content
2. **TF-IDF Similarity**: Compare content to topic descriptions
3. **Company Weights**: Apply company-specific topic preferences
4. **Score Normalization**: Normalize scores to 0-1 range
5. **Primary Topic**: Select highest-scoring topic as primary

### Company-Specific Weights

Different companies have different focus areas:

- **Netflix**: Distributed systems, caching, monitoring
- **Uber**: Messaging, databases, distributed systems
- **LinkedIn**: Databases, monitoring, scalability
- **Google**: Distributed systems, databases, scalability

## 📈 Analytics Features

### Topic Distribution
- Overall topic frequency
- Company-specific topic preferences
- Topic-company correlation matrix

### Content Quality
- Content length statistics
- Extraction method effectiveness
- Quality score distribution

### Similarity Analysis
- Find similar blogs based on topic scores
- Cosine similarity between topic vectors
- Recommendation system

## 🛠️ Configuration

### Topic Keywords

Customize topic keywords in `content_categorizer.py`:

```python
self.system_design_topics = {
    "distributed_systems": ["microservices", "load balancing", ...],
    "databases": ["SQL", "NoSQL", "sharding", ...],
    # Add more topics...
}
```

### Company Weights

Adjust company-specific weights:

```python
self.company_weights = {
    "Netflix": {"distributed_systems": 1.2, "caching": 1.1},
    # Add more companies...
}
```

## 📊 Database Schema

### blog_topics Table

```sql
CREATE TABLE blog_topics (
    blog_id TEXT PRIMARY KEY,
    primary_topic TEXT,
    topic_scores TEXT,  -- JSON string
    top_topics TEXT,    -- JSON string
    FOREIGN KEY (blog_id) REFERENCES blog_content (blog_id)
);
```

## 🚀 Next Steps

1. **Vector Embeddings**: Add semantic embeddings for better similarity
2. **LLM Integration**: Use LLMs for more sophisticated categorization
3. **RAG Pipeline**: Build retrieval system for interview questions
4. **Chat Interface**: Create interactive Q&A system
5. **Evaluation**: Add metrics for categorization accuracy

## 📝 Notes

- Requires existing blog content from the crawler
- Categorization is based on text content only (images ignored)
- Results are saved to the same database as crawler data
- Analytics can be exported to JSON for further analysis

## 🤝 Contributing

1. Add new topic categories in `content_categorizer.py`
2. Improve keyword lists for better accuracy
3. Add new analytics features in `analytics.py`
4. Enhance similarity algorithms for better recommendations
