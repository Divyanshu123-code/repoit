"""Secret and token redaction utility (Hard Rule 4).

Enforces:
'Never log or send secrets/tokens. Redact before any LLM call.'
"""

from __future__ import annotations

import re
from typing import Any

# High-confidence secret patterns to mask
REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Private Key blocks (RSA, EC, DSA, OPENSSH, PGP)
    (
        re.compile(
            r"-----BEGIN (?:[A-Z0-9_-]+\s)?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z0-9_-]+\s)?PRIVATE KEY-----"
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    # AWS access key IDs
    (
        re.compile(r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}"),
        "[REDACTED_AWS_KEY]",
    ),
    # GitHub personal access tokens and fine-grained tokens
    (
        re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,255}|github_pat_[a-zA-Z0-9_]{82}"),
        "[REDACTED_GITHUB_TOKEN]",
    ),
    # GitLab personal access tokens
    (
        re.compile(r"glpat-[a-zA-Z0-9_\-]{20,255}"),
        "[REDACTED_GITLAB_TOKEN]",
    ),
    # Slack tokens
    (
        re.compile(r"xox[baprs]-[0-9a-zA-Z]{10,48}"),
        "[REDACTED_SLACK_TOKEN]",
    ),
    # Google API Key
    (
        re.compile(r"AIza[0-9A-Za-z\-_]{35,}"),
        "[REDACTED_GOOGLE_API_KEY]",
    ),
    # OpenAI API Key pattern (sk-...)
    (
        re.compile(r"sk-[a-zA-Z0-9]{20,T3BlbkFJ[a-zA-Z0-9]{20,}|sk-proj-[a-zA-Z0-9_\-]{40,}"),
        "[REDACTED_OPENAI_KEY]",
    ),
    # Anthropic API Key pattern (sk-ant-...)
    (
        re.compile(r"sk-ant-(?:api\d{2}-)?[a-zA-Z0-9_\-]{32,}"),
        "[REDACTED_ANTHROPIC_KEY]",
    ),
    # Database connection strings with embedded passwords: postgres://user:password@host
    (
        re.compile(
            r"""(?i)(?P<proto>postgres(?:ql)?|mysql|redis|mongodb):\/\/(?P<user>[^:\s\/]+):(?P<pass>[^@\s]+)@(?P<rest>[^\s]+)"""
        ),
        r"\g<proto>://\g<user>:[REDACTED_PASSWORD]@\g<rest>",
    ),
    # Authorization: Bearer tokens (matched before naked JWTs)
    (
        re.compile(r"""(?i)(?P<prefix>bearer\s+)[a-zA-Z0-9_\-\.]{20,}"""),
        r"\g<prefix>[REDACTED_BEARER_TOKEN]",
    ),
    # JSON Web Tokens (JWT)
    (
        re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b"),
        "[REDACTED_JWT_TOKEN]",
    ),
    # Generic high-confidence secrets assigned in code: api_key = "...", password = "..."
    (
        re.compile(
            r"""(?i)(?P<prefix>(?:api[_-]?key|secret[_-]?key|auth[_-]?token|client[_-]?secret|password|access[_-]?token|private[_-]?token)\s*[:=]\s*['"])[^\s'"]{8,}(?P<suffix>['"])"""
        ),
        r"\g<prefix>[REDACTED_SECRET]\g<suffix>",
    ),
)


def redact_secrets(text: str) -> str:
    """Scrub potential tokens, credentials, and API keys before sending to LLM / Embedding APIs."""
    if not text:
        return text

    sanitized = text
    for pattern, replacement in REDACTION_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)

    return sanitized


def redact_dict_secrets(data: Any) -> Any:
    """Recursively scrub secrets from strings within dicts, lists, and primitives."""
    if isinstance(data, str):
        return redact_secrets(data)
    if isinstance(data, dict):
        return {k: redact_dict_secrets(v) for k, v in data.items()}
    if isinstance(data, list):
        return [redact_dict_secrets(item) for item in data]
    return data
