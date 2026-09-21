import enum
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.domains.auth.models import AccessRole, Department, TenantScope, UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=1, max_length=160)
    phone: str | None = Field(default=None, min_length=5, max_length=32)


class ProviderRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    contact_name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=5, max_length=32)
    legal_name: str = Field(min_length=2, max_length=180)
    display_name: str = Field(min_length=2, max_length=120)
    provider_type: str = Field(default="COMPANY", pattern="^(COMPANY|INDEPENDENT)$")
    business_address: str = Field(min_length=5, max_length=240)
    city: str = Field(min_length=2, max_length=120)
    state: str = Field(min_length=2, max_length=3)
    postal_code: str = Field(pattern=r"^\d{5}(?:-\d{4})?$")
    timezone_id: str = Field(min_length=3, max_length=64)
    service_slugs: list[str] = Field(min_length=1, max_length=50)
    service_postal_codes: list[str] = Field(min_length=1, max_length=500)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)


class TokenRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(TokenRequest):
    new_password: str = Field(min_length=10, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)


class SetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=10, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    email_verified: bool


class ProviderRegistrationResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str
    refresh_expires_in: int
    user: UserRead
    provider_organization_id: uuid.UUID
    onboarding_status: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str
    refresh_expires_in: int
    user: UserRead


class BrowserSessionResponse(BaseModel):
    user: UserRead


class MessageResponse(BaseModel):
    message: str


class AccessAssignmentInput(BaseModel):
    role: AccessRole
    department: Department
    tenant_scope: TenantScope = TenantScope.brand
    vendor_id: uuid.UUID | None = None
    is_primary: bool = False

    @model_validator(mode="after")
    def validate_vendor_scope(self):
        if self.tenant_scope == TenantScope.vendor and self.vendor_id is None:
            raise ValueError("vendor_id is required for vendor-scoped access")
        if self.tenant_scope != TenantScope.vendor and self.vendor_id is not None:
            raise ValueError("vendor_id is only valid for vendor-scoped access")
        return self


class AccessProfileUpdate(BaseModel):
    brand_key: str = Field(
        default="breero",
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9_-]+$",
    )
    assignments: list[AccessAssignmentInput] = Field(max_length=32)

    @model_validator(mode="after")
    def one_primary_assignment(self):
        if sum(assignment.is_primary for assignment in self.assignments) > 1:
            raise ValueError("only one primary access assignment is allowed")
        unique = {(item.role, item.department) for item in self.assignments}
        if len(unique) != len(self.assignments):
            raise ValueError("duplicate role and department assignment")
        return self


class AccessAssignmentRead(BaseModel):
    role: AccessRole
    department: Department
    tenant_scope: TenantScope
    vendor_id: uuid.UUID | None = None
    is_primary: bool = False


class PortalContext(BaseModel):
    user: UserRead
    brand_key: str
    dashboard_path: str
    roles: list[AccessRole]
    departments: list[Department]
    permissions: list[str]
    assignments: list[AccessAssignmentRead]
    identity_mode: str


class InternalAccountRole(enum.StrEnum):
    BREERO_SUPPORT = "BREERO_SUPPORT"
    BREERO_DISPATCH = "BREERO_DISPATCH"
    BREERO_ADMIN = "BREERO_ADMIN"


class InternalUserProvisionRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=160)
    role: InternalAccountRole
    brand_key: str = Field(
        default="breero",
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9_-]+$",
    )


class InternalUserProvisionResponse(BaseModel):
    user: UserRead
    access: PortalContext
    credential_mode: Literal["keycloak", "invitation"]
    invitation_state: Literal[
        "not_required",
        "pending_configuration",
        "pending_delivery",
    ]
