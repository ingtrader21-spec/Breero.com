from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException

from app.domains.auth import keycloak
from app.domains.auth.models import UserRole


def test_oidc_transaction_is_signed_pkce_state_and_rejects_tampering(monkeypatch) -> None:
    monkeypatch.setattr(keycloak, "settings", SimpleNamespace(jwt_secret="test-secret-at-least-32-characters", breero_web_url="https://breero.test", breero_provider_web_url="https://provider.breero.test", breero_admin_web_url="https://admin.breero.test"))
    state, nonce, verifier, raw = keycloak.create_transaction("/account")
    transaction = keycloak.read_transaction(raw, state)
    assert transaction["nonce"] == nonce
    assert transaction["verifier"] == verifier
    with pytest.raises(HTTPException):
        keycloak.read_transaction(raw + "tampered", state)
    with pytest.raises(HTTPException):
        keycloak.read_transaction(raw, "wrong-state")


def test_namespaced_roles_map_to_local_operational_roles(monkeypatch) -> None:
    monkeypatch.setattr(keycloak, "settings", SimpleNamespace(keycloak_audience="breero-api", keycloak_client_id="breero-client-web"))
    assert keycloak.roles_from_claims({"realm_access": {"roles": ["breero_client"]}}) == {"breero_client"}
    assert keycloak.ROLE_MAP["breero_provider"] is UserRole.technician
    assert keycloak.ROLE_MAP["breero_admin"] is UserRole.admin


def test_transaction_contains_no_client_secret(monkeypatch) -> None:
    secret = "server-only-client-secret"
    monkeypatch.setattr(keycloak, "settings", SimpleNamespace(jwt_secret="test-secret-at-least-32-characters", keycloak_client_secret=secret, breero_web_url="https://breero.test", breero_provider_web_url="https://provider.breero.test", breero_admin_web_url="https://admin.breero.test"))
    *_, raw = keycloak.create_transaction("/provider")
    assert secret not in raw
    assert jwt.decode(raw, "test-secret-at-least-32-characters", algorithms=["HS256"])["return_to"] == "https://provider.breero.test"
