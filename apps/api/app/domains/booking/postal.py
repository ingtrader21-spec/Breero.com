import re
from dataclasses import dataclass

from app.core.errors import DomainError
from app.domains.common.us import US_STATES_AND_DC

ZIP_PATTERN = re.compile(r"^(?P<zip>\d{5})(?:-(?P<plus4>\d{4}))?$")


@dataclass(frozen=True)
class USPostalCode:
    postal_code: str
    plus4: str | None = None

    @property
    def formatted(self) -> str:
        return f"{self.postal_code}-{self.plus4}" if self.plus4 else self.postal_code


def normalize_us_postal_code(value: str) -> USPostalCode:
    normalized = value.strip()
    match = ZIP_PATTERN.fullmatch(normalized)
    if not match:
        raise DomainError("INVALID_ZIP_CODE", "A five-digit U.S. ZIP or ZIP+4 is required", 422)
    return USPostalCode(match.group("zip"), match.group("plus4"))


def normalize_state(value: str) -> str:
    state = value.strip().upper()
    if state not in US_STATES_AND_DC:
        raise DomainError("UNSUPPORTED_ADDRESS", "A valid U.S. state or DC is required", 422)
    return state
