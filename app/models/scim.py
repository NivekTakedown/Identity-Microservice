"""
Schemas Pydantic para SCIM 2.0
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import re


class SCIMMeta(BaseModel):
    """Metadatos SCIM estándar"""
    resourceType: str = "User"
    created: str = Field(default_factory=lambda: datetime.now().isoformat() + "Z")
    lastModified: str = Field(default_factory=lambda: datetime.now().isoformat() + "Z")
    location: Optional[str] = None


class SCIMName(BaseModel):
    """Nombre completo SCIM"""
    givenName: Optional[str] = None
    familyName: Optional[str] = None
    formatted: Optional[str] = None
    
    def model_post_init(self, __context):
        """Auto-generar formatted si no se proporciona"""
        if not self.formatted and (self.givenName or self.familyName):
            parts = [self.givenName or "", self.familyName or ""]
            self.formatted = " ".join(filter(None, parts))


class SCIMEmail(BaseModel):
    """Email SCIM"""
    value: str
    primary: bool = False
    type: str = "work"
    
    @field_validator('value')
    @classmethod
    def validate_email(cls, v):
        """Validar formato de email"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Invalid email format')
        return v


class UserSCIM(BaseModel):
    """Modelo completo de usuario SCIM 2.0"""
    id: str
    userName: str
    name: Optional[SCIMName] = None
    active: bool = True
    emails: List[SCIMEmail] = []
    groups: List[str] = []
    
    # Campos adicionales para nuestro dominio
    dept: Optional[str] = None
    riskScore: int = 0
    
    # Metadatos SCIM
    meta: SCIMMeta = Field(default_factory=SCIMMeta)
    schemas: List[str] = ["urn:ietf:params:scim:schemas:core:2.0:User"]
    
    @field_validator('userName')
    @classmethod
    def validate_username(cls, v):
        """Validar userName"""
        if not v or len(v.strip()) == 0:
            raise ValueError('userName cannot be empty')
        if len(v) < 2 or len(v) > 50:
            raise ValueError('userName must be between 2 and 50 characters')
        if not re.match(r'^[a-zA-Z0-9._-]+$', v):
            raise ValueError('userName can only contain letters, numbers, dots, hyphens and underscores')
        return v.strip()
    
    @field_validator('riskScore')
    @classmethod
    def validate_risk_score(cls, v):
        """Validar riskScore"""
        if v < 0 or v > 100:
            raise ValueError('riskScore must be between 0 and 100')
        return v


class UserCreateSCIM(BaseModel):
    """Validación para creación de usuario"""
    userName: str
    name: Optional[SCIMName] = None
    active: bool = True
    emails: List[SCIMEmail] = []
    groups: List[str] = []
    dept: Optional[str] = None
    riskScore: int = 0
    
    @field_validator('userName')
    @classmethod
    def validate_username(cls, v):
        """Validar userName único"""
        if not v or len(v.strip()) == 0:
            raise ValueError('userName is required')
        if len(v) < 2 or len(v) > 50:
            raise ValueError('userName must be between 2 and 50 characters')
        if not re.match(r'^[a-zA-Z0-9._-]+$', v):
            raise ValueError('userName can only contain letters, numbers, dots, hyphens and underscores')
        return v.strip()
    
    @field_validator('emails')
    @classmethod
    def validate_emails(cls, v):
        """Validar que haya al menos un email primario"""
        if not v:
            return v
        
        primary_count = sum(1 for email in v if email.primary)
        if primary_count > 1:
            raise ValueError('Only one email can be marked as primary')
        
        return v


class UserUpdateSCIM(BaseModel):
    """Validación para actualización PATCH de usuario"""
    userName: Optional[str] = None
    name: Optional[SCIMName] = None
    active: Optional[bool] = None
    emails: Optional[List[SCIMEmail]] = None
    groups: Optional[List[str]] = None
    dept: Optional[str] = None
    riskScore: Optional[int] = None
    
    @field_validator('userName')
    @classmethod
    def validate_username(cls, v):
        """Validar userName si se proporciona"""
        if v is not None:
            if len(v.strip()) == 0:
                raise ValueError('userName cannot be empty')
            if len(v) < 2 or len(v) > 50:
                raise ValueError('userName must be between 2 and 50 characters')
            if not re.match(r'^[a-zA-Z0-9._-]+$', v):
                raise ValueError('userName can only contain letters, numbers, dots, hyphens and underscores')
            return v.strip()
        return v
    
    @field_validator('riskScore')
    @classmethod
    def validate_risk_score(cls, v):
        """Validar riskScore si se proporciona"""
        if v is not None and (v < 0 or v > 100):
            raise ValueError('riskScore must be between 0 and 100')
        return v


