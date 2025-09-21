"""
Configuración centralizada usando Pydantic Settings
"""
import secrets
import json
from typing import List, Union
from pydantic import Field
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Configuración centralizada de la aplicación"""
    
    # Aplicación
    app_name: str = Field(default="Identity Microservice", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=True, alias="DEBUG")
    
    # Servidor
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    
    # Base de datos
    db_path: str = Field(default="./data/identity.db", alias="DB_PATH")
    
    # JWT Configuration
    jwt_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(32), alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=30, alias="JWT_EXPIRE_MINUTES")
    
    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")
    
    # CORS
    cors_origins: Union[str, List[str]] = Field(
        default='["http://localhost:3000", "http://localhost:8080"]',
        alias="CORS_ORIGINS"
    )
    
    # Políticas ABAC
    policies_path: str = Field(default="./policies/policies.json", alias="POLICIES_PATH")
    
    def model_post_init(self, __context):
        """Post-init validation using model_post_init instead of @validator"""
        # Parse CORS origins
        if isinstance(self.cors_origins, str):
            try:
                self.cors_origins = json.loads(self.cors_origins)
            except json.JSONDecodeError:
                self.cors_origins = [origin.strip() for origin in self.cors_origins.split(",")]
        
        # Validate log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        self.log_level = self.log_level.upper()
        
        # Validate environment
        valid_envs = ["development", "testing", "production"]
        if self.environment.lower() not in valid_envs:
            raise ValueError(f"environment must be one of {valid_envs}")
        self.environment = self.environment.lower()

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }


# Singleton instance
_settings = None

def get_settings() -> Settings:
    """Get settings singleton instance"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Validación al startup
def validate_configuration():
    """Validar configuración al iniciar la aplicación"""
    settings = get_settings()
    
    # Validar JWT secret en producción
    if settings.environment == "production" and len(settings.jwt_secret) < 32:
        raise ValueError("JWT_SECRET must be at least 32 characters in production")
    
    # Validar paths de archivos
    
    # Crear directorio de base de datos si no existe
    db_dir = Path(settings.db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    
    # Crear directorio de políticas si no existe
    policies_dir = Path(settings.policies_path).parent
    policies_dir.mkdir(parents=True, exist_ok=True)
    
    return True