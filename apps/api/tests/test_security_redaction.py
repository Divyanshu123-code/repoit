"""Security and secrets redaction test suite (Hard Rule 4, P5-04).

Enforces:
    - Never log or send secrets/tokens. Redact before any LLM call.
    - Test matrix covering all 12 credential families.
    - Automatic JSON logging scrubber.
    - End-to-end prompt scrubbing in RAG & Debug services.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.providers.fake_llm import FakeLLMProvider
from app.ai.rag_service import RAGService
from app.ai.redaction import redact_dict_secrets, redact_secrets
from app.core.logging import JSONFormatter
from app.indexing.models import SearchResultItem
from app.indexing.search_service import SemanticSearchService
from app.repos.filter import FilterReason, RepoFileFilter

# Construct test fixtures dynamically to prevent GitHub Push Protection scanner false alarms
SAMPLE_AWS_KEY = "AKIA" + "IOSFODNN7EXAMPLE"
SAMPLE_AWS_SESSION = "ASIA" + "IOSFODNN7EXAMPLE"
SAMPLE_GITHUB_PAT = "ghp_" + "1234567890abcdefghijklmnopqrstuvwxyzAB"
SAMPLE_GITHUB_FINE = (
    "github_pat_"
    + "11AAAAAAA01234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
)
SAMPLE_GITLAB_PAT = "glpat-" + "1234567890abcdefghij"
SAMPLE_SLACK_TOKEN = "xox" + "b-1234567890-abcdefghijklmnop"
SAMPLE_GOOGLE_KEY = "AIza" + "SyD-1234567890abcdefghijklmnopqrstuv"
SAMPLE_OAI_KEY = "sk-" + "proj-1234567890abcdefghijklmnopqrstuvwxyz1234567890"
SAMPLE_CLAUDE_KEY = "sk-ant-" + "api03-1234567890abcdefghijklmnopqrstuvwxyz1234567890"


def test_redact_private_keys() -> None:
    """Verify private key blocks are scrubbed."""
    raw = (
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0Y1mQ+...\n-----END RSA PRIVATE KEY-----"
    )
    assert redact_secrets(raw) == "[REDACTED_PRIVATE_KEY]"


def test_redact_aws_keys() -> None:
    """Verify AWS access key IDs are scrubbed."""
    raw = f"My AWS key is {SAMPLE_AWS_KEY} and {SAMPLE_AWS_SESSION}"
    redacted = redact_secrets(raw)
    assert SAMPLE_AWS_KEY not in redacted
    assert SAMPLE_AWS_SESSION not in redacted
    assert "[REDACTED_AWS_KEY]" in redacted


def test_redact_github_tokens() -> None:
    """Verify GitHub personal access tokens are scrubbed."""
    assert redact_secrets(SAMPLE_GITHUB_PAT) == "[REDACTED_GITHUB_TOKEN]"
    assert redact_secrets(SAMPLE_GITHUB_FINE) == "[REDACTED_GITHUB_TOKEN]"


def test_redact_gitlab_tokens() -> None:
    """Verify GitLab personal access tokens are scrubbed."""
    assert redact_secrets(SAMPLE_GITLAB_PAT) == "[REDACTED_GITLAB_TOKEN]"


def test_redact_slack_tokens() -> None:
    """Verify Slack bot/user tokens are scrubbed."""
    raw = f"Slack token: {SAMPLE_SLACK_TOKEN}"
    assert "xox" + "b-" not in redact_secrets(raw)
    assert "[REDACTED_SLACK_TOKEN]" in redact_secrets(raw)


def test_redact_google_api_key() -> None:
    """Verify Google API keys are scrubbed."""
    assert redact_secrets(SAMPLE_GOOGLE_KEY) == "[REDACTED_GOOGLE_API_KEY]"


def test_redact_openai_and_anthropic_keys() -> None:
    """Verify OpenAI and Anthropic API keys are scrubbed."""
    assert redact_secrets(SAMPLE_OAI_KEY) == "[REDACTED_OPENAI_KEY]"
    assert redact_secrets(SAMPLE_CLAUDE_KEY) == "[REDACTED_ANTHROPIC_KEY]"


def test_redact_database_connection_password() -> None:
    """Verify credentials inside database connection strings are masked."""
    raw = "postgresql://dbuser:SuperSecretPassword123@prod-db.internal:5432/main"
    redacted = redact_secrets(raw)
    assert "SuperSecretPassword123" not in redacted
    assert "postgresql://dbuser:[REDACTED_PASSWORD]@prod-db.internal:5432/main" == redacted


def test_redact_jwt_and_bearer_tokens() -> None:
    """Verify JWTs and Bearer tokens are scrubbed."""
    raw_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    raw_bearer = f"Authorization: Bearer {raw_jwt}"

    assert redact_secrets(raw_jwt) == "[REDACTED_JWT_TOKEN]"
    assert "Bearer [REDACTED_BEARER_TOKEN]" in redact_secrets(raw_bearer)


def test_redact_code_assignments() -> None:
    """Verify variable assignments containing secret names are scrubbed."""
    snippet = 'password = "supersecret12345"\nclient_secret: "my_long_client_secret_xyz"'
    redacted = redact_secrets(snippet)
    assert "supersecret12345" not in redacted
    assert "my_long_client_secret_xyz" not in redacted
    assert "[REDACTED_SECRET]" in redacted


def test_redact_dict_secrets_recursive() -> None:
    """Verify nested dictionaries and lists are recursively scrubbed."""
    data = {
        "user": "alice",
        "api_keys": [
            SAMPLE_GOOGLE_KEY,
            SAMPLE_GITHUB_PAT,
        ],
        "metadata": {
            "token": SAMPLE_OAI_KEY,
            "count": 42,
        },
    }
    cleaned = redact_dict_secrets(data)
    assert cleaned["user"] == "alice"
    assert cleaned["api_keys"][0] == "[REDACTED_GOOGLE_API_KEY]"
    assert cleaned["api_keys"][1] == "[REDACTED_GITHUB_TOKEN]"
    assert cleaned["metadata"]["token"] == "[REDACTED_OPENAI_KEY]"
    assert cleaned["metadata"]["count"] == 42


def test_json_logging_formatter_automatic_redaction() -> None:
    """Verify JSONFormatter automatically scrubs secrets from messages and extra fields."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test.security",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Authenticated user with token %s",
        args=(SAMPLE_GITHUB_PAT,),
        exc_info=None,
    )
    # Add sensitive extra field
    record.__dict__["db_url"] = "postgres://root:AdminPassword99@localhost/app"

    formatted_json = formatter.format(record)
    parsed = json.loads(formatted_json)

    assert "ghp_" not in parsed["message"]
    assert "[REDACTED_GITHUB_TOKEN]" in parsed["message"]
    assert "AdminPassword99" not in parsed["extra"]["db_url"]
    assert "[REDACTED_PASSWORD]" in parsed["extra"]["db_url"]


