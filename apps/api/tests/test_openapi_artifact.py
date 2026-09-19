from pathlib import Path

from scripts.generate_openapi import render_openapi


def test_committed_openapi_matches_runtime_contract() -> None:
    artifact = Path(__file__).resolve().parents[1] / "openapi.json"
    assert artifact.read_text(encoding="utf-8") == render_openapi(), (
        "apps/api/openapi.json is stale; run `python scripts/generate_openapi.py` "
        "and commit the deterministic result"
    )
