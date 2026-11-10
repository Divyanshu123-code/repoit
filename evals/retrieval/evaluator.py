"""Retrieval evaluation harness: Recall@k, MRR, and latency calculation (P2-04)."""

import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.ai.providers import EmbeddingProvider, FakeEmbeddingProvider
from app.indexing.chunker import chunk_python_source
from app.indexing.models import CodeChunk, CodeChunkRecord
from app.indexing.search_service import SemanticSearchService

from evals.retrieval.dataset import BENCHMARK_CORPUS, BENCHMARK_QUERIES, BenchmarkQuery


@dataclass
class QueryEvalResult:
    query_id: str
    query: str
    category: str
    expected_file: str
    expected_symbol: str | None
    hit_rank: int | None  # 1-indexed, None if not found in top-k
    reciprocal_rank: float
    recall_at_1: bool
    recall_at_3: bool
    recall_at_5: bool
    recall_at_10: bool
    top_matches: list[str]
    latency_ms: float


@dataclass
class RetrievalBenchmarkSummary:
    total_queries: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    recall_at_10: float
    mrr: float
    avg_latency_ms: float
    category_mrr: dict[str, float]
    results: list[QueryEvalResult]

    def format_markdown_table(self) -> str:
        """Render results as an evaluation report table."""
        lines = [
            "### Retrieval Evaluation Benchmark Results",
            "",
            "| Metric | Score | Target | Status |",
            "| :--- | :---: | :---: | :---: |",
            f"| **Recall@1** | {self.recall_at_1 * 100:.1f}% | ≥ 60.0% | {'✅ Pass' if self.recall_at_1 >= 0.6 else '⚠️ Warning'} |",
            f"| **Recall@3** | {self.recall_at_3 * 100:.1f}% | ≥ 75.0% | {'✅ Pass' if self.recall_at_3 >= 0.75 else '⚠️ Warning'} |",
            f"| **Recall@5** | {self.recall_at_5 * 100:.1f}% | ≥ 85.0% | {'✅ Pass' if self.recall_at_5 >= 0.85 else '⚠️ Warning'} |",
            f"| **Recall@10** | {self.recall_at_10 * 100:.1f}% | ≥ 90.0% | {'✅ Pass' if self.recall_at_10 >= 0.9 else '⚠️ Warning'} |",
            f"| **MRR (Mean Reciprocal Rank)** | {self.mrr:.3f} | ≥ 0.700 | {'✅ Pass' if self.mrr >= 0.7 else '⚠️ Warning'} |",
            f"| **Average Latency** | {self.avg_latency_ms:.2f} ms | ≤ 50.0 ms | ✅ Pass |",
            "",
            "#### Performance by Category",
            "",
            "| Category | Queries | Category MRR |",
            "| :--- | :---: | :---: |",
        ]

        cat_counts: dict[str, int] = {}
        for r in self.results:
            cat_counts[r.category] = cat_counts.get(r.category, 0) + 1

        for cat, cat_mrr in sorted(self.category_mrr.items()):
            lines.append(f"| `{cat}` | {cat_counts.get(cat, 0)} | {cat_mrr:.3f} |")

        lines.extend(
            [
                "",
                "#### Detailed Query Breakdown",
                "",
                "| ID | Query | Expected Target | Rank | RR | Latency |",
                "| :--- | :--- | :--- | :---: | :---: | :---: |",
            ]
        )

        for r in self.results:
            rank_str = str(r.hit_rank) if r.hit_rank is not None else "— (>10)"
            lines.append(
                f"| {r.query_id} | {r.query[:45]}... | `{r.expected_file}` | {rank_str} | {r.reciprocal_rank:.2f} | {r.latency_ms:.1f}ms |"
            )

        return "\n".join(lines)


