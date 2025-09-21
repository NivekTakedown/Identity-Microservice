"""
GroupRepository - Capa de acceso a datos para grupos SCIM
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
from app.core.database import get_db
from app.core.logger import get_logger
from app.models.database import GroupModel
from app.repositories import GroupNotFoundError, GroupAlreadyExistsError, DatabaseError

logger = get_logger("group_repository")


class GroupRepository:
    """Repositorio para operaciones CRUD de grupos"""
    
    def __init__(self):
        self.db = get_db()
    
    def create_group(self, group_model: GroupModel) -> GroupModel:
        """
        Creación de grupos con validación de unicidad
        
        Args:
            group_model: Modelo de grupo a crear
            
        Returns:
            GroupModel: Grupo creado con timestamps actualizados
            
        Raises:
            GroupAlreadyExistsError: Si displayName ya existe
            DatabaseError: Error en base de datos
        """
        try:
            # Verificar si displayName ya existe
            existing = self._check_display_name_exists(group_model.displayName)
            if existing:
                logger.warning("Attempt to create duplicate group", displayName=group_model.displayName)
                raise GroupAlreadyExistsError(f"Group with displayName '{group_model.displayName}' already exists")
            
            # Actualizar timestamps
            now = datetime.now().isoformat() + "Z"
            group_model.created = now
            group_model.lastModified = now
            
            # Preparar datos para inserción
            group_data = group_model.to_dict()
            
            # Query de inserción con parámetros (protección SQL injection)
            insert_query = """
                INSERT INTO groups 
                (id, displayName, members, created, lastModified)
                VALUES (?, ?, ?, ?, ?)
            """
            
            params = (
                group_data['id'], group_data['displayName'], group_data['members'],
                group_data['created'], group_data['lastModified']
            )
            
            # Ejecutar inserción
            self.db.execute_insert(insert_query, params)
            
            logger.info("Group created successfully", groupId=group_model.id, displayName=group_model.displayName)
            return group_model
            
        except GroupAlreadyExistsError:
            raise
        except Exception as e:
            logger.error("Failed to create group", error=str(e), displayName=group_model.displayName)
            raise DatabaseError(f"Failed to create group: {str(e)}")
    
    def get_group_by_id(self, group_id: str) -> Optional[GroupModel]:
        """
        Búsqueda de grupos por ID
        
        Args:
            group_id: ID del grupo
            
        Returns:
            GroupModel o None si no existe
            
        Raises:
            DatabaseError: Error en base de datos
        """
        try:
            query = "SELECT * FROM groups WHERE id = ?"
            results = self.db.execute_query(query, (group_id,))
            
            if not results:
                logger.debug("Group not found by ID", groupId=group_id)
                return None
            
            group_data = results[0]
            group_model = GroupModel.from_dict(group_data)
            
            logger.debug("Group found by ID", groupId=group_id, displayName=group_model.displayName)
            return group_model
            
        except Exception as e:
            logger.error("Failed to get group by ID", error=str(e), groupId=group_id)
            raise DatabaseError(f"Failed to get group by ID: {str(e)}")
    
    def update_group_members(self, group_id: str, members: List[str]) -> GroupModel:
        """
        Gestión de membresías - actualizar miembros del grupo
        
        Args:
            group_id: ID del grupo a actualizar
            members: Lista de IDs de usuarios miembros
            
        Returns:
            GroupModel: Grupo actualizado
            
        Raises:
            GroupNotFoundError: Si grupo no existe
            DatabaseError: Error en base de datos
        """
        try:
            # Verificar que el grupo existe
            existing_group = self.get_group_by_id(group_id)
            if not existing_group:
                raise GroupNotFoundError(f"Group with ID '{group_id}' not found")
            
            # Actualizar lastModified y members
            now = datetime.now().isoformat() + "Z"
            members_json = json.dumps(members)
            
            update_query = "UPDATE groups SET members = ?, lastModified = ? WHERE id = ?"
            params = (members_json, now, group_id)
            
            # Ejecutar actualización
            rows_affected = self.db.execute_update(update_query, params)
            
            if rows_affected == 0:
                raise GroupNotFoundError(f"Group with ID '{group_id}' not found")
            
            # Obtener grupo actualizado
            updated_group = self.get_group_by_id(group_id)
            
            logger.info("Group members updated successfully", groupId=group_id, memberCount=len(members))
            return updated_group
            
        except GroupNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to update group members", error=str(e), groupId=group_id)
            raise DatabaseError(f"Failed to update group members: {str(e)}")
    
    def add_member_to_group(self, group_id: str, user_id: str) -> GroupModel:
        """
        Agregar un miembro al grupo (relación Many-to-Many)
        
        Args:
            group_id: ID del grupo
            user_id: ID del usuario a agregar
            
        Returns:
            GroupModel: Grupo actualizado
        """
        try:
            group = self.get_group_by_id(group_id)
            if not group:
                raise GroupNotFoundError(f"Group with ID '{group_id}' not found")
            
            # Agregar usuario si no está ya en el grupo
            if user_id not in group.members:
                group.members.append(user_id)
                return self.update_group_members(group_id, group.members)
            
            logger.debug("User already member of group", groupId=group_id, userId=user_id)
            return group
            
        except GroupNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to add member to group", error=str(e), groupId=group_id, userId=user_id)
            raise DatabaseError(f"Failed to add member to group: {str(e)}")
    
    def remove_member_from_group(self, group_id: str, user_id: str) -> GroupModel:
        """
        Remover un miembro del grupo (relación Many-to-Many)
        
        Args:
            group_id: ID del grupo
            user_id: ID del usuario a remover
            
        Returns:
            GroupModel: Grupo actualizado
        """
        try:
            group = self.get_group_by_id(group_id)
            if not group:
                raise GroupNotFoundError(f"Group with ID '{group_id}' not found")
            
            # Remover usuario si está en el grupo
            if user_id in group.members:
                group.members.remove(user_id)
                return self.update_group_members(group_id, group.members)
            
            logger.debug("User not member of group", groupId=group_id, userId=user_id)
            return group
            
        except GroupNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to remove member from group", error=str(e), groupId=group_id, userId=user_id)
            raise DatabaseError(f"Failed to remove member from group: {str(e)}")
    
    def find_by_display_name(self, display_name: str) -> Optional[GroupModel]:
        """
        Búsqueda por displayName
        
        Args:
            display_name: displayName a buscar
            
        Returns:
            GroupModel o None si no existe
        """
        try:
            query = "SELECT * FROM groups WHERE displayName = ?"
            results = self.db.execute_query(query, (display_name,))
            
            if not results:
                logger.debug("Group not found by displayName", displayName=display_name)
                return None
            
            group_data = results[0]
            group_model = GroupModel.from_dict(group_data)
            
            logger.debug("Group found by displayName", displayName=display_name, groupId=group_model.id)
            return group_model
            
        except Exception as e:
            logger.error("Failed to find group by displayName", error=str(e), displayName=display_name)
            raise DatabaseError(f"Failed to find group by displayName: {str(e)}")
    
    def list_groups(self, limit: int = 100, offset: int = 0) -> List[GroupModel]:
        """
        Listar grupos con paginación
        
        Args:
            limit: Número máximo de resultados
            offset: Offset para paginación
            
        Returns:
            List[GroupModel]: Lista de grupos
        """
        try:
            query = "SELECT * FROM groups ORDER BY created DESC LIMIT ? OFFSET ?"
            params = (limit, offset)
            
            results = self.db.execute_query(query, params)
            
            groups = [GroupModel.from_dict(group_data) for group_data in results]
            
            logger.debug("Groups listed", count=len(groups))
            return groups
            
        except Exception as e:
            logger.error("Failed to list groups", error=str(e))
            raise DatabaseError(f"Failed to list groups: {str(e)}")
    
    def get_groups_for_user(self, user_id: str) -> List[GroupModel]:
        """
        Obtener todos los grupos de un usuario (relaciones Many-to-Many)
        
        Args:
            user_id: ID del usuario
            
        Returns:
            List[GroupModel]: Lista de grupos donde el usuario es miembro
        """
        try:
            # Buscar grupos que contengan el user_id en members
            query = "SELECT * FROM groups WHERE members LIKE ?"
            # Usar LIKE para buscar en JSON - no es ideal pero funciona para el scope
            search_pattern = f'%"{user_id}"%'
            
            results = self.db.execute_query(query, (search_pattern,))
            
            groups = []
            for group_data in results:
                group_model = GroupModel.from_dict(group_data)
                # Verificar que realmente está en la lista de miembros
                if user_id in group_model.members:
                    groups.append(group_model)
            
            logger.debug("Groups found for user", userId=user_id, groupCount=len(groups))
            return groups
            
        except Exception as e:
            logger.error("Failed to get groups for user", error=str(e), userId=user_id)
            raise DatabaseError(f"Failed to get groups for user: {str(e)}")
    
    def delete_group(self, group_id: str) -> bool:
        """
        Eliminar grupo por ID
        
        Args:
            group_id: ID del grupo a eliminar
            
        Returns:
            bool: True si se eliminó, False si no existía
        """
        try:
            query = "DELETE FROM groups WHERE id = ?"
            rows_affected = self.db.execute_update(query, (group_id,))
            
            if rows_affected > 0:
                logger.info("Group deleted successfully", groupId=group_id)
                return True
            else:
                logger.debug("Group not found for deletion", groupId=group_id)
                return False
                
        except Exception as e:
            logger.error("Failed to delete group", error=str(e), groupId=group_id)
            raise DatabaseError(f"Failed to delete group: {str(e)}")
    
    def count_groups(self) -> int:
        """
        Contar grupos total
        
        Returns:
            int: Número de grupos
        """
        try:
            query = "SELECT COUNT(*) as count FROM groups"
            results = self.db.execute_query(query)
            return results[0]['count']
            
        except Exception as e:
            logger.error("Failed to count groups", error=str(e))
            raise DatabaseError(f"Failed to count groups: {str(e)}")
    
    def _check_display_name_exists(self, display_name: str) -> bool:
        """
        Verificar si displayName ya existe (método privado)
        
        Args:
            display_name: displayName a verificar
            
        Returns:
            bool: True si existe, False si no
        """
        try:
            query = "SELECT 1 FROM groups WHERE displayName = ? LIMIT 1"
            results = self.db.execute_query(query, (display_name,))
            return len(results) > 0
        except Exception:
            return False


# Instancia singleton del repositorio
_group_repository = None

def get_group_repository() -> GroupRepository:
    """Obtener instancia singleton del GroupRepository"""
    global _group_repository
    if _group_repository is None:
        _group_repository = GroupRepository()
    return _group_repository