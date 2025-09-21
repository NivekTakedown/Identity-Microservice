"""
Repositorios de datos con manejo de errores personalizados
"""

class RepositoryError(Exception):
    """Excepción base para errores de repositorio"""
    pass

class UserNotFoundError(RepositoryError):
    """Usuario no encontrado"""
    pass

class UserAlreadyExistsError(RepositoryError):
    """Usuario ya existe (duplicado userName)"""
    pass

class GroupNotFoundError(RepositoryError):
    """Grupo no encontrado"""
    pass

class GroupAlreadyExistsError(RepositoryError):
    """Grupo ya existe (duplicado displayName)"""
    pass

class DatabaseError(RepositoryError):
    """Error de base de datos"""
    pass