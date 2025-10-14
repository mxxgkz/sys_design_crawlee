"""
Text Chunking Strategy for System Design Blog Content

This module implements various chunking strategies optimized for technical blog content
to prepare it for embedding and retrieval in the RAG system.
"""

import re
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata."""
    chunk_id: str
    blog_id: str
    content: str
    chunk_type: str  # 'title', 'section', 'paragraph', 'code', 'list'
    chunk_index: int
    start_pos: int
    end_pos: int
    metadata: Dict[str, Any]
    topic_scores: Dict[str, float]
    primary_topic: str


class TextChunker:
    """
    Implements various text chunking strategies for technical blog content.
    """
    
    def __init__(self, db_path: str = "storage/table_data.db"):
        """Initialize the chunker with database path."""
        self.db_path = db_path
        self.chunk_size = 512  # Default chunk size in tokens
        self.chunk_overlap = 50  # Overlap between chunks
        self.min_chunk_size = 100  # Minimum chunk size
    
    def load_categorized_blogs(self) -> List[Dict]:
        """Load categorized blog content from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = """
        SELECT 
            bc.blog_id, bc.title, bc.company, bc.url, bc.text_file_path, 
            bc.content_length, bt.primary_topic, bt.topic_scores, bt.top_topics
        FROM blog_content bc
        LEFT JOIN blog_topics bt ON bc.blog_id = bt.blog_id
        WHERE bc.content_length > 500
        ORDER BY bc.content_length DESC
        """
        
        cursor.execute(query)
        blogs = cursor.fetchall()
        
        print(f"🔍 Debug: Found {len(blogs)} blogs in database")
        if len(blogs) > 0:
            print(f"🔍 Debug: First blog: {blogs[0][1][:50]}...")  # Show title
        
        blog_data = []
        
        for blog_id, title, company, url, text_file_path, content_length, primary_topic, topic_scores, top_topics in blogs:
            print(f"🔍 Debug: Processing {blog_id} - {title[:30]}...")
            print(f"🔍 Debug: Text file path: {text_file_path}")
            print(f"🔍 Debug: File exists: {Path(text_file_path).exists() if text_file_path else False}")
            
            # Read text content from file
            if text_file_path and Path(text_file_path).exists():
                try:
                    with open(text_file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    print(f"🔍 Debug: Content length: {len(content)} chars")
                    
                    # Parse JSON fields
                    topic_scores_dict = json.loads(topic_scores) if topic_scores else {}
                    top_topics_list = json.loads(top_topics) if top_topics else []
                    
                    blog_data.append({
                        'blog_id': blog_id,
                        'title': title,
                        'company': company,
                        'url': url,
                        'content': content,
                        'content_length': content_length,
                        'primary_topic': primary_topic,
                        'topic_scores': topic_scores_dict,
                        'top_topics': top_topics_list
                    })
                    
                    print(f"✅ Added blog {blog_id} to data")
                except Exception as e:
                    print(f"❌ Error reading content for {blog_id}: {e}")
            else:
                print(f"⚠️ Skipping {blog_id} - file not found or path is None")
        
        conn.close()
        return blog_data
    
    def semantic_chunking(self, content: str, title: str = "") -> List[Dict[str, Any]]:
        """
        Semantic chunking that preserves logical structure.
        
        Args:
            content: The blog content to chunk
            title: The blog title
            
        Returns:
            List of semantic chunks with metadata
        """
        chunks = []
        
        # Split content into sections based on headers
        sections = self._split_by_headers(content)
        
        chunk_index = 0
        for section in sections:
            if len(section['content'].strip()) < self.min_chunk_size:
                continue
            
            # If section is too large, split it further
            if len(section['content']) > self.chunk_size * 4:  # 4x chunk size
                sub_chunks = self._split_large_section(section['content'])
                for sub_chunk in sub_chunks:
                    chunks.append({
                        'content': sub_chunk,
                        'chunk_type': section['type'],
                        'section_title': section['title'],
                        'chunk_index': chunk_index,
                        'metadata': {
                            'section_type': section['type'],
                            'section_title': section['title'],
                            'is_code': self._contains_code(sub_chunk),
                            'is_list': self._is_list_content(sub_chunk)
                        }
                    })
                    chunk_index += 1
            else:
                chunks.append({
                    'content': section['content'],
                    'chunk_type': section['type'],
                    'section_title': section['title'],
                    'chunk_index': chunk_index,
                    'metadata': {
                        'section_type': section['type'],
                        'section_title': section['title'],
                        'is_code': self._contains_code(section['content']),
                        'is_list': self._is_list_content(section['content'])
                    }
                })
                chunk_index += 1
        
        return chunks
    
    def _split_by_headers(self, content: str) -> List[Dict[str, Any]]:
        """Split content by headers (H1, H2, H3, etc.)."""
        sections = []
        
        # Common header patterns
        header_patterns = [
            r'^#{1,6}\s+(.+)$',  # Markdown headers
            r'^(.+)\n={3,}$',     # Underline headers
            r'^(.+)\n-{3,}$',     # Underline headers
            r'^##\s+(.+)$',       # Common blog headers
            r'^###\s+(.+)$',      # Subsection headers
        ]
        
        lines = content.split('\n')
        current_section = {'title': '', 'content': '', 'type': 'paragraph'}
        
        for line in lines:
            is_header = False
            for pattern in header_patterns:
                match = re.match(pattern, line.strip())
                if match:
                    # Save previous section if it has content
                    if current_section['content'].strip():
                        sections.append(current_section)
                    
                    # Start new section
                    current_section = {
                        'title': match.group(1).strip(),
                        'content': line + '\n',
                        'type': 'section'
                    }
                    is_header = True
                    break
            
            if not is_header:
                current_section['content'] += line + '\n'
        
        # Add final section
        if current_section['content'].strip():
            sections.append(current_section)
        
        return sections
    
    def _split_large_section(self, content: str) -> List[str]:
        """Split large sections into smaller chunks."""
        # Split by paragraphs first
        paragraphs = content.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) > self.chunk_size:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                current_chunk += '\n\n' + paragraph if current_chunk else paragraph
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _contains_code(self, text: str) -> bool:
        """Check if text contains code blocks."""
        code_indicators = [
            '```', '`', 'def ', 'class ', 'import ', 'from ',
            'function(', 'const ', 'var ', 'let ', 'if (', 'for ('
        ]
        return any(indicator in text for indicator in code_indicators)
    
    def _is_list_content(self, text: str) -> bool:
        """Check if text is list content."""
        lines = text.strip().split('\n')
        list_indicators = ['- ', '* ', '1. ', '2. ', '• ', '◦ ']
        list_lines = sum(1 for line in lines if any(line.strip().startswith(indicator) for indicator in list_indicators))
        return list_lines > len(lines) * 0.3  # 30% of lines are list items
    
    def fixed_size_chunking(self, content: str, chunk_size: int = None) -> List[Dict[str, Any]]:
        """
        Fixed-size chunking with overlap.
        
        Args:
            content: The content to chunk
            chunk_size: Size of each chunk (default: self.chunk_size)
            
        Returns:
            List of fixed-size chunks
        """
        if chunk_size is None:
            chunk_size = self.chunk_size
        
        chunks = []
        
        # Use character-based chunking for better performance with large content
        start = 0
        chunk_index = 0
        max_chunks = len(content) // (chunk_size * 2) + 10  # Safety limit
        chunk_count = 0
        
        while start < len(content) and chunk_count < max_chunks:
            # Calculate end position
            end = min(start + chunk_size * 4, len(content))  # Approximate 4 chars per word
            
            # Find a good break point (end of sentence or paragraph)
            if end < len(content):
                # Look for sentence endings within reasonable range
                search_start = max(start + chunk_size * 2, end - 200)
                for i in range(end, search_start, -1):
                    if content[i] in '.!?':
                        end = i + 1
                        break
                else:
                    # Look for paragraph breaks
                    search_start = max(start + chunk_size, end - 100)
                    for i in range(end, search_start, -1):
                        if content[i] == '\n':
                            end = i
                            break
            
            chunk_text = content[start:end].strip()
            
            if len(chunk_text) >= self.min_chunk_size:
                chunks.append({
                    'content': chunk_text,
                    'chunk_type': 'fixed_size',
                    'chunk_index': chunk_index,
                    'start_pos': start,
                    'end_pos': end,
                    'metadata': {
                        'chunk_size': len(chunk_text),
                        'is_code': self._contains_code(chunk_text),
                        'is_list': self._is_list_content(chunk_text)
                    }
                })
                chunk_index += 1
            
            # Move start position with overlap - ensure we make progress
            overlap_chars = max(50, self.chunk_overlap * 4)  # Minimum 50 char overlap
            start = max(start + chunk_size * 2, end - overlap_chars)  # Ensure progress
            
            # Safety check to prevent infinite loops
            if start >= end:
                start = end
            
            chunk_count += 1
        
        return chunks
    
    def hierarchical_chunking(self, content: str, title: str = "") -> List[Dict[str, Any]]:
        """
        Hierarchical chunking: blog → sections → paragraphs.
        
        Args:
            content: The blog content
            title: The blog title
            
        Returns:
            List of hierarchical chunks
        """
        chunks = []
        
        # Level 1: Full blog (if not too large)
        if len(content) <= self.chunk_size * 2:
            chunks.append({
                'content': content,
                'chunk_type': 'full_blog',
                'chunk_index': 0,
                'metadata': {
                    'level': 1,
                    'title': title,
                    'is_full_blog': True
                }
            })
            return chunks
        
        # Level 2: Sections
        sections = self._split_by_headers(content)
        for i, section in enumerate(sections):
            if len(section['content'].strip()) < self.min_chunk_size:
                continue
            
            chunks.append({
                'content': section['content'],
                'chunk_type': 'section',
                'chunk_index': i,
                'metadata': {
                    'level': 2,
                    'section_title': section['title'],
                    'section_type': section['type']
                }
            })
        
        # Level 3: Paragraphs (for large sections)
        for i, section in enumerate(sections):
            if len(section['content']) > self.chunk_size:
                paragraphs = section['content'].split('\n\n')
                for j, paragraph in enumerate(paragraphs):
                    if len(paragraph.strip()) >= self.min_chunk_size:
                        chunks.append({
                            'content': paragraph,
                            'chunk_type': 'paragraph',
                            'chunk_index': f"{i}_{j}",
                            'metadata': {
                                'level': 3,
                                'section_title': section['title'],
                                'paragraph_index': j
                            }
                        })
        
        return chunks
    
    def chunk_blog(self, blog_data: Dict[str, Any], strategy: str = "semantic") -> List[TextChunk]:
        """
        Chunk a single blog using the specified strategy.
        
        Args:
            blog_data: Blog data dictionary
            strategy: Chunking strategy ("semantic", "fixed_size", "hierarchical")
            
        Returns:
            List of TextChunk objects
        """
        content = blog_data['content']
        title = blog_data['title']
        
        # Choose chunking strategy
        if strategy == "semantic":
            raw_chunks = self.semantic_chunking(content, title)
        elif strategy == "fixed_size":
            raw_chunks = self.fixed_size_chunking(content)
        elif strategy == "hierarchical":
            raw_chunks = self.hierarchical_chunking(content, title)
        else:
            raise ValueError(f"Unknown chunking strategy: {strategy}")
        
        # Convert to TextChunk objects
        text_chunks = []
        for i, chunk_data in enumerate(raw_chunks):
            chunk_id = f"{blog_data['blog_id']}_{i}"
            
            text_chunk = TextChunk(
                chunk_id=chunk_id,
                blog_id=blog_data['blog_id'],
                content=chunk_data['content'],
                chunk_type=chunk_data['chunk_type'],
                chunk_index=i,
                start_pos=0,  # Simplified for now
                end_pos=len(chunk_data['content']),
                metadata=chunk_data.get('metadata', {}),
                topic_scores=blog_data.get('topic_scores', {}),
                primary_topic=blog_data.get('primary_topic', 'general')
            )
            
            text_chunks.append(text_chunk)
        
        return text_chunks
    
    def chunk_all_blogs(self, strategy: str = "semantic", limit: int = None) -> List[TextChunk]:
        """
        Chunk all blogs using the specified strategy.
        
        Args:
            strategy: Chunking strategy
            limit: Limit number of blogs to process
            
        Returns:
            List of all TextChunk objects
        """
        blog_data = self.load_categorized_blogs()
        
        if limit:
            blog_data = blog_data[:limit]
        
        all_chunks = []
        
        print(f"📊 Chunking {len(blog_data)} blogs using {strategy} strategy...")
        
        for i, blog in enumerate(blog_data):
            print(f"Processing {i+1}/{len(blog_data)}: {blog['title'][:50]}...")
            
            try:
                chunks = self.chunk_blog(blog, strategy)
                all_chunks.extend(chunks)
                
                print(f"  Created {len(chunks)} chunks")
            except Exception as e:
                print(f"  Error chunking blog {blog['blog_id']}: {e}")
        
        print(f"✅ Total chunks created: {len(all_chunks)}")
        return all_chunks
    
    def save_chunks_to_database(self, chunks: List[TextChunk]) -> None:
        """
        Save chunks to database.
        
        Args:
            chunks: List of TextChunk objects
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create chunks table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blog_chunks (
                chunk_id TEXT PRIMARY KEY,
                blog_id TEXT,
                content TEXT,
                chunk_type TEXT,
                chunk_index INTEGER,
                start_pos INTEGER,
                end_pos INTEGER,
                metadata TEXT,
                topic_scores TEXT,
                primary_topic TEXT,
                FOREIGN KEY (blog_id) REFERENCES blog_content (blog_id)
            )
        """)
        
        # Insert chunks
        for chunk in chunks:
            cursor.execute("""
                INSERT OR REPLACE INTO blog_chunks 
                (chunk_id, blog_id, content, chunk_type, chunk_index, 
                 start_pos, end_pos, metadata, topic_scores, primary_topic)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chunk.chunk_id,
                chunk.blog_id,
                chunk.content,
                chunk.chunk_type,
                chunk.chunk_index,
                chunk.start_pos,
                chunk.end_pos,
                json.dumps(chunk.metadata),
                json.dumps(chunk.topic_scores),
                chunk.primary_topic
            ))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Saved {len(chunks)} chunks to database")
    
    def analyze_chunks(self, chunks: List[TextChunk]) -> None:
        """
        Analyze and display chunk statistics.
        
        Args:
            chunks: List of TextChunk objects
        """
        if not chunks:
            print("❌ No chunks to analyze")
            return
        
        print("\n📊 Chunk Analysis")
        print("=" * 50)
        
        # Basic statistics
        total_chunks = len(chunks)
        avg_length = sum(len(chunk.content) for chunk in chunks) / total_chunks
        
        print(f"📈 Basic Statistics:")
        print(f"  Total chunks: {total_chunks}")
        print(f"  Average length: {avg_length:.0f} characters")
        print(f"  Min length: {min(len(chunk.content) for chunk in chunks)}")
        print(f"  Max length: {max(len(chunk.content) for chunk in chunks)}")
        
        # Chunk type distribution
        chunk_types = defaultdict(int)
        for chunk in chunks:
            chunk_types[chunk.chunk_type] += 1
        
        print(f"\n📋 Chunk Type Distribution:")
        for chunk_type, count in sorted(chunk_types.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_chunks) * 100
            print(f"  {chunk_type}: {count} chunks ({percentage:.1f}%)")
        
        # Topic distribution
        topics = defaultdict(int)
        for chunk in chunks:
            topics[chunk.primary_topic] += 1
        
        print(f"\n🎯 Topic Distribution:")
        for topic, count in sorted(topics.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_chunks) * 100
            print(f"  {topic}: {count} chunks ({percentage:.1f}%)")
        
        # Blog distribution
        blogs = defaultdict(int)
        for chunk in chunks:
            blogs[chunk.blog_id] += 1
        
        print(f"\n📝 Blog Distribution:")
        print(f"  Total blogs: {len(blogs)}")
        print(f"  Average chunks per blog: {total_chunks / len(blogs):.1f}")
        print(f"  Min chunks per blog: {min(blogs.values())}")
        print(f"  Max chunks per blog: {max(blogs.values())}")


def main():
    """Main function to run text chunking."""
    chunker = TextChunker()
    
    print("🚀 Starting Text Chunking Process")
    print("=" * 50)
    
    # Test different strategies
    strategies = ["semantic", "hierarchical", "fixed_size"]
    
    for strategy in strategies:
        print(f"\n📊 Testing {strategy} chunking...")
        chunks = chunker.chunk_all_blogs(strategy=strategy, limit=5)  # Test with 5 blogs
        
        if chunks:
            chunker.analyze_chunks(chunks)
            chunker.save_chunks_to_database(chunks)
        
        print(f"✅ {strategy} chunking completed")
    
    print("\n🎉 Text chunking process completed!")


if __name__ == "__main__":
    main()
