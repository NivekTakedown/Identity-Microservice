"""
Sistema de logging estructurado (JSON)
"""
import logging
import sys
from typing import Any, Dict
import structlog
from app.core.config import get_settings


def configure_logging():
    """Configurar logging estructurado"""
    settings = get_settings()
    
    # Configurar structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if settings.log_format == "json" 
            else structlog.dev.ConsoleRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configurar logging estándar
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )


def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """Obtener logger estructurado"""
    return structlog.get_logger(name)


def log_request(method: str, path: str, status_code: int, duration: float, **kwargs):
    """Log para requests HTTP"""
    logger = get_logger("request")
    logger.info(
        "HTTP Request",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=round(duration * 1000, 2),
        **kwargs
    )


def log_auth_event(event_type: str, user_id: str = None, success: bool = True, **kwargs):
    """Log para eventos de autenticación"""
    logger = get_logger("auth")
    logger.info(
        "Authentication Event",
        event_type=event_type,
        user_id=user_id,
        success=success,
        **kwargs
    )


def log_abac_decision(subject: Dict[str, Any], resource: Dict[str, Any], 
                     decision: str, rules_applied: list, **kwargs):
    """Log para decisiones ABAC"""
    logger = get_logger("abac")
    logger.info(
        "ABAC Decision",
        subject_dept=subject.get("dept"),
        resource_type=resource.get("type"),
        decision=decision,
        rules_applied=rules_applied,
        **kwargs
    )