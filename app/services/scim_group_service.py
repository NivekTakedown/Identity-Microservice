"""
SCIMGroupService - Lógica de negocio para grupos SCIM 2.0
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.core.logger import get_logger
from app.models.scim import (
    GroupSCIM, GroupCreateSCIM, SCIMResponse, SCIMError
)
from app.models.database import GroupModel
from app.repositories.group_repository import get_group_repository
from app.repositories.user_repository import get_user_repository
from app.repositories import (
    GroupNotFoundError, GroupAlreadyExistsError, UserNotFoundError, DatabaseError
)

logger = get_logger("scim_group_service")


def group_model_to_scim(group_model: GroupModel) -> GroupSCIM:
    """
    Convertir GroupModel a GroupSCIM
    
    Args:
        group_model: Modelo interno de grupo
        
    Returns:
        GroupSCIM: Grupo en formato SCIM 2.0
    """
    from app.models.scim import SCIMMeta
    
    # Convertir members de lista de IDs a formato SCIM
    members_scim = []
    if group_model.members:
        for user_id in group_model.members:
            # Obtener userName para display
            user_repo = get_user_repository()
            user = user_repo.get_user_by_id(user_id)
            if user:
                members_scim.append({
                    "value": user_id,
                    "display": user.userName,
                    "$ref": f"/scim/v2/Users/{user_id}"
                })
    
    # Crear meta con timestamps
    meta = SCIMMeta(
        resourceType="Group",
        created=group_model.created,
        lastModified=group_model.lastModified,
        location=f"/scim/v2/Groups/{group_model.id}"
    )
    
    return GroupSCIM(
        id=group_model.id,
        displayName=group_model.displayName,
        members=members_scim,
        meta=meta
    )


def scim_create_to_group_model(group_create: GroupCreateSCIM) -> GroupModel:
    """
    Convertir GroupCreateSCIM a GroupModel
    
    Args:
        group_create: Datos de creación SCIM
        
    Returns:
        GroupModel: Modelo interno de grupo
    """
    import uuid
    
    # Extraer solo los IDs de usuarios de los miembros
    member_ids = []
    if group_create.members:
        for member in group_create.members:
            if isinstance(member, dict) and "value" in member:
                member_ids.append(member["value"])
    
    return GroupModel(
        id=f"grp_{str(uuid.uuid4())[:8]}",
        displayName=group_create.displayName,
        members=member_ids
    )


class SCIMGroupService:
    """Servicio de lógica de negocio para grupos SCIM"""
    
    def __init__(self):
        self.group_repo = get_group_repository()
        self.user_repo = get_user_repository()
    
    def create_group(self, group_create: GroupCreateSCIM) -> GroupSCIM:
        """
        Crear grupo con validación completa de reglas de negocio SCIM
        
        Args:
            group_create: Datos de grupo a crear
            
        Returns:
            GroupSCIM: Grupo creado con metadatos completos
            
        Raises:
            GroupAlreadyExistsError: Si displayName ya existe
            UserNotFoundError: Si algún miembro especificado no existe
            DatabaseError: Error en operaciones de base de datos
        """
        try:
            logger.info("Creating SCIM group", displayName=group_create.displayName)
            
            # 1. Validar integridad referencial - verificar que usuarios miembros existen
            valid_members = []
            if group_create.members:
                for member in group_create.members:
                    user_id = member.get("value") if isinstance(member, dict) else member
                    if user_id:
                        existing_user = self.user_repo.get_user_by_id(user_id)
                        if not existing_user:
                            logger.warning("User not found during group creation", 
                                         displayName=group_create.displayName, userId=user_id)
                            raise UserNotFoundError(f"User '{user_id}' does not exist")
                        valid_members.append(user_id)
                        logger.debug("User validated for group membership", 
                                   userId=user_id, userName=existing_user.userName)
            
            # 2. Convertir SCIM a modelo interno
            group_model = scim_create_to_group_model(group_create)
            group_model.members = valid_members  # Usar miembros validados
            
            # 3. Crear grupo en repositorio
            created_group = self.group_repo.create_group(group_model)
            
            # 4. Convertir a SCIM con metadatos completos
            scim_group = group_model_to_scim(created_group)
            
            logger.info("SCIM group created successfully", 
                       groupId=created_group.id, displayName=created_group.displayName,
                       memberCount=len(valid_members))
            
            return scim_group
            
        except (GroupAlreadyExistsError, UserNotFoundError):
            raise
        except Exception as e:
            logger.error("Failed to create SCIM group", 
                        displayName=group_create.displayName, error=str(e))
            raise DatabaseError(f"Failed to create group: {str(e)}")
    
    def get_group_by_id(self, group_id: str) -> Optional[GroupSCIM]:
        """
        Obtener grupo por ID con metadatos SCIM completos
        
        Args:
            group_id: ID del grupo
            
        Returns:
            GroupSCIM o None si no existe
        """
        try:
            logger.debug("Getting SCIM group by ID", groupId=group_id)
            
            # 1. Obtener grupo del repositorio
            group_model = self.group_repo.get_group_by_id(group_id)
            if not group_model:
                logger.debug("Group not found", groupId=group_id)
                return None
            
            # 2. Convertir a SCIM con metadatos
            scim_group = group_model_to_scim(group_model)
            
            logger.debug("SCIM group retrieved successfully", 
                        groupId=group_id, displayName=group_model.displayName)
            
            return scim_group
            
        except Exception as e:
            logger.error("Failed to get SCIM group", groupId=group_id, error=str(e))
            raise DatabaseError(f"Failed to get group: {str(e)}")
    
    def update_group_members(self, group_id: str, members: List[Dict[str, str]]) -> GroupSCIM:
        """
        Actualizar miembros del grupo con validación de membresías
        
        Args:
            group_id: ID del grupo a actualizar
            members: Lista de miembros en formato SCIM [{"value": "user_id", "display": "userName"}]
            
        Returns:
            GroupSCIM: Grupo actualizado
            
        Raises:
            GroupNotFoundError: Si grupo no existe
            UserNotFoundError: Si algún usuario no existe
        """
        try:
            logger.info("Updating SCIM group members", groupId=group_id)
            
            # 1. Verificar que grupo existe
            existing_group = self.group_repo.get_group_by_id(group_id)
            if not existing_group:
                raise GroupNotFoundError(f"Group with ID '{group_id}' not found")
            
            # 2. Validar membresías - verificar que todos los usuarios existen
            valid_member_ids = []
            for member in members:
                user_id = member.get("value") if isinstance(member, dict) else str(member)
                if user_id:
                    existing_user = self.user_repo.get_user_by_id(user_id)
                    if not existing_user:
                        logger.warning("User not found during group update", 
                                     groupId=group_id, userId=user_id)
                        raise UserNotFoundError(f"User '{user_id}' does not exist")
                    valid_member_ids.append(user_id)
                    logger.debug("User validated for group membership", 
                               userId=user_id, userName=existing_user.userName)
            
            # 3. Actualizar miembros en repositorio
            updated_group = self.group_repo.update_group_members(group_id, valid_member_ids)
            
            # 4. Convertir a SCIM
            scim_group = group_model_to_scim(updated_group)
            
            logger.info("SCIM group members updated successfully", 
                       groupId=group_id, memberCount=len(valid_member_ids))
            
            return scim_group
            
        except (GroupNotFoundError, UserNotFoundError):
            raise
        except Exception as e:
            logger.error("Failed to update SCIM group members", groupId=group_id, error=str(e))
            raise DatabaseError(f"Failed to update group members: {str(e)}")
    
    def add_member_to_group(self, group_id: str, user_id: str) -> GroupSCIM:
        """
        Agregar un miembro al grupo con validación
        
        Args:
            group_id: ID del grupo
            user_id: ID del usuario a agregar
            
        Returns:
            GroupSCIM: Grupo actualizado
        """
        try:
            logger.info("Adding member to SCIM group", groupId=group_id, userId=user_id)
            
            # 1. Validar que usuario existe
            existing_user = self.user_repo.get_user_by_id(user_id)
            if not existing_user:
                raise UserNotFoundError(f"User '{user_id}' does not exist")
            
            # 2. Agregar miembro usando repositorio
            updated_group = self.group_repo.add_member_to_group(group_id, user_id)
            
            # 3. Convertir a SCIM
            scim_group = group_model_to_scim(updated_group)
            
            logger.info("Member added to SCIM group successfully", 
                       groupId=group_id, userId=user_id, userName=existing_user.userName)
            
            return scim_group
            
        except (GroupNotFoundError, UserNotFoundError):
            raise
        except Exception as e:
            logger.error("Failed to add member to SCIM group", 
                        groupId=group_id, userId=user_id, error=str(e))
            raise DatabaseError(f"Failed to add member to group: {str(e)}")
    
    def remove_member_from_group(self, group_id: str, user_id: str) -> GroupSCIM:
        """
        Remover un miembro del grupo
        
        Args:
            group_id: ID del grupo
            user_id: ID del usuario a remover
            
        Returns:
            GroupSCIM: Grupo actualizado
        """
        try:
            logger.info("Removing member from SCIM group", groupId=group_id, userId=user_id)
            
            # 1. Remover miembro usando repositorio
            updated_group = self.group_repo.remove_member_from_group(group_id, user_id)
            
            # 2. Convertir a SCIM
            scim_group = group_model_to_scim(updated_group)
            
            logger.info("Member removed from SCIM group successfully", 
                       groupId=group_id, userId=user_id)
            
            return scim_group
            
        except GroupNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to remove member from SCIM group", 
                        groupId=group_id, userId=user_id, error=str(e))
            raise DatabaseError(f"Failed to remove member from group: {str(e)}")
    
    def find_by_display_name(self, display_name: str) -> Optional[GroupSCIM]:
        """
        Buscar grupo por displayName (filtro SCIM)
        
        Args:
            display_name: displayName a buscar
            
        Returns:
            GroupSCIM o None si no existe
        """
        try:
            logger.debug("Finding SCIM group by displayName", displayName=display_name)
            
            # 1. Buscar grupo
            group_model = self.group_repo.find_by_display_name(display_name)
            if not group_model:
                logger.debug("Group not found by displayName", displayName=display_name)
                return None
            
            # 2. Convertir a SCIM
            scim_group = group_model_to_scim(group_model)
            
            logger.debug("SCIM group found by displayName", 
                        displayName=display_name, groupId=group_model.id)
            
            return scim_group
            
        except Exception as e:
            logger.error("Failed to find SCIM group by displayName", 
                        displayName=display_name, error=str(e))
            raise DatabaseError(f"Failed to find group: {str(e)}")
    
    def list_groups(self, start_index: int = 1, count: int = 100) -> SCIMResponse:
        """
        Listar grupos con formato de respuesta SCIM estándar
        
        Args:
            start_index: Índice de inicio (SCIM usa 1-based)
            count: Número máximo de resultados
            
        Returns:
            SCIMResponse: Respuesta SCIM con paginación
        """
        try:
            logger.debug("Listing SCIM groups", startIndex=start_index, count=count)
            
            # Convertir de SCIM 1-based a 0-based offset
            offset = max(0, start_index - 1)
            
            # 1. Obtener grupos del repositorio
            groups = self.group_repo.list_groups(limit=count, offset=offset)
            
            # 2. Convertir cada grupo a SCIM
            scim_groups = []
            for group in groups:
                scim_group = group_model_to_scim(group)
                scim_groups.append(scim_group)
            
            # 3. Obtener total para metadatos de paginación
            total_results = self.group_repo.count_groups()
            
            # 4. Crear respuesta SCIM estándar
            response = SCIMResponse(
                schemas=["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
                totalResults=total_results,
                Resources=scim_groups,
                startIndex=start_index,
                itemsPerPage=len(scim_groups)
            )
            
            logger.debug("SCIM groups listed successfully", 
                        returnedCount=len(scim_groups), totalResults=total_results)
            
            return response
            
        except Exception as e:
            logger.error("Failed to list SCIM groups", error=str(e))
            raise DatabaseError(f"Failed to list groups: {str(e)}")
    
    def delete_group(self, group_id: str) -> bool:
        """
        Eliminar grupo
        
        Args:
            group_id: ID del grupo a eliminar
            
        Returns:
            bool: True si se eliminó, False si no existía
        """
        try:
            logger.info("Deleting SCIM group", groupId=group_id)
            
            # 1. Verificar que grupo existe
            existing_group = self.group_repo.get_group_by_id(group_id)
            if not existing_group:
                logger.debug("Group not found for deletion", groupId=group_id)
                return False
            
            # 2. Eliminar grupo
            deleted = self.group_repo.delete_group(group_id)
            
            if deleted:
                logger.info("SCIM group deleted successfully", 
                           groupId=group_id, displayName=existing_group.displayName)
            
            return deleted
            
        except Exception as e:
            logger.error("Failed to delete SCIM group", groupId=group_id, error=str(e))
            raise DatabaseError(f"Failed to delete group: {str(e)}")
    
    def get_group_members(self, group_id: str) -> List[Dict[str, str]]:
        """
        Obtener miembros de un grupo en formato SCIM
        
        Args:
            group_id: ID del grupo
            
        Returns:
            List[Dict]: Lista de miembros en formato SCIM
        """
        try:
            logger.debug("Getting SCIM group members", groupId=group_id)
            
            group = self.group_repo.get_group_by_id(group_id)
            if not group:
                raise GroupNotFoundError(f"Group with ID '{group_id}' not found")
            
            members_scim = []
            for user_id in group.members:
                user = self.user_repo.get_user_by_id(user_id)
                if user:
                    members_scim.append({
                        "value": user_id,
                        "display": user.userName,
                        "$ref": f"/scim/v2/Users/{user_id}"
                    })
                else:
                    logger.warning("User not found in group members", 
                                 groupId=group_id, userId=user_id)
            
            logger.debug("SCIM group members retrieved", 
                        groupId=group_id, memberCount=len(members_scim))
            
            return members_scim
            
        except GroupNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to get SCIM group members", groupId=group_id, error=str(e))
            raise DatabaseError(f"Failed to get group members: {str(e)}")
    
    def synchronize_group_relations(self, group_id: str) -> Dict[str, Any]:
        """
        Sincronización de relaciones - validar y limpiar membresías inconsistentes
        
        Args:
            group_id: ID del grupo a sincronizar
            
        Returns:
            Dict con resultado de sincronización
        """
        try:
            logger.info("Synchronizing SCIM group relations", groupId=group_id)
            
            group = self.group_repo.get_group_by_id(group_id)
            if not group:
                return {"synchronized": False, "error": "Group not found"}
            
            # Verificar que todos los miembros existen
            valid_members = []
            removed_members = []
            
            for user_id in group.members:
                user = self.user_repo.get_user_by_id(user_id)
                if user:
                    valid_members.append(user_id)
                else:
                    removed_members.append(user_id)
                    logger.warning("Removing invalid member from group", 
                                 groupId=group_id, userId=user_id)
            
            # Actualizar grupo si hay inconsistencias
            if len(removed_members) > 0:
                self.group_repo.update_group_members(group_id, valid_members)
                logger.info("Group relations synchronized", 
                           groupId=group_id, removedMembers=len(removed_members))
            
            return {
                "synchronized": True,
                "group_id": group_id,
                "display_name": group.displayName,
                "valid_members": len(valid_members),
                "removed_members": removed_members,
                "was_dirty": len(removed_members) > 0
            }
            
        except Exception as e:
            logger.error("Failed to synchronize group relations", groupId=group_id, error=str(e))
            return {"synchronized": False, "error": str(e)}


_scim_group_service = None

def get_scim_group_service() -> SCIMGroupService:
    """Obtener instancia singleton del SCIMGroupService"""
    global _scim_group_service
    if _scim_group_service is None:
        _scim_group_service = SCIMGroupService()
    return _scim_group_service