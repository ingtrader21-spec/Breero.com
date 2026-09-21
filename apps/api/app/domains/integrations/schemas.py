import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class IntegrationConfigRead(BaseModel):
    middleware_enabled: bool
    middleware_url_configured: bool
    middleware_ca_configured: bool
    middleware_client_certificate_configured: bool
    middleware_hmac_configured: bool
    middleware_identity_configured: bool
    odoo_enabled: bool
    odoo_url_configured: bool
    odoo_credentials_configured: bool


class IntegrationOperationRead(BaseModel):
    id: uuid.UUID
    operation_type: Literal["activate_pending", "park_unconfigured"]
    actor_id: uuid.UUID | None
    before_counts: dict[str, int]
    after_counts: dict[str, int]
    affected_count: int = Field(ge=0)
    created_at: datetime
