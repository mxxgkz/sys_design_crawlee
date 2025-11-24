#!/usr/bin/env python3
"""
Step-by-step helper for bringing the BEIR/FIQA dataset into the RAG pipeline.

This script performs three sequential stages:
  1. Download and inspect the FIQA corpus, queries, and relevance labels.
  2. Chunk each FIQA document with the existing TextChunker and store the chunks
     in Chroma using the SentenceTransformersEmbeddingSystem.
  3. Run retrieval-only metrics (Precision@K, Recall@K, MRR, NDCG) using the
     provided FIQA qrels so you can benchmark models before applying changes to
     your scraped tech blogs.

Example:
    python rag_app/scripts/beir_fiqa_dataset.py --max-docs 200 --max-queries 100
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Iterable

# Add project root to Python path so we can import rag_app modules
# This allows the script to be run from any directory
_project_root = Path(__file__).parent.parent.parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from beir import util
    from beir.datasets.data_loader import GenericDataLoader
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit("beir not installed. Run `pip install beir` to use this script.") from exc

from tqdm import tqdm

try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None  # Will check later if reranking is requested

from rag_app.data_processing.text_chunker import TextChunker
from rag_app.embeddings_sentence_transformers import SentenceTransformersEmbeddingSystem
from rag_app.evaluation_metrics import RetrievalMetrics, RetrievalResult


# ---------------------------------------------------------------------------
# Stage 1: Load dataset
# ---------------------------------------------------------------------------
def load_fiqa_dataset(sample_docs: int | None = None) -> Tuple[List[Dict], Dict[str, str], Dict[str, Dict[str, int]]]:
    """Download BEIR/FIQA and return corpus, queries, and qrels."""
    print("📥 Step 1/3: Downloading beir/fiqa dataset...")
    
    # Download and extract FIQA dataset using beir package
    url = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/fiqa.zip"
    out_dir = Path.home() / ".cache" / "beir" / "datasets"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    dataset_path = util.download_and_unzip(url, str(out_dir))
    
    # The download_and_unzip returns the path to the extracted folder
    # Check the actual structure and find where corpus.jsonl is located
    data_path = Path(dataset_path)
    
    # Check if corpus.jsonl exists directly in the extracted folder
    if (data_path / "corpus.jsonl").exists():
        # Data is directly in the extracted folder
        data_path = data_path
    elif (data_path / "fiqa" / "corpus.jsonl").exists():
        # Data is in a subfolder named "fiqa"
        data_path = data_path / "fiqa"
    elif data_path.name == "fiqa" and (data_path / "corpus.jsonl").exists():
        # The extracted folder itself is named "fiqa"
        data_path = data_path
    else:
        # Try to find corpus.jsonl anywhere in the directory tree
        corpus_files = list(data_path.rglob("corpus.jsonl"))
        if corpus_files:
            data_path = corpus_files[0].parent
        else:
            raise ValueError(
                f"Could not find corpus.jsonl in {dataset_path}. "
                f"Please check the downloaded dataset structure."
            )
    
    print(f"   📂 Using dataset path: {data_path}")
    
    # Load FIQA files directly (FIQA doesn't use train/test splits)
    # Files are: corpus.jsonl, queries.jsonl, qrels.jsonl (or qrels.tsv)
    import json
    
    # Load corpus
    corpus = {}
    corpus_file = data_path / "corpus.jsonl"
    if not corpus_file.exists():
        raise ValueError(f"Corpus file not found: {corpus_file}")
    with open(corpus_file, 'r', encoding='utf-8') as f:
        for line in f:
            doc = json.loads(line.strip())
            corpus[doc['_id']] = doc
    
    # Load queries
    queries = {}
    queries_file = data_path / "queries.jsonl"
    if not queries_file.exists():
        raise ValueError(f"Queries file not found: {queries_file}")
    with open(queries_file, 'r', encoding='utf-8') as f:
        for line in f:
            query = json.loads(line.strip())
            queries[query['_id']] = query['text']
    
    # Load qrels (can be JSONL, TSV, or in a qrels/ subdirectory with train/dev/test splits)
    qrels = defaultdict(dict)
    import csv
    
    # Check for qrels in subdirectory first (BEIR format)
    qrels_dir = data_path / "qrels"
    if qrels_dir.exists() and qrels_dir.is_dir():
        # Try test.tsv first (for evaluation), then dev.tsv, then train.tsv
        for split_file in ["test.tsv", "dev.tsv", "train.tsv"]:
            qrels_file = qrels_dir / split_file
            if qrels_file.exists():
                print(f"   📄 Loading qrels from: {qrels_file}")
                with open(qrels_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f, delimiter='\t')
                    for row in reader:
                        query_id = row.get('query-id') or row.get('query_id')
                        corpus_id = row.get('corpus-id') or row.get('corpus_id')
                        score = int(row.get('score', 1))
                        qrels[query_id][corpus_id] = score
                break
        if not qrels:
            raise ValueError(f"No qrels files found in {qrels_dir}")
    else:
        # Check for qrels files directly in data_path
        qrels_file_jsonl = data_path / "qrels.jsonl"
        qrels_file_tsv = data_path / "qrels.tsv"
        
        if qrels_file_jsonl.exists():
            with open(qrels_file_jsonl, 'r', encoding='utf-8') as f:
                for line in f:
                    qrel = json.loads(line.strip())
                    qrels[qrel['query-id']][qrel['corpus-id']] = qrel['score']
        elif qrels_file_tsv.exists():
            with open(qrels_file_tsv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter='\t')
                for row in reader:
                    query_id = row.get('query-id') or row.get('query_id')
                    corpus_id = row.get('corpus-id') or row.get('corpus_id')
                    score = int(row.get('score', 1))
                    qrels[query_id][corpus_id] = score
        else:
            raise ValueError(f"Qrels file not found. Looked for: {qrels_dir} or {qrels_file_jsonl} or {qrels_file_tsv}")
    
    # Convert corpus to list of dicts (limit if needed)
    corpus_list: List[Dict] = []
    for idx, (doc_id, doc_data) in enumerate(corpus.items()):
        if sample_docs is not None and idx >= sample_docs:
            break
        corpus_list.append(
            {
                "_id": doc_id,
                "title": doc_data.get("title") or f"FIQA Document {doc_id}",
                "text": doc_data.get("text", ""),
            }
        )
    
    # Convert queries dict to our format
    queries_dict: Dict[str, str] = dict(queries)
    
    # Convert qrels to nested dict format
    qrels_dict: Dict[str, Dict[str, int]] = defaultdict(dict)
    for query_id, relevant_docs in qrels.items():
        for doc_id, score in relevant_docs.items():
            qrels_dict[query_id][doc_id] = score

    print(f"   ✅ Loaded {len(corpus_list)} documents, {len(queries_dict)} queries, {len(qrels_dict)} qrels entries")
    return corpus_list, queries_dict, qrels_dict


# ---------------------------------------------------------------------------
# Stage 2: Chunk + index corpus
# ---------------------------------------------------------------------------
def chunk_corpus(corpus: Iterable[Dict], chunker: TextChunker) -> List[Dict]:
    """Convert FIQA docs into chunks compatible with the embedding system."""
    print("🧩 Step 2/3: Chunking FIQA documents with the semantic strategy...")
    chunks: List[Dict] = []
    corpus_list = list(corpus)
    total_docs = len(corpus_list)

    for doc in tqdm(corpus_list, desc="Chunking FIQA docs", total=total_docs):
        combined_text = f"{doc['title']}\n\n{doc['text']}"
        semantic_chunks = chunker.semantic_chunking(combined_text, title=doc["title"])

        for chunk in semantic_chunks:
            chunks.append(
                {
                    "content": chunk["content"],
                    "chunk_type": chunk.get("chunk_type", "section"),
                    "title": doc["title"],
                    "company": "fiqa",
                    # Store the FIQA doc id inside the URL field so we can read it back later.
                    "url": doc["_id"],
                    "topic": chunk.get("metadata", {}).get("section_title", ""),
                }
            )

    print(f"   ✅ Generated {len(chunks)} chunks from {total_docs} documents")
    return chunks


def build_embedding_collection(
    chunks: List[Dict],
    model_name: str,
    collection_name: str,
    vector_db_path: str | None,
) -> SentenceTransformersEmbeddingSystem:
    """Create embeddings for FIQA chunks and persist them to Chroma."""
    print("💾 Creating / updating Chroma collection with FIQA chunks...")
    embedding_system = SentenceTransformersEmbeddingSystem(
        model_name=model_name,
        collection_name=collection_name,
        vector_db_path=vector_db_path,
    )

    if not chunks:
        print("⚠️ No chunks to store. Exiting.")
        sys.exit(1)

    embedding_system.store_embeddings(chunks)
    stats = embedding_system.get_collection_stats()
    print(f"   ✅ Collection '{collection_name}' now contains {stats.get('total_chunks', 0)} chunks")
    return embedding_system


# ---------------------------------------------------------------------------
# Stage 3: Evaluate retrieval metrics
# ---------------------------------------------------------------------------
# Global reranker cache
_reranker_cache = {}


def rerank_results(
    query: str,
    candidates: List[Dict],
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    top_k: int = 10,
) -> List[Dict]:
    """Rerank retrieval candidates using a cross-encoder."""
    if CrossEncoder is None:
        raise ImportError("sentence-transformers not installed. Install it to use reranking.")
    
    if not candidates:
        return []
    
    # Initialize reranker (lazy loading with caching)
    if reranker_model not in _reranker_cache:
        print(f"   🔄 Loading reranker: {reranker_model}")
        _reranker_cache[reranker_model] = CrossEncoder(reranker_model)
    
    reranker = _reranker_cache[reranker_model]
    
    # Prepare pairs for reranking
    pairs = [[query, item.get("content", "")] for item in candidates]
    
    # Get reranking scores
    scores = reranker.predict(pairs)
    
    # Combine scores with original items and sort
    reranked = [
        {**item, "score": float(score), "rerank_score": float(score)}
        for item, score in zip(candidates, scores)
    ]
    reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
    
    return reranked[:top_k]


def evaluate_retrieval(
    embedding_system: SentenceTransformersEmbeddingSystem,
    queries: Dict[str, str],
    qrels: Dict[str, Dict[str, int]],
    k_values: List[int],
    max_queries: int | None = None,
    use_reranking: bool = False,
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
) -> Dict[str, float]:
    """Run retrieval metrics using FIQA qrels."""
    print("📊 Step 3/3: Evaluating retrieval quality on FIQA qrels...")
    
    # Diagnostic: Check if we have any overlap between stored docs and qrels
    print("🔍 Diagnostic: Checking document ID overlap...")
    all_relevant_doc_ids = set()
    for relevant_docs in qrels.values():
        all_relevant_doc_ids.update(relevant_docs.keys())
    print(f"   Total unique relevant doc IDs in qrels: {len(all_relevant_doc_ids)}")
    print(f"   Sample doc IDs from qrels: {list(all_relevant_doc_ids)[:5]}")
    
    # Try to query a sample to see what doc IDs we're storing
    sample_query = list(queries.values())[0] if queries else ""
    if sample_query:
        sample_results = embedding_system.query_vectors(sample_query, n_results=10)
        stored_doc_ids = set()
        for item in sample_results:
            metadata = item.get("metadata") or {}
            doc_id = metadata.get("url", "") or metadata.get("doc_id", "")
            if doc_id:
                stored_doc_ids.add(doc_id)
        print(f"   Sample doc IDs from stored chunks: {list(stored_doc_ids)[:5]}")
        overlap = all_relevant_doc_ids & stored_doc_ids
        print(f"   Overlap: {len(overlap)}/{len(all_relevant_doc_ids)} ({100*len(overlap)/len(all_relevant_doc_ids):.1f}%)")
        if len(overlap) == 0:
            print("   ⚠️ WARNING: No overlap between stored doc IDs and qrels doc IDs!")
            print("   This suggests the document IDs don't match. Check how IDs are stored vs. how they appear in qrels.")
    
    metrics = RetrievalMetrics()
    metric_totals = defaultdict(list)
    k_max = max(k_values)

    evaluated = 0
    debug_count = 0
    for query_id, query_text in tqdm(queries.items(), desc="Evaluating queries"):
        if max_queries is not None and evaluated >= max_queries:
            break

        relevant_docs = qrels.get(query_id)
        if not relevant_docs:
            continue

        # Initial retrieval (get more candidates if reranking)
        initial_k = k_max * 3 if use_reranking else k_max
        retrieved = embedding_system.query_vectors(query_text, n_results=initial_k)
        
        # Apply reranking if requested
        if use_reranking and retrieved:
            retrieved = rerank_results(query_text, retrieved, reranker_model, top_k=k_max)
        
        retrieval_results = []
        
        # Debug: Print first few queries to see what's happening
        if debug_count < 3:
            print(f"\n🔍 DEBUG Query {query_id}: '{query_text[:60]}...'")
            print(f"   Relevant docs: {list(relevant_docs.keys())[:5]}... (total: {len(relevant_docs)})")
            print(f"   Retrieved {len(retrieved)} chunks")

        for item in retrieved:
            # Try multiple ways to get the document ID
            metadata = item.get("metadata") or {}
            doc_id = metadata.get("url", "") or metadata.get("doc_id", "") or metadata.get("_id", "")
            
            # Debug first few items
            if debug_count < 3 and len(retrieval_results) < 3:
                print(f"      Chunk doc_id: '{doc_id}' (from metadata: {list(metadata.keys())})")
            
            is_relevant = doc_id in relevant_docs if doc_id else False
            retrieval_results.append(
                RetrievalResult(
                    content=item.get("content", ""),
                    metadata={"doc_id": doc_id, **metadata},
                    score=item.get("score", 0.0),
                    is_relevant=is_relevant,
                )
            )
        
        if debug_count < 3:
            relevant_found = sum(1 for r in retrieval_results[:k_max] if r.is_relevant)
            print(f"   Relevant chunks in top {k_max}: {relevant_found}/{len(relevant_docs)}")
            debug_count += 1

        total_relevant = len(relevant_docs)
        per_query_metrics = metrics.calculate_all_metrics(retrieval_results, total_relevant, k_values=k_values)
        for key, value in per_query_metrics.items():
            metric_totals[key].append(value)

        evaluated += 1

    if evaluated == 0:
        print("⚠️ No queries were evaluated (possibly due to filtering).")
        return {}

    averages = {f"avg_{metric}": sum(values) / len(values) for metric, values in metric_totals.items()}
    print(f"   ✅ Evaluated {evaluated} queries. Aggregate metrics:")
    for metric, value in averages.items():
        print(f"      - {metric}: {value:.4f}")

    return averages


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Use BEIR/FIQA to benchmark the RAG stack.")
    parser.add_argument("--max-docs", type=int, default=500, help="Limit number of FIQA docs to index (default: 500)")
    parser.add_argument(
        "--max-queries", type=int, default=200, help="Limit number of FIQA queries to evaluate (default: 200)"
    )
    parser.add_argument(
        "--collection-name", type=str, default="fiqa_chunks", help="Chroma collection name dedicated to FIQA"
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="all-MiniLM-L6-v2",
        help="SentenceTransformers model to use for embeddings",
    )
    parser.add_argument(
        "--vector-db-path",
        type=str,
        default=None,
        help="Optional custom path for Chroma storage (defaults to rag_app/common_setup paths)",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Skip chunking + indexing (use existing FIQA collection and only run evaluation)",
    )
    parser.add_argument("--k-values", type=int, nargs="+", default=[5, 10], help="List of K values for retrieval metrics")
    parser.add_argument(
        "--use-reranking",
        action="store_true",
        help="Use cross-encoder reranking to improve retrieval quality",
    )
    parser.add_argument(
        "--reranker-model",
        type=str,
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        help="Cross-encoder model for reranking (default: ms-marco-MiniLM-L-6-v2)",
    )
    parser.add_argument(
        "--test-models",
        type=str,
        nargs="+",
        default=None,
        help="Test multiple embedding models and compare results. Example: --test-models all-MiniLM-L6-v2 multi-qa-MiniLM-L6-cos-v1",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    corpus, queries, qrels = load_fiqa_dataset(sample_docs=args.max_docs)

    # Handle multi-model testing
    if args.test_models:
        print(f"🧪 Testing {len(args.test_models)} embedding models...")
        results_comparison = {}
        
        for model_name in args.test_models:
            print(f"\n{'='*60}")
            print(f"📊 Testing model: {model_name}")
            print(f"{'='*60}")
            
            collection_name = f"{args.collection_name}_{model_name.replace('/', '_').replace('-', '_')}"
            
            if args.skip_index:
                print("⏭️ Skipping chunking/indexing stage as requested.")
                embedding_system = SentenceTransformersEmbeddingSystem(
                    model_name=model_name,
                    collection_name=collection_name,
                    vector_db_path=args.vector_db_path,
                )
            else:
                chunker = TextChunker()
                chunks = chunk_corpus(corpus, chunker)
                embedding_system = build_embedding_collection(
                    chunks,
                    model_name=model_name,
                    collection_name=collection_name,
                    vector_db_path=args.vector_db_path,
                )

            metrics = evaluate_retrieval(
                embedding_system=embedding_system,
                queries=queries,
                qrels=qrels,
                k_values=args.k_values,
                max_queries=args.max_queries,
                use_reranking=args.use_reranking,
                reranker_model=args.reranker_model,
            )
            results_comparison[model_name] = metrics
        
        # Print comparison table
        print(f"\n{'='*60}")
        print("📊 MODEL COMPARISON SUMMARY")
        print(f"{'='*60}")
        print(f"{'Model':<40} {'P@5':<8} {'R@5':<8} {'NDCG@5':<10} {'MRR':<8}")
        print("-" * 60)
        for model_name, metrics in results_comparison.items():
            p5 = metrics.get("avg_precision@5", 0.0)
            r5 = metrics.get("avg_recall@5", 0.0)
            ndcg5 = metrics.get("avg_ndcg@5", 0.0)
            mrr = metrics.get("avg_mrr", 0.0)
            print(f"{model_name:<40} {p5:<8.4f} {r5:<8.4f} {ndcg5:<10.4f} {mrr:<8.4f}")
        
    else:
        # Single model evaluation
        if args.skip_index:
            print("⏭️ Skipping chunking/indexing stage as requested.")
            embedding_system = SentenceTransformersEmbeddingSystem(
                model_name=args.model_name,
                collection_name=args.collection_name,
                vector_db_path=args.vector_db_path,
            )
        else:
            chunker = TextChunker()
            chunks = chunk_corpus(corpus, chunker)
            embedding_system = build_embedding_collection(
                chunks,
                model_name=args.model_name,
                collection_name=args.collection_name,
                vector_db_path=args.vector_db_path,
            )

        evaluate_retrieval(
            embedding_system=embedding_system,
            queries=queries,
            qrels=qrels,
            k_values=args.k_values,
            max_queries=args.max_queries,
            use_reranking=args.use_reranking,
            reranker_model=args.reranker_model,
        )


if __name__ == "__main__":
    main()
