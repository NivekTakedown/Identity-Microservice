"""
Modelos Pydantic para autenticación JWT
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime

class TokenRequest(BaseModel):
    """Credenciales de entrada para solicitar token"""
    grant_type: str = Field(default="client_credentials", description="Tipo de grant OAuth2")
    
    # Para client_credentials
    client_id: Optional[str] = Field(None, description="ID del cliente")
    client_secret: Optional[str] = Field(None, description="Secret del cliente")
    
    # Para password grant (alternativo)
    username: Optional[str] = Field(None, description="Nombre de usuario")
    password: Optional[str] = Field(None, description="Contraseña")
    
    scope: Optional[str] = Field(default="read", description="Scopes solicitados")
    
    @field_validator('grant_type')
    @classmethod
    def validate_grant_type(cls, v):
        if v not in ["client_credentials", "password"]:
            raise ValueError("grant_type debe ser 'client_credentials' o 'password'")
        return v
    
    @model_validator(mode='after')
    def validate_credentials(self):
        """Valida que las credenciales sean apropiadas para el grant_type"""
        if self.grant_type == "client_credentials":
            if not self.client_id or not self.client_secret:
                raise ValueError("client_id y client_secret requeridos para client_credentials")
        elif self.grant_type == "password":
            if not self.username or not self.password:
                raise ValueError("username y password requeridos para password grant")
        return self

class TokenResponse(BaseModel):
    """Respuesta con JWT token"""
    access_token: str = Field(..., description="JWT token")
    token_type: str = Field(default="Bearer", description="Tipo de token")
    expires_in: int = Field(..., description="Segundos hasta expiración")
    scope: str = Field(..., description="Scopes concedidos")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "read write"
            }
        }
    }

class UserClaims(BaseModel):
    """Claims del usuario en JWT"""
    sub: str = Field(..., description="Subject - identificador único del usuario")
    scope: str = Field(..., description="Scopes del token")
    groups: List[str] = Field(default_factory=list, description="Grupos del usuario")
    dept: str = Field(..., description="Departamento del usuario")
    riskScore: int = Field(..., ge=0, le=100, description="Score de riesgo 0-100")
    
    # Claims estándar JWT
    iss: Optional[str] = Field(None, description="Issuer")
    aud: Optional[str] = Field(None, description="Audience")
    exp: Optional[datetime] = Field(None, description="Expiration time")
    iat: Optional[datetime] = Field(None, description="Issued at")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "sub": "jdoe",
                "scope": "read write",
                "groups": ["HR_READERS"],
                "dept": "HR",
                "riskScore": 20,
                "iss": "identity-microservice",
                "aud": "identity-api"
            }
        }
    }

class CredentialsValidator:
    """Validador de credenciales mock - datos hardcodeados"""
    
    # Credenciales mock para testing
    MOCK_CLIENTS = {
        "test_client": {
            "secret": "test_secret",
            "scopes": ["read", "write"],
            "user_data": {
                "sub": "test_client",
                "dept": "IT",
                "groups": ["API_CLIENTS"],
                "riskScore": 10
            }
        },
        "hr_app": {
            "secret": "hr_secret_2024",
            "scopes": ["read", "write", "hr:payroll"],
            "user_data": {
                "sub": "hr_app",
                "dept": "HR",
                "groups": ["HR_READERS", "HR_WRITERS"],
                "riskScore": 15
            }
        }
    }
    
    MOCK_USERS = {
        "jdoe": {
            "password": "password123",
            "data": {
                "sub": "jdoe",
                "dept": "HR",
                "groups": ["HR_READERS"],
                "riskScore": 20
            }
        },
        "agonzalez": {
            "password": "finance2024",
            "data": {
                "sub": "agonzalez",
                "dept": "Finance",
                "groups": ["FIN_APPROVERS"],
                "riskScore": 30
            }
        },
        "mrios": {
            "password": "admin_pass",
            "data": {
                "sub": "mrios",
                "dept": "IT",
                "groups": ["ADMINS"],
                "riskScore": 15
            }
        }
    }
    
    @classmethod
    def validate_client_credentials(cls, client_id: str, client_secret: str) -> Optional[Dict[str, Any]]:
        """Valida credenciales de cliente y retorna datos del usuario"""
        client = cls.MOCK_CLIENTS.get(client_id)
        if client and client["secret"] == client_secret:
            return client["user_data"]
        return None
    
    @classmethod
    def validate_user_password(cls, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Valida credenciales de usuario y retorna datos"""
        user = cls.MOCK_USERS.get(username)
        if user and user["password"] == password:
            return user["data"]
        return None
    
    @classmethod
    def get_user_scopes(cls, client_id: str = None, username: str = None) -> List[str]:
        """Obtiene scopes para el cliente o usuario"""
        if client_id and client_id in cls.MOCK_CLIENTS:
            return cls.MOCK_CLIENTS[client_id]["scopes"]
        elif username and username in cls.MOCK_USERS:
            return ["read", "write"]  # Scopes por defecto para usuarios
        return ["read"]

class TokenError(BaseModel):
    """Error en solicitud de token según RFC 6749"""
    error: str = Field(..., description="Código de error OAuth2")
    error_description: Optional[str] = Field(None, description="Descripción del error")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "invalid_client",
                "error_description": "Client authentication failed"
            }
        }
    }