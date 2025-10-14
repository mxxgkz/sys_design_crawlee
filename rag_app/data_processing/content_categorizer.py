"""
Content Categorization System for System Design Blog Posts

This module provides various approaches to categorize blog content by system design topics.
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class ContentCategorizer:
    """
    Categorizes blog content by system design topics using multiple approaches.
    """
    
    def __init__(self):
        """Initialize the categorizer with system design topics."""
        self.system_design_topics = {
            "distributed_systems": [
                "microservices", "distributed", "consistency", "availability", "partition tolerance",
                "CAP theorem", "eventual consistency", "strong consistency", "load balancing",
                "horizontal scaling", "vertical scaling", "sharding", "replication",
                "service mesh", "API gateway", "circuit breaker", "bulkhead pattern"
            ],
            "databases": [
                "database", "SQL", "NoSQL", "MongoDB", "PostgreSQL", "MySQL", "Redis",
                "Cassandra", "DynamoDB", "sharding", "replication", "ACID", "BASE",
                "transaction", "indexing", "query optimization", "database design",
                "data modeling", "normalization", "denormalization", "data consistency"
            ],
            "caching": [
                "cache", "caching", "Redis", "Memcached", "CDN", "cache invalidation",
                "cache strategy", "TTL", "cache hit", "cache miss", "distributed cache",
                "cache warming", "cache aside", "write through", "write behind"
            ],
            "messaging": [
                "message queue", "Kafka", "RabbitMQ", "pub/sub", "event streaming",
                "message broker", "asynchronous", "producer", "consumer", "topic",
                "event sourcing", "CQRS", "event store", "message patterns"
            ],
            "monitoring": [
                "monitoring", "logging", "metrics", "tracing", "observability", "APM",
                "alerting", "dashboard", "SLI", "SLO", "SLA", "health check",
                "distributed tracing", "performance monitoring", "error tracking"
            ],
            "security": [
                "authentication", "authorization", "OAuth", "JWT", "encryption", "SSL",
                "security", "vulnerability", "penetration testing", "access control",
                "RBAC", "ABAC", "zero trust", "security audit", "data protection"
            ],
            "deployment": [
                "deployment", "CI/CD", "Docker", "Kubernetes", "container", "orchestration",
                "infrastructure", "DevOps", "pipeline", "automation", "blue green",
                "canary deployment", "infrastructure as code", "GitOps"
            ],
            "scalability": [
                "scalability", "performance", "throughput", "latency", "auto scaling",
                "load testing", "capacity planning", "bottleneck", "optimization",
                "resource management", "concurrency", "parallel processing"
            ],
            "machine_learning": [
                "machine learning", "ML", "model training", "feature engineering", "data pipeline",
                "model serving", "inference", "batch processing", "real-time ML", "MLOps",
                "model deployment", "A/B testing", "model versioning", "data drift",
                "model monitoring", "feature store", "model registry", "pipeline orchestration"
            ],
            "ai_llm_systems": [
                "LLM", "large language model", "GPT", "transformer", "embedding", "vector database",
                "RAG", "retrieval augmented generation", "semantic search", "vector similarity",
                "prompt engineering", "fine-tuning", "in-context learning", "AI agent",
                "chatbot", "conversational AI", "text generation", "natural language processing",
                "NLP", "tokenization", "attention mechanism", "neural network", "deep learning"
            ],
            "data_engineering": [
                "data pipeline", "ETL", "ELT", "data warehouse", "data lake", "data processing",
                "batch processing", "stream processing", "Apache Spark", "Apache Flink",
                "data ingestion", "data transformation", "data quality", "data governance",
                "data lineage", "data catalog", "schema evolution", "data partitioning"
            ]
        }
        
        # Company-specific topic weights
        self.company_weights = {
            "Netflix": {"distributed_systems": 1.2, "caching": 1.1, "monitoring": 1.1},
            "Uber": {"messaging": 1.2, "databases": 1.1, "distributed_systems": 1.1},
            "LinkedIn": {"databases": 1.2, "monitoring": 1.1, "scalability": 1.1},
            "Google": {"distributed_systems": 1.3, "databases": 1.2, "scalability": 1.2, "ai_llm_systems": 1.3, "machine_learning": 1.2},
            "Amazon": {"databases": 1.2, "deployment": 1.1, "scalability": 1.1, "machine_learning": 1.2},
            "Facebook": {"distributed_systems": 1.2, "databases": 1.1, "caching": 1.1, "ai_llm_systems": 1.2},
            "Microsoft": {"deployment": 1.2, "security": 1.1, "monitoring": 1.1, "ai_llm_systems": 1.2},
            "Apple": {"security": 1.2, "deployment": 1.1, "monitoring": 1.1, "ai_llm_systems": 1.1},
            "OpenAI": {"ai_llm_systems": 1.5, "machine_learning": 1.3, "data_engineering": 1.1},
            "Anthropic": {"ai_llm_systems": 1.4, "machine_learning": 1.2, "data_engineering": 1.1},
            "Hugging Face": {"ai_llm_systems": 1.4, "machine_learning": 1.3, "data_engineering": 1.2},
            "NVIDIA": {"machine_learning": 1.4, "ai_llm_systems": 1.2, "scalability": 1.1},
            "Databricks": {"data_engineering": 1.4, "machine_learning": 1.3, "scalability": 1.1},
            "Snowflake": {"data_engineering": 1.3, "databases": 1.2, "scalability": 1.1}
        }
    
    def categorize_by_keywords(self, text_content: str, title: str = "") -> Dict[str, float]:
        """
        Categorize content based on keyword matching.
        
        Args:
            text_content: The main content of the blog post
            title: The title of the blog post
            
        Returns:
            Dictionary with topic scores
        """
        # Combine title and content for analysis
        full_text = f"{title} {text_content}".lower()
        
        topic_scores = {}
        
        for topic, keywords in self.system_design_topics.items():
            # Count keyword matches
            matches = sum(1 for keyword in keywords if keyword in full_text)
            
            # Normalize by content length and keyword count
            if matches > 0:
                # Weight title matches more heavily
                title_matches = sum(1 for keyword in keywords if keyword in title.lower())
                weighted_score = matches + (title_matches * 2)
                topic_scores[topic] = weighted_score
        
        return topic_scores
    
    def categorize_by_tfidf(self, text_content: str, title: str = "") -> Dict[str, float]:
        """
        Categorize using TF-IDF similarity to topic descriptions.
        
        Args:
            text_content: The main content of the blog post
            title: The title of the blog post
            
        Returns:
            Dictionary with topic scores
        """
        # Topic descriptions for TF-IDF comparison
        topic_descriptions = {
            "distributed_systems": "microservices architecture distributed systems scalability load balancing consistency availability partition tolerance service mesh API gateway",
            "databases": "database design SQL NoSQL sharding replication indexing query optimization ACID transactions data modeling consistency",
            "caching": "cache strategies Redis Memcached CDN cache invalidation performance optimization distributed cache TTL",
            "messaging": "message queues Kafka RabbitMQ pub/sub event streaming asynchronous communication producer consumer",
            "monitoring": "monitoring logging metrics tracing observability APM alerting performance distributed tracing health checks",
            "security": "authentication authorization OAuth JWT encryption security vulnerabilities access control RBAC zero trust",
            "deployment": "CI/CD Docker Kubernetes containerization orchestration DevOps infrastructure automation blue green canary",
            "scalability": "scalability performance throughput latency auto scaling load testing capacity planning optimization",
            "machine_learning": "machine learning ML model training feature engineering data pipeline model serving inference batch processing real-time ML MLOps model deployment A/B testing model versioning data drift model monitoring feature store model registry pipeline orchestration",
            "ai_llm_systems": "LLM large language model GPT transformer embedding vector database RAG retrieval augmented generation semantic search vector similarity prompt engineering fine-tuning in-context learning AI agent chatbot conversational AI text generation natural language processing NLP tokenization attention mechanism neural network deep learning",
            "data_engineering": "data pipeline ETL ELT data warehouse data lake data processing batch processing stream processing Apache Spark Apache Flink data ingestion data transformation data quality data governance data lineage data catalog schema evolution data partitioning"
        }
        
        # Prepare documents for TF-IDF
        documents = list(topic_descriptions.values())
        documents.append(f"{title} {text_content}")
        
        # Create TF-IDF vectors
        vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=1000,
            ngram_range=(1, 2)  # Include bigrams
        )
        
        try:
            tfidf_matrix = vectorizer.fit_transform(documents)
            
            # Calculate similarity between content and each topic
            content_vector = tfidf_matrix[-1]  # Last vector is our content
            topic_vectors = tfidf_matrix[:-1]   # All others are topics
            
            similarities = cosine_similarity(content_vector, topic_vectors)[0]
            
            # Create topic scores dictionary
            topic_names = list(topic_descriptions.keys())
            topic_scores = dict(zip(topic_names, similarities))
            
            return topic_scores
            
        except Exception as e:
            print(f"Error in TF-IDF categorization: {e}")
            return {}
    
    def categorize_hybrid(self, text_content: str, title: str = "", company: str = "") -> Dict[str, float]:
        """
        Combine multiple approaches for best categorization results.
        
        Args:
            text_content: The main content of the blog post
            title: The title of the blog post
            company: The company that published the blog
            
        Returns:
            Dictionary with normalized topic scores
        """
        # Get scores from different methods
        keyword_scores = self.categorize_by_keywords(text_content, title)
        tfidf_scores = self.categorize_by_tfidf(text_content, title)
        
        # Combine scores with weights
        final_scores = {}
        
        for topic in self.system_design_topics.keys():
            keyword_score = keyword_scores.get(topic, 0)
            tfidf_score = tfidf_scores.get(topic, 0)
            
            # Weighted combination (adjust weights based on testing)
            combined_score = (keyword_score * 0.4) + (tfidf_score * 0.6)
            
            # Apply company-specific weights
            if company in self.company_weights and topic in self.company_weights[company]:
                combined_score *= self.company_weights[company][topic]
            
            final_scores[topic] = combined_score
        
        # Normalize scores to 0-1 range
        max_score = max(final_scores.values()) if final_scores.values() else 0
        if max_score > 0:
            final_scores = {k: v/max_score for k, v in final_scores.items()}
        
        return final_scores
    
    def get_primary_topic(self, topic_scores: Dict[str, float], threshold: float = 0.1) -> str:
        """
        Get the primary topic from scores.
        
        Args:
            topic_scores: Dictionary of topic scores
            threshold: Minimum score to consider a topic relevant
            
        Returns:
            Primary topic name
        """
        if not topic_scores:
            return "general"
        
        # Filter scores above threshold
        relevant_topics = {k: v for k, v in topic_scores.items() if v >= threshold}
        
        if not relevant_topics:
            return "general"
        
        # Return the topic with highest score
        return max(relevant_topics.items(), key=lambda x: x[1])[0]
    
    def get_top_topics(self, topic_scores: Dict[str, float], n: int = 3) -> List[Tuple[str, float]]:
        """
        Get top N topics by score.
        
        Args:
            topic_scores: Dictionary of topic scores
            n: Number of top topics to return
            
        Returns:
            List of (topic, score) tuples sorted by score
        """
        if not topic_scores:
            return []
        
        return sorted(topic_scores.items(), key=lambda x: x[1], reverse=True)[:n]


class BlogContentProcessor:
    """
    Processes blog content from database and applies categorization.
    """
    
    def __init__(self, db_path: str = "storage/table_data.db"):
        """
        Initialize the processor.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.categorizer = ContentCategorizer()
    
    def extract_blog_content(self) -> List[Dict]:
        """
        Extract blog content from database.
        
        Returns:
            List of blog dictionaries with content
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all blog content with sufficient length
        cursor.execute("""
            SELECT blog_id, title, company, url, text_file_path, content_length, 
                   extraction_method, extraction_quality
            FROM blog_content 
            WHERE content_length > 500
            ORDER BY content_length DESC
        """)
        
        blogs = cursor.fetchall()
        blog_data = []
        
        for blog_id, title, company, url, text_file_path, content_length, extraction_method, extraction_quality in blogs:
            # Read text content from file
            if text_file_path and Path(text_file_path).exists():
                try:
                    with open(text_file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    blog_data.append({
                        'blog_id': blog_id,
                        'title': title,
                        'company': company,
                        'url': url,
                        'content': content,
                        'content_length': content_length,
                        'extraction_method': extraction_method,
                        'extraction_quality': extraction_quality
                    })
                except Exception as e:
                    print(f"Error reading content for {blog_id}: {e}")
        
        conn.close()
        return blog_data
    
    def categorize_all_blogs(self) -> List[Dict]:
        """
        Categorize all blog content.
        
        Returns:
            List of categorized blog dictionaries
        """
        blog_data = self.extract_blog_content()
        categorized_blogs = []
        
        print(f"📊 Processing {len(blog_data)} blogs for categorization...")
        
        for i, blog in enumerate(blog_data):
            print(f"Processing {i+1}/{len(blog_data)}: {blog['title'][:50]}...")
            
            # Categorize content
            topic_scores = self.categorizer.categorize_hybrid(
                blog['content'], 
                blog['title'], 
                blog['company']
            )
            
            # Get primary topic and top topics
            primary_topic = self.categorizer.get_primary_topic(topic_scores)
            top_topics = self.categorizer.get_top_topics(topic_scores, 3)
            
            categorized_blog = {
                **blog,
                'primary_topic': primary_topic,
                'topic_scores': topic_scores,
                'top_topics': top_topics
            }
            
            categorized_blogs.append(categorized_blog)
        
        return categorized_blogs
    
    def save_categorized_data(self, categorized_blogs: List[Dict]) -> None:
        """
        Save categorized data to database.
        
        Args:
            categorized_blogs: List of categorized blog dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create topics table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blog_topics (
                blog_id TEXT PRIMARY KEY,
                primary_topic TEXT,
                topic_scores TEXT,
                top_topics TEXT,
                FOREIGN KEY (blog_id) REFERENCES blog_content (blog_id)
            )
        """)
        
        # Insert categorized data
        for blog in categorized_blogs:
            cursor.execute("""
                INSERT OR REPLACE INTO blog_topics 
                (blog_id, primary_topic, topic_scores, top_topics)
                VALUES (?, ?, ?, ?)
            """, (
                blog['blog_id'],
                blog['primary_topic'],
                json.dumps(blog['topic_scores']),
                json.dumps(blog['top_topics'])
            ))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Saved categorization for {len(categorized_blogs)} blogs")
    
    def analyze_categorization_results(self) -> None:
        """
        Analyze and display categorization results.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get topic distribution
        cursor.execute("""
            SELECT primary_topic, COUNT(*) as count
            FROM blog_topics
            GROUP BY primary_topic
            ORDER BY count DESC
        """)
        
        topic_distribution = cursor.fetchall()
        
        print("\n📊 Topic Distribution:")
        for topic, count in topic_distribution:
            print(f"  {topic}: {count} blogs")
        
        # Get company-specific topics
        cursor.execute("""
            SELECT bt.primary_topic, bc.company, COUNT(*) as count
            FROM blog_topics bt
            JOIN blog_content bc ON bt.blog_id = bc.blog_id
            GROUP BY bt.primary_topic, bc.company
            ORDER BY count DESC
            LIMIT 20
        """)
        
        company_topics = cursor.fetchall()
        
        print("\n🏢 Company-Specific Topics (Top 20):")
        for topic, company, count in company_topics:
            print(f"  {company} - {topic}: {count} blogs")
        
        conn.close()


def main():
    """Main function to run the categorization process."""
    processor = BlogContentProcessor()
    
    print("🚀 Starting blog content categorization...")
    
    # Categorize all blogs
    categorized_blogs = processor.categorize_all_blogs()
    
    # Save results
    processor.save_categorized_data(categorized_blogs)
    
    # Analyze results
    processor.analyze_categorization_results()
    
    print("\n✅ Categorization complete!")


if __name__ == "__main__":
    main()
