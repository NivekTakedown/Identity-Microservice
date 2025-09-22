"""
Authorization Router - Endpoints de autorización ABAC
Evaluación de permisos basada en atributos
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import Dict, Any

from app.models.abac import ABACRequest, ABACResponse
from app.models.auth import UserClaims  # Agregar este import
from app.services.authz_service import get_authz_service
from app.core.auth_middleware import get_current_user
from app.core.logger import get_logger

logger = get_logger("authorization_router")

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Security scheme
security = HTTPBearer()

# Router
router = APIRouter(
    prefix="/authz",
    tags=["Authorization"],
    responses={
        401: {"description": "Unauthorized - Invalid or missing token"},
        403: {"description": "Forbidden - Insufficient permissions"},
        429: {"description": "Too Many Requests - Rate limit exceeded"}
    }
)

@router.post(
    "/evaluate",
    response_model=ABACResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate ABAC authorization request",
    description="""
    Evaluates an authorization request using ABAC (Attribute-Based Access Control).
    
    Returns a decision (Permit/Deny/Challenge) based on configured policies.
    
    **Request Example:**
    ```json
    {
        "subject": {
            "dept": "HR",
            "groups": ["HR_READERS"],
            "riskScore": 20
        },
        "resource": {
            "type": "payroll",
            "env": "prod"
        },
        "context": {
            "geo": "CL",
            "deviceTrusted": true,
            "timeOfDay": "10:30"
        }
    }
    ```
    """,
    responses={
        200: {
            "description": "Authorization evaluation completed",
            "content": {
                "application/json": {
                    "examples": {
                        "permit": {
                            "summary": "Permit Decision",
                            "value": {
                                "decision": "Permit",
                                "reasons": ["ruleId: HR-PAYROLL-01"],
                                "advice": [],
                                "obligations": ["Log successful access"]
                            }
                        },
                        "challenge": {
                            "summary": "Challenge Decision",
                            "value": {
                                "decision": "Challenge",
                                "reasons": ["ruleId: RISK-STEPUP-01"],
                                "advice": ["Require MFA authentication"],
                                "obligations": ["Log high-risk access attempt", "correlation_id: authz-abc123"]
                            }
                        },
                        "deny": {
                            "summary": "Deny Decision",
                            "value": {
                                "decision": "Deny",
                                "reasons": ["No applicable policies found"],
                                "advice": ["Contact administrator"],
                                "obligations": ["Log denied access attempt"]
                            }
                        }
                    }
                }
            }
        }
    }
)
@limiter.limit("100/minute")
async def evaluate_authorization(
    request: Request,
    abac_request: ABACRequest,
    current_user: UserClaims = Depends(get_current_user),  # Cambiar tipo
    authz_service = Depends(get_authz_service)
) -> ABACResponse:
    """
    Evalúa una solicitud de autorización ABAC
    
    Args:
        abac_request: Solicitud con subject, resource y context
        current_user: Usuario autenticado desde JWT
        authz_service: Servicio de autorización
        
    Returns:
        ABACResponse: Decisión de autorización con razones
    """
    correlation_id = request.headers.get("X-Correlation-ID")
    
    logger.info("Authorization evaluation requested",
               correlation_id=correlation_id,
               authenticated_user=current_user.sub,  # Cambiar .get("sub") por .sub
               subject_dept=abac_request.subject.dept,
               resource_type=abac_request.resource.type)
    
    try:
        # Evaluar autorización
        response = authz_service.evaluate_authorization(
            abac_request, 
            correlation_id=correlation_id
        )
        
        logger.info("Authorization evaluation completed",
                   correlation_id=correlation_id,
                   decision=response.decision.value,
                   authenticated_user=current_user.sub)  # Cambiar .get("sub") por .sub
        
        return response
        
    except Exception as e:
        logger.error("Authorization evaluation failed",
                    correlation_id=correlation_id,
                    error=str(e),
                    authenticated_user=current_user.sub)  # Cambiar .get("sub") por .sub
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "authorization_evaluation_failed",
                "message": "Failed to evaluate authorization request",
                "correlation_id": correlation_id
            }
        )

@router.get(
    "/policies",
    response_model=Dict[str, Any],
    summary="Get applicable policies for a request",
    description="Returns information about which policies would apply to a given request (debugging endpoint)"
)
@limiter.limit("50/minute")
async def get_applicable_policies(
    request: Request,
    abac_request: ABACRequest,
    current_user: UserClaims = Depends(get_current_user),  # Cambiar tipo
    authz_service = Depends(get_authz_service)
) -> Dict[str, Any]:
    """
    Obtiene políticas aplicables sin evaluarlas (para debugging)
    
    Args:
        abac_request: Solicitud ABAC para analizar
        current_user: Usuario autenticado
        authz_service: Servicio de autorización
        
    Returns:
        Información detallada sobre políticas aplicables
    """
    correlation_id = request.headers.get("X-Correlation-ID")
    
    logger.info("Applicable policies requested",
               correlation_id=correlation_id,
               authenticated_user=current_user.sub)  # Cambiar .get("sub") por .sub
    
    try:
        result = authz_service.get_applicable_policies(abac_request)
        
        logger.info("Applicable policies retrieved",
                   correlation_id=correlation_id,
                   total_policies=result["total_policies"],
                   applicable_count=len(result["applicable_policies"]))
        
        return result
        
    except Exception as e:
        logger.error("Failed to get applicable policies",
                    correlation_id=correlation_id,
                    error=str(e))
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "policies_retrieval_failed",
                "message": "Failed to retrieve applicable policies",
                "correlation_id": correlation_id
            }
        )

@router.get(
    "/health",
    response_model=Dict[str, Any],
    summary="Authorization service health check",
    description="Returns health status of authorization service and policy validation"
)
async def authorization_health(
    authz_service = Depends(get_authz_service)
) -> Dict[str, Any]:
    """
    Health check específico para el servicio de autorización
    
    Returns:
        Estado de salud del servicio y políticas
    """
    try:
        # Obtener métricas del servicio
        metrics = authz_service.get_metrics()
        
        # Validar políticas
        validation = authz_service.validate_policies()
        
        health_status = {
            "service": "authorization",
            "status": "healthy" if validation["validation"]["valid"] else "degraded",
            "policies": {
                "valid": validation["validation"]["valid"],
                "count": validation["metadata"]["policies_count"],
                "errors": validation["validation"]["errors"],
                "warnings": validation["validation"]["warnings"]
            },
            "metrics": metrics,
            "timestamp": validation["timestamp"]
        }
        
        logger.info("Authorization health check completed",
                   status=health_status["status"],
                   policies_valid=validation["validation"]["valid"])
        
        return health_status
        
    except Exception as e:
        logger.error("Authorization health check failed", error=str(e))
        
        return {
            "service": "authorization",
            "status": "unhealthy",
            "error": str(e),
            "timestamp": authz_service.get_metrics()["service"]["timestamp"]
        }

@router.post(
    "/policies/reload",
    response_model=Dict[str, Any],
    summary="Reload authorization policies",
    description="Forces reload of authorization policies from file (admin endpoint)"
)
@limiter.limit("10/minute")  # Más restrictivo para operaciones admin
async def reload_policies(
    request: Request,
    current_user: UserClaims = Depends(get_current_user),  # Cambiar tipo
    authz_service = Depends(get_authz_service)
) -> Dict[str, Any]:
    """
    Fuerza la recarga de políticas desde archivo
    
    Args:
        current_user: Usuario autenticado (debe tener permisos admin)
        authz_service: Servicio de autorización
        
    Returns:
        Resultado de la recarga de políticas
    """
    correlation_id = request.headers.get("X-Correlation-ID")
    
    # Verificar permisos de administrador
    user_groups = current_user.groups  # Cambiar .get("groups", []) por .groups
    if "ADMINS" not in user_groups:
        logger.warning("Unauthorized policy reload attempt",
                      correlation_id=correlation_id,
                      user=current_user.sub,  # Cambiar .get("sub") por .sub
                      user_groups=user_groups)
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "insufficient_permissions",
                "message": "Admin privileges required for policy reload",
                "correlation_id": correlation_id
            }
        )
    
    logger.info("Policy reload requested",
               correlation_id=correlation_id,
               admin_user=current_user.sub)  # Cambiar .get("sub") por .sub
    
    try:
        result = authz_service.reload_policies()
        
        logger.info("Policies reloaded successfully",
                   correlation_id=correlation_id,
                   admin_user=current_user.sub,
                   policies_count=result["reload_result"]["policies_count"])
        
        return result
        
    except Exception as e:
        logger.error("Policy reload failed",
                    correlation_id=correlation_id,
                    admin_user=current_user.sub,
                    error=str(e))
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "policy_reload_failed",
                "message": "Failed to reload policies",
                "correlation_id": correlation_id
            }
        )

@router.get(
    "/metrics",
    response_model=Dict[str, Any],
    summary="Get authorization service metrics",
    description="Returns performance and usage metrics for the authorization service"
)
async def get_authorization_metrics(
    current_user: UserClaims = Depends(get_current_user),  # Cambiar tipo
    authz_service = Depends(get_authz_service)
) -> Dict[str, Any]:
    """
    Obtiene métricas del servicio de autorización
    
    Args:
        current_user: Usuario autenticado
        authz_service: Servicio de autorización
        
    Returns:
        Métricas de performance y uso
    """
    try:
        metrics = authz_service.get_metrics()
        
        logger.info("Authorization metrics requested",
                   user=current_user.sub,  # Cambiar .get("sub") por .sub
                   service_status=metrics["service"]["status"])
        
        return metrics
        
    except Exception as e:
        logger.error("Failed to get authorization metrics",
                    user=current_user.sub,  # Cambiar .get("sub") por .sub
                    error=str(e))
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "metrics_retrieval_failed",
                "message": "Failed to retrieve authorization metrics"
            }
        )

