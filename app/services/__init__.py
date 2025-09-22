"""
Servicios de negocio - Capa de lógica de aplicación
"""

class ServiceError(Exception):
    """Excepción base para errores de servicios"""
    pass

class ValidationError(ServiceError):
    """Error de validación de reglas de negocio"""
    pass

class BusinessRuleError(ServiceError):
    """Error de reglas de negocio específicas"""
    pass