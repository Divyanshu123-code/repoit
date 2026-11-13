"""RAG assistant service with source citations and abstention threshold (P2-05).

Enforces:
- AC: Unanswerable question yields "not enough evidence".
- Hard Rule 4: Never log or send secrets/tokens. Redact before any LLM call.
- Hard Rule 5: Labelled by source ('llm_generated' for answer, 'static' for citations).
- Hard Rule 7: LLM/embedding calls go ONLY through app/ai/providers/.
"""

import uuid

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers import LLMProvider, get_llm_provider
from app.ai.redaction import redact_secrets
from app.core.config import get_settings
from app.indexing.models import SearchResultItem
from app.indexing.search_service import SemanticSearchService

ABSTENTION_MESSAGE = "Not enough evidence in the codebase to answer this question."

RAG_SYSTEM_PROMPT = """You are RepoPilot AI, an expert code understanding assistant.
Answer the user's question strictly based on the provided code excerpts.
Guidelines:
1. Ground every statement in the evidence. Include bracketed citations in the format [file_path:start_line-end_line] or [file_path:start_line].
2. Do not hallucinate or guess functions/methods not present in the context.
3. If the provided code snippets do not contain sufficient evidence to answer the question accurately, you must respond with:
"I do not have enough evidence in the codebase to answer this question."
"""


class RAGCitation(BaseModel):
    """Citation pointing to verified source code chunk."""

    file_path: str
    start_line: int
    end_line: int
    content: str
    symbol_name: str | None = None
    similarity_score: float = 0.0
    source: str = Field(default="static", description="Rule 5: labelled static")


class RAGAnswer(BaseModel):
    """Synthesized RAG response with grounded citations and source metadata."""

    question: str
    answer: str
    abstained: bool
    citations: list[RAGCitation] = Field(default_factory=list)
    source: str = Field(default="llm_generated", description="Rule 5: labelled llm_generated")
    model_version: str


class RAGService:
    """Orchestrates retrieval and grounded generation with explicit abstention."""

    def __init__(
        self,
        search_service: SemanticSearchService | None = None,
        llm_provider: LLMProvider | None = None,
        abstention_threshold: float | None = None,
    ) -> None:
        settings = get_settings()
        self.search_service = search_service or SemanticSearchService()
        self.llm = llm_provider or get_llm_provider()
        self.abstention_threshold = (
            abstention_threshold
            if abstention_threshold is not None
            else settings.RAG_ABSTENTION_THRESHOLD
        )

    def _format_context(self, matches: list[SearchResultItem]) -> str:
        """Format retrieved code matches into an annotated context block."""
        blocks: list[str] = []
        for i, m in enumerate(matches, start=1):
            header = f"[{m.path}:{m.start_line}-{m.end_line}]"
            if m.symbol_name:
                header += f" (symbol: {m.symbol_name})"
            blocks.append(f"--- Evidence {i}: {header} ---\n{m.content}")
        return "\n\n".join(blocks)

    async def answer_question(
        self,
        db: AsyncSession,
        repository_id: uuid.UUID,
        question: str,
        max_citations: int = 5,
        min_score: float | None = None,
    ) -> RAGAnswer:
        """Retrieve relevant context and answer question with citations or abstain."""
        threshold = min_score if min_score is not None else self.abstention_threshold

        # 1. Retrieve matching chunks from vector store
        matches = await self.search_service.search(
            db=db,
            repository_id=repository_id,
            query=question,
            limit=max_citations,
            min_score=threshold,
        )

        # 2. Check for empty or low-relevance results -> Abstain
        if not matches:
            return RAGAnswer(
                question=question,
                answer=ABSTENTION_MESSAGE,
                abstained=True,
                citations=[],
                source="llm_generated",
                model_version=self.llm.model_name,
            )

        # 3. Assemble prompt with citations instructions (scrubbed per Hard Rule 4)
        clean_context = redact_secrets(self._format_context(matches))
        clean_question = redact_secrets(question)
        user_message = (
            f"Codebase Evidence:\n{clean_context}\n\n"
            f"Question: {clean_question}\n\n"
            f"Please provide an answer referencing the evidence with [file_path:line] citations:"
        )

        messages = [
            {"role": "system", "content": RAG_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        # 4. Generate LLM completion
        raw_completion = await self.llm.generate_completion(messages, temperature=0.0)

        # 5. Check if model abstained in completion
        lower_completion = raw_completion.lower()
        is_abstained = (
            "not enough evidence" in lower_completion
            or "not sufficient evidence" in lower_completion
        )

        citations = [
            RAGCitation(
                file_path=m.path,
                start_line=m.start_line,
                end_line=m.end_line,
                content=m.content,
                symbol_name=m.symbol_name,
                similarity_score=m.score,
                source="static",
            )
            for m in matches
        ]

        return RAGAnswer(
            question=question,
            answer=raw_completion,
            abstained=is_abstained,
            citations=citations if not is_abstained else [],
            source="llm_generated",
            model_version=self.llm.model_name,
        )