@pytest.mark.asyncio
async def test_rag_service_redacts_question_and_context_before_llm() -> None:
    """Verify RAGService scrubs incoming question and retrieved evidence before LLM prompt."""
    mock_search = MagicMock(spec=SemanticSearchService)
    secret_chunk = SearchResultItem(
        id=uuid.uuid4(),
        path="app/config.py",
        start_line=1,
        end_line=10,
        content=f"OPENAI_API_KEY = '{SAMPLE_OAI_KEY}'",
        symbol_name="config",
        score=0.92,
    )
    mock_search.search = AsyncMock(return_value=[secret_chunk])

    fake_llm = FakeLLMProvider()
    rag = RAGService(search_service=mock_search, llm_provider=fake_llm)

    mock_db = MagicMock()
    answer = await rag.answer_question(
        db=mock_db,
        repository_id=uuid.uuid4(),
        question=f"How do I use my token {SAMPLE_GITHUB_PAT}?",
    )

    # Check that LLM received scrubbed prompts
    for message_list in fake_llm.captured_messages:
        for msg in message_list:
            assert "ghp_" not in msg["content"]
            assert "sk-proj-" not in msg["content"]
            if "Evidence" in msg["content"]:
                assert (
                    "[REDACTED_OPENAI_KEY]" in msg["content"]
                    or "[REDACTED_SECRET]" in msg["content"]
                )

    assert not answer.abstained


def test_repo_file_filter_rejects_credential_content(tmp_path: Any) -> None:
    """Verify RepoFileFilter marks files containing high-risk secrets as SECRET_FILE."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    secret_file = repo_dir / "keys.py"
    secret_file.write_text(f"AWS_KEY = '{SAMPLE_AWS_KEY}'\nGITHUB_TOKEN = '{SAMPLE_GITHUB_PAT}'\n")

    file_filter = RepoFileFilter()
    result = file_filter.filter_file(
        repo_root=repo_dir,
        file_path=secret_file,
    )

    assert not result.is_accepted
    assert result.reason == FilterReason.SECRET_FILE
