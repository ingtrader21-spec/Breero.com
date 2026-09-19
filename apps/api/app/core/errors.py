from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class DomainError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        *,
        fields: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.fields = dict(fields) if fields is not None else None
        self.headers = {str(key): str(value) for key, value in (headers or {}).items()}
        super().__init__(message)


def is_v2_request(request: Request) -> bool:
    return request.url.path == "/api/v2" or request.url.path.startswith("/api/v2/")


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unavailable")


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", _request_id(request))


def _v2_response_headers(
    request: Request,
    headers: Mapping[str, str] | None = None,
) -> dict[str, str]:
    response_headers = {str(key): str(value) for key, value in (headers or {}).items()}
    response_headers["X-Request-ID"] = _request_id(request)
    response_headers["X-Correlation-ID"] = _correlation_id(request)
    response_headers["X-Content-Type-Options"] = "nosniff"
    response_headers["X-Frame-Options"] = "DENY"
    response_headers["Referrer-Policy"] = "no-referrer"
    response_headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response_headers


def _encode_error_datetime(value: datetime) -> str:
    """Preserve the caller-visible ISO-8601 representation consistently."""

    return value.isoformat()


def _encode_error_model(value: BaseModel) -> Any:
    """Encode nested models from Python values so custom scalar encoders apply."""

    return _encode_error_content(value.model_dump(mode="python"))


def _encode_error_content(value: Any) -> Any:
    return jsonable_encoder(
        value,
        custom_encoder={
            Decimal: str,
            datetime: _encode_error_datetime,
            BaseModel: _encode_error_model,
        },
    )


def _v2_error(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    fields: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    # Decimal values commonly represent money and measurements. Encode them as
    # strings so structured error feedback remains exact across JSON and
    # JavaScript clients instead of silently rounding through IEEE-754 floats.
    # Nested Pydantic models are first dumped in Python mode so their datetime
    # and Decimal values use the same lossless encoders as direct field values.
    content = _encode_error_content(
        {
            "code": code,
            "message": message,
            "correlation_id": _correlation_id(request),
            "fields": dict(fields) if fields is not None else None,
        }
    )
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers=_v2_response_headers(request, headers),
    )


def v2_unexpected_error_response(request: Request) -> JSONResponse:
    """Return the stable fail-closed V2 response for an unexpected platform error."""

    return _v2_error(
        request,
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred.",
    )


def _http_code(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).name
    except ValueError:
        return "HTTP_ERROR"


def _http_message(exc: StarletteHTTPException) -> str:
    if isinstance(exc.detail, str):
        return exc.detail
    try:
        return HTTPStatus(exc.status_code).phrase
    except ValueError:
        return "HTTP request failed"


def _validation_fields(exc: RequestValidationError) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ())) or "request"
        fields.setdefault(location, []).append(str(error.get("msg", "Invalid value")))
    return fields


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        if is_v2_request(request):
            return _v2_error(
                request,
                status_code=exc.status_code,
                code=exc.code,
                message=exc.message,
                fields=exc.fields,
                headers=exc.headers,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
            headers=exc.headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> Response:
        if not is_v2_request(request):
            return await http_exception_handler(request, exc)
        return _v2_error(
            request,
            status_code=exc.status_code,
            code=_http_code(exc.status_code),
            message=_http_message(exc),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> Response:
        if not is_v2_request(request):
            return await request_validation_exception_handler(request, exc)
        return _v2_error(
            request,
            status_code=422,
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            fields=_validation_fields(exc),
        )