class SCIMResponse(BaseModel):
    """Formato de respuestas estándar SCIM"""
    schemas: List[str]
    totalResults: int
    Resources: List[UserSCIM] = []
    startIndex: int = 1
    itemsPerPage: int = 100


class SCIMError(BaseModel):
    """Formato de errores SCIM"""
    schemas: List[str] = ["urn:ietf:params:scim:api:messages:2.0:Error"]
    status: str
    detail: str
    scimType: Optional[str] = None


# Schemas para grupos (opcional)
class GroupSCIM(BaseModel):
    """Modelo de grupo SCIM 2.0"""
    id: str
    displayName: str
    members: List[Dict[str, str]] = []  # [{"value": "user_id", "display": "userName"}]
    meta: SCIMMeta = Field(default_factory=lambda: SCIMMeta(resourceType="Group"))
    schemas: List[str] = ["urn:ietf:params:scim:schemas:core:2.0:Group"]
    
    @field_validator('displayName')
    @classmethod
    def validate_display_name(cls, v):
        """Validar displayName"""
        if not v or len(v.strip()) == 0:
            raise ValueError('displayName is required')
        if len(v) > 100:
            raise ValueError('displayName must be 100 characters or less')
        return v.strip()


class GroupCreateSCIM(BaseModel):
    """Validación para creación de grupo"""
    displayName: str
    members: List[Dict[str, str]] = []
    
    @field_validator('displayName')
    @classmethod
    def validate_display_name(cls, v):
        """Validar displayName único"""
        if not v or len(v.strip()) == 0:
            raise ValueError('displayName is required')
        if len(v) > 100:
            raise ValueError('displayName must be 100 characters or less')
        return v.strip()


# Función helper mejorada para conversión
def user_model_to_scim(user_model, user_groups: List[str] = None) -> UserSCIM:
    """
    Convertir UserModel a UserSCIM con grupos consistentes
    
    Args:
        user_model: UserModel de la base de datos
        user_groups: Lista de grupos obtenida de forma consistente desde GroupRepository
    """
    from app.models.database import UserModel
    
    # Convertir emails de lista de strings a lista de SCIMEmail
    emails = []
    if user_model.emails:
        for i, email in enumerate(user_model.emails):
            emails.append(SCIMEmail(
                value=email,
                primary=(i == 0),  # Primer email es primario
                type="work"
            ))
    
    # Construir nombre
    name = None
    if user_model.givenName or user_model.familyName:
        name = SCIMName(
            givenName=user_model.givenName,
            familyName=user_model.familyName
        )
    
    # Crear meta con timestamps
    meta = SCIMMeta(
        resourceType="User",
        created=user_model.created,
        lastModified=user_model.lastModified,
        location=f"/scim/v2/Users/{user_model.id}"
    )
    
    return UserSCIM(
        id=user_model.id,
        userName=user_model.userName,
        name=name,
        active=user_model.active,
        emails=emails,
        groups=user_groups or [],  # Usar grupos consistentes pasados como parámetro
        dept=user_model.dept,
        riskScore=user_model.riskScore,
        meta=meta
    )


def scim_create_to_user_model(user_create: UserCreateSCIM):
    """Convertir UserCreateSCIM a UserModel"""
    from app.models.database import UserModel
    import uuid
    
    # Convertir emails
    emails = [email.value for email in user_create.emails]
    
    return UserModel(
        id=f"usr_{str(uuid.uuid4())[:8]}",
        userName=user_create.userName,
        givenName=user_create.name.givenName if user_create.name else None,
        familyName=user_create.name.familyName if user_create.name else None,
        active=user_create.active,
        emails=emails,
        dept=user_create.dept,
        riskScore=user_create.riskScore
    )