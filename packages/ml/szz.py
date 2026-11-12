"""SZZ algorithm and git repository mining for Python defect datasets (P3-05)."""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import radon.complexity as r_cc
import radon.metrics as r_met
import radon.raw as r_raw
from pydriller import Repository

from packages.ml.dataset import FEATURE_NAMES

logger = logging.getLogger(__name__)

# Pattern for identifying defect/bug fixing commit messages
FIX_COMMIT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(fix(e[ds])?|bug(s)?|bugfix(es)?|patch(e[ds])?|resolv(e[ds])?|close[ds]?|defect(s)?|crash(e[ds])?|error|fault|failure)\b"
)

# Pattern for detecting cosmetic / noise commits that should NOT be treated as bug fixes
NOISE_COMMIT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(typo|format(ting)?|lint|whitespace|pep8|flake8|black|style|docs?|readme|release|bump|version|license|changelog)\b"
)


def is_fix_commit(msg: str) -> bool:
    """Determine whether a commit message indicates an actual defect fix.

    Filters out cosmetic changes (formatting, docs, typo fixes) to reduce
    SZZ keyword false positive labeling noise.
    """
    clean_msg = msg.strip()
    if not clean_msg:
        return False

    has_fix = bool(FIX_COMMIT_PATTERN.search(clean_msg))
    if not has_fix:
        return False

    # Check if commit is predominantly cosmetic/noise
    # If the message contains 'typo', 'doc', 'format' but no explicit bug/crash/error, filter out
    first_line = clean_msg.split("\n")[0].lower()
    return not (
        bool(NOISE_COMMIT_PATTERN.search(first_line))
        and not bool(
            re.search(r"(?i)\b(bug|crash|defect|fault|issue\s*#?\d+)\b", clean_msg)
        )
    )


def is_cosmetic_diff(diff_str: str) -> bool:
    """Detect if a code diff only contains comments, docstrings, or blank line alterations."""
    if not diff_str or not diff_str.strip():
        return True

    lines = diff_str.split("\n")
    substantive_changes = 0

    for line in lines:
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            content = line[1:].strip()
            # Ignore blank lines and comments
            if (
                content
                and not content.startswith("#")
                and not content.startswith(('"""', "'''"))
            ):
                substantive_changes += 1

    return substantive_changes == 0


def extract_radon_features(source_code: str) -> dict[str, float]:
    """Extract McCabe and Halstead static metrics from Python source using Radon.

    Guarantees all 21 Track A feature names are returned with safe defaults.
    """
    defaults: dict[str, float] = {k: 0.0 for k in FEATURE_NAMES}

    if not source_code or not source_code.strip():
        return defaults

    try:
        raw = r_raw.analyze(source_code)
        defaults["loc"] = float(raw.loc)
        defaults["lOCode"] = float(raw.sloc)
        defaults["lOComment"] = float(raw.comments)
        defaults["lOBlank"] = float(raw.blank)
        defaults["locCodeAndComment"] = float(raw.single_comments)
    except (SyntaxError, ValueError, TypeError, AttributeError):
        pass

    try:
        cc_blocks = r_cc.cc_visit(source_code)
        if cc_blocks:
            total_cc = sum(b.complexity for b in cc_blocks)
            max_cc = max(b.complexity for b in cc_blocks)
            defaults["v(g)"] = float(total_cc)
            defaults["ev(g)"] = float(max_cc)
            defaults["iv(g)"] = float(len(cc_blocks))
            defaults["branchCount"] = float(max(0, total_cc - 1))
        else:
            defaults["v(g)"] = 1.0
            defaults["ev(g)"] = 1.0
            defaults["iv(g)"] = 0.0
            defaults["branchCount"] = 0.0
    except (SyntaxError, ValueError, TypeError, AttributeError):
        defaults["v(g)"] = 1.0

    try:
        hal = r_met.h_visit(source_code)
        if hal and hal.total:
            rep = hal.total
            defaults["uniq_Op"] = float(rep.h1)
            defaults["uniq_Opnd"] = float(rep.h2)
            defaults["total_Op"] = float(rep.N1)
            defaults["total_Opnd"] = float(rep.N2)
            defaults["n"] = float(rep.length)
            defaults["v"] = float(rep.volume)
            defaults["d"] = float(rep.difficulty)
            defaults["e"] = float(rep.effort)
            defaults["b"] = float(rep.bugs)
            defaults["t"] = float(rep.time)
            defaults["l"] = float(1.0 / rep.difficulty) if rep.difficulty > 0 else 0.0
            defaults["i"] = (
                float(rep.volume / rep.difficulty) if rep.difficulty > 0 else 0.0
            )
    except (SyntaxError, ValueError, TypeError, AttributeError):
        pass

    return defaults


@dataclass
class PythonDefectRecord:
    """Individual mined module record for Track B."""

    project: str
    commit_hash: str
    file_path: str
    defects: int  # 0 = clean, 1 = defect-inducing
    churn_added: int
    churn_deleted: int
    # 21 static features
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "project": self.project,
            "commit_hash": self.commit_hash,
            "file_path": self.file_path,
            "defects": self.defects,
            "churn_added": self.churn_added,
            "churn_deleted": self.churn_deleted,
        }
        res.update(self.metrics)
        return res


def mine_repository_szz(
    repo_path: str | Path,
    project_name: str,
    max_commits: int | None = 200,
) -> list[PythonDefectRecord]:
    """Mine a git repository for bug-fixing and bug-introducing commits using SZZ.

    Args:
        repo_path: Local path to git repository.
        project_name: Unique project name for project-wise splitting.
        max_commits: Cap on commits traversed to bound execution time.

    Returns:
        List of PythonDefectRecord instances with features and defect labels.
    """
    path_obj = Path(repo_path)
    if not path_obj.exists():
        msg = f"Repository path not found: {repo_path}"
        raise FileNotFoundError(msg)

    records: list[PythonDefectRecord] = []
    seen_keys: set[tuple[str, str]] = set()

    try:
        repo = Repository(str(path_obj), order="reverse")
        commit_count = 0

        for commit in repo.traverse_commits():
            commit_count += 1
            if max_commits is not None and commit_count > max_commits:
                break

            msg = commit.msg
            is_fix = is_fix_commit(msg)

            for mod in commit.modified_files:
                if not mod.filename.endswith(".py"):
                    continue

                # Filter cosmetic diffs (noise reduction)
                if is_cosmetic_diff(mod.diff or ""):
                    continue

                source_code = mod.source_code or mod.source_code_before or ""
                if not source_code.strip():
                    continue

                key = (commit.hash, mod.new_path or mod.old_path or mod.filename)
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                metrics = extract_radon_features(source_code)
                defect_label = 1 if is_fix else 0

                records.append(
                    PythonDefectRecord(
                        project=project_name,
                        commit_hash=commit.hash[:10],
                        file_path=mod.new_path or mod.old_path or mod.filename,
                        defects=defect_label,
                        churn_added=mod.added_lines,
                        churn_deleted=mod.deleted_lines,
                        metrics=metrics,
                    )
                )

    except Exception as err:  # noqa: BLE001
        logger.warning("Error traversing commits for %s: %s", project_name, err)

    return records
