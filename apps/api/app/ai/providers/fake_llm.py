"""Fake/mock LLM provider for deterministic offline testing (P2-05, Hard Rule 7)."""

import re

from app.ai.providers.base import LLMProvider
from app.ai.redaction import redact_secrets


class FakeLLMProvider(LLMProvider):
    """Deterministic LLM mock that attributes citations and tests abstention."""

    def __init__(
        self,
        model_name: str = "fake-gpt-4o-mini",
        canned_responses: dict[str, str] | None = None,
    ) -> None:
        self._model_name = model_name
        self._canned_responses = canned_responses or {}
        self.captured_messages: list[list[dict[str, str]]] = []

    @property
    def model_name(self) -> str:
        return self._model_name

    async def generate_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 1000,
    ) -> str:
        # Scrub incoming messages prior to processing (Hard Rule 4)
        scrubbed_messages: list[dict[str, str]] = [
            {"role": m["role"], "content": redact_secrets(m["content"])} for m in messages
        ]
        self.captured_messages.append(scrubbed_messages)

        full_prompt = " ".join(m["content"] for m in scrubbed_messages)

        # Check canned responses
        for trigger, response in self._canned_responses.items():
            if trigger in full_prompt:
                return response

        # Check if prompt is a Debug Assistant request
        if "Senior Debugging Assistant" in full_prompt or "VERIFIED EVIDENCE" in full_prompt:
            return (
                "PROBABLE ROOT CAUSES:\n"
                "- Default argument evaluation occurs at module import time in Python, creating shared state\n"
                "- Function call in parameter default creates unexpected dependency cycles\n\n"
                "RECOMMENDED FIX:\n"
                "Use Annotated dependency injection pattern or set default to None and initialize inside the function body.\n\n"
                "CODE DIFF:\n"
                "```python\n"
                "-def get_data(session: Session = Depends(get_db)):\n"
                "+DatabaseSession = Annotated[Session, Depends(get_db)]\n"
                "+def get_data(session: DatabaseSession = None):\n"
                "```\n\n"
                "REGRESSION RISKS:\n"
                "- Callers expecting explicit parameter passing must adhere to type annotation\n"
                "- Downstream modules depending on this function must not override default argument positional semantics\n\n"
                "VERIFICATION PLAN:\n"
                "- Run `ruff check app/core/db.py` to verify B008 is resolved\n"
                "- Run `pytest tests/test_db.py` to ensure database connectivity tests pass"
            )

        # Check if prompt is a Test Generation request
        if "Test Generation Agent" in full_prompt or "test function" in full_prompt.lower():
            return (
                "```python\n"
                "import pytest\n\n"
                "def test_repo_file_filter_symlinks():\n"
                '    """Verify that path traversal symlinks are rejected."""\n'
                "    from app.repos.filter import RepoFileFilter, FilterReason\n"
                "    filter_svc = RepoFileFilter()\n"
                "    res = filter_svc.check_path('../secret/key.pem')\n"
                "    assert res.is_rejected is True\n"
                "    assert res.reason == FilterReason.UNSAFE_SYMLINK\n"
                "```"
            )

        # Check if prompt is a Conversational ChatGPT assistant request
        if (
            "ChatGPT expert for this GitHub repository" in full_prompt
            or "conversational ChatGPT companion" in full_prompt
            or "VERIFIED REPOSITORY INTELLIGENCE" in full_prompt
        ):
            citations = re.findall(r"\[([a-zA-Z0-9_\-\./]+:\d+(?:-\d+)?)\]", full_prompt)
            citation_str = " ".join(f"[{c}]" for c in citations[:4]) if citations else ""

            user_query = ""
            for m in reversed(scrubbed_messages):
                if m.get("role") == "user":
                    user_query = m.get("content", "").lower()
                    break

            # Extract repository profile attributes
            repo_name = "this repository"
            repo_match = re.search(r"### Repository Profile:\s*([^\n]+)", full_prompt)
            if repo_match:
                repo_name = repo_match.group(1).strip()

            scale_info = ""
            scale_match = re.search(r"- Scale:\s*([^\n]+)", full_prompt)
            if scale_match:
                scale_info = scale_match.group(1).strip()

            quality_info = ""
            quality_match = re.search(r"- Quality Metrics:\s*([^\n]+)", full_prompt)
            if quality_match:
                quality_info = quality_match.group(1).strip()

            manifest_content = ""
            manifest_match = re.search(
                r"#### Complete Repository Module Manifest:\s*\n(.*?)(?=\n#### Top Largest Modules|\n#### Defect Risk|\Z)",
                full_prompt,
                re.DOTALL,
            )
            if manifest_match:
                manifest_content = manifest_match.group(1).strip()

            # 1. Broad repository overview & purpose queries
            is_overview_query = any(
                k in user_query
                for k in [
                    "tell me about",
                    "about this project",
                    "about this repo",
                    "purpose",
                    "what is this",
                    "what does this project do",
                    "what does this repo do",
                    "overview",
                    "architecture",
                    "explain the project",
                    "explain this repo",
                    "explain the repo",
                    "how does it work",
                    "describe",
                ]
            )

            if is_overview_query:
                # Infer domain and core mission based on repository name & files
                domain_desc = ""
                name_lower = repo_name.lower()
                if "bookurtime" in name_lower or "book" in name_lower:
                    domain_desc = (
                        f"**{repo_name}** is an asynchronous appointment scheduling and service booking platform. "
                        "It provides a complete end-to-end booking flow: managing service provider profiles, "
                        "computing available time slots without double-booking collisions, handling customer reservations, "
                        "and dispatching appointment reminders."
                    )
                elif "mangaverse" in name_lower or "manga" in name_lower:
                    domain_desc = (
                        f"**{repo_name}** is a digital manga reading, discovery, and chapter tracking application. "
                        "It features catalog browsing, user library management, reading progress synchronization, "
                        "and content ingestion APIs."
                    )
                elif "repoit" in name_lower or "repopilot" in name_lower:
                    domain_desc = (
                        f"**{repo_name}** is an intelligent code understanding and quality intelligence platform. "
                        "It connects to Python repositories, parses code semantics using Tree-sitter AST, provides grounded "
                        "conversational RAG with bracketed line citations, predicts defect risk with ML models, and builds dependency graphs."
                    )
                else:
                    domain_desc = (
                        f"**{repo_name}** is a modular Python application designed for scalable backend services. "
                        "It implements structured request routing, schema-validated inputs, service-layer business logic, "
                        "and automated test coverage."
                    )

                manifest_section = ""
                if manifest_content:
                    manifest_section = f"### 🏗️ File-by-File Architecture Breakdown\n\n{manifest_content}\n\n"

                flow_section = (
                    "### 🔄 Core Data & Request Lifecycle\n\n"
                    "1. **Client Ingress**: Requests enter through the API routing layer with input validation.\n"
                    "2. **Validation & Schemas**: Data models and Pydantic schemas enforce type constraints and field contracts.\n"
                    "3. **Business Logic Execution**: Specialized service engines process business rules (e.g. slot calculations, validations).\n"
                    "4. **Persistence**: Transactions are committed to the database session.\n"
                    "5. **Response Delivery**: Formatted JSON responses and event reminders are returned to the client."
                )

                metrics_section = ""
                if scale_info or quality_info:
                    metrics_section = (
                        f"### 📊 Codebase Scale & Health\n\n"
                        f"- **Scale**: {scale_info}\n"
                        f"- **Code Quality**: {quality_info}\n\n"
                    )

                citations_note = f" (Key implementation references: {citation_str})" if citation_str else ""

                return (
                    f"# 🚀 {repo_name} — Deep Repository Overview\n\n"
                    f"{domain_desc}{citations_note}\n\n"
                    f"---\n\n"
                    f"{manifest_section}"
                    f"{flow_section}\n\n"
                    f"{metrics_section}"
                    f"---\n\n"
                    f"### 💡 Ask Me About Every Single File & Doubt!\n"
                    f"Unlike generic tools that only summarize the README, I have indexed every single file, function, "
                    f"and line in this repository. If you have a doubt about **any specific file, function, schema, or error**, "
                    f"ask me directly and I will walk you through the exact code!"
                )

            # 2. Specific file inquiry (e.g., "tell me about backend/models.py" or "what does slot_engine do?")
            file_match = re.search(r"([a-zA-Z0-9_\-\./]+\.py)", user_query)
            if file_match or any(k in user_query for k in ["file", "module", "function", "class", "where is"]):
                target_name = file_match.group(1) if file_match else ""
                relevant_chunks = [
                    m for m in full_prompt.split("--- Code Evidence ") if target_name and target_name in m
                ]
                if relevant_chunks or citation_str:
                    return (
                        f"### Deep Dive: `{target_name or 'Requested Module'}`\n\n"
                        f"Based on the indexed codebase, this module implements core business logic and structure {citation_str}.\n\n"
                        f"#### What this File Does:\n"
                        f"- Defines strict schema contracts and validated data structures\n"
                        f"- Implements core execution functions with error handling and dependency coordination\n"
                        f"- Integrates with database models and service layers across the application\n\n"
                        f"#### Implementation Notes:\n"
                        f"- Functions are designed for async execution to avoid blocking the event loop\n"
                        f"- Integrates with configured logging and environment settings\n\n"
                        f"Would you like me to explain any specific function, write a pytest test case, or refactor any logic in this file?"
                    )

            # 3. Code volume, largest files, complexity
            if any(
                k in user_query
                for k in ["most", "largest", "loc", "lines of code", "biggest file", "complexity"]
            ):
                largest_match = re.search(
                    r"#### Top Largest Modules by Code Volume:\s*\n((?:- `[^`]+`:[^\n]+\n?)+)",
                    full_prompt,
                )
                if not largest_match:
                    largest_match = re.search(
                        r"#### Top Largest Modules:\s*\n((?:- `[^`]+`:[^\n]+\n?)+)", full_prompt
                    )
                if largest_match:
                    modules_text = largest_match.group(1).strip()
                    return (
                        f"### Code Volume & Largest Files in {repo_name}\n\n"
                        f"Based on the repository scan metrics, here are the modules with the highest lines of code and complexity:\n\n"
                        f"{modules_text}\n\n"
                        f"These core modules handle the heaviest application logic and are prime candidates for modularization or focused unit testing."
                    )
                return f"Based on the repository metrics, the core service modules contain the largest volume of logic {citation_str}."

            # 4. Defect risk predictions
            if any(k in user_query for k in ["risk", "defect", "bug", "ml", "prediction"]):
                risk_match = re.search(
                    r"#### Defect Risk Estimates[^\n]*\n[^\n]*\n((?:- `[^`]+`:[^\n]+\n?)+)",
                    full_prompt,
                )
                if risk_match:
                    risk_text = risk_match.group(1).strip()
                    return (
                        f"### Defect Risk Analysis for {repo_name} (ML Model Track B)\n\n"
                        f"> ⚠️ **Statistical Risk Estimates**: These are machine-learning estimates based on code churn, "
                        f"Halstead complexity, and cyclomatic metrics, *never confirmed bugs* (Hard Rule 6).\n\n"
                        f"Here are the modules flagged with higher statistical defect probability:\n\n"
                        f"{risk_text}\n\n"
                        f"I recommend reviewing high-risk modules with focused unit tests and static analysis."
                    )

            # 5. Dependency hubs
            if any(
                k in user_query for k in ["dependency", "dependencies", "import", "graph", "hub"]
            ):
                hubs_match = re.search(
                    r"#### Architectural Hubs[^\n]*\n((?:- `[^`]+`:[^\n]+\n?)+)", full_prompt
                )
                if hubs_match:
                    hubs_text = hubs_match.group(1).strip()
                    return (
                        f"### Dependency Hubs & Architecture Structure in {repo_name}\n\n"
                        f"The internal import graph shows the following key architectural hubs:\n\n"
                        f"{hubs_text}\n\n"
                        f"Changes to these central modules have a higher transitive impact blast radius across the repository."
                    )

            # Default conversational synthesis
            if citation_str:
                return (
                    f"### Codebase Analysis for {repo_name}\n\n"
                    f"Based on the codebase evidence, the relevant implementation is located in {citation_str}.\n\n"
                    f"#### Key Findings:\n"
                    f"- Implements core domain behaviors and service coordination\n"
                    f"- Enforces input data validation and schema integrity\n"
                    f"- Handles error cases and structured persistence\n\n"
                    f"Let me know if you would like me to explain any specific function, inspect line ranges, or write tests for it!"
                )

            return (
                f"### Repository Insights: {repo_name}\n\n"
                f"This codebase is structured around modular layers with {scale_info or 'multiple Python modules'}. "
                f"You can ask me about **any single file, function implementation, dependency relationship, or defect risk**!"
            )

        # Check if prompt contains citations markers like [file:line]
        citations = re.findall(r"\[([a-zA-Z0-9_\-\./]+:\d+(?:-\d+)?)\]", full_prompt)

        if not citations:
            return "Not enough evidence in the codebase to answer this question."

        citation_str = " ".join(f"[{c}]" for c in citations[:3])
        return (
            f"Based on the codebase evidence, the requested functionality is implemented "
            f"in {citation_str}."
        )
