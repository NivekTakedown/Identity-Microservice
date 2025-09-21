"""
JWT Manager - Gestión de tokens JWT para autenticación
Soporta algoritmos HS256 y RS256
"""
import jwt
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Union
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import base64
import os

from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger("jwt_manager")

class JWTManagerError(Exception):
    """Excepción base para errores del JWT Manager"""
    pass

class TokenExpiredError(JWTManagerError):
    """Token ha expirado"""
    pass

class TokenInvalidError(JWTManagerError):
    """Token inválido"""
    pass

class JWTManager:
    """
    Manager singleton para operaciones JWT
    Soporta HS256 (clave simétrica) y RS256 (claves asimétricas)
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.settings = get_settings()
            self._algorithm = self.settings.jwt_algorithm
            self._secret_key = None
            self._private_key = None
            self._public_key = None
            self._load_keys()
            JWTManager._initialized = True
            logger.info("JWT Manager initialized", algorithm=self._algorithm)
    
    def _load_keys(self):
        """Carga las claves de firma según el algoritmo configurado"""
        try:
            if self._algorithm == "HS256":
                self._secret_key = self.settings.jwt_secret
                if not self._secret_key:
                    raise JWTManagerError("JWT_SECRET is required for HS256 algorithm")
                logger.info("HS256 secret key loaded successfully")
                
            elif self._algorithm == "RS256":
                # Para RS256, podemos generar claves o cargarlas desde variables de entorno
                private_key_data = os.getenv("JWT_PRIVATE_KEY")
                public_key_data = os.getenv("JWT_PUBLIC_KEY")
                
                if private_key_data and public_key_data:
                    # Cargar claves desde variables de entorno
                    self._load_keys_from_env(private_key_data, public_key_data)
                else:
                    # Generar claves para desarrollo (no recomendado para producción)
                    logger.warning("Generating RSA keys for development. Use environment variables in production.")
                    self._generate_rsa_keys()
                    
                logger.info("RS256 keys loaded successfully")
            else:
                raise JWTManagerError(f"Unsupported JWT algorithm: {self._algorithm}")
                
        except Exception as e:
            logger.error("Failed to load JWT keys", error=str(e), algorithm=self._algorithm)
            raise JWTManagerError(f"Failed to load JWT keys: {e}")
    
    def _load_keys_from_env(self, private_key_data: str, public_key_data: str):
        """Carga claves RSA desde variables de entorno"""
        try:
            # Decodificar claves base64 si es necesario
            if private_key_data.startswith("LS0t"):  # Base64 encoded
                private_key_data = base64.b64decode(private_key_data).decode()
            if public_key_data.startswith("LS0t"):  # Base64 encoded
                public_key_data = base64.b64decode(public_key_data).decode()
            
            self._private_key = serialization.load_pem_private_key(
                private_key_data.encode(),
                password=None,
                backend=default_backend()
            )
            
            self._public_key = serialization.load_pem_public_key(
                public_key_data.encode(),
                backend=default_backend()
            )
            
        except Exception as e:
            raise JWTManagerError(f"Failed to load RSA keys from environment: {e}")
    
    def _generate_rsa_keys(self):
        """Genera claves RSA para desarrollo"""
        try:
            # Generar clave privada
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            
            # Obtener clave pública
            public_key = private_key.public_key()
            
            self._private_key = private_key
            self._public_key = public_key
            
            # Log de las claves generadas (solo para desarrollo)
            if self.settings.environment == "development":
                private_pem = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
                public_pem = public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
                
                logger.debug("Generated RSA keys for development",
                           private_key_preview=private_pem.decode()[:100] + "...",
                           public_key_preview=public_pem.decode()[:100] + "...")
                
        except Exception as e:
            raise JWTManagerError(f"Failed to generate RSA keys: {e}")
    
    def generate_token(self, 
                      payload: Dict[str, Any], 
                      expires_in_minutes: Optional[int] = None) -> str:
        """
        Genera un token JWT con el payload especificado
        
        Args:
            payload: Claims a incluir en el token
            expires_in_minutes: Tiempo de expiración en minutos (default: configuración)
        
        Returns:
            Token JWT firmado
        """
        try:
            # Configurar tiempo de expiración
            if expires_in_minutes is None:
                expires_in_minutes = self.settings.jwt_expiration_minutes
            
            now = datetime.now(timezone.utc)
            exp_time = now + timedelta(minutes=expires_in_minutes)
            
            # Construir claims estándar
            claims = {
                "iat": now,
                "exp": exp_time,
                "iss": self.settings.jwt_issuer,
                "aud": self.settings.jwt_audience,
                **payload
            }
            
            # Generar token según algoritmo
            if self._algorithm == "HS256":
                token = jwt.encode(claims, self._secret_key, algorithm=self._algorithm)
            elif self._algorithm == "RS256":
                token = jwt.encode(claims, self._private_key, algorithm=self._algorithm)
            else:
                raise JWTManagerError(f"Unsupported algorithm: {self._algorithm}")
            
            logger.info("JWT token generated successfully", 
                       subject=payload.get("sub"), 
                       algorithm=self._algorithm,
                       expires_at=exp_time.isoformat())
            
            return token
            
        except Exception as e:
            logger.error("Failed to generate JWT token", error=str(e), payload_keys=list(payload.keys()))
            raise JWTManagerError(f"Failed to generate token: {e}")
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Valida y decodifica un token JWT
        
        Args:
            token: Token JWT a validar
            
        Returns:
            Claims del token decodificado
            
        Raises:
            TokenExpiredError: Si el token ha expirado
            TokenInvalidError: Si el token es inválido
        """
        try:
            # Determinar clave de verificación según algoritmo
            if self._algorithm == "HS256":
                verify_key = self._secret_key
            elif self._algorithm == "RS256":
                verify_key = self._public_key
            else:
                raise TokenInvalidError(f"Unsupported algorithm: {self._algorithm}")
            
            # Decodificar y validar token
            payload = jwt.decode(
                token,
                verify_key,
                algorithms=[self._algorithm],
                issuer=self.settings.jwt_issuer,
                audience=self.settings.jwt_audience,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_iss": True,
                    "verify_aud": True
                }
            )
            
            logger.info("JWT token validated successfully", 
                       subject=payload.get("sub"),
                       algorithm=self._algorithm)
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired", algorithm=self._algorithm)
            raise TokenExpiredError("Token has expired")
            
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid JWT token", error=str(e), algorithm=self._algorithm)
            raise TokenInvalidError(f"Invalid token: {e}")
            
        except Exception as e:
            logger.error("Unexpected error validating JWT token", error=str(e))
            raise TokenInvalidError(f"Token validation failed: {e}")
    
    def refresh_token(self, token: str, extend_minutes: Optional[int] = None) -> str:
        """
        Refresca un token JWT válido extendiéndo su tiempo de vida
        
        Args:
            token: Token JWT actual
            extend_minutes: Minutos adicionales de vida (default: configuración)
            
        Returns:
            Nuevo token JWT con tiempo extendido
        """
        try:
            # Validar token actual
            payload = self.validate_token(token)
            
            # Remover claims de tiempo para regenerar
            filtered_payload = {k: v for k, v in payload.items() 
                              if k not in ["iat", "exp", "iss", "aud"]}
            
            # Generar nuevo token
            return self.generate_token(filtered_payload, extend_minutes)
            
        except (TokenExpiredError, TokenInvalidError) as e:
            logger.warning("Cannot refresh invalid token", error=str(e))
            raise e
    
    def decode_token_without_verification(self, token: str) -> Dict[str, Any]:
        """
        Decodifica un token sin verificar la firma (útil para inspección)
        
        Args:
            token: Token JWT a decodificar
            
        Returns:
            Claims del token sin verificar
        """
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            logger.debug("Token decoded without verification", subject=payload.get("sub"))
            return payload
        except Exception as e:
            logger.error("Failed to decode token", error=str(e))
            raise TokenInvalidError(f"Cannot decode token: {e}")
    
    def get_algorithm(self) -> str:
        """Retorna el algoritmo JWT configurado"""
        return self._algorithm
    
    def get_public_key_pem(self) -> Optional[str]:
        """
        Retorna la clave pública en formato PEM (solo para RS256)
        Útil para compartir con otros servicios para verificación
        """
        if self._algorithm == "RS256" and self._public_key:
            try:
                public_pem = self._public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
                return public_pem.decode()
            except Exception as e:
                logger.error("Failed to export public key", error=str(e))
        return None

# Instancia singleton global
jwt_manager = JWTManager()

def get_jwt_manager() -> JWTManager:
    """Factory function para obtener la instancia del JWT Manager"""
    return jwt_manager