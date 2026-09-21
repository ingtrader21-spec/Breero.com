from typing import Any
from urllib.parse import quote

import httpx
from fastapi import HTTPException

from app.config import settings
from app.domains.auth.keycloak import discovery


class KeycloakProvisioner:
    async def _client(self) -> tuple[httpx.AsyncClient, dict[str, str]]:
        document = await discovery()
        client = httpx.AsyncClient(timeout=10, follow_redirects=False)
        response = await client.post(document["token_endpoint"], data={"grant_type": "client_credentials", "client_id": settings.keycloak_provisioner_client_id, "client_secret": settings.keycloak_provisioner_client_secret})
        if response.status_code != 200:
            await client.aclose()
            raise HTTPException(503, "Identity provisioning is unavailable")
        return client, {"Authorization": f"Bearer {response.json()['access_token']}"}

    async def ensure_client(self, email: str, first_name: str, last_name: str) -> str:
        base = f"{settings.keycloak_issuer.rstrip('/').rsplit('/realms/', 1)[0]}/admin/realms/{quote(settings.keycloak_issuer.rstrip('/').rsplit('/', 1)[-1])}"
        client, headers = await self._client()
        try:
            found = await client.get(f"{base}/users", headers=headers, params={"email": email, "exact": "true", "max": 2})
            if found.status_code != 200:
                raise HTTPException(503, "Identity lookup failed")
            users: list[dict[str, Any]] = found.json()
            if len(users) > 1:
                raise HTTPException(409, "Identity lookup is ambiguous")
            if users:
                subject = str(users[0]["id"])
            else:
                created = await client.post(f"{base}/users", headers=headers, json={"username": email, "email": email, "firstName": first_name, "lastName": last_name, "enabled": True, "emailVerified": False, "requiredActions": ["VERIFY_EMAIL", "UPDATE_PASSWORD"]})
                if created.status_code != 201:
                    raise HTTPException(503, "Identity creation failed")
                subject = created.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
            role = await client.get(f"{base}/roles/breero_client", headers=headers)
            if role.status_code != 200:
                raise HTTPException(503, "Breero client role is unavailable")
            assigned = await client.post(f"{base}/users/{quote(subject)}/role-mappings/realm", headers=headers, json=[role.json()])
            if assigned.status_code != 204:
                raise HTTPException(503, "Breero client role assignment failed")
            return subject
        finally:
            await client.aclose()
