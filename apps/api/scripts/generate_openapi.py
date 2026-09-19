"""Generate and validate the deterministic OpenAPI artifact used by every client."""

import json
import os
from pathlib import Path
from typing import Any

from app.main import app

HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def build_openapi_schema() -> dict[str, Any]:
    schema = app.openapi()
    operation_ids: dict[str, str] = {}
    for path, operations in schema.get("paths", {}).items():
        for method, operation in operations.items():
            if method not in HTTP_METHODS:
                continue
            operation_id = operation.get("operationId")
            if not operation_id:
                raise RuntimeError(f"Missing operationId for {method.upper()} {path}")
            if operation_id in operation_ids:
                raise RuntimeError(
                    f"Duplicate operationId {operation_id}: {operation_ids[operation_id]} and "
                    f"{method.upper()} {path}"
                )
            operation_ids[operation_id] = f"{method.upper()} {path}"
    return schema


def render_openapi() -> str:
    return json.dumps(build_openapi_schema(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    target = Path(os.getenv("OPENAPI_PATH", "openapi.json"))
    content = render_openapi()
    target.write_text(content, encoding="utf-8")
    schema = json.loads(content)
    operations = sum(
        1
        for path_item in schema.get("paths", {}).values()
        for method in path_item
        if method in HTTP_METHODS
    )
    print(f"validated {len(schema.get('paths', {}))} paths / {operations} operations")
    print(target)


if __name__ == "__main__":
    main()
