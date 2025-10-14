#!/usr/bin/env python3
"""
Analytics script for categorized blog content.

This script provides various analytics and insights about the categorized blog data.
"""

import sqlite3
import json
import pandas as pd
from pathlib import Path
from collections import Counter

# Optional visualization imports
try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    HAS_VISUALIZATION = True
except ImportError:
    HAS_VISUALIZATION = False
    print("Note: matplotlib/seaborn not installed. Visualization features disabled.")


class BlogAnalytics:
    """Analytics for categorized blog content."""
    
    def __init__(self, db_path: str = "storage/table_data.db"):
        """Initialize analytics with database path."""
        self.db_path = db_path
    
    def load_categorized_data(self) -> pd.DataFrame:
        """Load categorized blog data into a DataFrame."""
        conn = sqlite3.connect(self.db_path)
        
        query = """
        SELECT 
            bc.blog_id,
            bc.title,
            bc.company,
            bc.url,
            bc.content_length,
            bc.extraction_method,
            bc.extraction_quality,
            bt.primary_topic,
            bt.topic_scores,
            bt.top_topics
        FROM blog_content bc
        LEFT JOIN blog_topics bt ON bc.blog_id = bt.blog_id
        WHERE bc.content_length > 500
        ORDER BY bc.content_length DESC
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # Parse JSON columns
        if not df.empty:
            df['topic_scores'] = df['topic_scores'].apply(
                lambda x: json.loads(x) if x else {}
            )
            df['top_topics'] = df['top_topics'].apply(
                lambda x: json.loads(x) if x else []
            )
        
        return df
    
    def topic_distribution(self) -> None:
        """Display topic distribution analysis."""
        df = self.load_categorized_data()
        
        if df.empty:
            print("❌ No categorized data found. Run categorization first.")
            return
        
        print("📊 Topic Distribution Analysis")
        print("=" * 50)
        
        # Overall topic distribution
        topic_counts = df['primary_topic'].value_counts()
        print("\n🎯 Primary Topics:")
        for topic, count in topic_counts.items():
            percentage = (count / len(df)) * 100
            print(f"  {topic}: {count} blogs ({percentage:.1f}%)")
        
        # Company-specific analysis
        print("\n🏢 Top Companies by Blog Count:")
        company_counts = df['company'].value_counts().head(10)
        for company, count in company_counts.items():
            print(f"  {company}: {count} blogs")
        
        # Topic-Company matrix
        print("\n📈 Topic-Company Matrix (Top 5x5):")
        topic_company_matrix = pd.crosstab(
            df['primary_topic'], 
            df['company'], 
            margins=True
        )
        print(topic_company_matrix.head(6))
    
    def content_quality_analysis(self) -> None:
        """Analyze content quality metrics."""
        df = self.load_categorized_data()
        
        if df.empty:
            print("❌ No data found.")
            return
        
        print("\n📏 Content Quality Analysis")
        print("=" * 50)
        
        # Content length statistics
        print(f"📊 Content Length Statistics:")
        print(f"  Mean: {df['content_length'].mean():,.0f} chars")
        print(f"  Median: {df['content_length'].median():,.0f} chars")
        print(f"  Min: {df['content_length'].min():,} chars")
        print(f"  Max: {df['content_length'].max():,} chars")
        
        # Extraction method distribution
        print(f"\n⚙️ Extraction Method Distribution:")
        method_counts = df['extraction_method'].value_counts()
        for method, count in method_counts.items():
            percentage = (count / len(df)) * 100
            print(f"  {method}: {count} blogs ({percentage:.1f}%)")
        
        # Quality distribution
        print(f"\n⭐ Extraction Quality Distribution:")
        quality_counts = df['extraction_quality'].value_counts()
        for quality, count in quality_counts.items():
            percentage = (count / len(df)) * 100
            print(f"  {quality}: {count} blogs ({percentage:.1f}%)")
    
    def topic_trends_by_company(self) -> None:
        """Analyze topic trends by company."""
        df = self.load_categorized_data()
        
        if df.empty:
            print("❌ No data found.")
            return
        
        print("\n🏢 Topic Trends by Company")
        print("=" * 50)
        
        # Get top companies
        top_companies = df['company'].value_counts().head(5).index
        
        for company in top_companies:
            company_df = df[df['company'] == company]
            print(f"\n📈 {company} ({len(company_df)} blogs):")
            
            topic_counts = company_df['primary_topic'].value_counts()
            for topic, count in topic_counts.head(3).items():
                percentage = (count / len(company_df)) * 100
                print(f"  {topic}: {count} blogs ({percentage:.1f}%)")
    
    def find_similar_blogs(self, blog_id: str, n: int = 5) -> None:
        """Find blogs similar to a given blog based on topic scores."""
        df = self.load_categorized_data()
        
        if df.empty:
            print("❌ No data found.")
            return
        
        # Find the target blog
        target_blog = df[df['blog_id'] == blog_id]
        if target_blog.empty:
            print(f"❌ Blog {blog_id} not found.")
            return
        
        target_scores = target_blog.iloc[0]['topic_scores']
        if not target_scores:
            print(f"❌ No topic scores for blog {blog_id}.")
            return
        
        print(f"\n🔍 Similar Blogs to: {target_blog.iloc[0]['title'][:60]}...")
        print("=" * 50)
        
        # Calculate similarity scores
        similarities = []
        for idx, row in df.iterrows():
            if row['blog_id'] == blog_id:
                continue
            
            if not row['topic_scores']:
                continue
            
            # Calculate cosine similarity between topic scores
            target_vector = list(target_scores.values())
            current_vector = list(row['topic_scores'].values())
            
            if len(target_vector) != len(current_vector):
                continue
            
            # Simple cosine similarity
            dot_product = sum(a * b for a, b in zip(target_vector, current_vector))
            norm_a = sum(a**2 for a in target_vector)**0.5
            norm_b = sum(b**2 for b in current_vector)**0.5
            
            if norm_a > 0 and norm_b > 0:
                similarity = dot_product / (norm_a * norm_b)
                similarities.append((row['blog_id'], similarity, row['title'], row['company']))
        
        # Sort by similarity and show top N
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        for i, (sim_blog_id, similarity, title, company) in enumerate(similarities[:n]):
            print(f"{i+1}. {title[:60]}... ({company}) - Similarity: {similarity:.3f}")
    
    def generate_insights(self) -> None:
        """Generate key insights from the data."""
        df = self.load_categorized_data()
        
        if df.empty:
            print("❌ No data found.")
            return
        
        print("\n💡 Key Insights")
        print("=" * 50)
        
        # Most common topics
        most_common_topic = df['primary_topic'].mode().iloc[0] if not df.empty else "N/A"
        print(f"🎯 Most common topic: {most_common_topic}")
        
        # Company with most blogs
        top_company = df['company'].mode().iloc[0] if not df.empty else "N/A"
        print(f"🏢 Most active company: {top_company}")
        
        # Average content length
        avg_length = df['content_length'].mean()
        print(f"📏 Average content length: {avg_length:,.0f} characters")
        
        # Quality distribution
        high_quality = (df['extraction_quality'] == 'high').sum()
        quality_percentage = (high_quality / len(df)) * 100
        print(f"⭐ High quality extractions: {quality_percentage:.1f}%")
        
        # Topic diversity
        unique_topics = df['primary_topic'].nunique()
        print(f"🌈 Topic diversity: {unique_topics} unique topics")
    
    def export_analytics(self, output_file: str = "blog_analytics.json") -> None:
        """Export analytics data to JSON file."""
        df = self.load_categorized_data()
        
        if df.empty:
            print("❌ No data found.")
            return
        
        analytics_data = {
            "summary": {
                "total_blogs": len(df),
                "unique_companies": df['company'].nunique(),
                "unique_topics": df['primary_topic'].nunique(),
                "avg_content_length": df['content_length'].mean(),
                "high_quality_percentage": (df['extraction_quality'] == 'high').mean() * 100
            },
            "topic_distribution": df['primary_topic'].value_counts().to_dict(),
            "company_distribution": df['company'].value_counts().to_dict(),
            "extraction_methods": df['extraction_method'].value_counts().to_dict(),
            "quality_distribution": df['extraction_quality'].value_counts().to_dict()
        }
        
        with open(output_file, 'w') as f:
            json.dump(analytics_data, f, indent=2)
        
        print(f"✅ Analytics exported to {output_file}")


def main():
    """Main function to run analytics."""
    analytics = BlogAnalytics()
    
    print("📊 Blog Content Analytics")
    print("=" * 50)
    
    # Run all analytics
    analytics.topic_distribution()
    analytics.content_quality_analysis()
    analytics.topic_trends_by_company()
    analytics.generate_insights()
    analytics.export_analytics()
    
    print("\n✅ Analytics complete!")


if __name__ == "__main__":
    main()
