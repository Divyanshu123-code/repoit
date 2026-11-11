"""Dataset loading and schema definitions for defect prediction (P3-01)."""

from pathlib import Path
from typing import Final, Literal

import pandas as pd

DATA_DIR: Final[Path] = Path(__file__).resolve().parent / "data"

FEATURE_NAMES: Final[list[str]] = [
    "loc",
    "v(g)",
    "ev(g)",
    "iv(g)",
    "n",
    "v",
    "l",
    "d",
    "i",
    "e",
    "b",
    "t",
    "lOCode",
    "lOComment",
    "lOBlank",
    "locCodeAndComment",
    "uniq_Op",
    "uniq_Opnd",
    "total_Op",
    "total_Opnd",
    "branchCount",
]

TARGET_COLUMN: Final[str] = "defects"

FEATURE_DESCRIPTIONS: Final[dict[str, str]] = {
    "loc": "McCabe's line count of code",
    "v(g)": "McCabe's cyclomatic complexity",
    "ev(g)": "McCabe's essential complexity",
    "iv(g)": "McCabe's design complexity",
    "n": "Halstead total operators and operands (length N)",
    "v": "Halstead program volume V",
    "l": "Halstead program length level L",
    "d": "Halstead difficulty level D",
    "i": "Halstead intelligence content I",
    "e": "Halstead effort E",
    "b": "Halstead delivered bugs estimator B",
    "t": "Halstead time to implement T (seconds)",
    "lOCode": "Lines of executable code",
    "lOComment": "Lines of comments",
    "lOBlank": "Lines of blank space",
    "locCodeAndComment": "Lines containing both code and comments",
    "uniq_Op": "Unique operators (mu1)",
    "uniq_Opnd": "Unique operands (mu2)",
    "total_Op": "Total operators (N1)",
    "total_Opnd": "Total operands (N2)",
    "branchCount": "Branch count of the control flow graph",
}

DATASET_METADATA: Final[dict[str, dict[str, str]]] = {
    "cm1": {
        "title": "NASA Metrics Data Program CM1 (Spacecraft Instrument)",
        "source": "NASA MDP / PROMISE Software Engineering Repository",
        "language": "C",
        "description": "CM1 is a NASA spacecraft instrument system written in C. Each row represents a module or C function with McCabe and Halstead static code metrics.",
        "license": "Public Domain (NASA Metrics Data Program / PROMISE Repository)",
    },
    "kc1": {
        "title": "NASA Metrics Data Program KC1 (Satellite Ground Receiving System)",
        "source": "NASA MDP / PROMISE Software Engineering Repository",
        "language": "C++",
        "description": "KC1 is a NASA ground system for receiving and processing satellite data written in C++. Each row represents a C++ module/method with McCabe and Halstead static metrics.",
        "license": "Public Domain (NASA Metrics Data Program / PROMISE Repository)",
    },
}


def load_dataset(
    name: Literal["cm1", "kc1"] | str,
    data_dir: Path | str | None = None,
    standardize_target: bool = True,
) -> pd.DataFrame:
    """Load and optionally standardize a NASA defect dataset (CM1 or KC1).

    Args:
        name: Name of the dataset ("cm1" or "kc1").
        data_dir: Path to directory containing csv files. Defaults to packages/ml/data.
        standardize_target: If True, convert 'defects' target to boolean/binary int (0, 1).

    Returns:
        pd.DataFrame containing 21 metric features and the defects target.
    """
    clean_name = name.strip().lower()
    if clean_name not in {"cm1", "kc1"}:
        msg = f"Unknown dataset '{name}'. Expected 'cm1' or 'kc1'."
        raise ValueError(msg)

    base_dir = Path(data_dir) if data_dir is not None else DATA_DIR
    csv_path = base_dir / f"{clean_name}.csv"
    if not csv_path.exists():
        msg = f"Dataset file not found at {csv_path}"
        raise FileNotFoundError(msg)

    df = pd.read_csv(csv_path)

    # Validate schema
    missing_cols = [col for col in FEATURE_NAMES if col not in df.columns]
    if missing_cols:
        msg = f"Dataset {name} missing expected feature columns: {missing_cols}"
        raise ValueError(msg)

    if TARGET_COLUMN not in df.columns:
        msg = f"Dataset {name} missing target column '{TARGET_COLUMN}'"
        raise ValueError(msg)

    # Ensure numeric types on features
    for col in FEATURE_NAMES:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if standardize_target:
        # Normalize target to binary 0 / 1 integer
        target = df[TARGET_COLUMN].astype(str).str.strip().str.lower()
        true_values = {"true", "y", "yes", "1", "1.0", "t"}
        df[TARGET_COLUMN] = target.isin(true_values).astype(int)

    return df


def load_cm1(
    data_dir: Path | str | None = None,
    standardize_target: bool = True,
) -> pd.DataFrame:
    """Convenience helper to load NASA CM1 dataset."""
    return load_dataset("cm1", data_dir=data_dir, standardize_target=standardize_target)


def load_kc1(
    data_dir: Path | str | None = None,
    standardize_target: bool = True,
) -> pd.DataFrame:
    """Convenience helper to load NASA KC1 dataset."""
    return load_dataset("kc1", data_dir=data_dir, standardize_target=standardize_target)
