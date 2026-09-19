import os
import subprocess
import sys
from pathlib import Path


def test_committed_openapi_matches_runtime_contract(tmp_path: Path) -> None:
    api_root = Path(__file__).resolve().parents[1]
    artifact = api_root / "openapi.json"
    generated = tmp_path / "openapi.json"
    subprocess.run(
        [sys.executable, "scripts/generate_openapi.py"],
        cwd=api_root,
        env={**os.environ, "OPENAPI_PATH": str(generated)},
        check=True,
        capture_output=True,
        text=True,
    )
    assert artifact.read_text(encoding="utf-8") == generated.read_text(encoding="utf-8"), (
        "apps/api/openapi.json is stale; run `python scripts/generate_openapi.py` "
        "and commit the deterministic result"
    )
