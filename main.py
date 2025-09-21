"""
Microservicio de Identidades Digitales
Punto de entrada principal
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings, validate_configuration

# Validar configuración al startup
validate_configuration()
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Microservicio de Identidades Digitales - SCIM 2.0, OAuth2 y ABAC",
    version=settings.app_version,
    debug=settings.debug
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": f"{settings.app_name} - Ready",
        "version": settings.app_version,
        "environment": settings.environment
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment
    }

@app.get("/config")
async def get_config():
    """Endpoint para verificar configuración (solo desarrollo)"""
    if settings.environment != "development":
        return {"error": "Config endpoint only available in development"}
    
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "log_level": settings.log_level,
        "cors_origins": settings.cors_origins,
        "db_path": settings.db_path,
        "policies_path": settings.policies_path,
        "jwt_algorithm": settings.jwt_algorithm
        # Note: No exponemos JWT_SECRET por seguridad
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host=settings.host, 
        port=settings.port,
        log_level=settings.log_level.lower()
    )