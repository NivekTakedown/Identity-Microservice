"""
SCIM Users Router - Endpoints para gestión de usuarios SCIM 2.0
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse
from app.core.logger import get_logger
from app.models.scim import (
    UserSCIM, UserCreateSCIM, UserUpdateSCIM, SCIMResponse, SCIMError
)
from app.services.scim_user_service import get_scim_user_service
from app.repositories import (
    UserNotFoundError, UserAlreadyExistsError, GroupNotFoundError, DatabaseError
)

logger = get_logger("scim_users_router")

router = APIRouter(
    prefix="/scim/v2",
    tags=["SCIM 2.0 - Users"],
    responses={
        400: {"description": "Bad Request - Invalid input"},
        404: {"description": "Not Found - User does not exist"},
        409: {"description": "Conflict - User already exists"},
        500: {"description": "Internal Server Error"}
    }
)

# Instancia del servicio
scim_service = get_scim_user_service()


@router.post(
    "/Users",
    response_model=UserSCIM,
    status_code=status.HTTP_201_CREATED,
    summary="Create User",
    description="Create a new user according to SCIM 2.0 specification",
    responses={
        201: {
            "description": "User created successfully",
            "content": {
                "application/scim+json": {
                    "example": {
                        "id": "usr_abc123",
                        "userName": "newuser",
                        "name": {
                            "givenName": "John",
                            "familyName": "Doe",
                            "formatted": "John Doe"
                        },
                        "active": True,
                        "emails": [
                            {
                                "value": "john.doe@company.com",
                                "primary": True,
                                "type": "work"
                            }
                        ],
                        "groups": ["HR_READERS"],
                        "dept": "HR",
                        "riskScore": 25,
                        "meta": {
                            "resourceType": "User",
                            "created": "2024-01-01T10:00:00Z",
                            "lastModified": "2024-01-01T10:00:00Z",
                            "location": "/scim/v2/Users/usr_abc123"
                        },
                        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"]
                    }
                }
            }
        },
        409: {
            "description": "User already exists",
            "content": {
                "application/scim+json": {
                    "example": {
                        "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                        "status": "409",
                        "detail": "User with userName 'jdoe' already exists",
                        "scimType": "uniqueness"
                    }
                }
            }
        }
    }
)
async def create_user(user_create: UserCreateSCIM):
    """
    **POST /scim/v2/Users** - Crear usuario
    
    Crea un nuevo usuario con validación completa SCIM 2.0:
    - userName único requerido
    - Validación de emails
    - Asignación de grupos después de crear usuario
    - Generación automática de metadatos
    """
    try:
        logger.info("Creating SCIM user via API", userName=user_create.userName)
        
        created_user = scim_service.create_user(user_create)
        
        logger.info("SCIM user created successfully via API", 
                   userId=created_user.id, userName=created_user.userName)
        
        return created_user
        
    except UserAlreadyExistsError as e:
        logger.warning("User creation failed - already exists", 
                      userName=user_create.userName, error=str(e))
        error_response = SCIMError(
            status="409",
            detail=str(e),
            scimType="uniqueness"
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_response.model_dump()
        )
    
    except GroupNotFoundError as e:
        logger.warning("User creation failed - group not found", 
                      userName=user_create.userName, error=str(e))
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
        logger.error("User creation failed - internal error", 
                    userName=user_create.userName, error=str(e))
        error_response = SCIMError(
            status="500",
            detail="Internal server error during user creation"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump()
        )


@router.get(
    "/Users/{user_id}",
    response_model=UserSCIM,
    summary="Get User by ID",
    description="Retrieve a specific user by their unique identifier",
    responses={
        200: {
            "description": "User found",
            "content": {
                "application/scim+json": {
                    "example": {
                        "id": "usr_jdoe",
                        "userName": "jdoe",
                        "name": {
                            "givenName": "John",
                            "familyName": "Doe",
                            "formatted": "John Doe"
                        },
                        "active": True,
                        "emails": [
                            {
                                "value": "john.doe@company.com",
                                "primary": True,
                                "type": "work"
                            }
                        ],
                        "groups": ["HR_READERS"],
                        "dept": "HR",
                        "riskScore": 20,
                        "meta": {
                            "resourceType": "User",
                            "created": "2024-01-01T10:00:00Z",
                            "lastModified": "2024-01-01T10:00:00Z",
                            "location": "/scim/v2/Users/usr_jdoe"
                        },
                        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"]
                    }
                }
            }
        }
    }
)
async def get_user(user_id: str):
    """
    **GET /scim/v2/Users/{id}** - Obtener usuario
    
    Obtiene un usuario específico por su ID único con:
    - Metadatos SCIM completos
    - Grupos obtenidos de forma consistente
    - Información actualizada
    """
    try:
        logger.debug("Getting SCIM user via API", userId=user_id)
        
        user = scim_service.get_user_by_id(user_id)
        
        if not user:
            logger.warning("User not found via API", userId=user_id)
            error_response = SCIMError(
                status="404",
                detail=f"User with ID '{user_id}' not found"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_response.model_dump()
            )
        
        logger.debug("SCIM user retrieved successfully via API", 
                    userId=user_id, userName=user.userName)
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get user via API", userId=user_id, error=str(e))
        error_response = SCIMError(
            status="500",
            detail="Internal server error during user retrieval"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump()
        )


@router.patch(
    "/Users/{user_id}",
    response_model=UserSCIM,
    summary="Update User",
    description="Partially update a user (PATCH operation)",
    responses={
        200: {
            "description": "User updated successfully",
            "content": {
                "application/scim+json": {
                    "example": {
                        "id": "usr_jdoe",
                        "userName": "jdoe",
                        "active": False,
                        "meta": {
                            "resourceType": "User",
                            "created": "2024-01-01T10:00:00Z",
                            "lastModified": "2024-01-01T12:00:00Z",
                            "location": "/scim/v2/Users/usr_jdoe"
                        }
                    }
                }
            }
        }
    }
)
async def update_user(user_id: str, user_update: UserUpdateSCIM):
    """
    **PATCH /scim/v2/Users/{id}** - Actualizar usuario
    
    Actualización parcial de usuario con:
    - Actualización de campos básicos (userName, name, active, emails, dept, riskScore)
    - Gestión de grupos (agregar/remover)
    - Actualización automática de lastModified
    - Validación de integridad referencial
    """
    try:
        logger.info("Updating SCIM user via API", userId=user_id)
        
        updated_user = scim_service.update_user(user_id, user_update)
        
        logger.info("SCIM user updated successfully via API", 
                   userId=user_id, userName=updated_user.userName)
        
        return updated_user
        
    except UserNotFoundError as e:
        logger.warning("User update failed - not found", userId=user_id, error=str(e))
        error_response = SCIMError(
            status="404",
            detail=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response.model_dump()
        )
    
    except UserAlreadyExistsError as e:
        logger.warning("User update failed - userName conflict", 
                      userId=user_id, error=str(e))
        error_response = SCIMError(
            status="409",
            detail=str(e),
            scimType="uniqueness"
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_response.model_dump()
        )
    
    except GroupNotFoundError as e:
        logger.warning("User update failed - group not found", 
                      userId=user_id, error=str(e))
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
        logger.error("User update failed - internal error", 
                    userId=user_id, error=str(e))
        error_response = SCIMError(
            status="500",
            detail="Internal server error during user update"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump()
        )


@router.get(
    "/Users",
    response_model=SCIMResponse,
    summary="List/Search Users",
    description="List users with optional filtering by userName",
    responses={
        200: {
            "description": "Users retrieved successfully",
            "content": {
                "application/scim+json": {
                    "example": {
                        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
                        "totalResults": 3,
                        "startIndex": 1,
                        "itemsPerPage": 3,
                        "Resources": [
                            {
                                "id": "usr_jdoe",
                                "userName": "jdoe",
                                "active": True,
                                "dept": "HR",
                                "groups": ["HR_READERS"]
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def list_users(
    filter: Optional[str] = Query(
        None, 
        description="SCIM filter (only 'userName eq \"value\"' supported)",
        example='userName eq "jdoe"'
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
    **GET /scim/v2/Users?filter=** - Búsqueda con filtros
    
    Búsqueda de usuarios con soporte para:
    - **Filtro SCIM**: `userName eq "valor"` para búsqueda exacta
    - **Paginación**: startIndex (1-based) y count
    - **Respuesta estándar** SCIM con totalResults y metadatos
    
    Ejemplos:
    - `GET /scim/v2/Users` - Listar todos los usuarios
    - `GET /scim/v2/Users?filter=userName eq "jdoe"` - Buscar usuario específico
    - `GET /scim/v2/Users?startIndex=1&count=10` - Paginación
    """
    try:
        logger.debug("Listing/searching SCIM users via API", filter=filter, 
                    startIndex=startIndex, count=count)
        
        # Manejar filtro SCIM simple: userName eq "valor"
        if filter:
            # Parsear filtro básico: userName eq "valor"
            if filter.startswith('userName eq "') and filter.endswith('"'):
                username = filter.split('"')[1]
                logger.debug("Filtering by userName", userName=username)
                
                user = scim_service.find_by_username(username)
                if user:
                    response = SCIMResponse(
                        schemas=["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
                        totalResults=1,
                        Resources=[user],
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
                
                logger.debug("SCIM users filtered successfully via API", 
                           userName=username, found=user is not None)
                return response
            else:
                # Filtro no soportado
                logger.warning("Unsupported filter format", filter=filter)
                error_response = SCIMError(
                    status="400",
                    detail=f"Unsupported filter format. Only 'userName eq \"value\"' is supported",
                    scimType="invalidFilter"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_response.model_dump()
                )
        
        # Sin filtro - listar todos con paginación
        response = scim_service.list_users(
            active_only=None,
            start_index=startIndex,
            count=count
        )
        
        logger.debug("SCIM users listed successfully via API", 
                    totalResults=response.totalResults, 
                    returnedCount=response.itemsPerPage)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list users via API", error=str(e))
        error_response = SCIMError(
            status="500",
            detail="Internal server error during user listing"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump()
        )


@router.delete(
    "/Users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete User",
    description="Delete a user by ID",
    responses={
        204: {"description": "User deleted successfully"},
        404: {"description": "User not found"}
    }
)
async def delete_user(user_id: str):
    """
    **DELETE /scim/v2/Users/{id}** - Eliminar usuario
    
    Elimina un usuario y limpia automáticamente:
    - Membresías de grupos
    - Referencias en otras entidades
    """
    try:
        logger.info("Deleting SCIM user via API", userId=user_id)
        
        deleted = scim_service.delete_user(user_id)
        
        if not deleted:
            logger.warning("User deletion failed - not found", userId=user_id)
            error_response = SCIMError(
                status="404",
                detail=f"User with ID '{user_id}' not found"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_response.model_dump()
            )
        
        logger.info("SCIM user deleted successfully via API", userId=user_id)
        return JSONResponse(
            status_code=status.HTTP_204_NO_CONTENT,
            content=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("User deletion failed - internal error", 
                    userId=user_id, error=str(e))
        error_response = SCIMError(
            status="500",
            detail="Internal server error during user deletion"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump()
        )