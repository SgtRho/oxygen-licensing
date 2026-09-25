from typing import Any, Optional
from pydantic import BaseModel, Field


class VerifyRequest(BaseModel):
    license_key: str = Field(..., description="Der in der Instanz hinterlegte Lizenzschlüssel")
    instance_uuid: str = Field(..., description="Die eindeutige UUID der Oxygen-Instanz")
    version: Optional[str] = Field(None, description="Client-Version")


class VerifyResponse(BaseModel):
    valid: bool
    code: str
    message: str
    customer: Optional[str] = None
    validUntil: Optional[str] = None
    instanceUuid: Optional[str] = None
    modules: dict[str, bool] = {}
    timestamp: Optional[int] = None
    signature: Optional[str] = None
    error: Optional[str] = None


class LicenseCreate(BaseModel):
    customer_name: str = Field(..., min_length=1, description="Name des Kunden / Lizenznehmers")
    license_key: Optional[str] = Field(None, description="Optionaler Lizenzschlüssel (wird sonst automatisch generiert)")
    instance_uuid: Optional[str] = Field("", description="Die UUID der lizenzierten Instanz")
    valid_until: Optional[str] = Field(None, description="Ablaufdatum YYYY-MM-DD oder None für unbegrenzt")
    modules: dict[str, bool] = Field(default_factory=dict, description="Freigeschaltete Module")
    notes: Optional[str] = Field("", description="Interne Notizen")
    is_active: bool = Field(True, description="Ob die Lizenz aktiv ist")


class LicenseUpdate(BaseModel):
    customer_name: Optional[str] = None
    instance_uuid: Optional[str] = None
    valid_until: Optional[str] = None
    modules: Optional[dict[str, bool]] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class LicenseOut(BaseModel):
    id: int
    license_key: str
    customer_name: str
    instance_uuid: str
    is_active: bool
    valid_until: Optional[str]
    modules: dict[str, bool]
    notes: str
    created_at: str
    updated_at: str
    last_check_at: Optional[str]
    last_check_ip: Optional[str]
    last_check_version: Optional[str]
    status: str  # 'active', 'expired', 'unassigned_uuid', 'inactive'


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    ok: bool
    token: Optional[str] = None
    message: Optional[str] = None