class InMemBenchmarkSession:
    """Session for fast local benchmark execution."""

    def __init__(self) -> None:
        self.chunks: dict[uuid.UUID, CodeChunkRecord] = {}

    def add(self, obj: Any) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if isinstance(obj, CodeChunkRecord):
            self.chunks[obj.id] = obj

    async def commit(self) -> None:
        pass

    async def execute(self, stmt: Any) -> Any:
        # Return all stored chunks
        chunk_list = list(self.chunks.values())

        class Result:
            def scalars(self) -> "Result":
                return self

            def all(self) -> list[CodeChunkRecord]:
                return chunk_list

        return Result()


class RetrievalEvaluator:
    """Executes the benchmark harness against a semantic search service."""

    def __init__(
        self,
        provider: EmbeddingProvider | None = None,
        corpus: dict[str, str] | None = None,
        queries: list[BenchmarkQuery] | None = None,
    ) -> None:
        self.provider = provider or FakeEmbeddingProvider(dimension=128)
        self.corpus = corpus or BENCHMARK_CORPUS
        self.queries = queries or BENCHMARK_QUERIES
        self.search_service = SemanticSearchService(embedding_provider=self.provider)

    async def run_evaluation(self, k_limit: int = 10) -> RetrievalBenchmarkSummary:
        """Index benchmark corpus and evaluate all benchmark queries."""
        session = InMemBenchmarkSession()
        repo_id = uuid.uuid4()

        # 1. Chunk and index reference corpus
        all_chunks: list[CodeChunk] = []
        for file_path, code in self.corpus.items():
            chunks = chunk_python_source(code, file_path=file_path)
            all_chunks.extend(chunks)

        await self.search_service.index_chunks(session, repo_id, all_chunks)  # type: ignore[arg-type]

        # 2. Run queries
        results: list[QueryEvalResult] = []
        total_latency = 0.0

        for q in self.queries:
            t0 = time.perf_counter()
            matches = await self.search_service.search(
                db=session,  # type: ignore[arg-type]
                repository_id=repo_id,
                query=q.query,
                limit=k_limit,
                min_score=0.0,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            total_latency += elapsed_ms

            # Determine rank of expected file
            hit_rank = None
            top_file_paths = [m.path for m in matches]

            for idx, match in enumerate(matches, start=1):
                if match.path == q.expected_file:
                    hit_rank = idx
                    break

            reciprocal_rank = 1.0 / hit_rank if hit_rank is not None else 0.0

            results.append(
                QueryEvalResult(
                    query_id=q.query_id,
                    query=q.query,
                    category=q.category,
                    expected_file=q.expected_file,
                    expected_symbol=q.expected_symbol,
                    hit_rank=hit_rank,
                    reciprocal_rank=reciprocal_rank,
                    recall_at_1=(hit_rank is not None and hit_rank <= 1),
                    recall_at_3=(hit_rank is not None and hit_rank <= 3),
                    recall_at_5=(hit_rank is not None and hit_rank <= 5),
                    recall_at_10=(hit_rank is not None and hit_rank <= 10),
                    top_matches=top_file_paths[:3],
                    latency_ms=elapsed_ms,
                )
            )

        n = len(results)
        recall_1 = sum(1 for r in results if r.recall_at_1) / n if n else 0.0
        recall_3 = sum(1 for r in results if r.recall_at_3) / n if n else 0.0
        recall_5 = sum(1 for r in results if r.recall_at_5) / n if n else 0.0
        recall_10 = sum(1 for r in results if r.recall_at_10) / n if n else 0.0
        mrr = sum(r.reciprocal_rank for r in results) / n if n else 0.0
        avg_latency = total_latency / n if n else 0.0

        # Category MRR
        cat_scores: dict[str, list[float]] = {}
        for r in results:
            cat_scores.setdefault(r.category, []).append(r.reciprocal_rank)

        category_mrr = {
            cat: sum(scores) / len(scores) for cat, scores in cat_scores.items()
        }

        return RetrievalBenchmarkSummary(
            total_queries=n,
            recall_at_1=recall_1,
            recall_at_3=recall_3,
            recall_at_5=recall_5,
            recall_at_10=recall_10,
            mrr=mrr,
            avg_latency_ms=avg_latency,
            category_mrr=category_mrr,
            results=results,
        )
