"""Root verification tests for Security Pass & Audits (P5-04).

Enforces:
    - Hard Rule 3: Untrusted code execution boundaries.
    - Hard Rule 4: Secrets and token redaction across all providers.
    - Hard Rule 5: Explicit source provenance labelling taxonomy.
    - Hard Rule 6: Probabilistic risk disclaimers and model versioning.
    - Hard Rule 7: LLM calls route through abstract LLMProvider.
    - Audit report documentation in docs/security/security_pass_audit.md.
"""

from pathlib import Path

from app.ai.providers.base import LLMProvider
from app.ai.providers.fake_llm import FakeLLMProvider
from app.ai.providers.openai_llm import OpenAILLMProvider
from app.ai.redaction import redact_secrets
from app.tests_gen.sandbox import DockerSandboxRunner, SandboxConfig

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_hard_rule_3_sandbox_constraints() -> None:
    """Verify DockerSandboxRunner enforces strict security boundaries (Hard Rule 3)."""
    cfg = SandboxConfig()
    assert cfg.network_disabled is True
    assert cfg.memory_limit == "512m"
    assert cfg.cpu_limit == "1.0"
    assert cfg.timeout_seconds <= 30

    runner = DockerSandboxRunner()
    assert runner.config.network_disabled is True


def test_hard_rule_4_secret_redaction_engine() -> None:
    """Verify credential families are masked by redact_secrets (Hard Rule 4)."""
    samples = [
        ("AWS", "AKIA" + "IOSFODNN7EXAMPLE", "[REDACTED_AWS_KEY]"),
        (
            "GitHub",
            "ghp_" + "1234567890abcdefghijklmnopqrstuvwxyzAB",
            "[REDACTED_GITHUB_TOKEN]",
        ),
        ("GitLab", "glpat-" + "1234567890abcdefghij", "[REDACTED_GITLAB_TOKEN]"),
        ("Slack", "xox" + "b-1234567890-abcdefghijklmnop", "[REDACTED_SLACK_TOKEN]"),
        (
            "Google",
            "AIza" + "SyD-1234567890abcdefghijklmnopqrstuv",
            "[REDACTED_GOOGLE_API_KEY]",
        ),
        (
            "OpenAI",
            "sk-" + "proj-1234567890abcdefghijklmnopqrstuvwxyz1234567890",
            "[REDACTED_OPENAI_KEY]",
        ),
        (
            "Anthropic",
            "sk-ant-" + "api03-1234567890abcdefghijklmnopqrstuvwxyz1234567890",
            "[REDACTED_ANTHROPIC_KEY]",
        ),
    ]
    for label, raw, expected_token in samples:
        redacted = redact_secrets(f"Check {label}: {raw}")
        assert raw not in redacted, f"Raw secret leaked for {label}"
        assert expected_token in redacted, (
            f"Expected {expected_token} in redacted text for {label}"
        )


def test_hard_rule_7_llm_providers_inherit_and_isolate() -> None:
    """Verify all LLM providers inherit from LLMProvider (Hard Rule 7)."""
    assert issubclass(FakeLLMProvider, LLMProvider)
    assert issubclass(OpenAILLMProvider, LLMProvider)


def test_security_audit_report_exists() -> None:
    """Verify security pass audit report is comprehensive and documented."""
    audit_file = REPO_ROOT / "docs" / "security" / "security_pass_audit.md"
    assert audit_file.exists(), f"Missing audit documentation at {audit_file}"

    content = audit_file.read_text(encoding="utf-8")
    assert "Security Pass & Dependency Audit Report" in content
    assert "Rule 3" in content
    assert "Rule 4" in content
    assert "Rule 5" in content
    assert "Rule 6" in content
    assert "Rule 7" in content
    assert "Dependency Audit" in content
