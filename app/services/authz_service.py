"""
AuthzService - Servicio de autorización ABAC
Orquestación de evaluación de políticas con logging y optimización
"""
from typing import Dict, Any, Optional
from datetime import datetime
import time

from app.models.abac import ABACRequest, ABACResponse, DecisionType
from app.services.abac_evaluator import get_abac_evaluator
from app.repositories.policy_repository import get_policy_repository
from app.core.logger import get_logger

logger = get_logger("authz_service")

class AuthzServiceError(Exception):
    """Excepción para errores del servicio de autorización"""
    pass

class AuthzService:
    """
    Servicio de autorización ABAC
    Orquesta la evaluación de políticas y maneja logging de decisiones
    """
    
    def __init__(self):
        self.abac_evaluator = get_abac_evaluator()
        self.policy_repository = get_policy_repository()
        self._decision_cache = {}  # Cache simple para optimización
        self._cache_ttl = 300  # 5 minutos TTL
        
        logger.info("AuthzService initialized")
    
    def evaluate_authorization(self, request: ABACRequest, 
                             correlation_id: Optional[str] = None) -> ABACResponse:
        """
        Evalúa una solicitud de autorización ABAC
        
        Args:
            request: Solicitud ABAC con subject, resource, context
            correlation_id: ID de correlación para trazabilidad
            
        Returns:
            ABACResponse con decisión y razones
        """
        start_time = time.time()
        correlation_id = correlation_id or self._generate_correlation_id()
        
        logger.info("Authorization evaluation started", 
                   correlation_id=correlation_id,
                   subject_dept=request.subject.dept,
                   resource_type=request.resource.type,
                   action=request.action)
        
        try:
            # Verificar cache primero (optimización)
            cache_key = self._generate_cache_key(request)
            cached_response = self._get_from_cache(cache_key)
            
            if cached_response:
                logger.info("Cache hit for authorization request", 
                           correlation_id=correlation_id,
                           cache_key=cache_key[:16])  # Solo primeros 16 chars
                
                self._log_decision(cached_response, correlation_id, 
                                 elapsed_ms=int((time.time() - start_time) * 1000),
                                 from_cache=True)
                return cached_response
            
            # Evaluar con ABACEvaluator
            response = self.abac_evaluator.evaluate(request)
            
            # Enriquecer respuesta con metadatos
            response = self._enrich_response(response, correlation_id)
            
            # Guardar en cache
            self._store_in_cache(cache_key, response)
            
            # Log de auditoría
            elapsed_ms = int((time.time() - start_time) * 1000)
            self._log_decision(response, correlation_id, elapsed_ms, from_cache=False)
            
            # Verificar contradicciones en políticas
            self._check_policy_conflicts(response, correlation_id)
            
            logger.info("Authorization evaluation completed", 
                       correlation_id=correlation_id,
                       decision=response.decision.value,
                       elapsed_ms=elapsed_ms)
            
            return response
            
        except Exception as e:
            logger.error("Authorization evaluation failed", 
                        correlation_id=correlation_id,
                        error=str(e),
                        elapsed_ms=int((time.time() - start_time) * 1000))
            
            # Retornar decisión de seguridad por defecto
            return ABACResponse(
                decision=DecisionType.DENY,
                reasons=[f"Evaluation error: {str(e)}"],
                advice=["Contact system administrator"],
                obligations=["Log authorization failure", "Alert security team"]
            )
    
    def get_applicable_policies(self, request: ABACRequest) -> Dict[str, Any]:
        """
        Obtiene políticas aplicables sin evaluarlas (para debugging)
        
        Args:
            request: Solicitud ABAC
            
        Returns:
            Información sobre políticas aplicables
        """
        try:
            policies = self.policy_repository.get_all_policies()
            context = self.abac_evaluator._flatten_request(request)
            
            applicable_policies = []
            
            for policy in policies:
                try:
                    is_applicable = self.abac_evaluator._evaluate_policy_conditions(
                        policy.conditions, context
                    )
                    
                    applicable_policies.append({
                        "ruleId": policy.ruleId,
                        "effect": policy.effect.value,
                        "description": policy.description,
                        "priority": policy.priority,
                        "applicable": is_applicable
                    })
                    
                except Exception as e:
                    logger.warning("Error checking policy applicability", 
                                 rule_id=policy.ruleId, 
                                 error=str(e))
                    continue
            
            # Ordenar por prioridad
            applicable_policies.sort(key=lambda p: p.get("priority", 100))
            
            return {
                "total_policies": len(policies),
                "applicable_policies": [p for p in applicable_policies if p["applicable"]],
                "non_applicable_policies": [p for p in applicable_policies if not p["applicable"]],
                "evaluation_context": context
            }
            
        except Exception as e:
            logger.error("Error getting applicable policies", error=str(e))
            raise AuthzServiceError(f"Failed to get applicable policies: {str(e)}")
    
    def validate_policies(self) -> Dict[str, Any]:
        """
        Valida las políticas actuales del repositorio
        
        Returns:
            Resultado de validación con errores y advertencias
        """
        try:
            validation_result = self.policy_repository.validate_current_policies()
            metadata = self.policy_repository.get_policy_set_metadata()
            
            return {
                "validation": validation_result.model_dump(),
                "metadata": metadata,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Policy validation failed", error=str(e))
            raise AuthzServiceError(f"Policy validation failed: {str(e)}")
    
    def reload_policies(self) -> Dict[str, Any]:
        """
        Fuerza la recarga de políticas y limpia cache
        
        Returns:
            Resultado de la recarga
        """
        try:
            # Limpiar cache
            self._clear_cache()
            
            # Recargar políticas
            reload_result = self.policy_repository.reload_policies()
            
            logger.info("Policies reloaded", 
                       valid=reload_result.valid,
                       policies_count=reload_result.policies_count)
            
            return {
                "reload_result": reload_result.model_dump(),
                "cache_cleared": True,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Policy reload failed", error=str(e))
            raise AuthzServiceError(f"Policy reload failed: {str(e)}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Obtiene métricas de performance del servicio
        
        Returns:
            Métricas del servicio de autorización
        """
        try:
            policies_metadata = self.policy_repository.get_policy_set_metadata()
            
            return {
                "policies": {
                    "total_count": policies_metadata["policies_count"],
                    "effects_distribution": policies_metadata["effects_distribution"],
                    "last_modified": policies_metadata["last_modified"]
                },
                "cache": {
                    "entries_count": len(self._decision_cache),
                    "ttl_seconds": self._cache_ttl
                },
                "service": {
                    "status": "healthy",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            logger.error("Error getting metrics", error=str(e))
            return {
                "service": {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
    
    def _generate_cache_key(self, request: ABACRequest) -> str:
        """Genera clave de cache basada en la request"""
        import hashlib
        
        # Crear string determinístico de la request
        cache_data = {
            "subject": request.subject.model_dump(exclude_none=True),
            "resource": request.resource.model_dump(exclude_none=True),
            "context": request.context.model_dump(exclude_none=True),
            "action": request.action
        }
        
        cache_string = str(sorted(cache_data.items()))
        return hashlib.md5(cache_string.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[ABACResponse]:
        """Obtiene respuesta del cache si no ha expirado"""
        if cache_key not in self._decision_cache:
            return None
        
        entry = self._decision_cache[cache_key]
        
        # Verificar TTL
        if time.time() - entry["timestamp"] > self._cache_ttl:
            del self._decision_cache[cache_key]
            return None
        
        return entry["response"]
    
    def _store_in_cache(self, cache_key: str, response: ABACResponse):
        """Almacena respuesta en cache"""
        self._decision_cache[cache_key] = {
            "response": response,
            "timestamp": time.time()
        }
        
        # Limpiar cache si está muy grande (límite simple)
        if len(self._decision_cache) > 1000:
            self._clean_expired_cache()
    
    def _clean_expired_cache(self):
        """Limpia entradas expiradas del cache"""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self._decision_cache.items()
            if current_time - entry["timestamp"] > self._cache_ttl
        ]
        
        for key in expired_keys:
            del self._decision_cache[key]
        
        logger.debug("Cache cleaned", expired_entries=len(expired_keys))
    
    def _clear_cache(self):
        """Limpia todo el cache"""
        self._decision_cache.clear()
        logger.info("Authorization cache cleared")
    
    def _enrich_response(self, response: ABACResponse, correlation_id: str) -> ABACResponse:
        """Enriquece la respuesta con metadatos adicionales"""
        # Agregar correlation_id a obligations si es Challenge o Deny
        if response.decision in [DecisionType.CHALLENGE, DecisionType.DENY]:
            if response.obligations is None:
                response.obligations = []
            response.obligations.append(f"correlation_id: {correlation_id}")
        
        return response
    
    def _log_decision(self, response: ABACResponse, correlation_id: str, 
                     elapsed_ms: int, from_cache: bool = False):
        """Log estructurado de decisiones para auditoría"""
        logger.info("Authorization decision", 
                   correlation_id=correlation_id,
                   decision=response.decision.value,
                   reasons_count=len(response.reasons),
                   advice_count=len(response.advice or []),
                   obligations_count=len(response.obligations or []),
                   elapsed_ms=elapsed_ms,
                   from_cache=from_cache,
                   audit=True)  # Flag para identificar logs de auditoría
        
        # Log detallado para decisiones críticas
        if response.decision in [DecisionType.DENY, DecisionType.CHALLENGE]:
            logger.warning("Critical authorization decision", 
                          correlation_id=correlation_id,
                          decision=response.decision.value,
                          reasons=response.reasons,
                          advice=response.advice,
                          obligations=response.obligations,
                          audit=True)
    
    def _check_policy_conflicts(self, response: ABACResponse, correlation_id: str):
        """Verifica posibles conflictos en políticas aplicables"""
        reasons = response.reasons or []
        
        # Contar diferentes tipos de decisiones en las razones
        permit_count = sum(1 for r in reasons if "Permit" in str(r))
        deny_count = sum(1 for r in reasons if "Deny" in str(r))
        challenge_count = sum(1 for r in reasons if "Challenge" in str(r))
        
        # Advertir si hay múltiples tipos de decisiones
        total_decisions = permit_count + deny_count + challenge_count
        if total_decisions > 1:
            logger.warning("Multiple policy effects detected", 
                          correlation_id=correlation_id,
                          permit_policies=permit_count,
                          deny_policies=deny_count,
                          challenge_policies=challenge_count,
                          final_decision=response.decision.value)
    
    def _generate_correlation_id(self) -> str:
        """Genera un correlation ID único"""
        import uuid
        return f"authz-{uuid.uuid4().hex[:8]}"

# Factory function
def get_authz_service() -> AuthzService:
    """Factory function para obtener instancia del AuthzService"""
    return AuthzService()