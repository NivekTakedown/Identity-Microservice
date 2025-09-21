"""
SCIM Groups Router - Endpoints para gestión de grupos SCIM 2.0
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse
from app.core.logger import get_logger
from app.models.scim import (
    GroupSCIM, GroupCreateSCIM, SCIMResponse, SCIMError
)
from app.services.scim_group_service import get_scim_group_service
from app.repositories import (
    GroupNotFoundError, GroupAlreadyExistsError, UserNotFoundError, DatabaseError
)

logger = get_logger("scim_groups_router")

router = APIRouter(
    prefix="/scim/v2",
    tags=["SCIM 2.0 - Groups"],
    responses={
        400: {"description": "Bad Request - Invalid input"},
        404: {"description": "Not Found - Group does not exist"},
        409: {"description": "Conflict - Group already exists"},
        500: {"description": "Internal Server Error"}
    }
)

# Instancia del servicio
scim_service = get_scim_group_service()


@router.post(
    "/Groups",
    response_model=GroupSCIM,
    status_code=status.HTTP_201_CREATED,
    summary="Create Group",
    description="Create a new group according to SCIM 2.0 specification",
    responses={
        201: {
            "description": "Group created successfully",
            "content": {
                "application/scim+json": {
                    "example": {
                        "id": "grp_abc123",
                        "displayName": "DEVELOPERS",
                        "members": [
                            {
                                "value": "usr_jdoe",
                                "display": "jdoe",
                                "$ref": "/scim/v2/Users/usr_jdoe"
                            }
                        ],
                        "meta": {
                            "resourceType": "Group",
                            "created": "2024-01-01T10:00:00Z",
                            "lastModified": "2024-01-01T10:00:00Z",
                            "location": "/scim/v2/Groups/grp_abc123"
                        },
                        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"]
                    }
                }
            }
        },
        409: {
            "description": "Group already exists",
            "content": {
                "application/scim+json": {
                    "example": {
                        "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                        "status": "409",
                        "detail": "Group with displayName 'DEVELOPERS' already exists",
                        "scimType": "uniqueness"
                    }
                }
            }
        }
    }
)
async def create_group(group_create: GroupCreateSCIM):
    """
    **POST /scim/v2/Groups** - Crear grupo
    
    Crea un nuevo grupo con validación completa SCIM 2.0:
    - displayName único requerido
    - Validación de existencia de usuarios miembros
    - Generación automática de metadatos
    - Formato de miembros SCIM estándar
    """
    try:
        logger.info("Creating SCIM group via API", displayName=group_create.displayName)
        
        created_group = scim_service.create_group(group_create)
        
        logger.info("SCIM group created successfully via API", 
                   groupId=created_group.id, displayName=created_group.displayName)
        
        return created_group
        
    except GroupAlreadyExistsError as e:
        logger.warning("Group creation failed - already exists", 
                      displayName=group_create.displayName, error=str(e))
        error_response = SCIMError(
            status="409",
            detail=str(e),
            scimType="uniqueness"
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_response.model_dump()
        )
    
    except UserNotFoundError as e:
        logger.warning("Group creation failed - user not found", 
                      displayName=group_create.displayName, error=str(e))
        error_response = SCIMError(
            status="400",
            detail=str(e),
            scimType="invalidValue"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response.model_dump()
        )
    
    except Exception as e:
        logger.error("Group creation failed - internal error", 
                    displayName=group_create.displayName, error=str(e))
        error_response = SCIMError(
            status="500",
            detail="Internal server error during group creation"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump()
        )


@router.get(
    "/Groups/{group_id}",
    response_model=GroupSCIM,
    summary="Get Group by ID",
    description="Retrieve a specific group by their unique identifier",
    responses={
        200: {
            "description": "Group found",
            "content": {
                "application/scim+json": {
                    "example": {
                        "id": "grp_hr_readers",
                        "displayName": "HR_READERS",
                        "members": [
                            {
                                "value": "usr_jdoe",
                                "display": "jdoe",
                                "$ref": "/scim/v2/Users/usr_jdoe"
                            }
                        ],
                        "meta": {
                            "resourceType": "Group",
                            "created": "2024-01-01T10:00:00Z",
                            "lastModified": "2024-01-01T10:00:00Z",
                            "location": "/scim/v2/Groups/grp_hr_readers"
                        },
                        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"]
                    }
                }
            }
        }
    }
)
async def get_group(group_id: str):
    """
    **GET /scim/v2/Groups/{id}** - Obtener grupo
    
    Obtiene un grupo específico por su ID único con:
    - Metadatos SCIM completos
    - Miembros en formato SCIM estándar (value, display, $ref)
    - Información actualizada
    """
    try:
        logger.debug("Getting SCIM group via API", groupId=group_id)
        
        group = scim_service.get_group_by_id(group_id)
        
        if not group:
            logger.warning("Group not found via API", groupId=group_id)
            error_response = SCIMError(
                status="404",
                detail=f"Group with ID '{group_id}' not found"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_response.model_dump()
            )
        
        logger.debug("SCIM group retrieved successfully via API", 
                    groupId=group_id, displayName=group.displayName)
        
        return group
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get group via API", groupId=group_id, error=str(e))
        error_response = SCIMError(
            status="500",
            detail="Internal server error during group retrieval"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump()
        )


@router.patch(
    "/Groups/{group_id}",
    response_model=GroupSCIM,
    summary="Update Group",
    description="Update group members (PATCH operation)",
    responses={
        200: {
            "description": "Group updated successfully",
            "content": {
                "application/scim+json": {
                    "example": {
                        "id": "grp_hr_readers",
                        "displayName": "HR_READERS",
                        "members": [
                            {
                                "value": "usr_jdoe",
                                "display": "jdoe",
                                "$ref": "/scim/v2/Users/usr_jdoe"
                            },
                            {
                                "value": "usr_agonzalez",
                                "display": "agonzalez",
                                "$ref": "/scim/v2/Users/usr_agonzalez"
                            }
                        ],
                        "meta": {
                            "resourceType": "Group",
                            "created": "2024-01-01T10:00:00Z",
                            "lastModified": "2024-01-01T12:00:00Z",
                            "location": "/scim/v2/Groups/grp_hr_readers"
                        }
                    }
                }
            }
        }
    }
)
async def update_group_members(group_id: str, members_update: dict):
    """
    **PATCH /scim/v2/Groups/{id}** - Actualizar grupo
    
    Actualización de miembros del grupo con:
    - Validación de existencia de usuarios
    - Actualización automática de lastModified
    - Formato de miembros SCIM estándar
    - Validación de integridad referencial
    
    Formato de entrada esperado:
    ```json
    {
        "members": [
            {"value": "usr_id1", "display": "username1"},
            {"value": "usr_id2", "display": "username2"}
        ]
    }
    ```
    """
    try:
        logger.info("Updating SCIM group members via API", groupId=group_id)
        
        # Extraer miembros del body de la request
        if "members" not in members_update:
            error_response = SCIMError(
                status="400",
                detail="Missing 'members' field in request body",
                scimType="invalidSyntax"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_response.model_dump()
            )
        
        members = members_update["members"]
        updated_group = scim_service.update_group_members(group_id, members)
        
        logger.info("SCIM group members updated successfully via API", 
                   groupId=group_id, displayName=updated_group.displayName,
                   memberCount=len(updated_group.members))
        
        return updated_group
        
    except GroupNotFoundError as e:
        logger.warning("Group update failed - not found", groupId=group_id, error=str(e))
        error_response = SCIMError(
            status="404",
            detail=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response.model_dump()
        )
    
    except UserNotFoundError as e:
        logger.warning("Group update failed - user not found", 
                      groupId=group_id, error=str(e))
        error_response = SCIMError(
            status="400",
            detail=str(e),
            scimType="invalidValue"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response.model_dump()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Group update failed - internal error", 
                    groupId=group_id, error=str(e))
        error_response = SCIMError(
            status="500",
            detail="Internal server error during group update"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump()
        )


@router.get(
    "/Groups",
    response_model=SCIMResponse,
    summary="List/Search Groups",
    description="List groups with optional filtering by displayName",
    responses={
        200: {
            "description": "Groups retrieved successfully",
            "content": {
                "application/scim+json": {
                    "example": {
                        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
                        "totalResults": 3,
                        "startIndex": 1,
                        "itemsPerPage": 3,
                        "Resources": [
                            {
                                "id": "grp_hr_readers",
                                "displayName": "HR_READERS",
                                "members": [
                                    {
                                        "value": "usr_jdoe",
                                        "display": "jdoe",
                                        "$ref": "/scim/v2/Users/usr_jdoe"
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def list_groups(
    filter: Optional[str] = Query(
        None, 
        description="SCIM filter (only 'displayName eq \"value\"' supported)",
        example='displayName eq "HR_READERS"'
    ),
    startIndex: int = Query(
        1, 
        ge=1, 
        description="1-based start index for pagination"
    ),
    count: int = Query(
        100, 
        ge=1, 
        le=1000, 
        description="Number of results to return"
    )
):
    """
    **GET /scim/v2/Groups?filter=** - Búsqueda con filtros
    
    Búsqueda de grupos con soporte para:
    - **Filtro SCIM**: `displayName eq "valor"` para búsqueda exacta
    - **Paginación**: startIndex (1-based) y count
    - **Respuesta estándar** SCIM con totalResults y metadatos
    
    Ejemplos:
    - `GET /scim/v2/Groups` - Listar todos los grupos
    - `GET /scim/v2/Groups?filter=displayName eq "HR_READERS"` - Buscar grupo específico
    - `GET /scim/v2/Groups?startIndex=1&count=10` - Paginación
    """
    try:
        logger.debug("Listing/searching SCIM groups via API", filter=filter, 
                    startIndex=startIndex, count=count)
        
        # Manejar filtro SCIM simple: displayName eq "valor"
        if filter:
            # Parsear filtro básico: displayName eq "valor"
            if filter.startswith('displayName eq "') and filter.endswith('"'):
                display_name = filter.split('"')[1]
                logger.debug("Filtering by displayName", displayName=display_name)
                
                group = scim_service.find_by_display_name(display_name)
                if group:
                    response = SCIMResponse(
                        schemas=["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
                        totalResults=1,
                        Resources=[group],
                        startIndex=startIndex,
                        itemsPerPage=1
                    )
                else:
                    response = SCIMResponse(
                        schemas=["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
                        totalResults=0,
                        Resources=[],
                        startIndex=startIndex,
                        itemsPerPage=0
                    )
                
                logger.debug("SCIM groups filtered successfully via API", 
                           displayName=display_name, found=group is not None)
                return response
            else:
                # Filtro no soportado
                logger.warning("Unsupported filter format", filter=filter)
                error_response = SCIMError(
                    status="400",
                    detail=f"Unsupported filter format. Only 'displayName eq \"value\"' is supported",
                    scimType="invalidFilter"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_response.model_dump()
                )
        
        # Sin filtro - listar todos con paginación
        response = scim_service.list_groups(
            start_index=startIndex,
            count=count
        )
        
        logger.debug("SCIM groups listed successfully via API", 
                    totalResults=response.totalResults, 
                    returnedCount=response.itemsPerPage)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list groups via API", error=str(e))
        error_response = SCIMError(
            status="500",
            detail="Internal server error during group listing"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump()
        )


@router.delete(
    "/Groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Group",
    description="Delete a group by ID",
    responses={
        204: {"description": "Group deleted successfully"},
        404: {"description": "Group not found"}
    }
)
async def delete_group(group_id: str):
    """
    **DELETE /scim/v2/Groups/{id}** - Eliminar grupo
    
    Elimina un grupo permanentemente:
    - Limpieza automática de relaciones
    - Validación de existencia antes de eliminar
    """
    try:
        logger.info("Deleting SCIM group via API", groupId=group_id)
        
        deleted = scim_service.delete_group(group_id)
        
        if not deleted:
            logger.warning("Group deletion failed - not found", groupId=group_id)
            error_response = SCIMError(
                status="404",
                detail=f"Group with ID '{group_id}' not found"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_response.model_dump()
            )
        
        logger.info("SCIM group deleted successfully via API", groupId=group_id)
        
        from fastapi import Response
        return Response(status_code=status.HTTP_204_NO_CONTENT)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Group deletion failed - internal error", 
                    groupId=group_id, error=str(e))
        error_response = SCIMError(
            status="500",
            detail="Internal server error during group deletion"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump()
        )


@router.post(
    "/Groups/{group_id}/members",
    response_model=GroupSCIM,
    summary="Add Member to Group",
    description="Add a single member to a group",
    responses={
        200: {"description": "Member added successfully"}
    }
)
async def add_member_to_group(group_id: str, member_data: dict):
    """
    **POST /scim/v2/Groups/{id}/members** - Agregar miembro
    
    Agregar un usuario individual a un grupo:
    - Validación de existencia del usuario
    - Prevención de duplicados automática
    
    Formato de entrada:
    ```json
    {
        "value": "usr_id",
        "display": "username"
    }
    ```
    """
    try:
        logger.info("Adding member to SCIM group via API", groupId=group_id)
        
        if "value" not in member_data:
            error_response = SCIMError(
                status="400",
                detail="Missing 'value' field in request body",
                scimType="invalidSyntax"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_response.model_dump()
            )
        
        user_id = member_data["value"]
        updated_group = scim_service.add_member_to_group(group_id, user_id)
        
        logger.info("Member added to SCIM group successfully via API", 
                   groupId=group_id, userId=user_id)
        
        return updated_group
        
    except (GroupNotFoundError, UserNotFoundError) as e:
        logger.warning("Add member failed", groupId=group_id, error=str(e))
        error_response = SCIMError(
            status="404" if isinstance(e, GroupNotFoundError) else "400",
            detail=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if isinstance(e, GroupNotFoundError) else status.HTTP_400_BAD_REQUEST,
            detail=error_response.model_dump()
        )
    
    except Exception as e:
        logger.error("Add member failed - internal error", 
                    groupId=group_id, error=str(e))
        error_response = SCIMError(
            status="500",
            detail="Internal server error during member addition"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump()
        )


@router.delete(
    "/Groups/{group_id}/members/{user_id}",
    response_model=GroupSCIM,
    summary="Remove Member from Group",
    description="Remove a specific member from a group",
    responses={
        200: {"description": "Member removed successfully"}
    }
)
async def remove_member_from_group(group_id: str, user_id: str):
    """
    **DELETE /scim/v2/Groups/{id}/members/{user_id}** - Remover miembro
    
    Remover un usuario específico de un grupo:
    - Validación de existencia del grupo
    - Operación idempotente (no error si usuario no está en grupo)
    """
    try:
        logger.info("Removing member from SCIM group via API", 
                   groupId=group_id, userId=user_id)
        
        updated_group = scim_service.remove_member_from_group(group_id, user_id)
        
        logger.info("Member removed from SCIM group successfully via API", 
                   groupId=group_id, userId=user_id)
        
        return updated_group
        
    except GroupNotFoundError as e:
        logger.warning("Remove member failed - group not found", 
                      groupId=group_id, error=str(e))
        error_response = SCIMError(
            status="404",
            detail=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response.model_dump()
        )
    
    except Exception as e:
        logger.error("Remove member failed - internal error", 
                    groupId=group_id, userId=user_id, error=str(e))
        error_response = SCIMError(
            status="500",
            detail="Internal server error during member removal"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump()
        )