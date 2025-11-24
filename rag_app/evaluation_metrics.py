#!/usr/bin/env python3
"""
Evaluation Metrics Framework for RAG System

This module provides comprehensive metrics to evaluate retrieval and generation quality.
Useful for measuring improvements and demonstrating ML system design expertise.

Usage:
    python evaluation_metrics.py
"""

import json
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import time
from pathlib import Path


@dataclass
class RetrievalResult:
    """Represents a single retrieval result."""
    content: str
    metadata: Dict[str, Any]
    score: float
    is_relevant: bool = False  # Ground truth label


@dataclass
class QueryResult:
    """Represents results for a single query."""
    query: str
    retrieved_chunks: List[RetrievalResult]
    answer: str
    ground_truth_answer: Optional[str] = None
    relevant_chunk_ids: Optional[List[str]] = None


class RetrievalMetrics:
    """Metrics for evaluating retrieval quality."""
    
    @staticmethod
    def precision_at_k(results: List[RetrievalResult], k: int) -> float:
        """
        Calculate Precision@K: fraction of top-K results that are relevant.
        
        Args:
            results: List of retrieval results (sorted by relevance)
            k: Number of top results to consider
            
        Returns:
            Precision@K score (0.0 to 1.0)
        """
        if not results or k == 0:
            return 0.0
        
        top_k = results[:k]
        relevant_count = sum(1 for r in top_k if r.is_relevant)
        return relevant_count / len(top_k)
    
    @staticmethod
    def recall_at_k(results: List[RetrievalResult], k: int, total_relevant: int) -> float:
        """
        Calculate Recall@K: fraction of relevant docs retrieved in top-K.
        
        Args:
            results: List of retrieval results (sorted by relevance)
            k: Number of top results to consider
            total_relevant: Total number of relevant documents
            
        Returns:
            Recall@K score (0.0 to 1.0)
        """
        if total_relevant == 0:
            return 0.0
        
        top_k = results[:k]
        retrieved_relevant = sum(1 for r in top_k if r.is_relevant)
        return retrieved_relevant / total_relevant
    
    @staticmethod
    def mean_reciprocal_rank(results: List[RetrievalResult]) -> float:
        """
        Calculate MRR: average of 1/rank of first relevant result.
        
        Args:
            results: List of retrieval results (sorted by relevance)
            
        Returns:
            MRR score (0.0 to 1.0)
        """
        for rank, result in enumerate(results, start=1):
            if result.is_relevant:
                return 1.0 / rank
        return 0.0
    
    @staticmethod
    def ndcg_at_k(results: List[RetrievalResult], k: int) -> float:
        """
        Calculate NDCG@K: normalized discounted cumulative gain.
        
        Args:
            results: List of retrieval results (sorted by relevance)
            k: Number of top results to consider
            
        Returns:
            NDCG@K score (0.0 to 1.0)
        """
        if not results or k == 0:
            return 0.0
        
        top_k = results[:k]
        
        # Calculate DCG
        dcg = 0.0
        for i, result in enumerate(top_k, start=1):
            relevance = 1.0 if result.is_relevant else 0.0
            dcg += relevance / np.log2(i + 1)
        
        # Calculate IDCG (ideal DCG - all relevant at top)
        num_relevant = sum(1 for r in top_k if r.is_relevant)
        idcg = sum(1.0 / np.log2(i + 1) for i in range(1, min(num_relevant, k) + 1))
        
        if idcg == 0:
            return 0.0
        
        return dcg / idcg
    
    @staticmethod
    def calculate_all_metrics(results: List[RetrievalResult], 
                             total_relevant: int,
                             k_values: List[int] = [5, 10]) -> Dict[str, float]:
        """
        Calculate all retrieval metrics.
        
        Args:
            results: List of retrieval results
            total_relevant: Total number of relevant documents
            k_values: List of K values to calculate metrics for
            
        Returns:
            Dictionary of metric names and values
        """
        metrics = {}
        
        for k in k_values:
            metrics[f'precision@{k}'] = RetrievalMetrics.precision_at_k(results, k)
            metrics[f'recall@{k}'] = RetrievalMetrics.recall_at_k(results, k, total_relevant)
            metrics[f'ndcg@{k}'] = RetrievalMetrics.ndcg_at_k(results, k)
        
        metrics['mrr'] = RetrievalMetrics.mean_reciprocal_rank(results)
        
        return metrics


