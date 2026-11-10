"""Secret and token redaction utility (Hard Rule 4).

Enforces:
'Never log or send secrets/tokens. Redact before any LLM call.'
"""

import re

# High-confidence secret patterns to mask
REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Private Key blocks
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
    # GitHub personal access tokens
    (
        re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,255}|github_pat_[a-zA-Z0-9_]{82}"),
        "[REDACTED_GITHUB_TOKEN]",
    ),
    # Slack tokens
    (
        re.compile(r"xox[baprs]-[0-9a-zA-Z]{10,48}"),
        "[REDACTED_SLACK_TOKEN]",
    ),
    # Google API Key
    (
        re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
        "[REDACTED_GOOGLE_API_KEY]",
    ),
    # OpenAI API Key pattern (sk-...)
    (
        re.compile(r"sk-[a-zA-Z0-9]{20,T3BlbkFJ[a-zA-Z0-9]{20,}|sk-proj-[a-zA-Z0-9_\-]{40,}"),
        "[REDACTED_OPENAI_KEY]",
    ),
    # Generic high-confidence secrets assigned in code: api_key = "..."
    (
        re.compile(
            r"""(?i)(?P<prefix>(?:api_key|apikey|secret_key|auth_token)\s*[:=]\s*['"])[a-zA-Z0-9_\-]{20,}(?P<suffix>['"])"""
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
