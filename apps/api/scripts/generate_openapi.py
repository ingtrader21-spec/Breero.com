"""Generate a deterministic OpenAPI artifact for contract review and CI."""

import json
import os
from pathlib import Path

from app.main import app

target = Path(os.getenv("OPENAPI_PATH", "openapi.json"))
schema = app.openapi()
operation_ids: dict[str, str] = {}
for path, operations in schema.get("paths", {}).items():
    for method, operation in operations.items():
        if method not in {"get", "put", "post", "delete", "options", "head", "patch", "trace"}:
            continue
        operation_id = operation.get("operationId")
        if not operation_id:
            raise SystemExit(f"Missing operationId for {method.upper()} {path}")
        if operation_id in operation_ids:
            raise SystemExit(
                f"Duplicate operationId {operation_id}: {operation_ids[operation_id]} and "
                f"{method.upper()} {path}"
            )
        operation_ids[operation_id] = f"{method.upper()} {path}"
target.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
print(f"validated {len(schema.get('paths', {}))} paths / {len(operation_ids)} operations")
print(target)