class GenerationMetrics:
    """Metrics for evaluating answer generation quality."""
    
    @staticmethod
    def calculate_bleu(reference: str, candidate: str, n: int = 4) -> float:
        """
        Calculate BLEU score (simplified version).
        
        Args:
            reference: Ground truth answer
            candidate: Generated answer
            n: Maximum n-gram order
            
        Returns:
            BLEU score (0.0 to 1.0)
        """
        # Simple token-based BLEU
        ref_tokens = reference.lower().split()
        cand_tokens = candidate.lower().split()
        
        if len(cand_tokens) == 0:
            return 0.0
        
        # Calculate precision for each n-gram
        precisions = []
        for i in range(1, n + 1):
            ref_ngrams = defaultdict(int)
            cand_ngrams = defaultdict(int)
            
            # Count n-grams in reference
            for j in range(len(ref_tokens) - i + 1):
                ngram = tuple(ref_tokens[j:j+i])
                ref_ngrams[ngram] += 1
            
            # Count n-grams in candidate
            for j in range(len(cand_tokens) - i + 1):
                ngram = tuple(cand_tokens[j:j+i])
                cand_ngrams[ngram] += 1
            
            # Calculate clipped precision
            matches = sum(min(ref_ngrams[ng], cand_ngrams[ng]) for ng in cand_ngrams)
            total = len(cand_tokens) - i + 1
            precisions.append(matches / total if total > 0 else 0.0)
        
        # Brevity penalty
        bp = min(1.0, len(cand_tokens) / len(ref_tokens)) if len(ref_tokens) > 0 else 0.0
        
        # Calculate BLEU
        bleu = bp * (np.prod(precisions) ** (1.0 / n))
        return bleu
    
    @staticmethod
    def calculate_rouge_l(reference: str, candidate: str) -> float:
        """
        Calculate ROUGE-L score (longest common subsequence).
        
        Args:
            reference: Ground truth answer
            candidate: Generated answer
            
        Returns:
            ROUGE-L score (0.0 to 1.0)
        """
        ref_tokens = reference.lower().split()
        cand_tokens = candidate.lower().split()
        
        # Calculate LCS length
        m, n = len(ref_tokens), len(cand_tokens)
        lcs = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if ref_tokens[i-1] == cand_tokens[j-1]:
                    lcs[i][j] = lcs[i-1][j-1] + 1
                else:
                    lcs[i][j] = max(lcs[i-1][j], lcs[i][j-1])
        
        lcs_length = lcs[m][n]
        
        if len(ref_tokens) == 0 or len(cand_tokens) == 0:
            return 0.0
        
        precision = lcs_length / len(cand_tokens)
        recall = lcs_length / len(ref_tokens)
        
        if precision + recall == 0:
            return 0.0
        
        f1 = 2 * precision * recall / (precision + recall)
        return f1
    
    @staticmethod
    def semantic_similarity(reference: str, candidate: str, 
                           embedding_model=None) -> float:
        """
        Calculate semantic similarity using embeddings.
        
        Args:
            reference: Ground truth answer
            candidate: Generated answer
            embedding_model: Sentence transformer model (optional)
            
        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        if embedding_model is None:
            # Fallback to simple word overlap
            ref_words = set(reference.lower().split())
            cand_words = set(candidate.lower().split())
            if len(ref_words) == 0 or len(cand_words) == 0:
                return 0.0
            intersection = ref_words & cand_words
            union = ref_words | cand_words
            return len(intersection) / len(union) if union else 0.0
        
        # Use embedding model if provided
        try:
            ref_embedding = embedding_model.encode([reference])[0]
            cand_embedding = embedding_model.encode([candidate])[0]
            similarity = np.dot(ref_embedding, cand_embedding) / (
                np.linalg.norm(ref_embedding) * np.linalg.norm(cand_embedding)
            )
            return float(similarity)
        except Exception:
            return 0.0
    
    @staticmethod
    def calculate_all_metrics(reference: str, 
                              candidate: str,
                              embedding_model=None) -> Dict[str, float]:
        """
        Calculate all generation metrics.
        
        Args:
            reference: Ground truth answer
            candidate: Generated answer
            embedding_model: Optional embedding model for semantic similarity
            
        Returns:
            Dictionary of metric names and values
        """
        metrics = {
            'bleu': GenerationMetrics.calculate_bleu(reference, candidate),
            'rouge_l': GenerationMetrics.calculate_rouge_l(reference, candidate),
            'semantic_similarity': GenerationMetrics.semantic_similarity(
                reference, candidate, embedding_model
            )
        }
        return metrics


class SystemMetrics:
    """Metrics for evaluating system performance."""
    
    @staticmethod
    def measure_latency(func, *args, **kwargs) -> Tuple[Any, float]:
        """
        Measure execution latency of a function.
        
        Args:
            func: Function to measure
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            Tuple of (result, latency_in_seconds)
        """
        start_time = time.time()
        result = func(*args, **kwargs)
        latency = time.time() - start_time
        return result, latency
    
    @staticmethod
    def calculate_percentiles(latencies: List[float], 
                             percentiles: List[float] = [50, 95, 99]) -> Dict[str, float]:
        """
        Calculate latency percentiles.
        
        Args:
            latencies: List of latency measurements
            percentiles: List of percentile values to calculate
            
        Returns:
            Dictionary of percentile names and values
        """
        if not latencies:
            return {}
        
        sorted_latencies = sorted(latencies)
        metrics = {}
        
        for p in percentiles:
            index = int(len(sorted_latencies) * p / 100)
            index = min(index, len(sorted_latencies) - 1)
            metrics[f'p{p}_latency'] = sorted_latencies[index]
        
        metrics['avg_latency'] = np.mean(latencies)
        metrics['min_latency'] = np.min(latencies)
        metrics['max_latency'] = np.max(latencies)
        
        return metrics


class RAGEvaluator:
    """Comprehensive RAG system evaluator."""
    
    def __init__(self, rag_system, embedding_model=None):
        """
        Initialize evaluator.
        
        Args:
            rag_system: RAG system instance to evaluate
            embedding_model: Optional embedding model for semantic similarity
        """
        self.rag_system = rag_system
        self.embedding_model = embedding_model
        self.retrieval_metrics = RetrievalMetrics()
        self.generation_metrics = GenerationMetrics()
        self.system_metrics = SystemMetrics()
    
    def evaluate_query(self, 
                      query: str,
                      ground_truth_answer: Optional[str] = None,
                      relevant_chunk_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Evaluate a single query.
        
        Args:
            query: User query
            ground_truth_answer: Optional ground truth answer
            relevant_chunk_ids: Optional list of relevant chunk IDs
            
        Returns:
            Dictionary with all evaluation metrics
        """
        # Measure total latency
        result, total_latency = self.system_metrics.measure_latency(
            self.rag_system.answer_question, query
        )
        
        # Extract retrieved chunks
        chunks = result.get('sources', [])
        
        # Mark chunks as relevant if IDs provided
        retrieval_results = []
        for chunk in chunks:
            chunk_id = chunk.get('index', '') or chunk.get('title', '')
            is_relevant = chunk_id in (relevant_chunk_ids or [])
            retrieval_results.append(RetrievalResult(
                content=chunk.get('preview', '') or chunk.get('content', ''),
                metadata=chunk,
                score=chunk.get('relevance', 0.0) or chunk.get('relevance_score', 0.0),
                is_relevant=is_relevant
            ))
        
        # Calculate retrieval metrics
        total_relevant = len(relevant_chunk_ids) if relevant_chunk_ids else 0
        retrieval_metrics = self.retrieval_metrics.calculate_all_metrics(
            retrieval_results, total_relevant
        )
        
        # Calculate generation metrics if ground truth available
        generation_metrics = {}
        if ground_truth_answer:
            answer = result.get('answer', '')
            generation_metrics = self.generation_metrics.calculate_all_metrics(
                ground_truth_answer, answer, self.embedding_model
            )
        
        # Combine all metrics
        evaluation = {
            'query': query,
            'retrieval_metrics': retrieval_metrics,
            'generation_metrics': generation_metrics,
            'system_metrics': {
                'total_latency': total_latency,
                'chunks_retrieved': len(chunks)
            },
            'answer': result.get('answer', ''),
            'sources': chunks
        }
        
        return evaluation
    
    def evaluate_dataset(self, 
                        queries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluate on a dataset of queries.
        
        Args:
            queries: List of query dictionaries with keys:
                - 'query': The question
                - 'ground_truth_answer': Optional ground truth
                - 'relevant_chunk_ids': Optional relevant chunk IDs
        
        Returns:
            Dictionary with aggregate metrics
        """
        all_evaluations = []
        latencies = []
        
        print(f"Evaluating {len(queries)} queries...")
        
        for i, query_data in enumerate(queries, 1):
            print(f"Processing query {i}/{len(queries)}: {query_data['query'][:50]}...")
            
            evaluation = self.evaluate_query(
                query=query_data['query'],
                ground_truth_answer=query_data.get('ground_truth_answer'),
                relevant_chunk_ids=query_data.get('relevant_chunk_ids')
            )
            
            all_evaluations.append(evaluation)
            latencies.append(evaluation['system_metrics']['total_latency'])
        
        # Aggregate metrics
        aggregate = self._aggregate_metrics(all_evaluations, latencies)
        
        return {
            'individual_evaluations': all_evaluations,
            'aggregate_metrics': aggregate,
            'total_queries': len(queries)
        }
    
    def _aggregate_metrics(self, 
                          evaluations: List[Dict[str, Any]],
                          latencies: List[float]) -> Dict[str, float]:
        """Aggregate metrics across all evaluations."""
        # Aggregate retrieval metrics
        retrieval_keys = ['precision@5', 'precision@10', 'recall@5', 'recall@10', 
                         'ndcg@5', 'ndcg@10', 'mrr']
        retrieval_agg = {}
        
        for key in retrieval_keys:
            values = [e['retrieval_metrics'].get(key, 0.0) for e in evaluations]
            retrieval_agg[f'avg_{key}'] = np.mean(values)
            retrieval_agg[f'std_{key}'] = np.std(values)
        
        # Aggregate generation metrics
        generation_keys = ['bleu', 'rouge_l', 'semantic_similarity']
        generation_agg = {}
        
        for key in generation_keys:
            values = [e['generation_metrics'].get(key, 0.0) 
                     for e in evaluations if key in e['generation_metrics']]
            if values:
                generation_agg[f'avg_{key}'] = np.mean(values)
                generation_agg[f'std_{key}'] = np.std(values)
        
        # System metrics
        system_agg = self.system_metrics.calculate_percentiles(latencies)
        
        return {
            **retrieval_agg,
            **generation_agg,
            **system_agg
        }
    
    def save_evaluation_results(self, 
                               results: Dict[str, Any],
                               output_path: str) -> None:
        """Save evaluation results to JSON file."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"✅ Evaluation results saved to {output_path}")


def main():
    """Example usage of the evaluation framework."""
    print("🚀 RAG Evaluation Metrics Framework")
    print("=" * 60)
    
    # Example: Create a simple test dataset
    test_queries = [
        {
            'query': 'How to scale databases?',
            'ground_truth_answer': 'Database scaling involves horizontal and vertical scaling...',
            'relevant_chunk_ids': ['chunk_1', 'chunk_2']
        },
        {
            'query': 'What is microservices architecture?',
            'ground_truth_answer': 'Microservices is an architectural pattern...',
            'relevant_chunk_ids': ['chunk_3', 'chunk_4']
        }
    ]
    
    print("\n📊 Example Evaluation Dataset:")
    for i, q in enumerate(test_queries, 1):
        print(f"{i}. {q['query']}")
    
    print("\n💡 To use this framework:")
    print("1. Create your RAG system instance")
    print("2. Create evaluator: evaluator = RAGEvaluator(rag_system)")
    print("3. Evaluate: results = evaluator.evaluate_dataset(test_queries)")
    print("4. Save results: evaluator.save_evaluation_results(results, 'results.json')")
    
    print("\n📈 Metrics Available:")
    print("- Retrieval: Precision@K, Recall@K, MRR, NDCG@K")
    print("- Generation: BLEU, ROUGE-L, Semantic Similarity")
    print("- System: Latency (P50, P95, P99), Throughput")
    
    print("\n🎉 Evaluation framework ready to use!")


if __name__ == "__main__":
    main()




