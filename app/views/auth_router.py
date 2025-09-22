"""
Authentication Router - Endpoints de autenticación OAuth2/OIDC-like
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import Dict, Any

from app.models.auth import TokenRequest, TokenResponse, UserClaims, TokenError
from app.services.auth_service import get_auth_service, InvalidCredentialsError, UserInactiveError
from app.core.auth_middleware import get_current_user
from app.core.logger import get_logger

logger = get_logger("auth_router")

# Rate limiter simple
limiter = Limiter(key_func=get_remote_address)

# Router con documentación
router = APIRouter(
    prefix="/auth",
    tags=["🔐 Authentication"],
    responses={
        401: {
            "model": TokenError,
            "description": "Authentication failed",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_credentials": {
                            "summary": "Invalid credentials",
                            "value": {
                                "error": "invalid_client",
                                "error_description": "Client authentication failed"
                            }
                        },
                        "user_inactive": {
                            "summary": "User inactive",
                            "value": {
                                "error": "invalid_grant",
                                "error_description": "User account is inactive"
                            }
                        }
                    }
                }
            }
        },
        429: {"description": "Rate limit exceeded"}
    }
)

# Configurar rate limiting para el router
limiter = Limiter(key_func=get_remote_address)

@router.post("/token",
             response_model=TokenResponse,
             status_code=status.HTTP_200_OK,
             summary="🔑 Generate JWT Token",
             description="""
Generate a JWT token using OAuth2-like flow.

**Supported Grant Types:**
- `client_credentials`: For service-to-service authentication
- `password`: For user authentication (mock implementation)

**Security:** Rate limited to 10 requests per minute per IP.

**Mock Credentials Available:**
- **Client Credentials:**
  - `test_client` : `test_secret`
  - `hr_app` : `hr_secret_2024`
- **User Credentials:**
  - `jdoe` : `password123`
  - `agonzalez` : `finance2024`
  - `mrios` : `admin_pass`
             """,
             responses={
                 200: {
                     "description": "Token generated successfully",
                     "content": {
                         "application/json": {
                             "examples": {
                                 "client_credentials": {
                                     "summary": "Client Credentials Success",
                                     "value": {
                                         "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                                         "token_type": "Bearer",
                                         "expires_in": 3600,
                                         "scope": "read write"
                                     }
                                 },
                                 "password_grant": {
                                     "summary": "Password Grant Success",
                                     "value": {
                                         "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                                         "token_type": "Bearer", 
                                         "expires_in": 3600,
                                         "scope": "read"
                                     }
                                 }
                             }
                         }
                     }
                 }
             })
@limiter.limit("10/minute")  # Rate limiting
async def create_token(request: Request, token_request: TokenRequest):
    """
    Generate JWT token with provided credentials.
    
    **Flow:**
    1. Validate credentials against mock data
    2. Check user active status (for password grant)
    3. Generate JWT with user claims
    4. Return token with expiration info
    """
    auth_service = get_auth_service()
    
    try:
        logger.info("Token generation requested", 
                   grant_type=token_request.grant_type,
                   client_ip=get_remote_address(request))
        
        response = auth_service.authenticate_and_generate_token(token_request)
        
        logger.info("Token generated successfully", 
                   grant_type=token_request.grant_type,
                   scope=response.scope)
        
        return response
        
    except InvalidCredentialsError as e:
        logger.warning("Invalid credentials provided", 
                      grant_type=token_request.grant_type,
                      error=str(e))
        
        error_response = auth_service.create_token_error(
            "invalid_client", 
            "Authentication failed - invalid credentials"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_response.model_dump()
        )
        
    except UserInactiveError as e:
        logger.warning("Inactive user attempted authentication",
                      username=token_request.username,
                      error=str(e))
        
        error_response = auth_service.create_token_error(
            "invalid_grant",
            "User account is inactive"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_response.model_dump()
        )
        
    except Exception as e:
        logger.error("Unexpected error during token generation", 
                    grant_type=token_request.grant_type,
                    error=str(e))
        
        error_response = auth_service.create_token_error(
            "server_error",
            "Internal server error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump()
        )

@router.get("/me",
            response_model=UserClaims,
            summary="👤 Get Current User Info",
            description="""
Validate JWT token and return user claims.

**Security:** Requires valid JWT token in Authorization header.

**Response includes:**
- User identity (sub)
- Granted scopes
- Group memberships
- Department information
- Risk score
- Token metadata (issuer, audience, expiration)

