"""
Validador de políticas ABAC
"""
from typing import List, Dict, Any, Tuple
from app.models.abac import ABACPolicySet, ABACPolicy, PolicyValidationResult, OperatorType
from app.core.logger import get_logger

logger = get_logger("policy_validator")

class PolicyValidator:
    """Validador de sintaxis y semántica de políticas ABAC"""
    
    SUPPORTED_OPERATORS = {op.value for op in OperatorType}
    
    VALID_ATTRIBUTES = {
        "subject": ["dept", "groups", "riskScore", "role", "clearanceLevel"],
        "resource": ["type", "env", "classification", "owner", "sensitivity"],
        "context": ["geo", "deviceTrusted", "timeOfDay", "dayOfWeek", "ipAddress", "userAgent"]
    }
    
    @classmethod
    def validate_policy_set(cls, policy_data: Dict[str, Any]) -> PolicyValidationResult:
        """
        Valida un conjunto completo de políticas
        
        Args:
            policy_data: Datos del archivo JSON de políticas
            
        Returns:
            PolicyValidationResult con errores y advertencias
        """
        errors = []
        warnings = []
        
        try:
            # Validar estructura básica
            if "policies" not in policy_data:
                errors.append("Missing 'policies' key in policy data")
                return PolicyValidationResult(
                    valid=False, 
                    errors=errors, 
                    warnings=warnings,
                    policies_count=0
                )
            
            # Validar cada política individualmente
            policies = policy_data["policies"]
            for i, policy_dict in enumerate(policies):
                policy_errors, policy_warnings = cls._validate_single_policy(policy_dict, i)
                errors.extend(policy_errors)
                warnings.extend(policy_warnings)
            
            # Validar conjunto completo
            set_errors, set_warnings = cls._validate_policy_set_rules(policies)
            errors.extend(set_errors)
            warnings.extend(set_warnings)
            
            # Crear PolicySet para validación Pydantic
            try:
                policy_set = ABACPolicySet(**policy_data)
            except Exception as e:
                errors.append(f"Pydantic validation failed: {str(e)}")
            
            is_valid = len(errors) == 0
            
            logger.info("Policy validation completed", 
                       valid=is_valid, 
                       errors_count=len(errors),
                       warnings_count=len(warnings),
                       policies_count=len(policies))
            
            return PolicyValidationResult(
                valid=is_valid,
                errors=errors,
                warnings=warnings,
                policies_count=len(policies)
            )
            
        except Exception as e:
            logger.error("Policy validation failed", error=str(e))
            errors.append(f"Validation exception: {str(e)}")
            return PolicyValidationResult(
                valid=False,
                errors=errors,
                warnings=warnings,
                policies_count=0
            )
    
    @classmethod
    def _validate_single_policy(cls, policy_dict: Dict[str, Any], index: int) -> Tuple[List[str], List[str]]:
        """Valida una política individual"""
        errors = []
        warnings = []
        prefix = f"Policy {index}"
        
        # Validar campos requeridos
        required_fields = ["ruleId", "effect", "description", "conditions"]
        for field in required_fields:
            if field not in policy_dict:
                errors.append(f"{prefix}: Missing required field '{field}'")
        
        # Validar effect
        if "effect" in policy_dict:
            valid_effects = ["Permit", "Deny", "Challenge"]
            if policy_dict["effect"] not in valid_effects:
                errors.append(f"{prefix}: Invalid effect '{policy_dict['effect']}'. Must be one of {valid_effects}")
        
        # Validar condiciones
        if "conditions" in policy_dict:
            cond_errors, cond_warnings = cls._validate_conditions(policy_dict["conditions"], prefix)
            errors.extend(cond_errors)
            warnings.extend(cond_warnings)
        
        # Validar prioridad
        if "priority" in policy_dict:
            priority = policy_dict["priority"]
            if not isinstance(priority, int) or priority < 0:
                errors.append(f"{prefix}: Priority must be a non-negative integer")
        
        return errors, warnings
    
    @classmethod
    def _validate_conditions(cls, conditions: Dict[str, Any], prefix: str) -> Tuple[List[str], List[str]]:
        """Valida condiciones recursivamente"""
        errors = []
        warnings = []
        
        # Manejar operadores lógicos
        if "AND" in conditions or "OR" in conditions:
            operator = "AND" if "AND" in conditions else "OR"
            sub_conditions = conditions[operator]
            
            if not isinstance(sub_conditions, list):
                errors.append(f"{prefix}: {operator} must contain a list of conditions")
            else:
                for i, sub_condition in enumerate(sub_conditions):
                    sub_errors, sub_warnings = cls._validate_conditions(
                        sub_condition, f"{prefix}.{operator}[{i}]"
                    )
                    errors.extend(sub_errors)
                    warnings.extend(sub_warnings)
        else:
            # Validar condiciones simples
            for attr_path, condition in conditions.items():
                if not isinstance(condition, dict):
                    errors.append(f"{prefix}: Condition for '{attr_path}' must be a dictionary")
                    continue
                
                # Validar atributo
                path_errors = cls._validate_attribute_path(attr_path, prefix)
                errors.extend(path_errors)
                
                # Validar operadores
                for operator, value in condition.items():
                    if operator not in cls.SUPPORTED_OPERATORS:
                        errors.append(f"{prefix}: Unsupported operator '{operator}' for '{attr_path}'")
                    
                    # Validar tipos de valores según operador
                    op_errors = cls._validate_operator_value(operator, value, attr_path, prefix)
                    errors.extend(op_errors)
        
        return errors, warnings
    
    @classmethod
    def _validate_attribute_path(cls, attr_path: str, prefix: str) -> List[str]:
        """Valida que el path del atributo sea válido"""
        errors = []
        
        if "." not in attr_path:
            errors.append(f"{prefix}: Attribute path '{attr_path}' must contain domain (subject/resource/context)")
            return errors
        
        domain, attribute = attr_path.split(".", 1)
        
        if domain not in cls.VALID_ATTRIBUTES:
            errors.append(f"{prefix}: Invalid domain '{domain}' in '{attr_path}'. Must be one of {list(cls.VALID_ATTRIBUTES.keys())}")
        elif attribute not in cls.VALID_ATTRIBUTES[domain]:
            errors.append(f"{prefix}: Invalid attribute '{attribute}' for domain '{domain}'. Valid attributes: {cls.VALID_ATTRIBUTES[domain]}")
        
        return errors
    
    @classmethod
    def _validate_operator_value(cls, operator: str, value: Any, attr_path: str, prefix: str) -> List[str]:
        """Valida el valor según el operador"""
        errors = []
        
        if operator in ["in", "not_in"]:
            if not isinstance(value, list):
                errors.append(f"{prefix}: Operator '{operator}' for '{attr_path}' requires a list value")
        elif operator in ["contains", "not_contains"]:
            # Para arrays, el valor debe ser un elemento simple
            pass
        elif operator in ["gt", "gte", "lt", "lte"]:
            if not isinstance(value, (int, float, str)):
                errors.append(f"{prefix}: Operator '{operator}' for '{attr_path}' requires a comparable value")
        
        return errors
    
    @classmethod
    def _validate_policy_set_rules(cls, policies: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
        """Valida reglas del conjunto de políticas"""
        errors = []
        warnings = []
        
        # Verificar ruleId únicos
        rule_ids = [p.get("ruleId") for p in policies if "ruleId" in p]
        duplicates = [rid for rid in set(rule_ids) if rule_ids.count(rid) > 1]
        if duplicates:
            errors.append(f"Duplicate ruleIds found: {duplicates}")
        
        # Verificar que hay al menos una política con efecto Permit
        effects = [p.get("effect") for p in policies]
        if "Permit" not in effects:
            warnings.append("No Permit policies found - this may result in all requests being denied")
        
        # Verificar distribución de prioridades
        priorities = [p.get("priority", 100) for p in policies]
        if len(set(priorities)) < len(priorities) * 0.5:
            warnings.append("Many policies have the same priority - consider adjusting for better evaluation order")
        
        return errors, warnings