from typing import Any

import httpx

from app.config import settings
from app.core.errors import DomainError
from app.integrations.contracts import GeocodedAddress, GeocodingGateway

__all__ = ["FakeGeocodingAdapter", "GeocodedAddress", "GeocodingAdapter", "GeocodingGateway"]


class FakeGeocodingAdapter:
    """Deterministic test adapter; it never performs network I/O."""

    def __init__(self, result: GeocodedAddress) -> None:
        self.result = result

    async def geocode(self, address: str) -> GeocodedAddress:
        del address
        return self.result

    async def resolve_timezone(self, latitude: float, longitude: float) -> str:
        del latitude, longitude
        if not self.result.timezone_name:
            raise DomainError(
                "TIMEZONE_NOT_FOUND",
                "Timezone could not be resolved for the supplied coordinates.",
                422,
            )
        return self.result.timezone_name


class GeocodingAdapter:
    """Geoapify-backed REAL adapter behind the replaceable geography protocol."""

    async def geocode(self, address: str) -> GeocodedAddress:
        payload = await self._request(
            "https://api.geoapify.com/v1/geocode/search",
            {"text": address, "limit": 5},
        )
        properties = self._first_properties(payload)
        latitude, longitude = self._coordinates(properties)
        country_code = str(properties.get("country_code") or "").upper()
        if country_code != "US":
            raise DomainError(
                "ADDRESS_OUTSIDE_SERVICE_COUNTRY",
                "Only U.S. service addresses are supported.",
                422,
            )
        postal_code, plus4 = self._postal_code(properties.get("postcode"))
        confidence = (properties.get("rank") or {}).get("confidence")
        if confidence is None or float(confidence) < 0.7:
            raise DomainError(
                "ADDRESS_AMBIGUOUS",
                "Address requires manual validation.",
                422,
            )
        city = str(
            properties.get("city")
            or properties.get("town")
            or properties.get("village")
            or ""
        ).strip()
        return GeocodedAddress(
            formatted_address=str(properties.get("formatted") or address),
            line1=str(properties.get("address_line1") or address),
            line2=str(properties.get("address_line2") or "").strip() or None,
            city=city,
            county=str(properties.get("county") or "").strip() or None,
            state_code=self._state_code(properties),
            postal_code=postal_code,
            postal_code_plus4=plus4,
            country_code=country_code,
            latitude=latitude,
            longitude=longitude,
            provider="geoapify",
            provider_reference=(
                str(properties.get("place_id"))
                if properties.get("place_id") is not None
                else None
            ),
            confidence=float(confidence),
            quality=(properties.get("rank") or {}).get("match_type"),
            timezone_name=str(
                (properties.get("timezone") or {}).get("name") or ""
            ).strip()
            or None,
        )

    async def resolve_timezone(self, latitude: float, longitude: float) -> str:
        payload = await self._request(
            "https://api.geoapify.com/v1/geocode/reverse",
            {"lat": latitude, "lon": longitude, "limit": 1},
        )
        properties = self._first_properties(payload)
        timezone = str(
            (properties.get("timezone") or {}).get("name") or ""
        ).strip()
        if not timezone:
            raise DomainError(
                "TIMEZONE_NOT_FOUND",
                "Timezone could not be resolved for the supplied coordinates.",
                422,
            )
        return timezone

    async def _request(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        if settings.geocoding_provider != "geoapify":
            raise DomainError(
                "GEOCODING_PROVIDER_UNSUPPORTED",
                "Configured address provider is not supported.",
                503,
            )
        if not settings.geocoding_enabled or not settings.geocoding_api_key:
            raise DomainError(
                "GEOCODING_UNAVAILABLE",
                "Address and timezone validation are not configured.",
                503,
            )
        request_params = {**params, "apiKey": settings.geocoding_api_key}
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                response = await client.get(url, params=request_params)
                response.raise_for_status()
                payload = response.json()
            except httpx.TimeoutException as exc:
                raise DomainError(
                    "GEOCODING_TIMEOUT",
                    "Address validation is temporarily unavailable.",
                    503,
                ) from exc
            except httpx.HTTPStatusError as exc:
                provider_status = exc.response.status_code
                code = (
                    "GEOCODING_CREDENTIAL_REJECTED"
                    if provider_status in {401, 403}
                    else "GEOCODING_RATE_LIMITED"
                    if provider_status == 429
                    else "GEOCODING_PROVIDER_FAILURE"
                )
                raise DomainError(
                    code,
                    "Address validation is temporarily unavailable.",
                    503,
                ) from exc
            except (httpx.HTTPError, ValueError) as exc:
                raise DomainError(
                    "GEOCODING_PROVIDER_FAILURE",
                    "Address validation is temporarily unavailable.",
                    503,
                ) from exc
        if not isinstance(payload, dict):
            raise DomainError(
                "GEOCODING_PROVIDER_FAILURE",
                "Address validation is temporarily unavailable.",
                503,
            )
        return payload

    @staticmethod
    def _first_properties(payload: dict[str, Any]) -> dict[str, Any]:
        features = payload.get("features", [])
        if not isinstance(features, list) or not features:
            raise DomainError(
                "ADDRESS_NOT_FOUND",
                "Address could not be resolved.",
                422,
            )
        try:
            properties = features[0]["properties"]
        except (KeyError, TypeError, IndexError) as exc:
            raise DomainError(
                "GEOCODING_PROVIDER_FAILURE",
                "Address validation is temporarily unavailable.",
                503,
            ) from exc
        if not isinstance(properties, dict):
            raise DomainError(
                "GEOCODING_PROVIDER_FAILURE",
                "Address validation is temporarily unavailable.",
                503,
            )
        return properties

    @staticmethod
    def _coordinates(properties: dict[str, Any]) -> tuple[float, float]:
        try:
            return float(properties["lat"]), float(properties["lon"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DomainError(
                "GEOCODING_PROVIDER_FAILURE",
                "Address validation is temporarily unavailable.",
                503,
            ) from exc

    @staticmethod
    def _state_code(properties: dict[str, Any]) -> str | None:
        value = str(
            properties.get("state_code")
            or properties.get("state_code_historic")
            or ""
        ).strip().upper()
        if not value:
            return None
        if "-" in value:
            value = value.rsplit("-", 1)[-1]
        if len(value) not in {2, 3} or not value.isalpha():
            raise DomainError(
                "ADDRESS_STATE_INVALID",
                "Address provider returned an invalid state code.",
                422,
            )
        return value

    @staticmethod
    def _postal_code(raw: object) -> tuple[str, str | None]:
        value = str(raw or "").strip()
        if len(value) == 9 and value.isdigit():
            value = f"{value[:5]}-{value[5:]}"
        pieces = value.split("-", 1)
        postal_code = pieces[0]
        plus4 = pieces[1] if len(pieces) == 2 else None
        if (
            len(postal_code) != 5
            or not postal_code.isdigit()
            or (plus4 is not None and (len(plus4) != 4 or not plus4.isdigit()))
        ):
            raise DomainError(
                "ADDRESS_ZIP_INVALID",
                "A five-digit U.S. ZIP code is required.",
                422,
            )
        return postal_code, plus4