**Usage:**
```bash
curl -H "Authorization: Bearer <your-jwt-token>" /auth/me
```
            """,
            responses={
                200: {
                    "description": "User information retrieved successfully",
                    "content": {
                        "application/json": {
                            "examples": {
                                "hr_user": {
                                    "summary": "HR Department User",
                                    "value": {
                                        "sub": "jdoe",
                                        "scope": "read write",
                                        "groups": ["HR_READERS"],
                                        "dept": "HR",
                                        "riskScore": 20,
                                        "iss": "identity-microservice",
                                        "aud": "identity-api",
                                        "exp": "2024-01-01T12:00:00Z",
                                        "iat": "2024-01-01T11:00:00Z"
                                    }
                                },
                                "admin_user": {
                                    "summary": "Admin User",
                                    "value": {
                                        "sub": "mrios",
                                        "scope": "read write admin",
                                        "groups": ["ADMINS"],
                                        "dept": "IT",
                                        "riskScore": 15,
                                        "iss": "identity-microservice",
                                        "aud": "identity-api"
                                    }
                                }
                            }
                        }
                    }
                },
                401: {
                    "description": "Token missing, invalid or expired",
                    "content": {
                        "application/json": {
                            "examples": {
                                "missing_token": {
                                    "summary": "Missing Authorization Header",
                                    "value": {
                                        "detail": "Authentication required"
                                    }
                                },
                                "invalid_token": {
                                    "summary": "Invalid/Expired Token",
                                    "value": {
                                        "detail": "Invalid or expired token: Token has expired"
                                    }
                                }
                            }
                        }
                    }
                }
            })
@limiter.limit("30/minute")  # Rate limiting más generoso para validación
async def get_current_user_info(request: Request, current_user: UserClaims = Depends(get_current_user)):
    """
    Get information about the currently authenticated user.
    
    **Flow:**
    1. Extract JWT from Authorization header
    2. Validate token signature and expiration
    3. Return decoded user claims
    
    **Security Features:**
    - Token signature validation
    - Expiration checking
    - Issuer/audience validation
    - Rate limiting protection
    """
    logger.info("User info requested", 
               subject=current_user.sub,
               client_ip=get_remote_address(request))
    
    return current_user

@router.get("/health",
            summary="🏥 Authentication Service Health",
            description="Health check for authentication service components",
            tags=["Health"],
            responses={
                200: {
                    "description": "Service is healthy",
                    "content": {
                        "application/json": {
                            "example": {
                                "status": "healthy",
                                "auth_service": "ok",
                                "jwt_manager": "ok",
                                "algorithm": "HS256"
                            }
                        }
                    }
                }
            })
async def auth_health():
    """Health check for authentication service"""
    try:
        auth_service = get_auth_service()
        jwt_manager = auth_service.jwt_manager
        
        return {
            "status": "healthy",
            "auth_service": "ok",
            "jwt_manager": "ok",
            "algorithm": jwt_manager.get_algorithm(),
            "timestamp": logger._get_timestamp()
        }
    except Exception as e:
        logger.error("Auth health check failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unhealthy", "error": str(e)}
        )

# Ejemplos adicionales para documentación
@router.get("/examples",
            summary="📚 Usage Examples",
            description="Get examples of how to use the authentication endpoints",
            include_in_schema=False)  # No incluir en schema principal
async def get_examples():
    """Get usage examples for authentication endpoints"""
    return {
        "token_generation": {
            "client_credentials": {
                "method": "POST",
                "url": "/auth/token",
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "grant_type": "client_credentials",
                    "client_id": "test_client",
                    "client_secret": "test_secret",
                    "scope": "read write"
                }
            },
            "password_grant": {
                "method": "POST", 
                "url": "/auth/token",
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "grant_type": "password",
                    "username": "jdoe",
                    "password": "password123",
                    "scope": "read"
                }
            }
        },
        "token_validation": {
            "method": "GET",
            "url": "/auth/me",
            "headers": {"Authorization": "Bearer <your-jwt-token>"}
        },
        "curl_examples": {
            "generate_token": 'curl -X POST /auth/token -H "Content-Type: application/json" -d \'{"grant_type":"client_credentials","client_id":"test_client","client_secret":"test_secret"}\'',
            "validate_token": 'curl -X GET /auth/me -H "Authorization: Bearer <token>"'
        }
    }