"""Package sample demo repository into a zip archive for one-click upload."""

import os
import zipfile
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent
SAMPLE_REPO_DIR = DEMO_DIR / "sample_repo"
OUTPUT_ZIP = DEMO_DIR / "sample_repo.zip"


def create_demo_zip() -> Path:
    """Create a zip archive containing the demo repository files."""
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(SAMPLE_REPO_DIR):
            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(SAMPLE_REPO_DIR)
                zf.write(file_path, arcname=rel_path.as_posix())
    print(f"Demo repository packaged successfully at: {OUTPUT_ZIP}")
    return OUTPUT_ZIP


if __name__ == "__main__":
    create_demo_zip()
