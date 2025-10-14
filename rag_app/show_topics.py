#!/usr/bin/env python3
"""
Show all available system design topics and their keywords.
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rag_app.data_processing.content_categorizer import ContentCategorizer


def show_all_topics():
    """Display all system design topics and their keywords."""
    categorizer = ContentCategorizer()
    
    print("🎯 System Design Topics for Content Categorization")
    print("=" * 60)
    
    for topic, keywords in categorizer.system_design_topics.items():
        print(f"\n📌 {topic.replace('_', ' ').title()}")
        print(f"   Keywords: {', '.join(keywords[:8])}{'...' if len(keywords) > 8 else ''}")
        print(f"   Total keywords: {len(keywords)}")
    
    print(f"\n📊 Summary:")
    print(f"   Total topics: {len(categorizer.system_design_topics)}")
    print(f"   Total keywords: {sum(len(keywords) for keywords in categorizer.system_design_topics.values())}")
    
    print(f"\n🏢 Company-Specific Weights:")
    for company, weights in categorizer.company_weights.items():
        if len(weights) > 0:
            top_weight = max(weights.items(), key=lambda x: x[1])
            print(f"   {company}: {top_weight[0]} ({top_weight[1]:.1f}x)")


if __name__ == "__main__":
    show_all_topics()
