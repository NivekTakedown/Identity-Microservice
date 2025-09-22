"""
AuthService - Lógica de negocio para autenticación
Minimalista y funcional
"""
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.logger import get_logger
from app.core.jwt_manager import get_jwt_manager
from app.models.auth import (
    TokenRequest, TokenResponse, UserClaims, CredentialsValidator, TokenError
)
from app.repositories.user_repository import get_user_repository

logger = get_logger("auth_service")

class AuthServiceError(Exception):
    """Excepción base para errores del AuthService"""
    pass

class InvalidCredentialsError(AuthServiceError):
    """Credenciales inválidas"""
    pass

class UserInactiveError(AuthServiceError):
    """Usuario inactivo"""
    pass

class AuthService:
    """Servicio de autenticación - Patrón Singleton"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.settings = get_settings()
            self.jwt_manager = get_jwt_manager()
            self.user_repository = get_user_repository()
            AuthService._initialized = True
            logger.info("AuthService initialized")
    
    def authenticate_and_generate_token(self, request: TokenRequest) -> TokenResponse:
        """
        Autentica credenciales y genera token JWT
        
        Args:
            request: Solicitud de token con credenciales
            
        Returns:
            TokenResponse con JWT token
            
        Raises:
            InvalidCredentialsError: Si las credenciales son inválidas
            UserInactiveError: Si el usuario está inactivo
        """
        try:
            logger.info("Starting authentication", grant_type=request.grant_type)
            
            # Validar credenciales según tipo de grant
            if request.grant_type == "client_credentials":
                user_data = self._validate_client_credentials(request.client_id, request.client_secret)
                scopes = CredentialsValidator.get_user_scopes(client_id=request.client_id)
            elif request.grant_type == "password":
                user_data = self._validate_user_password(request.username, request.password)
                scopes = CredentialsValidator.get_user_scopes(username=request.username)
                
                # Verificar si el usuario está activo en el repositorio
                self._check_user_active_status(request.username)
            else:
                raise InvalidCredentialsError(f"Unsupported grant_type: {request.grant_type}")
            
            if not user_data:
                logger.warning("Authentication failed", grant_type=request.grant_type)
                raise InvalidCredentialsError("Invalid credentials")
            
            # Generar claims dinámicos
            claims = self._generate_user_claims(user_data, request.scope or "read", scopes)
            
            # Generar token JWT
            token = self.jwt_manager.generate_token(
                payload=claims.model_dump(exclude_none=True, exclude={"exp", "iat"}),
                expires_in_minutes=self.settings.jwt_expiration_minutes
            )
            
            # Crear respuesta
            response = TokenResponse(
                access_token=token,
                expires_in=self.settings.jwt_expiration_minutes * 60,  # Convertir a segundos
                scope=" ".join(scopes)
            )
            
            logger.info("Authentication successful", 
                       subject=user_data["sub"], 
                       grant_type=request.grant_type,
                       scopes=scopes)
            
            return response
            
        except (InvalidCredentialsError, UserInactiveError) as e:
            logger.warning("Authentication error", error=str(e), grant_type=request.grant_type)
            raise e
        except Exception as e:
            logger.error("Unexpected authentication error", error=str(e))
            raise AuthServiceError(f"Authentication failed: {e}")
    
    def validate_token_and_get_claims(self, token: str) -> UserClaims:
        """
        Valida token JWT y retorna claims del usuario
        
        Args:
            token: Token JWT a validar
            
        Returns:
            UserClaims con información del usuario
            
        Raises:
            AuthServiceError: Si el token es inválido
        """
        try:
            logger.debug("Validating JWT token")
            
            # Validar token con JWT Manager
            decoded_claims = self.jwt_manager.validate_token(token)
            
            # Convertir a UserClaims
            user_claims = UserClaims(
                sub=decoded_claims["sub"],
                scope=decoded_claims["scope"],
                groups=decoded_claims.get("groups", []),
                dept=decoded_claims["dept"],
                riskScore=decoded_claims["riskScore"],
                iss=decoded_claims.get("iss"),
                aud=decoded_claims.get("aud"),
                exp=datetime.fromtimestamp(decoded_claims["exp"], tz=timezone.utc) if "exp" in decoded_claims else None,
                iat=datetime.fromtimestamp(decoded_claims["iat"], tz=timezone.utc) if "iat" in decoded_claims else None
            )
            
            logger.info("Token validation successful", subject=user_claims.sub)
            return user_claims
            
        except Exception as e:
            logger.warning("Token validation failed", error=str(e))
            raise AuthServiceError(f"Token validation failed: {e}")
    
    def _validate_client_credentials(self, client_id: str, client_secret: str) -> Optional[Dict[str, Any]]:
        """Valida credenciales de cliente usando datos mock"""
        return CredentialsValidator.validate_client_credentials(client_id, client_secret)
    
    def _validate_user_password(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Valida credenciales de usuario usando datos mock"""
        return CredentialsValidator.validate_user_password(username, password)
    
    def _check_user_active_status(self, username: str):
        """
        Verifica si el usuario está activo en el repositorio
        Integración con UserRepository para datos de usuario
        """
        try:
            # Buscar usuario en repositorio SCIM
            user = self.user_repository.find_by_username(username)
            if user and not user.get("active", True):
                logger.warning("User is inactive", username=username)
                raise UserInactiveError(f"User {username} is inactive")
                
        except Exception as e:
            # Si hay error accediendo al repositorio, log pero no falle la autenticación
            # ya que tenemos datos mock como fallback
            logger.warning("Could not check user status in repository", 
                         username=username, error=str(e))
    
    def _generate_user_claims(self, user_data: Dict[str, Any], 
                            requested_scope: str, 
                            available_scopes: list) -> UserClaims:
        """
        Genera claims dinámicos del usuario
        
        Args:
            user_data: Datos del usuario desde validador
            requested_scope: Scopes solicitados
            available_scopes: Scopes disponibles para el usuario
            
        Returns:
            UserClaims con claims del usuario
        """
        # Filtrar scopes solicitados vs disponibles
        requested_scopes = set(requested_scope.split())
        final_scopes = list(requested_scopes.intersection(set(available_scopes)))
        
        if not final_scopes:
            final_scopes = ["read"]  # Scope mínimo por defecto
        
        return UserClaims(
            sub=user_data["sub"],
            scope=" ".join(final_scopes),
            groups=user_data.get("groups", []),
            dept=user_data["dept"],
            riskScore=user_data["riskScore"]
        )
    
    def create_token_error(self, error_code: str, description: str = None) -> TokenError:
        """
        Crea respuesta de error OAuth2 estándar
        
        Args:
            error_code: Código de error OAuth2
            description: Descripción opcional del error
            
        Returns:
            TokenError con formato OAuth2
        """
        return TokenError(
            error=error_code,
            error_description=description
        )

# Instancia singleton
_auth_service = None

def get_auth_service() -> AuthService:
    """Factory function para obtener la instancia del AuthService"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service