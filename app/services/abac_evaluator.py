"""
ABACEvaluator - Motor de evaluación de políticas ABAC
Engine de evaluación de condiciones con operadores
"""
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, time
import re

from app.models.abac import (
    ABACRequest, ABACResponse, ABACPolicy, DecisionType, OperatorType
)
from app.repositories.policy_repository import get_policy_repository
from app.core.logger import get_logger

logger = get_logger("abac_evaluator")

class ABACEvaluationError(Exception):
    """Excepción para errores de evaluación ABAC"""
    pass

class ABACEvaluator:
    """
    Motor de evaluación ABAC
    Evalúa condiciones contra políticas y retorna decisiones
    """
    
    def __init__(self):
        self.policy_repository = get_policy_repository()
        logger.info("ABACEvaluator initialized")
    
    def evaluate(self, request: ABACRequest) -> ABACResponse:
        """
        Evalúa una solicitud ABAC contra todas las políticas
        
        Args:
            request: Solicitud con subject, resource, context
            
        Returns:
            ABACResponse con decisión final y razones
        """
        logger.info("Starting ABAC evaluation", 
                   subject_dept=request.subject.dept,
                   resource_type=request.resource.type,
                   action=request.action)
        
        try:
            # Obtener políticas ordenadas por prioridad
            policies = self.policy_repository.get_all_policies()
            
            # Contexto flattened para evaluación
            context = self._flatten_request(request)
            
            # Evaluar políticas en orden de prioridad
            permit_reasons = []
            deny_reasons = []
            challenge_reasons = []
            
            for policy in policies:
                try:
                    if self._evaluate_policy_conditions(policy.conditions, context):
                        logger.debug("Policy matched", 
                                   rule_id=policy.ruleId, 
                                   effect=policy.effect.value)
                        
                        if policy.effect == DecisionType.PERMIT:
                            permit_reasons.append(f"ruleId: {policy.ruleId}")
                        elif policy.effect == DecisionType.DENY:
                            deny_reasons.append(f"ruleId: {policy.ruleId}")
                        elif policy.effect == DecisionType.CHALLENGE:
                            challenge_reasons.append(f"ruleId: {policy.ruleId}")
                
                except Exception as e:
                    logger.warning("Error evaluating policy", 
                                 rule_id=policy.ruleId, 
                                 error=str(e))
                    continue
            
            # Lógica de decisión: Deny > Challenge > Permit
            decision, reasons, advice, obligations = self._make_decision(
                permit_reasons, deny_reasons, challenge_reasons
            )
            
            logger.info("ABAC evaluation completed", 
                       decision=decision.value,
                       reasons_count=len(reasons),
                       policies_evaluated=len(policies))
            
            return ABACResponse(
                decision=decision,
                reasons=reasons,
                advice=advice,
                obligations=obligations
            )
            
        except Exception as e:
            logger.error("ABAC evaluation failed", error=str(e))
            return ABACResponse(
                decision=DecisionType.DENY,
                reasons=[f"Evaluation error: {str(e)}"],
                advice=["Contact system administrator"],
                obligations=["Log evaluation failure"]
            )
    
    def _flatten_request(self, request: ABACRequest) -> Dict[str, Any]:
        """
        Convierte la request ABAC a un diccionario plano para evaluación
        
        Args:
            request: Solicitud ABAC
            
        Returns:
            Diccionario con paths tipo "subject.dept", "resource.type"
        """
        context = {}
        
        # Subject attributes
        if request.subject:
            for key, value in request.subject.model_dump(exclude_none=True).items():
                context[f"subject.{key}"] = value
        
        # Resource attributes  
        if request.resource:
            for key, value in request.resource.model_dump(exclude_none=True).items():
                context[f"resource.{key}"] = value
        
        # Context attributes
        if request.context:
            for key, value in request.context.model_dump(exclude_none=True).items():
                context[f"context.{key}"] = value
        
        # Action
        if request.action:
            context["action"] = request.action
        
        logger.debug("Request flattened", context_keys=list(context.keys()))
        return context
    
    def _evaluate_policy_conditions(self, conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Evalúa condiciones de una política recursivamente
        
        Args:
            conditions: Condiciones de la política
            context: Contexto flattened de la solicitud
            
        Returns:
            True si las condiciones se cumplen, False caso contrario
        """
        # Manejar operadores lógicos
        if "AND" in conditions:
            return all(
                self._evaluate_policy_conditions(sub_condition, context)
                for sub_condition in conditions["AND"]
            )
        
        if "OR" in conditions:
            return any(
                self._evaluate_policy_conditions(sub_condition, context)
                for sub_condition in conditions["OR"]
            )
        
        # Evaluar condiciones simples
        for attr_path, condition_spec in conditions.items():
            if not self._evaluate_simple_condition(attr_path, condition_spec, context):
                return False
        
        return True
    
    def _evaluate_simple_condition(self, attr_path: str, condition_spec: Dict[str, Any], 
                                  context: Dict[str, Any]) -> bool:
        """
        Evalúa una condición simple con operadores
        
        Args:
            attr_path: Path del atributo (ej: "subject.dept")
            condition_spec: Especificación de la condición (ej: {"eq": "HR"})
            context: Contexto de la solicitud
            
        Returns:
            True si la condición se cumple, False caso contrario
        """
        # Obtener valor del contexto
        actual_value = context.get(attr_path)
        
        # Evaluar cada operador en la condición
        for operator, expected_value in condition_spec.items():
            if not self._apply_operator(actual_value, operator, expected_value, attr_path):
                return False
        
        return True
    
    def _apply_operator(self, actual_value: Any, operator: str, expected_value: Any, 
                       attr_path: str) -> bool:
        """
        Aplica un operador específico
        
        Args:
            actual_value: Valor actual del atributo
            operator: Operador a aplicar
            expected_value: Valor esperado
            attr_path: Path del atributo (para logging)
            
        Returns:
            True si la operación es verdadera, False caso contrario
        """
        try:
            if operator == "eq":
                result = actual_value == expected_value
            elif operator == "ne":
                result = actual_value != expected_value
            elif operator == "gt":
                result = self._safe_compare(actual_value, expected_value, lambda a, b: a > b)
            elif operator == "gte":
                result = self._safe_compare(actual_value, expected_value, lambda a, b: a >= b)
            elif operator == "lt":
                result = self._safe_compare(actual_value, expected_value, lambda a, b: a < b)
            elif operator == "lte":
                result = self._safe_compare(actual_value, expected_value, lambda a, b: a <= b)
            elif operator == "in":
                result = actual_value in expected_value if expected_value else False
            elif operator == "not_in":
                result = actual_value not in expected_value if expected_value else True
            elif operator == "contains":
                result = self._safe_contains(actual_value, expected_value)
            elif operator == "not_contains":
                result = not self._safe_contains(actual_value, expected_value)
            else:
                logger.warning("Unknown operator", operator=operator, attr_path=attr_path)
                return False
            
            logger.debug("Operator applied", 
                        attr_path=attr_path,
                        operator=operator, 
                        actual_value=actual_value,
                        expected_value=expected_value,
                        result=result)
            
            return result
            
        except Exception as e:
            logger.warning("Error applying operator", 
                         operator=operator,
                         attr_path=attr_path,
                         error=str(e))
            return False
    
    def _safe_compare(self, actual: Any, expected: Any, comparator) -> bool:
        """Comparación segura con conversión de tipos"""
        try:
            # Intentar comparar directamente
            return comparator(actual, expected)
        except (TypeError, ValueError):
            try:
                # Intentar conversión numérica
                if isinstance(actual, str) and isinstance(expected, (int, float)):
                    return comparator(float(actual), expected)
                elif isinstance(expected, str) and isinstance(actual, (int, float)):
                    return comparator(actual, float(expected))
                
                # Comparación temporal para timeOfDay
                if "timeOfDay" in str(actual) or "timeOfDay" in str(expected):
                    return self._compare_time(actual, expected, comparator)
                
                return False
            except:
                return False
    
    def _safe_contains(self, container: Any, item: Any) -> bool:
        """Verificación segura de contención"""
        try:
            if isinstance(container, list):
                return item in container
            elif isinstance(container, str):
                return str(item) in container
            else:
                return False
        except:
            return False
    
    def _compare_time(self, actual: Any, expected: Any, comparator) -> bool:
        """Comparación especial para timeOfDay (HH:MM format)"""
        try:
            def parse_time(time_str):
                if isinstance(time_str, str) and ":" in time_str:
                    hour, minute = map(int, time_str.split(":"))
                    return hour * 60 + minute  # Convertir a minutos
                return None
            
            actual_minutes = parse_time(actual)
            expected_minutes = parse_time(expected)
            
            if actual_minutes is not None and expected_minutes is not None:
                return comparator(actual_minutes, expected_minutes)
            
            return False
        except:
            return False
    
    def _make_decision(self, permit_reasons: List[str], deny_reasons: List[str], 
                      challenge_reasons: List[str]) -> tuple:
        """
        Lógica de decisión final basada en razones encontradas
        Precedencia: Deny > Challenge > Permit > Default Deny
        
        Returns:
            (decision, reasons, advice, obligations)
        """
        # Precedencia: Deny tiene máxima prioridad
        if deny_reasons:
            return (
                DecisionType.DENY,
                deny_reasons,
                ["Access explicitly denied by policy"],
                ["Log denied access attempt"]
            )
        
        # Challenge tiene segunda prioridad
        if challenge_reasons:
            return (
                DecisionType.CHALLENGE,
                challenge_reasons,
                ["Additional authentication required", "Contact administrator if needed"],
                ["Log challenge requirement", "Initiate step-up authentication"]
            )
        
        # Permit si hay razones explícitas
        if permit_reasons:
            return (
                DecisionType.PERMIT,
                permit_reasons,
                [],
                ["Log successful access"]
            )
        
        # Default Deny si no hay políticas aplicables
        return (
            DecisionType.DENY,
            ["No applicable policies found"],
            ["Contact administrator for access", "Review policy configuration"],
            ["Log policy gap", "Alert security team"]
        )

# Factory function
def get_abac_evaluator() -> ABACEvaluator:
    """Factory function para obtener instancia del ABACEvaluator"""
    return ABACEvaluator()