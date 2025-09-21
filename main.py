"""
Microservicio de Identidades Digitales
Punto de entrada principal
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings, validate_configuration
from app.core.logger import configure_logging, get_logger
from app.core.middleware import LoggingMiddleware

# Configurar logging primero
configure_logging()
logger = get_logger("main")

# Validar configuración al startup
validate_configuration()
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manejo del ciclo de vida de la aplicación"""
    # Startup
    logger.info("Starting Identity Microservice", version=settings.app_version, environment=settings.environment)
    logger.info("Application startup completed", service=settings.app_name)
    
    yield
    
    # Shutdown
    logger.info("Application shutdown", service=settings.app_name)

app = FastAPI(
    title=settings.app_name,
    description="Microservicio de Identidades Digitales - SCIM 2.0, OAuth2 y ABAC",
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan
)

# Añadir middleware de logging
app.add_middleware(LoggingMiddleware)

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
    logger.info("Root endpoint accessed")
    return {
        "message": f"{settings.app_name} - Ready",
        "version": settings.app_version,
        "environment": settings.environment
    }

@app.get("/health")
async def health_check():
    logger.debug("Health check endpoint accessed")
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
        logger.warning("Config endpoint accessed in non-development environment")
        return {"error": "Config endpoint only available in development"}
    
    logger.info("Configuration endpoint accessed")
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
    logger.info("Starting server", host=settings.host, port=settings.port)
    uvicorn.run(
        app, 
        host=settings.host, 
        port=settings.port,
        log_level=settings.log_level.lower()
    )