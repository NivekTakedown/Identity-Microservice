"""
Database Manager singleton para SQLite con protección SQL injection
"""
import sqlite3
import threading
from contextlib import contextmanager
from typing import Dict, List, Optional, Any
from pathlib import Path
from app.core.config import get_settings
from app.core.logger import get_logger
from app.models.database import CREATE_USERS_TABLE, CREATE_GROUPS_TABLE, CREATE_INDEXES

logger = get_logger("database")


class DatabaseManager:
    """Singleton Database Manager para SQLite"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.settings = get_settings()
            self.db_path = self.settings.db_path
            self._ensure_database_exists()
            self._create_tables()
            self.initialized = True
    
    def _ensure_database_exists(self):
        """Crear directorio de base de datos si no existe"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    @contextmanager
    def get_connection(self):
        """Context manager para conexiones SQLite thread-safe"""
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30.0
        )
        conn.row_factory = sqlite3.Row  # Para acceso por nombre de columna
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            logger.error("Database error", error=str(e))
            raise
        finally:
            conn.close()
    
    def _create_tables(self):
        """Crear tablas e índices optimizados"""
        with self.get_connection() as conn:
            # Crear tabla users
            conn.execute(CREATE_USERS_TABLE)
            logger.debug("Users table created/verified")
            
            # Crear tabla groups (opcional)
            conn.execute(CREATE_GROUPS_TABLE)
            logger.debug("Groups table created/verified")
            
            # Crear índices optimizados para búsquedas SCIM
            for index_sql in CREATE_INDEXES:
                conn.execute(index_sql)
            
            conn.commit()
            logger.info("Database schema created with optimized indexes")
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Ejecutar query SELECT con parámetros (protección SQL injection)"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def execute_insert(self, query: str, params: tuple = ()) -> str:
        """Ejecutar INSERT y retornar lastrowid"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.lastrowid
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Ejecutar UPDATE/DELETE y retornar rows affected"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.rowcount


def get_db() -> DatabaseManager:
    """Función helper para obtener instancia del DatabaseManager"""
    return DatabaseManager()