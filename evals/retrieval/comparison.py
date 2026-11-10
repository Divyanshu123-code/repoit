"""Comparative evaluation of embedding models and chunk configurations (P2-07)."""

import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.ai.providers import FakeEmbeddingProvider
from app.indexing.chunker import CodeChunker
from app.indexing.models import ChunkStrategy, CodeChunk, CodeChunkRecord
from app.indexing.search_service import SemanticSearchService

from evals.retrieval.dataset import BENCHMARK_CORPUS, BENCHMARK_QUERIES, BenchmarkQuery


@dataclass
class ConfigEvalSummary:
    config_name: str
    chunk_size: int
    strategy_description: str
    embedding_dimension: int
    total_chunks: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    recall_at_10: float
    mrr: float
    avg_latency_ms: float


class InMemComparisonSession:
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
        chunk_list = list(self.chunks.values())

        class Result:
            def scalars(self) -> "Result":
                return self

            def all(self) -> list[CodeChunkRecord]:
                return chunk_list

        return Result()


class RetrievalComparisonExperiment:
    """Executes comparative evaluation across multiple chunk sizes and embedding dimensions."""

    def __init__(
        self,
        corpus: dict[str, str] | None = None,
        queries: list[BenchmarkQuery] | None = None,
    ) -> None:
        self.corpus = corpus or BENCHMARK_CORPUS
        self.queries = queries or BENCHMARK_QUERIES

    def _chunk_fixed_window(
        self, code: str, file_path: str, max_chars: int
    ) -> list[CodeChunk]:
        """Pure line-based sliding window chunking without symbol awareness."""
        lines = code.splitlines(keepends=True)
        chunks: list[CodeChunk] = []
        i = 0
        total_lines = len(lines)
        while i < total_lines:
            curr_lines: list[str] = []
            curr_chars = 0
            j = i
            while j < total_lines:
                line_len = len(lines[j])
                if curr_chars + line_len > max_chars and curr_lines:
                    break
                curr_lines.append(lines[j])
                curr_chars += line_len
                j += 1
            chunk_content = "".join(curr_lines).strip()
            if chunk_content:
                chunks.append(
                    CodeChunk(
                        file_path=file_path,
                        start_line=i + 1,
                        end_line=j,
                        content=chunk_content,
                        strategy=ChunkStrategy.WINDOW_FALLBACK,
                        context_header=f"# File: {file_path}\n",
                        char_count=len(chunk_content),
                        estimated_tokens=max(1, len(chunk_content) // 4),
                        content_sha256=f"hash_{file_path}_{i}",
                    )
                )
            step = max(1, (j - i) - 2)
            if j >= total_lines:
                break
            i += step
        return chunks

    async def evaluate_configuration(
        self,
        config_name: str,
        chunk_size: int,
        is_symbol_aware: bool,
        dimension: int,
    ) -> ConfigEvalSummary:
        """Run benchmark for a single configuration."""
        session = InMemComparisonSession()
        repo_id = uuid.uuid4()
        provider = FakeEmbeddingProvider(
            dimension=dimension, model_name=f"emb-{dimension}"
        )
        service = SemanticSearchService(embedding_provider=provider)

        # 1. Chunk corpus according to configuration
        all_chunks: list[CodeChunk] = []
        if is_symbol_aware:
            chunker = CodeChunker(max_chunk_chars=chunk_size)
            for path, code in self.corpus.items():
                all_chunks.extend(chunker.chunk_module(code, file_path=path))
        else:
            for path, code in self.corpus.items():
                all_chunks.extend(
                    self._chunk_fixed_window(code, file_path=path, max_chars=chunk_size)
                )

        await service.index_chunks(session, repo_id, all_chunks)  # type: ignore[arg-type]

        # 2. Query execution
        reciprocal_ranks: list[float] = []
        r1_hits = 0
        r3_hits = 0
        r5_hits = 0
        r10_hits = 0
        total_latency = 0.0

        for q in self.queries:
            t0 = time.perf_counter()
            matches = await service.search(
                db=session,  # type: ignore[arg-type]
                repository_id=repo_id,
                query=q.query,
                limit=10,
                min_score=0.0,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            total_latency += elapsed_ms

            hit_rank = None
            for idx, match in enumerate(matches, start=1):
                if match.path == q.expected_file:
                    hit_rank = idx
                    break

            if hit_rank is not None:
                rr = 1.0 / hit_rank
                if hit_rank <= 1:
                    r1_hits += 1
                if hit_rank <= 3:
                    r3_hits += 1
                if hit_rank <= 5:
                    r5_hits += 1
                if hit_rank <= 10:
                    r10_hits += 1
            else:
                rr = 0.0

            reciprocal_ranks.append(rr)

        n = len(self.queries)
        return ConfigEvalSummary(
            config_name=config_name,
            chunk_size=chunk_size,
            strategy_description="Symbol-aware (AST)"
            if is_symbol_aware
            else "Fixed window (no AST)",
            embedding_dimension=dimension,
            total_chunks=len(all_chunks),
            recall_at_1=r1_hits / n,
            recall_at_3=r3_hits / n,
            recall_at_5=r5_hits / n,
            recall_at_10=r10_hits / n,
            mrr=sum(reciprocal_ranks) / n,
            avg_latency_ms=total_latency / n,
        )

    async def run_all_comparisons(self) -> list[ConfigEvalSummary]:
        """Run evaluation across all designated configurations."""
        configs = [
            (
                "Config 1 (Symbol-aware 1500 chars, dim 128) [Selected Champion]",
                1500,
                True,
                128,
            ),
            ("Config 2 (Symbol-aware 500 chars, dim 128)", 500, True, 128),
            ("Config 3 (Pure sliding window 1000 chars, no AST)", 1000, False, 128),
            ("Config 4 (Pure sliding window 400 chars, no AST)", 400, False, 128),
            ("Config 5 (Symbol-aware 1500 chars, dim 64)", 1500, True, 64),
        ]

        summaries: list[ConfigEvalSummary] = []
        for name, chunk_size, is_sym, dim in configs:
            summary = await self.evaluate_configuration(name, chunk_size, is_sym, dim)
            summaries.append(summary)

        return summaries
