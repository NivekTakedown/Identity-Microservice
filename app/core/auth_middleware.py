"""
Middleware de autenticación JWT
"""
from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logger import get_logger
from app.services.auth_service import get_auth_service
from app.models.auth import UserClaims

logger = get_logger("auth_middleware")

class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware para autenticación automática en rutas protegidas
    """
    
    # Rutas públicas que no requieren autenticación
    EXCLUDED_PATHS = {
        "/",
        "/docs",
        "/openapi.json",
        "/health",
        "/config",
        "/auth/token",  # Endpoint de autenticación
    }
    
    def __init__(self, app, auto_error: bool = False):
        super().__init__(app)
        self.auto_error = auto_error
        self.auth_service = get_auth_service()
    
    async def dispatch(self, request: Request, call_next):
        """Procesa la request para extraer y validar JWT"""
        
        # Verificar si la ruta está excluida
        if self._is_excluded_path(request.url.path):
            return await call_next(request)
        
        # Intentar extraer y validar token
        try:
            claims = await self._extract_and_validate_token(request)
            if claims:
                # Inyectar claims en el contexto de la request
                request.state.user_claims = claims
                request.state.authenticated = True
                logger.debug("Request authenticated", 
                           subject=claims.sub, 
                           path=request.url.path)
            else:
                request.state.authenticated = False
                
        except HTTPException as e:
            if self.auto_error:
                raise e
            # Log pero permite continuar para que el endpoint decida
            logger.warning("Authentication failed for protected route", 
                         path=request.url.path, 
                         error=str(e.detail))
            request.state.authenticated = False
        
        return await call_next(request)
    
    def _is_excluded_path(self, path: str) -> bool:
        """Verifica si la ruta está excluida de autenticación"""
        # Rutas exactas
        if path in self.EXCLUDED_PATHS:
            return True
        
        # Rutas con patrones (prefijos)
        excluded_prefixes = ["/docs", "/openapi"]
        return any(path.startswith(prefix) for prefix in excluded_prefixes)
    
    async def _extract_and_validate_token(self, request: Request) -> Optional[UserClaims]:
        """
        Extrae JWT desde headers y lo valida
        
        Returns:
            UserClaims si el token es válido, None si no hay token
            
        Raises:
            HTTPException: Si el token es inválido
        """
        # Extraer token del header Authorization
        authorization = request.headers.get("Authorization")
        if not authorization:
            return None
        
        # Verificar formato Bearer
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format. Expected 'Bearer <token>'"
            )
        
        token = authorization[7:]  # Remover "Bearer "
        
        try:
            # Validar token con AuthService
            claims = self.auth_service.validate_token_and_get_claims(token)
            return claims
            
        except Exception as e:
            logger.warning("Token validation failed", 
                         error=str(e), 
                         path=request.url.path)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid or expired token: {str(e)}"
            )

# Dependency para obtener claims del usuario autenticado
async def get_current_user(request: Request) -> UserClaims:
    """
    Dependency para obtener claims del usuario autenticado
    
    Args:
        request: Request de FastAPI
        
    Returns:
        UserClaims del usuario autenticado
        
    Raises:
        HTTPException 401: Si no está autenticado
        HTTPException 403: Si está autenticado pero sin permisos
    """
    if not getattr(request.state, "authenticated", False):
        logger.warning("Unauthenticated access attempt", path=request.url.path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    claims = getattr(request.state, "user_claims", None)
    if not claims:
        logger.error("Authenticated but no claims found", path=request.url.path)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid authentication state"
        )
    
    return claims

# Dependency opcional para endpoints que pueden ser públicos o privados
async def get_current_user_optional(request: Request) -> Optional[UserClaims]:
    """
    Dependency opcional que retorna claims si está autenticado, None si no
    
    Args:
        request: Request de FastAPI
        
    Returns:
        UserClaims si está autenticado, None si no
    """
    if getattr(request.state, "authenticated", False):
        return getattr(request.state, "user_claims", None)
    return None

# Security scheme para documentación OpenAPI
security_scheme = HTTPBearer(
    scheme_name="Bearer",
    description="JWT Bearer token authentication"
)

async def verify_token_dependency(credentials: HTTPAuthorizationCredentials = security_scheme) -> UserClaims:
    """
    Dependency alternativo usando HTTPBearer para endpoints específicos
    Útil cuando no se usa el middleware global
    """
    auth_service = get_auth_service()
    
    try:
        claims = auth_service.validate_token_and_get_claims(credentials.credentials)
        return claims
    except Exception as e:
        logger.warning("Token verification failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )