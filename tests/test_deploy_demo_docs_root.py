"""Root verification tests for Deploy, Demo Repo, Documentation & Measured Bullets (P5-06).

Acceptance Criteria:
    - Production README with architecture diagrams and running instructions.
    - Turnkey demo repository fixture and packaging script.
    - Comprehensive system architecture documentation with Mermaid flowcharts.
    - Final evaluation report synthesizing measured benchmarks across all phases.
    - Resume bullets derived strictly from measured numbers.
"""

import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_readme_comprehensive_content() -> None:
    """Verify README.md contains full architectural overview and measured numbers."""
    readme_path = REPO_ROOT / "README.md"
    assert readme_path.exists()
    content = readme_path.read_text(encoding="utf-8")

    # Essential sections
    assert "RepoPilot AI" in content
    assert "System Architecture" in content
    assert "```mermaid" in content
    assert "Monorepo Layout" in content
    assert "Getting Started" in content
    assert "Turnkey Demo Repository Walkthrough" in content
    assert "Measured Benchmark Numbers" in content
    assert "285 passing automated tests" in content
    assert "0.908 ROC-AUC" in content
    assert "0.864 Mean Reciprocal Rank" in content


def test_demo_repository_and_zip_archive() -> None:
    """Verify turnkey demo repository files and zip package exist and are valid."""
    demo_dir = REPO_ROOT / "demo" / "sample_repo"
    assert demo_dir.exists()
    assert (demo_dir / "app" / "auth.py").exists()
    assert (demo_dir / "app" / "database.py").exists()
    assert (demo_dir / "app" / "crypto.py").exists()
    assert (demo_dir / "app" / "payments.py").exists()
    assert (demo_dir / "app" / "routes.py").exists()

    demo_zip = REPO_ROOT / "demo" / "sample_repo.zip"
    assert demo_zip.exists()
    with zipfile.ZipFile(demo_zip, "r") as zf:
        namelist = zf.namelist()
        assert any("auth.py" in name for name in namelist)
        assert any("database.py" in name for name in namelist)
        assert any("payments.py" in name for name in namelist)


def test_architecture_documentation_mermaid_and_rules() -> None:
    """Verify docs/ARCHITECTURE.md contains detailed Mermaid diagrams and rules."""
    arch_path = REPO_ROOT / "docs" / "ARCHITECTURE.md"
    assert arch_path.exists()
    content = arch_path.read_text(encoding="utf-8")

    assert "flowchart TD" in content
    assert "sequenceDiagram" in content
    assert "Hard Rules & Compliance" in content
    assert "Docker Sandbox Runner" in content
    assert "Change Impact Analysis" in content


def test_resume_bullets_measured_numbers_only() -> None:
    """Verify docs/RESUME_BULLETS.md derives strictly from measured metrics."""
    resume_path = REPO_ROOT / "docs" / "RESUME_BULLETS.md"
    assert resume_path.exists()
    content = resume_path.read_text(encoding="utf-8")

    assert "978 mined Python modules" in content
    assert "0.908 ROC-AUC" in content
    assert "0.835 PR-AUC" in content
    assert "0.864 MRR" in content
    assert "97.1% Recall@10" in content
    assert "285 automated tests" in content


def test_final_evaluation_report_synthesis() -> None:
    """Verify docs/eval/final_evaluation_report.md documents all phases."""
    eval_path = REPO_ROOT / "docs" / "eval" / "final_evaluation_report.md"
    assert eval_path.exists()
    content = eval_path.read_text(encoding="utf-8")

    assert "Executive Benchmark Summary" in content
    assert "Phase 2: Code Retrieval & RAG Benchmark" in content
    assert "Phase 3: Machine Learning Defect Prediction" in content
    assert "Phase 4: Import Graph & Change Impact" in content
    assert "Phase 5: AI Debug Assistant & Sandboxed Execution" in content
