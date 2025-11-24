# Public Retrieval/RAG Datasets

Quick reference for document+query datasets you can load from Hugging Face to evaluate the RAG pipeline. Sizes are approximate.

| Dataset | Corpus Size | Query Split Size | Relevance Labels | Notes |
| --- | --- | --- | --- | --- |
| MS MARCO Passage (`ms_marco`) | ~8.8M passages | ~1M train, 7K dev/test | Bing search relevance grades | Large general web QA benchmark; doc version has ~3.2M docs |
| NQ Open (`nq_open`) | Wikipedia (~21M passages) | 79K train, 8.7K dev/test | 1 relevant passage per question | Google Natural Questions reformatted for open-domain QA |
| HotpotQA (`hotpot_qa`) | ~5M Wikipedia paragraphs | 90K train, 7.4K dev/test | 2 supporting passages/question | Multi-hop reasoning requirement |
| BEIR FiQA (`beir/fiqa`) | 6,178 docs | 648 queries | 12,396 q-d pairs | Finance/QA domain |
| BEIR SciFact (`beir/scifact`) | 5,183 abstracts | 300 claims | 5,183 labels | Scientific fact verification |
| BEIR TREC-COVID (`beir/trec-covid`) | 171K docs | 200 queries | ~69K labels | Biomedical/COVID literature |
| WikiQA (`wiki_qa`) | 29K candidate sentences | 3,047 questions | Sentence-level binary labels | Compact Wikipedia QA benchmark |
| TREC (`trec`) | 5.5K train, 500 test questions | same | graded per question | Classic factoid question set |
| DBPedia14 (`dbpedia14`) | 342K entries | 400K labels | class labels (entities) | Can be adapted for retrieval/classification |
| Mr.TyDi (`castorini/mr-tydi`) | 3.2M docs across 11 langs | ~330K queries | relevance files per lang | Multilingual retrieval |
| Multi-News (`multi_news`) | 56K multi-doc sets | same | summaries per set | Useful for multi-document aggregation |
| GovReport (`gov_report`) | 19.5K reports | same | summaries | Long-document summarization/QA |
| ELI5 (`eli5`) | 270K questions | same | long answers referencing web sources | Good for long-form QA |

## Usage Tips

1. Load with `datasets.load_dataset("<name>")` (e.g., `datasets.load_dataset("beir/fiqa", "default")`).
2. Index the `corpus`/`documents` split with your chunker + embedder.
3. For each labeled query, retrieve top-K docs and compute Precision@K, Recall@K, MRR, NDCG, etc.
4. Start with a smaller BEIR subset (FiQA, SciFact) to validate metrics before tackling MS MARCO scale.
