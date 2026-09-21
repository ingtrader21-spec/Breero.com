import pytest

from app.core.errors import DomainError
from app.domains.booking.postal import normalize_state, normalize_us_postal_code


@pytest.mark.parametrize(
    ("raw", "postal", "plus4", "formatted"),
    [
        ("77001", "77001", None, "77001"),
        (" 77001 ", "77001", None, "77001"),
        ("77001-1234", "77001", "1234", "77001-1234"),
    ],
)
def test_zip_and_zip_plus4_normalization(raw: str, postal: str, plus4: str | None, formatted: str) -> None:
    result = normalize_us_postal_code(raw)
    assert (result.postal_code, result.plus4, result.formatted) == (postal, plus4, formatted)


@pytest.mark.parametrize("invalid", ["", "7700", "770011", "ABCDE", "77001-123"])
def test_invalid_zip_is_rejected(invalid: str) -> None:
    with pytest.raises(DomainError) as exc_info:
        normalize_us_postal_code(invalid)
    assert exc_info.value.code == "INVALID_ZIP_CODE"


def test_state_is_normalized_and_territories_fail_closed() -> None:
    assert normalize_state(" tx ") == "TX"
    with pytest.raises(DomainError) as exc_info:
        normalize_state("PR")
    assert exc_info.value.code == "UNSUPPORTED_ADDRESS"
