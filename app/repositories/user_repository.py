"""
UserRepository - Capa de acceso a datos para usuarios SCIM
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import sqlite3
from app.core.database import get_db
from app.core.logger import get_logger
from app.models.database import UserModel
from app.repositories import UserNotFoundError, UserAlreadyExistsError, DatabaseError

logger = get_logger("user_repository")


class UserRepository:
    """Repositorio para operaciones CRUD de usuarios"""
    
    def __init__(self):
        self.db = get_db()
    
    def create_user(self, user_model: UserModel) -> UserModel:
        """
        Insertar usuario con validación de unicidad
        
        Args:
            user_model: Modelo de usuario a crear
            
        Returns:
            UserModel: Usuario creado con timestamps actualizados
            
        Raises:
            UserAlreadyExistsError: Si userName ya existe
            DatabaseError: Error en base de datos
        """
        try:
            # Verificar si userName ya existe
            existing = self._check_username_exists(user_model.userName)
            if existing:
                logger.warning("Attempt to create duplicate user", userName=user_model.userName)
                raise UserAlreadyExistsError(f"User with userName '{user_model.userName}' already exists")
            
            # Actualizar timestamps
            now = datetime.now().isoformat() + "Z"
            user_model.created = now
            user_model.lastModified = now
            
            # Preparar datos para inserción
            user_data = user_model.to_dict()
            
            # Query de inserción con parámetros (protección SQL injection)
            insert_query = """
                INSERT INTO users 
                (id, userName, givenName, familyName, active, emails, groups_list, dept, riskScore, created, lastModified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            params = (
                user_data['id'], user_data['userName'], user_data['givenName'],
                user_data['familyName'], user_data['active'], user_data['emails'],
                user_data['groups_list'], user_data['dept'], user_data['riskScore'],
                user_data['created'], user_data['lastModified']
            )
            
            # Ejecutar inserción
            self.db.execute_insert(insert_query, params)
            
            logger.info("User created successfully", userId=user_model.id, userName=user_model.userName)
            return user_model
            
        except UserAlreadyExistsError:
            raise
        except Exception as e:
            logger.error("Failed to create user", error=str(e), userName=user_model.userName)
            raise DatabaseError(f"Failed to create user: {str(e)}")
    
    def get_user_by_id(self, user_id: str) -> Optional[UserModel]:
        """
        Búsqueda por UUID
        
        Args:
            user_id: ID del usuario
            
        Returns:
            UserModel o None si no existe
            
        Raises:
            DatabaseError: Error en base de datos
        """
        try:
            query = "SELECT * FROM users WHERE id = ?"
            results = self.db.execute_query(query, (user_id,))
            
            if not results:
                logger.debug("User not found by ID", userId=user_id)
                return None
            
            user_data = results[0]
            user_model = UserModel.from_dict(user_data)
            
            logger.debug("User found by ID", userId=user_id, userName=user_model.userName)
            return user_model
            
        except Exception as e:
            logger.error("Failed to get user by ID", error=str(e), userId=user_id)
            raise DatabaseError(f"Failed to get user by ID: {str(e)}")
    
    def update_user(self, user_id: str, updates: Dict[str, Any]) -> UserModel:
        """
        Actualización parcial (PATCH)
        
        Args:
            user_id: ID del usuario a actualizar
            updates: Diccionario con campos a actualizar
            
        Returns:
            UserModel: Usuario actualizado
            
        Raises:
            UserNotFoundError: Si usuario no existe
            DatabaseError: Error en base de datos
        """
        try:
            # Verificar que el usuario existe
            existing_user = self.get_user_by_id(user_id)
            if not existing_user:
                raise UserNotFoundError(f"User with ID '{user_id}' not found")
            
            # Verificar unicidad de userName si se está actualizando
            if 'userName' in updates and updates['userName'] != existing_user.userName:
                if self._check_username_exists(updates['userName']):
                    raise UserAlreadyExistsError(f"User with userName '{updates['userName']}' already exists")
            
            # Construir query de actualización dinámicamente
            set_clauses = []
            params = []
            
            # Campos permitidos para actualización
            allowed_fields = ['userName', 'givenName', 'familyName', 'active', 'emails', 'groups_list', 'dept', 'riskScore']
            
            for field, value in updates.items():
                if field in allowed_fields:
                    set_clauses.append(f"{field} = ?")
                    # Convertir listas a JSON si es necesario
                    if field in ['emails', 'groups_list'] and isinstance(value, list):
                        import json
                        params.append(json.dumps(value))
                    else:
                        params.append(value)
            
            if not set_clauses:
                logger.warning("No valid fields to update", userId=user_id, updates=updates)
                return existing_user
            
            # Actualizar lastModified
            now = datetime.now().isoformat() + "Z"
            set_clauses.append("lastModified = ?")
            params.append(now)
            
            # Agregar user_id al final para la cláusula WHERE
            params.append(user_id)
            
            update_query = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?"
            
            # Ejecutar actualización
            rows_affected = self.db.execute_update(update_query, tuple(params))
            
            if rows_affected == 0:
                raise UserNotFoundError(f"User with ID '{user_id}' not found")
            
            # Obtener usuario actualizado
            updated_user = self.get_user_by_id(user_id)
            
            logger.info("User updated successfully", userId=user_id, updatedFields=list(updates.keys()))
            return updated_user
            
        except (UserNotFoundError, UserAlreadyExistsError):
            raise
        except Exception as e:
            logger.error("Failed to update user", error=str(e), userId=user_id)
            raise DatabaseError(f"Failed to update user: {str(e)}")
    
    def find_by_username(self, username: str) -> Optional[UserModel]:
        """
        Búsqueda exacta con filtros SCIM
        
        Args:
            username: userName a buscar
            
        Returns:
            UserModel o None si no existe
            
        Raises:
            DatabaseError: Error en base de datos
        """
        try:
            query = "SELECT * FROM users WHERE userName = ?"
            results = self.db.execute_query(query, (username,))
            
            if not results:
                logger.debug("User not found by username", userName=username)
                return None
            
            user_data = results[0]
            user_model = UserModel.from_dict(user_data)
            
            logger.debug("User found by username", userName=username, userId=user_model.id)
            return user_model
            
        except Exception as e:
            logger.error("Failed to find user by username", error=str(e), userName=username)
            raise DatabaseError(f"Failed to find user by username: {str(e)}")
    
    def list_users(self, active_only: bool = None, limit: int = 100, offset: int = 0) -> List[UserModel]:
        """
        Listar usuarios con filtros opcionales
        
        Args:
            active_only: Filtrar solo usuarios activos
            limit: Número máximo de resultados
            offset: Offset para paginación
            
        Returns:
            List[UserModel]: Lista de usuarios
        """
        try:
            query = "SELECT * FROM users"
            params = []
            
            if active_only is not None:
                query += " WHERE active = ?"
                params.append(int(active_only))
            
            query += " ORDER BY created DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            results = self.db.execute_query(query, tuple(params))
            
            users = [UserModel.from_dict(user_data) for user_data in results]
            
            logger.debug("Users listed", count=len(users), activeOnly=active_only)
            return users
            
        except Exception as e:
            logger.error("Failed to list users", error=str(e))
            raise DatabaseError(f"Failed to list users: {str(e)}")
    
    def delete_user(self, user_id: str) -> bool:
        """
        Eliminar usuario por ID
        
        Args:
            user_id: ID del usuario a eliminar
            
        Returns:
            bool: True si se eliminó, False si no existía
            
        Raises:
            DatabaseError: Error en base de datos
        """
        try:
            query = "DELETE FROM users WHERE id = ?"
            rows_affected = self.db.execute_update(query, (user_id,))
            
            if rows_affected > 0:
                logger.info("User deleted successfully", userId=user_id)
                return True
            else:
                logger.debug("User not found for deletion", userId=user_id)
                return False
                
        except Exception as e:
            logger.error("Failed to delete user", error=str(e), userId=user_id)
            raise DatabaseError(f"Failed to delete user: {str(e)}")
    
    def count_users(self, active_only: bool = None) -> int:
        """
        Contar usuarios total
        
        Args:
            active_only: Contar solo usuarios activos
            
        Returns:
            int: Número de usuarios
        """
        try:
            query = "SELECT COUNT(*) as count FROM users"
            params = []
            
            if active_only is not None:
                query += " WHERE active = ?"
                params.append(int(active_only))
            
            results = self.db.execute_query(query, tuple(params))
            return results[0]['count']
            
        except Exception as e:
            logger.error("Failed to count users", error=str(e))
            raise DatabaseError(f"Failed to count users: {str(e)}")
    
    def _check_username_exists(self, username: str) -> bool:
        """
        Verificar si userName ya existe (método privado)
        
        Args:
            username: userName a verificar
            
        Returns:
            bool: True si existe, False si no
        """
        try:
            query = "SELECT 1 FROM users WHERE userName = ? LIMIT 1"
            results = self.db.execute_query(query, (username,))
            return len(results) > 0
        except Exception:
            return False


# Instancia singleton del repositorio
_user_repository = None

def get_user_repository() -> UserRepository:
    """Obtener instancia singleton del UserRepository"""
    global _user_repository
    if _user_repository is None:
        _user_repository = UserRepository()
    return _user_repository