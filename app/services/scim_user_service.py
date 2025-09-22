"""
SCIMUserService - Lógica de negocio para usuarios SCIM 2.0
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.core.logger import get_logger
from app.models.scim import (
    UserSCIM, UserCreateSCIM, UserUpdateSCIM, SCIMResponse, SCIMError,
    user_model_to_scim, scim_create_to_user_model
)
from app.models.database import UserModel
from app.repositories.user_repository import get_user_repository
from app.repositories.group_repository import get_group_repository
from app.repositories import (
    UserNotFoundError, UserAlreadyExistsError, GroupNotFoundError, DatabaseError
)

logger = get_logger("scim_user_service")


class SCIMUserService:
    """Servicio de lógica de negocio para usuarios SCIM"""
    
    def __init__(self):
        self.user_repo = get_user_repository()
        self.group_repo = get_group_repository()
    
    def create_user(self, user_create: UserCreateSCIM) -> UserSCIM:
        """
        Crear usuario con validación completa de reglas de negocio SCIM
        
        Args:
            user_create: Datos de usuario a crear
            
        Returns:
            UserSCIM: Usuario creado con metadatos completos
            
        Raises:
            UserAlreadyExistsError: Si userName ya existe
            GroupNotFoundError: Si algún grupo especificado no existe
            DatabaseError: Error en operaciones de base de datos
        """
        try:
            logger.info("Creating SCIM user", userName=user_create.userName)
            
            # 1. Validar integridad referencial - verificar que grupos existen
            if user_create.groups:
                for group_name in user_create.groups:
                    existing_group = self.group_repo.find_by_display_name(group_name)
                    if not existing_group:
                        logger.warning("Group not found during user creation", 
                                     userName=user_create.userName, groupName=group_name)
                        raise GroupNotFoundError(f"Group '{group_name}' does not exist")
            
            # 2. Convertir SCIM a modelo interno (SIN groups_list por consistencia)
            user_model = scim_create_to_user_model(user_create)
            
            # 3. Crear usuario en repositorio
            created_user = self.user_repo.create_user(user_model)
            
            # 4. DESPUÉS del usuario creado, asignar a grupos
            assigned_groups = []
            if user_create.groups:
                for group_name in user_create.groups:
                    try:
                        # Agregar usuario a cada grupo especificado
                        group = self.group_repo.find_by_display_name(group_name)
                        if group:
                            self.group_repo.add_member_to_group(group.id, created_user.id)
                            assigned_groups.append(group_name)
                            logger.debug("User added to group", 
                                       userId=created_user.id, groupName=group_name)
                        else:
                            logger.warning("Group not found when adding member", 
                                         userId=created_user.id, groupName=group_name)
                    except Exception as e:
                        logger.warning("Failed to add user to group", 
                                     userId=created_user.id, groupName=group_name, error=str(e))
                        # Continuar con otros grupos, no fallar completamente
            
            # 5. Obtener grupos finales para respuesta SCIM consistente
            final_groups = self.user_repo.get_user_groups(created_user.id)
            
            # 6. Convertir a SCIM con metadatos completos
            scim_user = user_model_to_scim(created_user, final_groups)
            
            logger.info("SCIM user created successfully", 
                       userId=created_user.id, userName=created_user.userName,
                       assignedGroups=len(assigned_groups),
                       finalGroups=len(final_groups))  # Agregar logging para debug
            
            return scim_user
            
        except (UserAlreadyExistsError, GroupNotFoundError):
            raise
        except Exception as e:
            logger.error("Failed to create SCIM user", 
                        userName=user_create.userName, error=str(e))
            raise DatabaseError(f"Failed to create user: {str(e)}")
    
    def get_user_by_id(self, user_id: str) -> Optional[UserSCIM]:
        """
        Obtener usuario por ID con metadatos SCIM completos
        
        Args:
            user_id: ID del usuario
            
        Returns:
            UserSCIM o None si no existe
        """
        try:
            logger.debug("Getting SCIM user by ID", userId=user_id)
            
            # 1. Obtener usuario del repositorio
            user_model = self.user_repo.get_user_by_id(user_id)
            if not user_model:
                logger.debug("User not found", userId=user_id)
                return None
            
            # 2. Obtener grupos de forma consistente
            user_groups = self.user_repo.get_user_groups(user_id)
            
            # 3. Convertir a SCIM con metadatos
            scim_user = user_model_to_scim(user_model, user_groups)
            
            logger.debug("SCIM user retrieved successfully", 
                        userId=user_id, userName=user_model.userName)
            
            return scim_user
            
        except Exception as e:
            logger.error("Failed to get SCIM user", userId=user_id, error=str(e))
            raise DatabaseError(f"Failed to get user: {str(e)}")
    
    def update_user(self, user_id: str, user_update: UserUpdateSCIM) -> UserSCIM:
        """
        Actualizar usuario con validación de reglas de negocio SCIM
        
        Args:
            user_id: ID del usuario a actualizar
            user_update: Datos de actualización
            
        Returns:
            UserSCIM: Usuario actualizado
            
        Raises:
            UserNotFoundError: Si usuario no existe
            UserAlreadyExistsError: Si nuevo userName ya existe
            GroupNotFoundError: Si algún grupo especificado no existe
        """
        try:
            logger.info("Updating SCIM user", userId=user_id)
            
            # 1. Verificar que usuario existe
            existing_user = self.user_repo.get_user_by_id(user_id)
            if not existing_user:
                raise UserNotFoundError(f"User with ID '{user_id}' not found")
            
            # 2. Validar integridad referencial si se actualizan grupos
            if user_update.groups is not None:
                for group_name in user_update.groups:
                    existing_group = self.group_repo.find_by_display_name(group_name)
                    if not existing_group:
                        logger.warning("Group not found during user update", 
                                     userId=user_id, groupName=group_name)
                        raise GroupNotFoundError(f"Group '{group_name}' does not exist")
            
            # 3. Preparar campos de actualización (excluyendo groups)
            update_fields = {}
            if user_update.userName is not None:
                update_fields['userName'] = user_update.userName
            if user_update.name is not None:
                if user_update.name.givenName is not None:
                    update_fields['givenName'] = user_update.name.givenName
                if user_update.name.familyName is not None:
                    update_fields['familyName'] = user_update.name.familyName
            if user_update.active is not None:
                update_fields['active'] = user_update.active
            if user_update.emails is not None:
                update_fields['emails'] = [email.value for email in user_update.emails]
            if user_update.dept is not None:
                update_fields['dept'] = user_update.dept
            if user_update.riskScore is not None:
                update_fields['riskScore'] = user_update.riskScore
            
            # 4. Actualizar campos básicos del usuario (SIN groups)
            updated_user = self.user_repo.update_user(user_id, update_fields)
            
            # 5. Gestionar grupos si se especificaron
            if user_update.groups is not None:
                # Obtener grupos actuales del usuario
                current_groups = self.group_repo.get_groups_for_user(user_id)
                current_group_names = [g.displayName for g in current_groups]
                
                # Grupos a agregar (nuevos)
                groups_to_add = set(user_update.groups) - set(current_group_names)
                # Grupos a remover (ya no están en la lista)
                groups_to_remove = set(current_group_names) - set(user_update.groups)
                
                # Remover de grupos
                for group_name in groups_to_remove:
                    try:
                        group = self.group_repo.find_by_display_name(group_name)
                        if group:
                            self.group_repo.remove_member_from_group(group.id, user_id)
                            logger.debug("User removed from group", 
                                       userId=user_id, groupName=group_name)
                    except Exception as e:
                        logger.warning("Failed to remove user from group", 
                                     userId=user_id, groupName=group_name, error=str(e))
                
                # Agregar a grupos
                for group_name in groups_to_add:
                    try:
                        group = self.group_repo.find_by_display_name(group_name)
                        if group:
                            self.group_repo.add_member_to_group(group.id, user_id)
                            logger.debug("User added to group", 
                                       userId=user_id, groupName=group_name)
                    except Exception as e:
                        logger.warning("Failed to add user to group", 
                                     userId=user_id, groupName=group_name, error=str(e))
            
            # 6. Obtener grupos finales para respuesta consistente
            final_groups = self.user_repo.get_user_groups(user_id)
            
            # 7. Obtener usuario actualizado y convertir a SCIM
            final_user = self.user_repo.get_user_by_id(user_id)
            scim_user = user_model_to_scim(final_user, final_groups)
            
            logger.info("SCIM user updated successfully", 
                       userId=user_id, userName=final_user.userName,
                       updatedFields=list(update_fields.keys()))
            
            return scim_user
            
        except (UserNotFoundError, UserAlreadyExistsError, GroupNotFoundError):
            raise
        except Exception as e:
            logger.error("Failed to update SCIM user", userId=user_id, error=str(e))
            raise DatabaseError(f"Failed to update user: {str(e)}")
    
    def find_by_username(self, username: str) -> Optional[UserSCIM]:
        """
        Buscar usuario por userName (filtro SCIM)
        
        Args:
            username: userName a buscar
            
        Returns:
            UserSCIM o None si no existe
        """
        try:
            logger.debug("Finding SCIM user by username", userName=username)
            
            # 1. Buscar usuario
            user_model = self.user_repo.find_by_username(username)
            if not user_model:
                logger.debug("User not found by username", userName=username)
                return None
            
            # 2. Obtener grupos consistentes
            user_groups = self.user_repo.get_user_groups(user_model.id)
            
            # 3. Convertir a SCIM
            scim_user = user_model_to_scim(user_model, user_groups)
            
            logger.debug("SCIM user found by username", 
                        userName=username, userId=user_model.id)
            
            return scim_user
            
        except Exception as e:
            logger.error("Failed to find SCIM user by username", 
                        userName=username, error=str(e))
            raise DatabaseError(f"Failed to find user: {str(e)}")
    
    def list_users(self, active_only: bool = None, start_index: int = 1, 
                   count: int = 100) -> SCIMResponse:
        """
        Listar usuarios con formato de respuesta SCIM estándar
        
        Args:
            active_only: Filtrar solo usuarios activos
            start_index: Índice de inicio (SCIM usa 1-based)
            count: Número máximo de resultados
            
        Returns:
            SCIMResponse: Respuesta SCIM con paginación
        """
        try:
            logger.debug("Listing SCIM users", activeOnly=active_only, 
                        startIndex=start_index, count=count)
            
            # Convertir de SCIM 1-based a 0-based offset
            offset = max(0, start_index - 1)
            
            # 1. Obtener usuarios del repositorio
            users = self.user_repo.list_users(
                active_only=active_only, 
                limit=count, 
                offset=offset
            )
            
            # 2. Convertir cada usuario a SCIM con grupos
            scim_users = []
            for user in users:
                user_groups = self.user_repo.get_user_groups(user.id)
                scim_user = user_model_to_scim(user, user_groups)
                scim_users.append(scim_user)
            
            # 3. Obtener total para metadatos de paginación
            total_results = self.user_repo.count_users(active_only=active_only)
            
            # 4. Crear respuesta SCIM estándar
            response = SCIMResponse(
                schemas=["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
                totalResults=total_results,
                Resources=scim_users,
                startIndex=start_index,
                itemsPerPage=len(scim_users)
            )
            
            logger.debug("SCIM users listed successfully", 
                        returnedCount=len(scim_users), totalResults=total_results)
            
            return response
            
        except Exception as e:
            logger.error("Failed to list SCIM users", error=str(e))
            raise DatabaseError(f"Failed to list users: {str(e)}")
    
    def delete_user(self, user_id: str) -> bool:
        """
        Eliminar usuario y limpiar sus membresías de grupos
        
        Args:
            user_id: ID del usuario a eliminar
            
        Returns:
            bool: True si se eliminó, False si no existía
        """
        try:
            logger.info("Deleting SCIM user", userId=user_id)
            
            # 1. Verificar que usuario existe
            existing_user = self.user_repo.get_user_by_id(user_id)
            if not existing_user:
                logger.debug("User not found for deletion", userId=user_id)
                return False
            
            # 2. Remover usuario de todos los grupos (limpieza de integridad)
            user_groups = self.group_repo.get_groups_for_user(user_id)
            for group in user_groups:
                try:
                    self.group_repo.remove_member_from_group(group.id, user_id)
                    logger.debug("User removed from group during deletion", 
                               userId=user_id, groupId=group.id)
                except Exception as e:
                    logger.warning("Failed to remove user from group during deletion", 
                                 userId=user_id, groupId=group.id, error=str(e))
            
            # 3. Eliminar usuario
            deleted = self.user_repo.delete_user(user_id)
            
            if deleted:
                logger.info("SCIM user deleted successfully", 
                           userId=user_id, userName=existing_user.userName)
            
            return deleted
            
        except Exception as e:
            logger.error("Failed to delete SCIM user", userId=user_id, error=str(e))
            raise DatabaseError(f"Failed to delete user: {str(e)}")
    
    def validate_user_integrity(self, user_id: str) -> Dict[str, Any]:
        """
        Validar integridad referencial de un usuario
        
        Args:
            user_id: ID del usuario a validar
            
        Returns:
            Dict con resultado de validación
        """
        try:
            logger.debug("Validating user integrity", userId=user_id)
            
            user = self.user_repo.get_user_by_id(user_id)
            if not user:
                return {"valid": False, "error": "User not found"}
            
            # Verificar que grupos del usuario existen
            user_groups = self.user_repo.get_user_groups(user_id)
            group_issues = []
            
            for group_name in user_groups:
                group = self.group_repo.find_by_display_name(group_name)
                if not group:
                    group_issues.append(f"Group '{group_name}' does not exist")
                elif user_id not in group.members:
                    group_issues.append(f"User not properly registered in group '{group_name}'")
            
            return {
                "valid": len(group_issues) == 0,
                "user_id": user_id,
                "username": user.userName,
                "groups": user_groups,
                "issues": group_issues
            }
            
        except Exception as e:
            logger.error("Failed to validate user integrity", userId=user_id, error=str(e))
            return {"valid": False, "error": str(e)}


# Instancia singleton del servicio
_scim_user_service = None

def get_scim_user_service() -> SCIMUserService:
    """Obtener instancia singleton del SCIMUserService"""
    global _scim_user_service
    if _scim_user_service is None:
        _scim_user_service = SCIMUserService()
    return _scim_user_service